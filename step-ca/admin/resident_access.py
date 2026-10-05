"""Resident self-service, group-scoped Duo directory and Universal SDK verification.

The optional directory identifies a selected resident; it does not authenticate
them. Neither mode exposes previously issued Wi-Fi passwords.
"""

import hashlib
import json
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie, CookieError
from urllib.parse import urlencode

import ui
import guidance
import identity_settings

SETTINGS_OVERRIDE = None
SESSIONS = {}
LOCK = threading.RLock()
TTL = 1800
SECRET_FIELDS = identity_settings.SECRET_FIELDS
TEXT_FIELDS = ("duo_client_id", "duo_api_hostname", "duo_redirect_uri",
               "duo_admin_integration_key", "duo_admin_hostname", "duo_group_id")
BOOL_FIELDS = ("self_service_enabled", "sign_in_required", "no_sign_in_user_list")


def settings():
    return dict(SETTINGS_OVERRIDE if SETTINGS_OVERRIDE is not None else
                json.loads(os.environ.get("RESIDENT_SETTINGS_JSON") or "{}"))


def enabled(config=None):
    config = settings() if config is None else config
    return any(config.get(key, False) for key in BOOL_FIELDS)


def validate_settings(config):
    if config.get("key_backend", "meraki_legacy") not in ("access_manager", "meraki_legacy"):
        raise ValueError("Choose a supported resident key service.")
    if config.get("key_backend") == "access_manager":
        if config.get("duration_hours", 0):
            raise guidance.FieldError("duration_hours", "Access Manager resident keys require a lifetime of 0; the API has no per-client expiry.")
        if (config.get("enabled") or enabled(config)) and not config.get("access_manager_group_id"):
            raise ValueError("Choose the Access Manager resident group in Network and onboarding first.")
    try:
        limit = int(config.get("max_devices_per_resident", 5))
    except (TypeError, ValueError) as err:
        raise guidance.FieldError("max_devices_per_resident", "Choose a device limit from 1 to 50.") from err
    if not 1 <= limit <= 50:
        raise guidance.FieldError("max_devices_per_resident", "Choose a device limit from 1 to 50.")
    if not enabled(config):
        return
    if not config.get("network_id"):
        raise ValueError("Choose the resident Meraki network in the add-on options first.")
    needs_directory = config.get("sign_in_required") or config.get("no_sign_in_user_list")
    if needs_directory:
        identity_settings.validate(config, "directory", required=True)
    if config.get("sign_in_required"):
        identity_settings.validate(config, "authentication", required=True)


def _host(value):
    return identity_settings.duo_hostname(value)


def admin_client(config):
    import duo_client
    return duo_client.Admin(ikey=config["duo_admin_integration_key"], skey=config["duo_admin_secret"],
                            host=_host(config["duo_admin_hostname"]), timeout=8, paging_limit=500)


def _duo_call(method, *args, **kwargs):
    """Keep provider exception bodies out of resident pages and logs."""
    try:
        return method(*args, **kwargs)
    except Exception:
        raise RuntimeError("The Duo resident service is unavailable.") from None


def _duo_group_users(client, group_id):
    """Also contain failures when the SDK fetches a subsequent page lazily."""
    try:
        yield from client.get_group_users_iterator(group_id)
    except Exception:
        raise RuntimeError("The Duo resident directory is unavailable.") from None


def duo_form_origin():
    """Permit the configured Duo POST redirect without broadening other forms."""
    config = settings()
    if config.get("sign_in_required"):
        try:
            return "https://" + _host(config.get("duo_api_hostname"))
        except ValueError:
            pass
    return ""


def group_members(config):
    """Use the group endpoint exclusively; never fall back to the tenant user list."""
    identity_settings.validate(config, "directory", required=True)
    client = _duo_call(admin_client, config)
    group = _duo_call(client.get_group, config["duo_group_id"], api_version=2)
    # Duo documents both "Active" and "active" across group responses.
    if str(group.get("status", "")).casefold() != "active":
        raise ValueError("The permitted Duo group must be active. Contact your administrator.")
    members = []
    for member in _duo_group_users(client, config["duo_group_id"]):
        if len(members) >= 500:
            raise RuntimeError("The permitted group is too large for this portal. Use a smaller resident group.")
        if member.get("user_id") and member.get("username"):
            members.append({"user_id": str(member["user_id"]), "username": str(member["username"]),
                            "display_name": str(member.get("realname") or member["username"])})
    return sorted(members, key=lambda row: row["username"].casefold())


