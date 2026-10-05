"""Resident Wi-Fi onboarding backed by Home Assistant's Meraki iPSK service.

Resident records and invitation codes live in Step CA's configured MariaDB
schema. This module never creates or signs certificates; certificate
enrollment stays in the Step CA enrollment flow.
"""

import asyncio
import base64
import hashlib
import html
import io
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.cookies import SimpleCookie, CookieError

import aiohttp
import pymysql
import qrcode
import qrcode.image.svg
import ui
import portal_skin
import guidance
import captive
import resident_access
import meraki_provider
import sys

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
CORE_WEBSOCKET = os.environ.get("CORE_WEBSOCKET", "ws://supervisor/core/websocket")
CORE_RPC_TIMEOUT = 55
PORTAL_ENABLED = os.environ.get("RESIDENT_PORTAL_ENABLED", "false").lower() == "true"
INVITE_REQUIRED = os.environ.get("RESIDENT_INVITE_REQUIRED", "true").lower() == "true"
PUBLIC_BASE = os.environ.get("RESIDENT_PUBLIC_BASE", "/api/step_ca_scep/portal")
RATE_LIMIT = {}
RATE_LOCK = threading.Lock()
CAPTIVE_SESSIONS = captive.CaptiveSessions()
PORTAL_STYLE = """
.resident-portal input:not([type=hidden]) { font-size: 16px; }
.resident-portal select { font-size: 16px; }
.resident-portal .btn { min-height: 44px; }
.resident-portal code { overflow-wrap: anywhere; }
.resident-portal .qr { text-align: center; }
.resident-access-form label { margin-top:16px; }
.resident-access-form .btn { margin-top:16px; }
.resident-access-form > p:not(.hint) { margin-top:16px; }
"""


def esc(value):
    return html.escape(str(value or ""), quote=True)