def member_identity(config, user_id="", username=""):
    members = group_members(config)
    member = next((row for row in members if
                   (row["user_id"] == user_id if user_id else row["username"].casefold() == username.casefold())), None)
    if member is None:
        raise ValueError("This resident is not in the permitted group. Contact your administrator.")
    user = _duo_call(admin_client(config).get_user_by_id, member["user_id"])
    if user.get("status") != "active" or user.get("user_id") != member["user_id"]:
        raise ValueError("This resident account is unavailable. Contact your administrator.")
    return {"owner": "duo:" + member["user_id"], "user_id": member["user_id"],
            "username": member["username"], "name": str(user.get("realname") or member["username"]),
            "email": str(user.get("email") or ""), "verified": False}


def universal_client(config):
    import duo_universal
    import duo_universal.client as sdk_module
    import requests

    class TimedRequests:
        @staticmethod
        def post(*args, **kwargs):
            return requests.post(*args, timeout=8, **kwargs)

    # This SDK has no timeout option. Bound its HTTP calls without modifying
    # requests itself, while retaining Duo's TLS verification and certificate pinning.
    sdk_module.requests = TimedRequests
    return duo_universal.Client(client_id=config["duo_client_id"], client_secret=config["duo_client_secret"],
                                host=_host(config["duo_api_hostname"]), redirect_uri=config["duo_redirect_uri"])


def policy_stamp(config):
    fields = (*BOOL_FIELDS, *TEXT_FIELDS, *SECRET_FIELDS, "max_devices_per_resident", "network_id",
              "ssid_number", "group_policy_id", "invite_required", "key_backend", "access_manager_group_id", "duration_hours")
    return hashlib.sha256(json.dumps({k: config.get(k) for k in fields}, sort_keys=True).encode()).hexdigest()


def new_session(config, captive_token="", identity=None):
    with LOCK:
        now = time.monotonic()
        for token in list(SESSIONS):
            if SESSIONS[token]["expires"] <= now:
                del SESSIONS[token]
        if len(SESSIONS) >= 1000:
            raise RuntimeError("The portal is busy. Please try again shortly.")
        token = secrets.token_urlsafe(32)
        session = {"expires": now + TTL, "policy": policy_stamp(config), "csrf": secrets.token_urlsafe(32),
                   "captive": captive_token, "identity": identity, "pending": None, "busy": False}
        SESSIONS[token] = session
        return token, session


def cookie(token, base):
    return f"resident_session={token}; Path={base}; Max-Age={TTL if token else 0}; HttpOnly; Secure; SameSite=Lax"


def session_for(handler, config):
    try:
        jar = SimpleCookie()
        jar.load(handler.headers.get("Cookie", ""))
        token = jar["resident_session"].value if "resident_session" in jar else ""
    except CookieError:
        return "", None
    with LOCK:
        session = SESSIONS.get(token)
        if session and session["expires"] > time.monotonic() and session["policy"] == policy_stamp(config):
            return token, session
        SESSIONS.pop(token, None)
    return "", None


def url(base, action):
    return base + "?" + urlencode({"action": action})


def redirect(handler, location, set_cookie=""):
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    if set_cookie:
        handler.send_header("Set-Cookie", set_cookie)
    handler.end_headers()