def db_connect():
    return pymysql.connect(
        host=os.environ["PORTAL_DB_HOST"],
        port=int(os.environ.get("PORTAL_DB_PORT") or 3306),
        user=os.environ["PORTAL_DB_USER"],
        password=os.environ["PORTAL_DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "stepca"),
        connect_timeout=5,
        read_timeout=10,
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def lock_device(conn, mac):
    """Serialize this MAC across both resident tables before any snapshot reads."""
    name = "stepca:" + hashlib.sha256((os.environ.get("DB_NAME", "stepca") + ":" + mac).encode()).hexdigest()[:56]
    with conn.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 15) AS acquired", (name,))
        if not cursor.fetchone()["acquired"]:
            raise ValueError("This device is being registered. Please try again shortly.")
    return name


def unlock_device(conn, name):
    if name:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
        except pymysql.MySQLError:
            # Closing the connection below also releases its advisory lock.
            pass


async def _core_call(*messages):
    try:
        async with asyncio.timeout(CORE_RPC_TIMEOUT):
            return await _core_exchange(*messages)
    except TimeoutError:
        raise RuntimeError("The Home Assistant Wi-Fi service did not respond in time. Check Meraki Dashboard before retrying key creation.") from None


async def _core_exchange(*messages):
    if not SUPERVISOR_TOKEN:
        raise RuntimeError("Home Assistant is not connected to the resident portal.")
    timeout = aiohttp.ClientTimeout(total=CORE_RPC_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(CORE_WEBSOCKET) as ws:
            if (await ws.receive_json()).get("type") != "auth_required":
                raise RuntimeError("Home Assistant returned an unexpected response.")
            await ws.send_json({"type": "auth", "access_token": SUPERVISOR_TOKEN})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise RuntimeError("Home Assistant authentication failed.")
            results = []
            for msg_id, message in enumerate(messages, 1):
                await ws.send_json({"id": msg_id, **message})
                while True:
                    reply = await ws.receive_json()
                    if reply.get("id") == msg_id and reply.get("type") == "result":
                        break
                if not reply.get("success"):
                    error = reply.get("error") or {}
                    if error.get("code") == "unknown_command":
                        raise meraki_provider.ProviderUnavailable("Update the bundled Step CA companion integration, then restart Home Assistant.")
                    if error.get("code") == "provider_unavailable":
                        raise meraki_provider.ProviderUnavailable("Connect Meraki HA or save an API key under Settings → Meraki → Connection.")
                    raise RuntimeError(error.get("message") or "The Wi-Fi service rejected the request.")
                results.append(reply.get("result"))
            return results


def core_call(*messages):
    return asyncio.run(meraki_provider.call(_core_call, messages, SUPERVISOR_TOKEN))


def get_options(network_id=""):
    result = core_call({"type": "step_ca_scep/ipsk/options", "network_id": network_id})[0]
    return result if isinstance(result, dict) else {}


def _key_records():
    if not os.environ.get("PORTAL_DB_HOST"):
        return []
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT ipsk_id, network_id, ssid_number, associated_user, associated_unit, status FROM stepca_ipsks WHERE status != 'deleted'")
        return cursor.fetchall()


def _default_scope():
    config = resident_access.settings()
    return {"network_id": str(config.get("network_id") or ""),
            "ssid_number": int(config.get("ssid_number", 0))}


def _key_command(action, ident):
    return {"type": "step_ca_scep/ipsk/" + action, "ipsk_id": ident, **_default_scope()}


def list_ipsks(status=""):
    records = _key_records()
    scopes = {(str(row["network_id"]), int(row["ssid_number"])) for row in records}
    default = _default_scope()
    if default["network_id"]:
        scopes.add((default["network_id"], default["ssid_number"]))
    if not scopes:
        return []
    command = {"type": "step_ca_scep/ipsk/list", "scopes": [
        {"network_id": network, "ssid_number": number} for network, number in sorted(scopes)]}
    result = core_call(command)[0]
    if not isinstance(result, list):
        raise RuntimeError("Home Assistant returned invalid Wi-Fi key details.")
    metadata = {row["ipsk_id"]: row for row in records}
    for key in result:
        record = metadata.get(key.get("id"), {})
        key["associated_user"] = record.get("associated_user", "")
        key["associated_unit"] = record.get("associated_unit", "")
        if record.get("status") == "revoked":
            key["status"] = "revoked"
    return [key for key in result if not status or key.get("status") == status]


def inactive_ipsk_ids(keys=None):
    """Only explicit remote expiry/revocation releases recorded device slots."""
    identifiers = []
    default = _default_scope()
    for key in (list_ipsks() if keys is None else keys):
        if key.get("status") not in ("expired", "revoked"):
            continue
        ident = str(key.get("id") or key.get("psk_group_id") or "")
        if ident:
            identifiers.append(ident)
        # Raw Dashboard IDs are scoped to the configured resident network.
        # Never apply that alias to another network/SSID.
        if (key.get("remote_id") and key.get("network_id") == default["network_id"]
                and key.get("ssid_number") == default["ssid_number"]):
            identifiers.append(str(key["remote_id"]))
    return identifiers


def sync_inactive_keys(cursor, identifiers):
    for ident in identifiers:
        for table in ("stepca_residents", "stepca_resident_devices"):
            cursor.execute(f"UPDATE {table} SET active = FALSE WHERE ipsk_id = %s", (ident,))


def create_ipsk(name, network_id, ssid_number, duration_hours, unit="", email="", group_policy_id=""):
    if not os.environ.get("PORTAL_DB_HOST"):
        raise RuntimeError("Select MariaDB in the add-on options before creating Wi-Fi keys.")
    command = {
        "type": "step_ca_scep/ipsk/create",
        "name": name,
        "network_id": network_id,
        "ssid_number": int(ssid_number),
        "duration_hours": int(duration_hours) if duration_hours else 0,
        "associated_user": email,
        "associated_unit": unit,
    }
    if group_policy_id:
        command["group_policy_id"] = group_policy_id
    result = core_call(command)[0]
    _record_key(result, unit, email)
    return result if isinstance(result, dict) else {}


def create_admin_ipsk(name, network_id, ssid_number, passphrase="", duration_hours=0,
                     group_policy_id="", unit="", user=""):
    if not os.environ.get("PORTAL_DB_HOST"):
        raise RuntimeError("Select MariaDB in the add-on options before creating Wi-Fi keys.")
    command = {
        "type": "step_ca_scep/ipsk/create", "name": name,
        "network_id": network_id, "ssid_number": int(ssid_number),
        "duration_hours": int(duration_hours or 0),
    }
    for field, value in (("passphrase", passphrase), ("group_policy_id", group_policy_id),
                         ("associated_unit", unit), ("associated_user", user)):
        if value:
            command[field] = value
    result = core_call(command)[0]
    _record_key(result, unit, user)
    return result if isinstance(result, dict) else {}


def _record_key(key, unit, user):
    """Store attribution in MariaDB; never store a Wi-Fi password."""
    ident = str((key or {}).get("id") or "")
    if not ident:
        raise RuntimeError("The Wi-Fi service did not return the key ID.")
    try:
        validate_wifi_credentials(key.get("ssid_name"), key.get("passphrase"))
        with db_connect() as conn, conn.cursor() as cursor:
            cursor.execute("INSERT INTO stepca_ipsks (ipsk_id, network_id, ssid_number, associated_user, associated_unit, created_at) "
                           "VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP())",
                           (ident, key["network_id"], int(key["ssid_number"]), user[:254], unit[:80]))
            conn.commit()
    except Exception:
        try:
            core_call(_key_command("delete", ident))
        except Exception:
            print(f"Wi-Fi key cleanup failed for {ident}; administrator action required.", flush=True)
        raise


def reveal_ipsk(ipsk_id):
    result = core_call(_key_command("reveal_passphrase", ipsk_id))[0]
    return str((result or {}).get("passphrase") or "")


def ipsk_join_details(ipsk_id):
    """Get current network details before revealing a key for an admin QR."""
    key = core_call(_key_command("get", ipsk_id))[0]
    if not isinstance(key, dict) or key.get("status") != "active":
        raise ValueError("Only an active Wi-Fi key can be shared as a join QR.")
    ssid = str(key.get("ssid_name") or "")
    if not ssid:
        raise ValueError("Home Assistant did not return the network name. A join QR could not be generated.")
    passphrase = reveal_ipsk(ipsk_id)
    validate_wifi_credentials(ssid, passphrase)
    return {"id": ipsk_id, "name": str(key.get("name") or ipsk_id),
            "ssid": ssid, "passphrase": passphrase}


def validate_wifi_credentials(ssid, passphrase):
    """Keep literal network names and passphrases; validate without trimming them."""
    if not isinstance(ssid, str) or not ssid or len(ssid.encode("utf-8")) > 32 or not ssid.isprintable():
        raise ValueError("Enter a Wi-Fi network name of 1 to 32 UTF-8 bytes.")
    if not isinstance(passphrase, str) or not (
        8 <= len(passphrase) <= 63 and passphrase.isascii() and passphrase.isprintable()
        or re.fullmatch(r"[0-9A-Fa-f]{64}", passphrase)
    ):
        raise ValueError("Use 8–63 printable ASCII characters or a 64-digit hexadecimal Wi-Fi key.")


def wifi_qr_payload(ssid, passphrase):
    validate_wifi_credentials(ssid, passphrase)

    def escape(value):
        return "".join("\\" + char if char in '\\;,:"' else char for char in value)

    return f"WIFI:T:WPA;S:{escape(ssid)};P:{escape(passphrase)};;"


def wifi_qr_svg(ssid, passphrase):
    image = qrcode.make(wifi_qr_payload(ssid, passphrase),
                        image_factory=qrcode.image.svg.SvgPathFillImage, box_size=5, border=4)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue()


def wifi_qr_image(ssid, passphrase):
    return "data:image/svg+xml;base64," + base64.b64encode(wifi_qr_svg(ssid, passphrase)).decode("ascii")


def wifi_join_card(title, ssid, passphrase, description, filename="wifi-join.svg", show_password=False,
                   download_primary=True, credentials_first=False, completion=""):
    """An authenticated admin's shareable QR, with a download and literal SSID."""
    image = wifi_qr_image(ssid, passphrase)
    secret = (
        '<div class="field"><span class="label">Wi-Fi password</span>'
        + ui.copy_field(passphrase, "Wi-Fi password", "secret") + '</div>'
        if show_password else ""
    )
    qr = ('<div class="qr"><img width="232" height="232" src="' + image
          + '" alt="Scan to join ' + esc(ssid) + ' Wi-Fi"></div>')
    network = '<div class="field"><span class="label">Network</span><code>' + esc(ssid) + '</code></div>'
    download = ('<a class="btn' + ('' if download_primary else ' text')
                + '" href="' + image + '" download="' + esc(filename) + '">Download QR</a>')
    contents = (network + secret + completion + '<details class="expand"><summary>QR for another device</summary>'
                + qr + download + '</details>') if credentials_first else qr + network + secret + download + completion
    return (
        '<section class="card wifi-join-card"><div class="card-header"><h2>' + esc(title) + '</h2></div>'
        '<div class="card-content"><p>' + esc(description) + '</p>'
        + contents +
        '</div></section>'
    )


def device_success(result, grant="", identity=True):
    """Shared one-time result; put current-device completion before the optional QR."""
    current = bool(grant)
    description = ("Save the password below. Finish setup, then open Wi-Fi settings and join "
                   + result["ssid"] + " with this password.") if current else (
                   "Scan this QR with the other device to join " + result["ssid"]
                   + ". You can also download the QR or enter the Wi-Fi password in that device’s settings.")
    completion = (f'<p><a class="btn" href="{esc(grant)}">Finish setup</a></p>'
                  '<p class="hint">This closes the setup sign-in with a five-minute access window. '
                  'Then join the resident network with your saved individual password.</p>') if current else ""
    return (guidance.progress(3 if identity else 2, identity=identity)
            + ui.alert("warning", "Save this Wi-Fi password before leaving this page. "
                       "It is shown only once; contact your administrator if you lose it.", "Save your password")
            + wifi_join_card("Join with " + result["name"], result["ssid"], result["passphrase"], description,
                             filename="device-wifi.svg", show_password=True, download_primary=not current,
                             credentials_first=current, completion=completion).replace('class="card wifi-join-card"', 'class="wifi-join-card"')
            + '<p>Keep private or randomized addressing off for this resident network.</p>')


def set_ipsk_status(ipsk_id, action):
    command = "revoke" if action == "revoke" else "delete"
    core_call(_key_command(command, ipsk_id))
    if os.environ.get("PORTAL_DB_HOST"):
        with db_connect() as conn, conn.cursor() as cursor:
            cursor.execute("UPDATE stepca_ipsks SET status = %s WHERE ipsk_id = %s", ("revoked" if command == "revoke" else "deleted", ipsk_id))
            conn.commit()


def resident_count():
    if not os.environ.get("PORTAL_DB_HOST"):
        return 0
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM stepca_residents")
        return cursor.fetchone()["count"]


def list_residents():
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT name, email, unit, ipsk_id, ipsk_name, mac_address, created_at "
            "FROM stepca_residents WHERE active = TRUE UNION ALL "
            "SELECT a.name, a.email, d.unit, d.ipsk_id, d.device_name AS ipsk_name, d.mac_address, d.created_at "
            "FROM stepca_resident_devices d JOIN stepca_resident_accounts a ON a.owner_key = d.owner_key WHERE d.active = TRUE "
            "ORDER BY created_at DESC LIMIT 250"
        )
        return cursor.fetchall()


def resident_inventory(search="", sort="newest", page=1, size=25):
    """Search and page the complete inventory, rather than its newest 250 rows."""
    orders = {"newest": "created_at DESC", "oldest": "created_at ASC", "name": "name ASC", "unit": "unit ASC"}
    order = orders.get(sort, orders["newest"])
    search = str(search)[:254].strip().lower()
    size = min(max(int(size), 1), 50)
    page = guidance.page_number(page)
    records = (
        "(SELECT id AS record_id, 0 AS source, name, email, unit, ipsk_id, ipsk_name, mac_address, created_at "
        "FROM stepca_residents WHERE active = TRUE UNION ALL "
        "SELECT d.id AS record_id, 1 AS source, a.name, a.email, d.unit, d.ipsk_id, "
        "d.device_name AS ipsk_name, d.mac_address, d.created_at FROM stepca_resident_devices d "
        "JOIN stepca_resident_accounts a ON a.owner_key = d.owner_key WHERE d.active = TRUE) AS records"
    )
    where = " WHERE LOCATE(%s, LOWER(CONCAT_WS(' ', name, email, unit, ipsk_id, ipsk_name, mac_address))) > 0" if search else ""
    args = (search,) if search else ()
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM " + records)
        total = int(cursor.fetchone()["count"])
        cursor.execute("SELECT COUNT(*) AS count FROM " + records + where, args)
        matched = int(cursor.fetchone()["count"])
        pages = max(1, (matched + size - 1) // size)
        page = min(page, pages)
        cursor.execute("SELECT * FROM " + records + where + " ORDER BY " + order
                       + ", source ASC, record_id ASC LIMIT %s OFFSET %s", (*args, size, (page - 1) * size))
        return {"rows": cursor.fetchall(), "total": total, "matched": matched, "page": page, "pages": pages, "size": size}


def list_invites():
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, label, created_by, created_at, used_at FROM stepca_invites "
            "WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP()) ORDER BY created_at DESC LIMIT 100"
        )
        return cursor.fetchall()


def revoke_invite(invite_id):
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "UPDATE stepca_invites SET revoked_at = UTC_TIMESTAMP() "
            "WHERE id = %s AND used_at IS NULL AND revoked_at IS NULL", (int(invite_id),)
        )
        conn.commit()
        return cursor.rowcount


def create_invite(created_by="Home Assistant administrator", label=""):
    label = str(label).strip()
    if len(label) > 100 or (label and not label.isprintable()):
        raise guidance.FieldError("label", "Use at most 100 printable characters for the invitation label.")
    code = secrets.token_urlsafe(9).replace("-", "A").replace("_", "B").upper()
    with db_connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO stepca_invites (code_hash, created_by, label, created_at) VALUES (SHA2(%s, 256), %s, %s, UTC_TIMESTAMP())",
            (code, created_by[:128], label),
        )
        conn.commit()
    return code


def register_resident(name, email, unit, invite_code, client_ip, client_mac):
    # Validate before connecting to the database, consuming invitations or creating keys.
    client_mac = captive.hardware_mac(client_mac)
    name, email, unit = name.strip(), email.strip().lower(), unit.strip()
    if len(name) < 2 or len(name) > 100 or not name.isprintable():
        raise guidance.FieldError("name", "Enter your full name (2 to 100 characters).")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise guidance.FieldError("email", "Enter a valid email address, such as name@example.com.")
    if len(unit) > 80 or (unit and not unit.isprintable()):
        raise guidance.FieldError("unit", "Enter a unit or room using at most 80 printable characters.")
    if INVITE_REQUIRED and not invite_code.strip():
        raise guidance.FieldError("invite", "Enter the invitation code provided by your building.")

    settings = json.loads(os.environ.get("RESIDENT_SETTINGS_JSON") or "{}")
    network_id = str(settings.get("network_id") or "")
    ssid_number = int(settings.get("ssid_number") or 0)
    duration_hours = int(settings.get("duration_hours") or 0)
    group_policy_id = str(settings.get("group_policy_id") or "")
    if not network_id:
        raise RuntimeError("Resident Wi-Fi onboarding is not configured yet. Contact your administrator.")

    inactive = inactive_ipsk_ids()
    conn = db_connect()
    created_ipsk_id = ""
    device_lock = ""
    try:
        device_lock = lock_device(conn, client_mac)
        with conn.cursor() as cursor:
            sync_inactive_keys(cursor, inactive)
            cursor.execute("SELECT id FROM stepca_residents WHERE email = %s AND active = TRUE LIMIT 1", (email,))
            if cursor.fetchone():
                raise ValueError("This email already has Wi-Fi access. Contact your administrator for help.")
            cursor.execute("SELECT id FROM stepca_residents WHERE mac_address = %s AND active = TRUE "
                           "UNION SELECT id FROM stepca_resident_devices WHERE mac_address = %s AND active = TRUE LIMIT 1", (client_mac, client_mac))
            if cursor.fetchone():
                raise ValueError("This device is already registered. Contact your administrator for its Wi-Fi details.")
            invite_id = None
            if INVITE_REQUIRED:
                cursor.execute(
                    "SELECT id FROM stepca_invites WHERE code_hash = SHA2(%s, 256) AND used_at IS NULL AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > UTC_TIMESTAMP()) FOR UPDATE",
                    (invite_code.strip().upper(),),
                )
                invite = cursor.fetchone()
                if not invite:
                    raise guidance.FieldError("invite", "That invitation is invalid, expired or already used. Ask your administrator for a new code.")
                invite_id = invite["id"]
            clean = re.sub(r"[^A-Za-z0-9 ._-]", "", name).strip()[:64] or "Resident"
            label = (f"Unit-{unit}-{clean}" if unit else f"Resident-{clean}")[:128]
            created = create_ipsk(label, network_id, ssid_number, duration_hours, unit, name, group_policy_id)
            ipsk_id = str(created.get("id") or created.get("psk_group_id") or "")
            created_ipsk_id = ipsk_id
            passphrase = str(created.get("passphrase") or "")
            if not ipsk_id:
                raise RuntimeError("The Wi-Fi service did not return the key ID.")
            ssid = str(created.get("ssid_name") or "")
            validate_wifi_credentials(ssid, passphrase)
            cursor.execute(
                "INSERT INTO stepca_residents (name, email, unit, ipsk_id, ipsk_name, created_at, source_ip, mac_address) "
                "VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), %s, %s)",
                (name, email, unit, ipsk_id, label, client_ip[:45], client_mac),
            )
            if invite_id:
                cursor.execute("UPDATE stepca_invites SET used_at = UTC_TIMESTAMP() WHERE id = %s", (invite_id,))
        conn.commit()
        return {"name": name, "ssid": ssid, "passphrase": passphrase}
    except Exception:
        conn.rollback()
        if created_ipsk_id:
            try:
                set_ipsk_status(created_ipsk_id, "delete")
            except Exception:  # Retain the original failure without logging provider bodies.
                print(f"Could not remove unrecorded resident iPSK {created_ipsk_id}; administrator action required.", flush=True)
        raise
    finally:
        unlock_device(conn, device_lock)
        conn.close()