def identity_form(engine, config, session, error=None):
    draft = session.get("identity_draft") or {}
    csrf = f'<input type=hidden name=csrf value="{engine.esc(session["csrf"])}">'
    if config.get("sign_in_required"):
        fields = ('<label for=username>Duo username</label><input id=username name=username autocomplete=username maxlength=100 required '
                  + f'value="{engine.esc(draft.get("username"))}">')
        action, button = "duo_login", "Continue with Duo"
        intro = "Enter your resident username, then verify with Duo. Only members of the permitted resident group can continue."
    elif config.get("no_sign_in_user_list"):
        members = group_members(config)
        if not members:
            return ui.alert("warning", "No residents are in the permitted group. Contact your administrator.")
        fields = ('<div data-choice-filter><div data-filter-controls hidden><label for=resident-search>Find your resident account</label>'
                  '<input id=resident-search type=search autocomplete=off maxlength=100 data-filter-input '
                  'aria-controls=resident aria-describedby=resident-search-help>'
                  '<p id=resident-search-help class=hint>Search by name or username, then select your account. '
                  'Only the permitted resident group is listed.</p><p class=hint role=status data-filter-status></p>'
                  '</div><label for=resident>Resident account</label><select id=resident name=user_id required>'
                  '<option value="">Choose your account</option>')
        fields += "".join(f'<option value="{engine.esc(m["user_id"])}">'
                          + engine.esc((m.get("display_name") or m["username"])
                                       + (" (" + m["username"] + ")" if m.get("display_name") and m["display_name"] != m["username"] else ""))
                          + '</option>' for m in members) + '</select></div>'
        action, button = "choose", "Continue"
        intro = "Choose your resident account to create a new device key. This portal does not verify your identity."
    else:
        fields = ('<label for=name>Full name</label><input id=name name=name autocomplete=name maxlength=100 required '
                  + f'value="{engine.esc(draft.get("name"))}">'
                  + '<label for=email>Email</label><input id=email name=email type=email autocomplete=email maxlength=254 required '
                  + f'value="{engine.esc(draft.get("email"))}">')
        action, button = "choose", "Continue"
        intro = "Enter your details to create a new device key. This portal does not verify your identity."
    markup = (guidance.progress(1) + f'<p>{intro}</p><form class=resident-access-form method=post action="{engine.esc(url(engine.PUBLIC_BASE, action))}">{csrf}'
            + fields + f'<button class="btn" type=submit>{button}</button></form>')
    return guidance.form_error(markup, error)


def account_form(engine, config, session, error=None):
    identity = session["identity"]
    draft = session.get("draft") or {}
    context = engine.CAPTIVE_SESSIONS.get(session["captive"])
    if not context and not config.get("self_service_enabled"):
        raise ValueError("Reconnect to setup Wi-Fi to register this device.")
    device_choice = ''
    if context:
        device_choice = (f'<p><b>This device address:</b> <code>{engine.esc(context.mac)}</code></p>'
                         '<label for=target>Device to connect</label><select id=target name=target>'
                         '<option value=current>This device</option>')
        if config.get("self_service_enabled"):
            device_choice += '<option value=other' + (' selected' if draft.get("target") == "other" else '') + '>Another device</option>'
        device_choice += '</select>'
    else:
        device_choice = '<input type=hidden name=target value=other>'
    mac = ('<div class="field"' + (' data-show-when="target=other" data-control-when-visible' if context else '') + '>'
           '<label for=mac>Other device’s hardware MAC address</label>'
           '<input id=mac name=mac maxlength=32 autocomplete=off data-required-when-visible '
           'aria-describedby="other-device-help" placeholder="00:11:22:33:44:55" value="' + engine.esc(draft.get("mac")) + '"'
           + (' required' if not context or draft.get("target") == "other" else '') + '>'
           '<p id="other-device-help" class=hint>For another device, enter its hardware Wi-Fi address from settings. '
           'Turn off private addressing on that device before connecting.</p></div>') if config.get("self_service_enabled") else ''
    invite = ('<label for=invite>Invitation code</label><input id=invite name=invite autocomplete=off required>') if config.get("invite_required", True) else ''
    markup = (guidance.progress(2) + f'<p>Creating a key for <b>{engine.esc(identity["name"])}</b>. Each device receives its own Wi-Fi password and join QR.</p>'
            f'<form class=resident-access-form method=post action="{engine.esc(url(engine.PUBLIC_BASE, "create_device"))}">'
            f'<input type=hidden name=csrf value="{engine.esc(session["csrf"])}">'
            '<label for=device>Device name</label><input id=device name=device maxlength=100 required placeholder="Living room TV" value="' + engine.esc(draft.get("device")) + '">'
            + device_choice + mac + '<label for=unit>Unit or room</label><input id=unit name=unit maxlength=80 autocomplete=address-line2 value="' + engine.esc(draft.get("unit")) + '">'
            + invite + '<button class="btn" type=submit>Create device key and QR</button></form>'
            f'<p class=hint>Up to {int(config.get("max_devices_per_resident", 5))} device keys per resident. Existing passwords are never shown here.</p>'
            f'<form method=post action="{engine.esc(url(engine.PUBLIC_BASE, "logout"))}">'
            f'<input type=hidden name=csrf value="{engine.esc(session["csrf"])}"><button class="btn text" type=submit>Finish session</button></form>')
    return guidance.form_error(markup, error)