def _public_page(handler, title, body, status=200, set_cookie="", include_private_help=True, welcome=False):
    config = portal_skin.settings()
    nonce = secrets.token_urlsafe(24)
    markup = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width, initial-scale=1">'
        '<meta name=referrer content=no-referrer><title>' + esc(title) + " · " + esc(config["portal_name"]) + "</title>"
        + "<style>" + ui.STYLE + PORTAL_STYLE + portal_skin.css(config) + f'</style></head><body class="portal-skin" data-portal-theme="{config["theme"]}">' + ui.DIRECTION
        + '<a class="skip-link" href="#main-content">Skip to content</a>'
        + '<main id="main-content" tabindex="-1" class="public resident-portal">'
        + portal_skin.content(config, title, body + guidance.resident_help(include_private_help), welcome=welcome) + "</main>"
        + f'<script nonce="{nonce}">{ui.SCRIPT}</script></body></html>'
    )
    data = markup.encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header(
        "Content-Security-Policy",
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        + f"script-src 'nonce-{nonce}'; form-action 'self'"
        + (" " + origin if (origin := resident_access.duo_form_origin()) else "")
        + "; base-uri 'none'; frame-ancestors 'none'",
    )
    if set_cookie:
        handler.send_header("Set-Cookie", set_cookie)
    handler.end_headers()
    handler.wfile.write(data)