def handle_get(engine, handler, action, query, captive_token=""):
    config = settings()
    try:
        validate_settings(config)
        if not enabled(config) or action not in ("", "account", "duo_callback"):
            handler.send_error(404)
            return
        token, session = session_for(handler, config)
        if action == "duo_callback":
            if not session:
                raise ValueError("Your sign-in expired. Return to the portal and start again.")
            with LOCK:
                pending, session["pending"] = session["pending"], None
            state = query.get("state", [""])[0]
            code = query.get("duo_code", [""])[0]
            if (not pending or pending["expires"] <= time.monotonic() or not code
                    or not secrets.compare_digest(state, pending["state"])):
                raise ValueError("Your sign-in could not be verified. Start again.")
            result = _duo_call(universal_client(config).exchange_authorization_code_for_2fa_result,
                               code, pending["identity"]["username"], pending["nonce"])
            if (result.get("auth_result", {}).get("result") != "allow"
                    or not isinstance(result.get("amr"), list) or not result["amr"]
                    or result.get("preferred_username") != pending["identity"]["username"]):
                raise ValueError("Duo verification is required. Bypass responses cannot sign in.")
            identity = member_identity(config, user_id=pending["identity"]["user_id"])
            identity["verified"] = True
            with LOCK:
                SESSIONS.pop(token, None)
                token, session = new_session(config, session["captive"], identity)
            redirect(handler, url(engine.PUBLIC_BASE, "account"), cookie(token, engine.PUBLIC_BASE))
            return
        if captive_token:
            # Every splash entry starts a fresh identity flow; a captured MAC
            # cannot replace another session's context through a browser field.
            token, session = new_session(config, captive_token)
        if not session:
            if not config.get("sign_in_required"):
                engine._connect_page(handler, "Connect to the setup network before choosing a resident or creating a key.")
                return
            token, session = new_session(config)
        if session["identity"]:
            check_identity(config, session["identity"])
            body = account_form(engine, config, session)
        else:
            body = identity_form(engine, config, session)
        engine._public_page(handler, "Resident device access", body, set_cookie=cookie(token, engine.PUBLIC_BASE), welcome=not session["identity"])
    except ValueError as err:
        engine._public_page(handler, "Check resident access", ui.alert("error", engine.esc(err))
                            + f'<p><a href="{engine.esc(url(engine.PUBLIC_BASE, "account"))}">Return to resident access</a></p>', 403)
    except Exception:
        engine._public_page(handler, "Resident access unavailable", ui.alert("error", "We could not reach the resident service. Contact your administrator or try again shortly."), 503)


def check_identity(config, identity):
    if config.get("sign_in_required") and not identity.get("verified"):
        raise ValueError("Sign in with Duo before creating a key.")
    if config.get("sign_in_required") or config.get("no_sign_in_user_list"):
        fresh = member_identity(config, user_id=identity.get("user_id", ""))
        if fresh["owner"] != identity["owner"]:
            raise ValueError("Your resident account is unavailable. Sign in again.")


def handle_post(engine, handler, action, form, ip):
    config = settings()
    token, session = session_for(handler, config)
    try:
        validate_settings(config)
        if not enabled(config) or not session:
            raise ValueError("Your resident session expired. Reconnect or sign in again.")
        if not secrets.compare_digest(str(form.get("csrf", [""])[0]), session["csrf"]):
            raise ValueError("This form expired. Reload the page and try again.")
        if action == "logout":
            with LOCK:
                SESSIONS.pop(token, None)
            engine._public_page(handler, "Session finished", '<p>You can close this page.</p>', set_cookie=cookie("", engine.PUBLIC_BASE))
            return
        if action == "duo_login" and config.get("sign_in_required"):
            with LOCK:
                session["identity_draft"] = {"username": form.get("username", [""])[0][:100]}
            try:
                identity = member_identity(config, username=form.get("username", [""])[0].strip())
            except ValueError as err:
                raise guidance.FieldError("username", str(err)) from None
            client = universal_client(config)
            _duo_call(client.health_check)
            state, nonce = client.generate_state(), secrets.token_urlsafe(32)
            with LOCK:
                session["pending"] = {"identity": identity, "state": state, "nonce": nonce, "expires": time.monotonic() + 300}
            redirect(handler, _duo_call(client.create_auth_url, identity["username"], state, nonce=nonce))
            return
        if action == "choose" and not config.get("sign_in_required"):
            if config.get("no_sign_in_user_list"):
                try:
                    identity = member_identity(config, user_id=form.get("user_id", [""])[0])
                except ValueError as err:
                    raise guidance.FieldError("resident", str(err)) from None
            else:
                name, email = form.get("name", [""])[0].strip(), form.get("email", [""])[0].strip().lower()
                with LOCK:
                    session["identity_draft"] = {"name": name[:100], "email": email[:254]}
                if not 2 <= len(name) <= 100 or not name.isprintable():
                    raise guidance.FieldError("name", "Enter your full name (2 to 100 characters).")
                if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise guidance.FieldError("email", "Enter a valid email address, such as name@example.com.")
                identity = {"owner": "email:" + email, "name": name, "email": email, "verified": False}
            with LOCK:
                SESSIONS.pop(token, None)
                token, session = new_session(config, session["captive"], identity)
            redirect(handler, url(engine.PUBLIC_BASE, "account"), cookie(token, engine.PUBLIC_BASE))
            return
        if action != "create_device" or not session["identity"]:
            raise ValueError("Choose your resident account or sign in before creating a key.")
        check_identity(config, session["identity"])
        context = engine.CAPTIVE_SESSIONS.get(session["captive"])
        target = form.get("target", [""])[0]
        if target == "current" and context:
            mac = context.mac
        elif target == "other" and config.get("self_service_enabled"):
            mac = form.get("mac", [""])[0]
        else:
            raise ValueError("Reconnect to setup Wi-Fi or choose another device.")
        with LOCK:
            if session["busy"] or not secrets.compare_digest(str(form.get("csrf", [""])[0]), session["csrf"]):
                raise ValueError("A key request is already being processed. Wait for it to finish.")
            session["busy"] = True
            session["draft"] = {k: form.get(k, [""])[0][:100] for k in ("device", "mac", "unit", "target")}
        try:
            result = create_device(engine, config, session["identity"], form.get("device", [""])[0],
                                   mac, form.get("unit", [""])[0], form.get("invite", [""])[0], ip)
            # Consume the old token while the request is still marked busy.
            # No second request may enter between provisioning and rotation.
            with LOCK:
                session["csrf"] = secrets.token_urlsafe(32)
                session.pop("draft", None)
        finally:
            with LOCK:
                session["busy"] = False
        body = engine.device_success(result, context.grant if target == "current" else "")
        if target == "current":
            engine.CAPTIVE_SESSIONS.discard(session["captive"])
            session["captive"] = ""
        if config.get("self_service_enabled"):
            body += f'<p><a class="btn text" href="{engine.esc(url(engine.PUBLIC_BASE, "account"))}">Add another device</a></p>'
        body += (f'<form method=post action="{engine.esc(url(engine.PUBLIC_BASE, "logout"))}">'
                 f'<input type=hidden name=csrf value="{engine.esc(session["csrf"])}">'
                 '<button class="btn text" type=submit>Finish session</button></form>')
        engine._public_page(handler, "Your device key is ready", body)
    except ValueError as err:
        recovery = f'<p><a href="{engine.esc(url(engine.PUBLIC_BASE, "account"))}">Return to resident access</a></p>'
        if session and session["identity"] and action == "create_device":
            try:
                recovery = account_form(engine, config, session, err)
            except ValueError:
                pass
        elif session and not session["identity"] and action in ("choose", "duo_login"):
            try:
                recovery = identity_form(engine, config, session, err)
            except (ValueError, RuntimeError):
                pass
        engine._public_page(handler, "Check your details", ui.alert("error", engine.esc(err))
                            + recovery, 400)
    except Exception:
        engine._public_page(handler, "Device access unavailable", ui.alert("error", "We could not complete this request. Contact your administrator before retrying if a key may have been created."), 503)