def _wifi_qr(ssid, passphrase):
    return base64.b64encode(wifi_qr_svg(ssid, passphrase)).decode("ascii")


def _cookie_token(handler):
    try:
        cookies = SimpleCookie()
        cookies.load(handler.headers.get("Cookie", ""))
        token = cookies.get("portal_csrf")
        return token.value if token else ""
    except CookieError:
        return ""


def _device_help():
    return (
        '<p>Registration requires your device’s hardware Wi-Fi address.</p>'
        '<ul><li><b>iPhone, iPad or Mac:</b> open this network’s Wi-Fi settings and set '
        '<b>Private Wi-Fi Address</b> to <b>Off</b>.</li>'
        '<li><b>Android:</b> open this network’s details, choose <b>Privacy</b> or '
        '<b>MAC address type</b>, then select <b>Use device MAC</b>.</li>'
        '<li><b>Windows:</b> open this network’s Wi-Fi properties and turn '
        '<b>Random hardware addresses</b> off.</li></ul>'
        '<p>Disconnect and reconnect using the default setup password. Open the new '
        'Wi-Fi sign-in page to register. Keep private addressing off for the resident network too.</p>'
        '<p class="hint">Menu names vary by device. If you need help, contact your building administrator.</p>'
    )


def _connect_page(handler, message="", status=200, title="Connect to setup Wi-Fi"):
    body = ui.alert("warning", esc(message)) if message else ""
    body += (
        '<p>Connect to your building’s setup Wi-Fi using its default password, then '
        'open the Wi-Fi sign-in notification. The captive portal checks your device '
        'before you receive your own resident password.</p>' + _device_help()
    )
    _public_page(handler, title, body, status,
                 f"portal_csrf=; Path={PUBLIC_BASE}; Max-Age=0; HttpOnly; Secure; SameSite=Strict",
                 include_private_help=False, welcome=status == 200 and not message)


def registration_form(context, csrf, draft=None, error=None):
    """Keep editable, non-secret registration details after validation errors."""
    draft = draft or {}
    required = ('<div class=field><label for=invite>Invitation code</label>'
                '<input id=invite name=invite autocomplete=off required></div>') if INVITE_REQUIRED else ""
    markup = (
        guidance.progress(1, identity=False)
        + '<p>Your device address is ready for registration. Enter your details to receive your individual Wi-Fi password.</p>'
        f'<p><b>Device address:</b> <code>{esc(context.mac)}</code></p>'
        f'<form method=post action="{esc(PUBLIC_BASE)}"><input type=hidden name=csrf value="{esc(csrf)}">'
        '<div class=field><label for=name>Full name</label><input id=name name=name autocomplete=name maxlength=100 required '
        f'value="{esc(str(draft.get("name", ""))[:100])}"></div>'
        '<div class=field><label for=email>Email</label><input id=email name=email type=email autocomplete=email maxlength=254 required '
        f'value="{esc(str(draft.get("email", ""))[:254])}"></div>'
        '<div class=field><label for=unit>Unit or room</label><input id=unit name=unit autocomplete=address-line2 maxlength=80 '
        f'value="{esc(str(draft.get("unit", ""))[:80])}"></div>'
        + required + '<button class="btn" type=submit>Get Wi-Fi access</button></form>'
        '<p class="hint">Your passphrase appears once after registration. Save it before closing this page.</p>'
    )
    return guidance.form_error(markup, error)