def create_device(engine, config, identity, name, mac, unit, invitation, ip):
    """Persist device attribution in Step CA's DB; serialize each resident's quota."""
    try:
        mac = engine.captive.hardware_mac(mac)
    except ValueError as err:
        err.field = "mac"
        raise
    name, unit = name.strip(), unit.strip()
    if not 1 <= len(name) <= 100 or not name.isprintable():
        raise guidance.FieldError("device", "Enter a device name using 1 to 100 printable characters.")
    if len(unit) > 80 or (unit and not unit.isprintable()):
        raise guidance.FieldError("unit", "Enter a unit or room using at most 80 printable characters.")
    if config.get("invite_required", True) and not invitation.strip():
        raise guidance.FieldError("invite", "Enter an invitation code from your building administrator.")
    inactive = engine.inactive_ipsk_ids()
    conn = engine.db_connect()
    created_id = ""
    device_lock = ""
    try:
        device_lock = engine.lock_device(conn, mac)
        with conn.cursor() as cur:
            engine.sync_inactive_keys(cur, inactive)
            cur.execute("INSERT INTO stepca_resident_accounts (owner_key, name, email) VALUES (%s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE owner_key = VALUES(owner_key)",
                        (identity["owner"], identity["name"][:100], identity["email"][:254]))
            cur.execute("SELECT owner_key FROM stepca_resident_accounts WHERE owner_key = %s FOR UPDATE", (identity["owner"],))
            cur.fetchone()
            cur.execute("SELECT COUNT(*) AS count FROM stepca_resident_devices WHERE owner_key = %s AND active = TRUE", (identity["owner"],))
            count = cur.fetchone()["count"]
            cur.execute("SELECT COUNT(*) AS count FROM stepca_residents WHERE email = %s AND email != '' AND active = TRUE", (identity["email"],))
            count += cur.fetchone()["count"]
            if count >= int(config.get("max_devices_per_resident", 5)):
                raise ValueError("You have reached your device limit. Contact your administrator to remove an old key.")
            cur.execute("SELECT mac_address FROM stepca_resident_devices WHERE mac_address = %s AND active = TRUE "
                        "UNION SELECT mac_address FROM stepca_residents WHERE mac_address = %s AND active = TRUE", (mac, mac))
            if cur.fetchone():
                raise ValueError("This device already has a key. Contact your administrator for help.")
            invite_id = None
            if config.get("invite_required", True):
                cur.execute("SELECT id FROM stepca_invites WHERE code_hash = SHA2(%s, 256) AND used_at IS NULL "
                            "AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP()) FOR UPDATE", (invitation.strip().upper(),))
                invite = cur.fetchone()
                if not invite:
                    raise guidance.FieldError("invite", "That invitation is invalid, expired or already used. Ask your administrator for a new code.")
                invite_id = invite["id"]
            if config.get("key_backend", "meraki_legacy") == "meraki_legacy":
                created = engine.create_ipsk(name, config["network_id"], config.get("ssid_number", 0),
                                             config.get("duration_hours", 0), unit, identity["name"], config.get("group_policy_id", ""))
            else:
                created = engine.create_resident_key(config, name, mac, unit, identity["name"])
            created_id = str(created.get("id") or created.get("psk_group_id") or "")
            ssid, passphrase = str(created.get("ssid_name") or ""), str(created.get("passphrase") or "")
            if not created_id:
                raise RuntimeError("The Wi-Fi service did not return the key ID.")
            engine.validate_wifi_credentials(ssid, passphrase)
            cur.execute("INSERT INTO stepca_resident_devices (owner_key, device_name, unit, mac_address, ipsk_id, source_ip, verified, created_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP())",
                        (identity["owner"], name, unit, mac, created_id, ip[:45], bool(identity.get("verified"))))
            if invite_id:
                cur.execute("UPDATE stepca_invites SET used_at = UTC_TIMESTAMP() WHERE id = %s", (invite_id,))
        conn.commit()
        return {"name": name, "ssid": ssid, "passphrase": passphrase}
    except Exception:
        conn.rollback()
        if created_id:
            try:
                engine.set_ipsk_status(created_id, "delete")
            except Exception:
                print(f"Resident device key cleanup failed for {created_id}; administrator action required.", flush=True)
        raise
    finally:
        engine.unlock_device(conn, device_lock)
        conn.close()


def admin_settings_card(engine, config, csrf, action_url, standalone=False, identity_urls=None):
    toggles = ""
    for key, label, help_text in (
        ("self_service_enabled", "Allow residents to add other devices", "Residents can issue a device key and download its join QR."),
        ("sign_in_required", "Require Duo verification", "Residents enter a username and verify with Duo. The SDK verifies a factor; it does not provide primary password SSO."),
        ("no_sign_in_user_list", "Show a resident list when sign-in is off", "Only members of the permitted Duo group are listed. Selecting a name does not verify identity or reveal existing keys."),
    ):
        if identity_urls and key == "sign_in_required":
            label, help_text = "Require authentication for IPSK", "Use the shared authentication provider and permitted user group before issuing a Wi-Fi key."
        elif identity_urls and key == "no_sign_in_user_list":
            label, help_text = "Use the user directory when authentication is off", "Let users select their name from the permitted group. Selection does not verify identity or reveal existing keys."
        toggles += (f'<label class="check"><input id="{key}" type=checkbox name="{key}" value=1 aria-describedby="{key}-help"' + (' checked' if config.get(key) else '')
                    + f'>{label}</label><p class=hint id="{key}-help">{help_text}</p>')
    if identity_urls:
        links = ' · '.join(f'<a href="{engine.esc(url)}">{label}</a>' for label, url in identity_urls)
        return ('<section class="card" id="resident-access-settings"><div class="card-content">'
                '<p>Choose how residents create Wi-Fi keys. Configure shared identity services under Identity &amp; access.</p>'
                f'<form method="post" action="{engine.esc(action_url)}">{csrf}{toggles}'
                '<label for="max_devices_per_resident">Device limit per resident</label>'
                '<input id="max_devices_per_resident" type="number" name="max_devices_per_resident" min="1" max="50" '
                f'value="{engine.esc(config.get("max_devices_per_resident", 5))}" required>'
                f'<p class="hint">{links}</p><button class="btn" type="submit">Save device access</button></form></div></section>')
    def field(key, label, hint=""):
        secret = key in SECRET_FIELDS
        return (f'<div class="field"><label>{label}<input id="{key}" name="{key}" maxlength="512" aria-describedby="{key}-help" type="{"password" if secret else "text"}" '
                + ('autocomplete="new-password" placeholder="Keep the saved secret"' if secret else f'value="{engine.esc(config.get(key))}" autocomplete=off')
                + f'></label><small class=muted id="{key}-help">' + engine.esc(hint or ("Blank keeps the saved secret." if secret else "")) + '</small></div>')
    opening = ('<section class=card id=resident-access-settings><div class=card-header><h2>Access settings</h2></div>'
               if standalone else '<section class=card><details class=expand id=resident-access-settings><summary>Resident self-service and Duo</summary>')
    closing = '</section>' if standalone else '</details></section>'
    return (opening +
            '<div class=card-content><p>Choose how residents create device keys. Guests still use the guest QR.</p>'
            f'<form method=post action="{engine.esc(action_url)}">{csrf}' + toggles
            + '<label>Device limit per resident<input id="max_devices_per_resident" type=number name=max_devices_per_resident min=1 max=50 '
            + f'value="{engine.esc(config.get("max_devices_per_resident", 5))}" required></label>'
            + '<p class=hint>Saved Duo configuration is retained when its options are off.</p>'
            + '<fieldset data-show-when="sign_in_required=1;no_sign_in_user_list=1" data-control-when-visible><legend>Permitted resident group</legend><div class=field-row>'
            + field("duo_group_id", "Duo group ID", "Required for Duo verification and the resident list. Only this group can receive keys.")
            + field("duo_admin_hostname", "Admin API hostname") + '</div><div class=field-row>'
            + field("duo_admin_integration_key", "Admin API integration key") + field("duo_admin_secret", "Admin API secret")
            + '</div><p class=hint>Use a separate Duo Admin API application with only Grant resource – Read enabled.</p></fieldset>'
            + '<fieldset data-show-when="sign_in_required=1" data-control-when-visible><legend>Duo Universal SDK</legend><div class=field-row>'
            + field("duo_client_id", "Client ID") + field("duo_client_secret", "Client secret") + '</div><div class=field-row>'
            + field("duo_api_hostname", "Web SDK API hostname")
            + field("duo_redirect_uri", "Public callback URL", "https://your-home-assistant/api/step_ca_scep/portal?action=duo_callback")
            + '</div><p class=hint>Duo failure or bypass blocks verification. Allow Duo Universal Prompt and its required resources through the setup network’s walled garden.</p></fieldset>'
            + '<button class=btn type=submit>Save access settings</button></form></div>' + closing)