class PublicPortalHandler(BaseHTTPRequestHandler):
    """Public resident onboarding listener; only Home Assistant Core can reach it."""

    server_version = "step-ca-resident-portal"
    sys_version = ""
    allowed_clients = set(os.environ.get("ENROLL_ALLOWED_CLIENTS", "172.30.32.1").split(","))

    def log_message(self, fmt, *args):
        pass

    def _allowed(self):
        if self.client_address[0] not in self.allowed_clients:
            self.send_error(HTTPStatus.FORBIDDEN)
            return False
        return True

    def do_GET(self):
        if not self._allowed():
            return
        if not PORTAL_ENABLED:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if urllib.parse.urlsplit(self.path).path.rstrip("/") != "/portal":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True)
        if any(len(values) != 1 for values in query.values()):
            _connect_page(self, "Reconnect to open a fresh Wi-Fi sign-in page.", 400)
            return
        action = query.get("action", [""])[0]
        if action:
            resident_access.handle_get(sys.modules[__name__], self, action, query)
            return
        csrf = _cookie_token(self)
        if query:
            # Only the Meraki splash entry point creates registration context.
            # Duplicate parameters are ambiguous and are rejected.
            if any(len(values) != 1 for values in query.values()):
                _connect_page(self, "Reconnect to open a fresh Wi-Fi sign-in page.", 400)
                return
            try:
                csrf = CAPTIVE_SESSIONS.create(
                    query.get("client_mac", [""])[0],
                    query.get("base_grant_url", [""])[0],
                    query.get("user_continue_url", query.get("continue_url", [""]))[0],
                )
            except captive.DeviceAddressError as err:
                _connect_page(self, str(err), 403, "Check your device address")
                return
            except ValueError as err:
                _connect_page(self, str(err), 400)
                return
            except RuntimeError as err:
                _connect_page(self, str(err), 503)
                return
        context = CAPTIVE_SESSIONS.get(csrf)
        if not context:
            if resident_access.settings().get("sign_in_required"):
                resident_access.handle_get(sys.modules[__name__], self, "account", {})
            else:
                _connect_page(self)
            return
        if resident_access.enabled():
            resident_access.handle_get(sys.modules[__name__], self, "", {}, csrf)
            return
        body = registration_form(context, csrf)
        cookie = f"portal_csrf={csrf}; Path={PUBLIC_BASE}; Max-Age=900; HttpOnly; Secure; SameSite=Strict"
        _public_page(self, "Connect to resident Wi-Fi", body, set_cookie=cookie, welcome=True)

    def do_POST(self):
        if not self._allowed():
            return
        if not PORTAL_ENABLED or urllib.parse.urlsplit(self.path).path.rstrip("/") != "/portal":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        ip = self.headers.get("X-Forwarded-For", self.client_address[0]).split(",", 1)[0].strip()
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, keep_blank_values=True)
        if any(len(values) != 1 for values in query.values()):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        action = query.get("action", [""])[0]
        # Choosing an identity must not consume a device registration's allowance.
        rate_key = (ip, "identity" if action in ("choose", "duo_login") else "device")
        now = time.monotonic()
        with RATE_LOCK:
            for address, stamps in list(RATE_LIMIT.items()):
                if not stamps or now - stamps[-1] >= 600:
                    RATE_LIMIT.pop(address, None)
            if rate_key not in RATE_LIMIT and len(RATE_LIMIT) >= 1000:
                _public_page(self, "Please try again shortly", ui.alert("warning", "The portal is busy. Try again in a few minutes."), 429)
                return
            attempts = [stamp for stamp in RATE_LIMIT.get(rate_key, []) if now - stamp < 600]
            limit = 60 if resident_access.enabled() and action in ("create_device", "choose") else 5
            if len(attempts) >= limit:
                RATE_LIMIT[rate_key] = attempts
                _public_page(self, "Please wait before trying again", ui.alert("warning", "Too many attempts. Try again in a few minutes."), 429)
                return
            attempts.append(now)
            RATE_LIMIT[rate_key] = attempts
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        if length < 0 or length > 4096:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        raw = self.rfile.read(length).decode(errors="replace")
        form = urllib.parse.parse_qs(raw, keep_blank_values=True)
        if any(len(values) != 1 for values in form.values()):
            _public_page(self, "Refresh to continue", ui.alert("error", "Reload the page and submit the form once."), 400)
            return
        if resident_access.enabled() or action:
            resident_access.handle_post(sys.modules[__name__], self, action, form, ip)
            return
        csrf = form.get("csrf", [""])[0]
        cookie_token = _cookie_token(self)
        if not csrf or not cookie_token or not secrets.compare_digest(csrf, cookie_token):
            _public_page(self, "Refresh to continue", ui.alert("warning", "This form expired. Reload the page and try again."), 400)
            return
        context = CAPTIVE_SESSIONS.get(cookie_token)
        if not context:
            _connect_page(self, "Your Wi-Fi sign-in session expired. Reconnect to start again.", 403)
            return
        try:
            result = register_resident(
                form.get("name", [""])[0], form.get("email", [""])[0],
                form.get("unit", [""])[0], form.get("invite", [""])[0], ip, context.mac,
            )
        except ValueError as err:
            draft = {key: form.get(key, [""])[0] for key in ("name", "email", "unit")}
            _public_page(self, "Check your details", ui.alert("error", esc(err))
                         + registration_form(context, csrf, draft, err), 400)
            return
        except Exception:  # Public errors and logs never contain provider exception bodies.
            print("Resident Wi-Fi registration failed; administrator action required.", flush=True)
            _public_page(self, "Registration unavailable", ui.alert("error", "We could not complete registration. Please contact your building administrator."), 503)
            return
        CAPTIVE_SESSIONS.discard(cookie_token)
        body = device_success(result, context.grant, identity=False)
        _public_page(self, "You are ready to connect", body, set_cookie=
                     f"portal_csrf=; Path={PUBLIC_BASE}; Max-Age=0; HttpOnly; Secure; SameSite=Strict")
