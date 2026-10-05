"""Meraki connection, SSID assignment and Access Manager admin workflows."""
import hashlib
import html
import json
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import ipsk
import meraki_provider
import resident_access
import ui

PENDING = {}
LOCK = threading.Lock()
ROOT = "/settings/meraki/"


def esc(value):
    return html.escape(str("" if value is None else value), quote=True)


def fingerprint():
    return hashlib.sha256(json.dumps(meraki_provider.settings(), sort_keys=True).encode()).hexdigest()


def remember(owner, action, message, plan):
    token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with LOCK:
        for key in list(PENDING):
            if PENDING[key]["expires"] < now:
                del PENDING[key]
        if len(PENDING) >= 100:
            raise ValueError("Too many pending previews. Try again after a few minutes.")
        PENDING[token] = {"owner": owner, "expires": now + 600, "action": action,
                          "message": dict(message), "revision": plan["revision"], "provider": fingerprint()}
    return token


def take(owner, token):
    with LOCK:
        value = PENDING.get(token)
        if value is None or value["owner"] != owner:
            raise ValueError("This preview is unavailable. Create a new preview.")
        del PENDING[token]
    if value["expires"] < time.monotonic() or value["provider"] != fingerprint():
        raise ValueError("The preview expired or the connection changed. Create a new preview.")
    return value


def options(name, rows, selected=""):
    return ''.join(f'<option value="{esc(value)}"' + (' selected' if str(value) == str(selected) else '')
                   + f'>{esc(label)}</option>' for value, label in rows)


class MerakiSettingsMixin:
    def meraki_csrf(self):
        import app
        return f'<input type="hidden" name="csrf" value="{esc(app.CSRF_TOKEN)}">'

    def meraki_page(self, kind, query=None, notice="", draft=None):
        import app
        query, draft = query or {}, draft or {}
        titles = {"connection": "Meraki connection", "ssids": "SSIDs and portals", "access-manager": "Access Manager"}
        if kind == "connection":
            try:
                config = dict(app.saved_options().get("meraki") or {})
            except Exception:
                self.page(titles[kind], ui.alert("warning", "Saved add-on options are unavailable. Check the Home Assistant connection.", "Settings unavailable"))
                return
            config.update({k: v for k, v in draft.items() if k != "api_key"})
            source = options("source", [("auto", "Prefer Meraki HA; use API key when unavailable"),
                                        ("meraki_ha", "Meraki HA only"), ("api_key", "API key only")], config.get("source", "auto"))
            body = ('<p class="settings-intro">Reuse the existing Meraki HA connection, including its OAuth session. If it is absent, enter a Dashboard API key.</p>'
                    '<section class="card"><div class="card-content">'
                    f'<form method="post" action="{esc(self.url(ROOT + "connection/save"))}">{self.meraki_csrf()}'
                    f'<label for="source">Connection source</label><select id="source" name="source">{source}</select>'
                    '<label for="api_key">Meraki API key</label><input id="api_key" name="api_key" type="password" autocomplete="new-password" maxlength="512">'
                    f'<p class="hint">{"A key is saved." if config.get("api_key") else "No fallback key is saved."} Blank keeps the saved key. It is stored in add-on options.</p>'
                    '<label class="check"><input type="checkbox" name="clear_key" value="1">Remove the saved API key</label>'
                    '<label for="organization_id">Organization ID for API key connection</label>'
                    f'<input id="organization_id" name="organization_id" inputmode="numeric" maxlength="80" value="{esc(config.get("organization_id"))}">'
                    '<p class="hint">Blank discovers every accessible organization. This filter applies to the API key connection.</p>'
                    '<button class="btn" type="submit">Save connection</button></form></div></section>'
                    '<section class="card"><div class="card-content"><h3>Check the saved connection</h3><p>Reads wireless networks and reports which connection is used.</p>'
                    f'<form method="post" action="{esc(self.url(ROOT + "connection/test"))}">{self.meraki_csrf()}'
                    '<button class="btn text" type="submit">Test Meraki connection</button></form></div></section>')
            self.page(titles[kind], notice + body)
            return
        network = str(draft.get("network_id", query.get("network", [""])[0]))
        choices = {}
        try:
            choices = ipsk.get_options(network)
        except Exception:
            notice += ui.alert("warning", "Could not load Meraki networks. Check the saved connection and API permissions, then reload.", "Meraki unavailable")
        networks = options("network", [("", "Choose a wireless network")] + [(r["id"], r["name"]) for r in choices.get("networks", [])], network)
        lookup = (f'<section class="card"><div class="card-content"><form method="get" action="{esc(self.url(ROOT + kind))}">'
                  f'<label for="network">Wireless network</label><select id="network" name="network">{networks}</select>'
                  '<button class="btn text" type="submit">Load enabled SSIDs</button></form></div></section>')
        active = choices.get("active_ssids", [])
        if not network or not active:
            self.page(titles[kind], notice + lookup + '<p>Select a wireless network with enabled SSIDs to continue.</p>')
            return
        ssid_choices = options("ssid_number", [(r["number"], f'{r["name"]} · {r.get("auth_mode", "unknown")}') for r in active
                                                if kind == "ssids" or r.get("auth_mode") == "ipsk-with-nac"], draft.get("ssid_number", ""))
        scope = (f'<input type="hidden" name="network_id" value="{esc(network)}">'
                 f'<label for="ssid_number">SSID</label><select id="ssid_number" name="ssid_number" required>{ssid_choices}</select>')
        if kind == "ssids":
            rows = ''.join('<tr><td>' + esc(r["name"]) + '</td><td>' + esc(r["number"]) + '</td><td>' + esc(r.get("auth_mode"))
                           + '</td><td>' + esc(r.get("splash_page")) + '</td></tr>' for r in active)
            inventory = '<section class="card"><div class="table-wrap"><table><thead><tr><th>SSID</th><th>Slot</th><th>Authentication</th><th>Captive portal</th></tr></thead><tbody>' + rows + '</tbody></table></div></section>'
            try:
                base = str((app.saved_options().get("enrollment") or {}).get("public_url") or "").rstrip("/")
            except Exception:
                base = ""
            default_url = base + "/api/step_ca_scep/portal" if base else ""
            fields = scope + '<label for="portal_type">Portal assignment</label><select id="portal_type" name="portal_type">' + options("portal_type", [
                ("resident", "Step CA resident portal"), ("external", "External captive portal / WPN portal"),
                ("guest", "Guest network: bypass portal"), ("none", "No captive portal (enterprise Wi-Fi)")], draft.get("portal_type", "external")) + '</select>'
            fields += ('<label for="portal_url">Public HTTPS portal URL</label>'
                       f'<input id="portal_url" name="portal_url" type="url" maxlength="2048" value="{esc(draft.get("portal_url", default_url))}">'
                       '<p class="hint">Step CA uses /api/step_ca_scep/portal on your public Home Assistant host. With Access Manager, assign this portal to the configured setup SSID in the resident Meraki network. Legacy onboarding uses the resident SSID. Bypass and no-portal assignments ignore the URL.</p>'
                       '<label for="auth_mode">SSID authentication</label><select id="auth_mode" name="auth_mode">' + options("auth_mode", [
                           ("preserve", "Keep current authentication"), ("ipsk-without-radius", "iPSK without RADIUS"),
                           ("ipsk-with-nac", "iPSK with Access Manager"),
                           ("8021x-nac", "Enterprise / EAP-TLS with Access Manager")], draft.get("auth_mode", "preserve")) + '</select>'
                       '<label class="check"><input type="checkbox" name="prepare_wpn" value="1"' + (' checked' if draft.get("prepare_wpn") else '') + '>Prepare bridge mode for WPN</label>'
                       '<p class="hint">Create at least one iPSK, then enable WPN in Dashboard on supported APs. The API cannot enable WPN.</p>'
                       '<label for="vlan_id">Default VLAN ID (optional)</label>'
                       f'<input id="vlan_id" name="vlan_id" type="number" min="1" max="4094" value="{esc(draft.get("vlan_id"))}">'
                       '<p class="hint">Blank retains the VLAN. Setting a VLAN also selects bridge mode and enables VLAN tagging. Changing authentication can disconnect clients.</p>'
                       '<label for="walled_garden_ranges">Additional walled-garden hosts or CIDR ranges</label>'
                       f'<textarea id="walled_garden_ranges" name="walled_garden_ranges" rows="4" maxlength="4096">{esc(draft.get("walled_garden_ranges"))}</textarea>'
                       '<p class="hint">One per line. The portal hostname and existing entries are retained. Include Duo and other portal dependencies needed before sign-in.</p>')
            body = '<p class="settings-intro">Assign a captive portal and configure its selected SSID. Review the exact API changes before applying them.</p>' + lookup + inventory
            body += f'<section class="card"><div class="card-content"><form method="post" action="{esc(self.url(ROOT + "ssids/preview"))}">{self.meraki_csrf()}{fields}<button class="btn" type="submit">Preview SSID changes</button></form></div></section>'
        else:
            body = ('<p class="settings-intro">Inspect Access Manager policies and assign a per-client iPSK to a hardware MAC address. '
                    + f'<a href="{esc(self.url("/settings/ipsk/network"))}">Configure resident self-service</a> to issue keys through Access Manager.</p>' + lookup)
            try:
                info = ipsk.core_call({"type": "step_ca_scep/ipsk/access_manager", "network_id": network})[0]
            except Exception as err:
                detail = str(err) if isinstance(err, ValueError) else "Access Manager could not be read. Check organization access, beta API availability and API permissions."
                self.page(titles[kind], notice + body + ui.alert("warning", esc(detail), "Access Manager unavailable"))
                return
            rows = ''.join('<tr><td>' + esc(p["name"]) + '</td><td>' + ('Enabled' if p["enabled"] else 'Disabled') + '</td><td>'
                           + '<br>'.join(esc(r["name"]) + ': ' + esc(r["ipsk_mode"]) + ' (' + esc(r["result"]) + (', enabled)' if r["enabled"] else ', disabled)') for r in p["rules"]) + '</td></tr>' for p in info["policies"])
            body += '<section class="card"><div class="card-content"><h3>Authorization policies</h3><p>Organization ' + esc(info["organization_id"]) + '. Policy keys are never displayed. Configure policy conditions and per-client key mode in Dashboard.</p></div>'
            body += '<div class="table-wrap"><table><thead><tr><th>Policy</th><th>Status</th><th>Rules</th></tr></thead><tbody>' + rows + '</tbody></table></div></section>' if rows else '<div class="card-content"><p>No authorization policies found. Create a policy in Access Manager first.</p></div></section>'
            if not ssid_choices:
                body += f'<p>No enabled Access Manager iPSK SSIDs. Configure one under <a href="{esc(self.url(ROOT + "ssids?" + urlencode({"network": network})))}">SSIDs and portals</a>.</p>'
            elif not info["groups"]:
                body += '<p>Create an Access Manager client group in Dashboard before assigning client keys.</p>'
            else:
                fields = scope + '<label for="group_id">Access Manager client group</label><select id="group_id" name="group_id">' + options("group_id", [(g["id"], g["name"]) for g in info["groups"]], draft.get("group_id", "")) + '</select>'
                for name, label, maximum in (("mac", "Hardware MAC address", 17), ("owner", "Client owner", 100)):
                    fields += f'<label for="{name}">{label}</label><input id="{name}" name="{name}" maxlength="{maximum}" required value="{esc(draft.get(name))}">'
                fields += '<label for="passphrase">Client iPSK</label><input id="passphrase" name="passphrase" type="password" autocomplete="new-password" minlength="8" maxlength="63" required>'
                fields += '<p class="hint">Per-client iPSK must be enabled for the organization, with a matching PERMIT rule using clientIpskOnly or clientIpskWithDefaultFallback. Disable private MAC addressing. Keys apply across the organization and have no automatic expiry.</p>'
                body += f'<section class="card"><div class="card-content"><form method="post" action="{esc(self.url(ROOT + "access-manager/preview"))}">{self.meraki_csrf()}{fields}<button class="btn" type="submit">Preview client key assignment</button></form></div></section>'
        self.page(titles[kind], notice + body)

    def meraki_post(self, kind, action, form):
        import app
        get = lambda key: str(form.get(key, [""])[0])
        try:
            if kind == "connection":
                if action == "save":
                    saved = app.saved_options()
                    config = dict(saved.get("meraki") or {})
                    config.update(source=get("source"), organization_id=get("organization_id").strip(),
                                  api_key="" if get("clear_key") == "1" else get("api_key").strip() or config.get("api_key", ""))
                    meraki_provider.validate(config)
                    saved["meraki"] = config
                    app.supervisor("POST", "/addons/self/options", {"options": saved})
                    meraki_provider.SETTINGS_OVERRIDE = config
                    notice = ui.alert("success", "Connection saved. Test it to load wireless networks.", "Saved")
                elif action == "test":
                    result = ipsk.get_options()
                    source = {"meraki_ha": "Meraki HA", "api_key": "API key"}.get(result.get("provider"), "Meraki connection")
                    notice = ui.alert("success", f'{len(result.get("networks", []))} wireless networks accessible through {source}.', "Connection succeeded")
                else:
                    raise ValueError("Unsupported connection action.")
                self.meraki_page(kind, notice=notice)
                return
            owner = self.headers.get("X-Remote-User-Id", "")
            if action == "apply":
                pending = take(owner, get("preview_token"))
                if pending["action"] != kind:
                    raise ValueError("Create a preview for this operation.")
                message = pending["message"]
                self.meraki_resident_scope(message)
                command = "configure" if kind == "ssids" else "assign_client_key"
                result = ipsk.core_call({**message, "type": "step_ca_scep/ipsk/" + command, "expected_revision": pending["revision"]})[0]
                notice = ui.alert("success" if result.get("complete", True) else "warning", esc(result["message"]), "Meraki result")
                if result.get("applied"):
                    notice += '<p>Confirmed steps: ' + esc(', '.join(result["applied"])) + '</p>'
                if result.get("failed"):
                    notice += '<p>Unconfirmed step: ' + esc(result["failed"]) + '</p>'
                notice += ''.join('<p class="hint">' + esc(s) + '</p>' for s in result.get("manual_steps", []))
                self.meraki_page(kind, {"network": [message["network_id"]]}, notice=notice)
                return
            if action != "preview":
                raise ValueError("Unsupported Meraki action.")
            try:
                number = int(get("ssid_number"))
                vlan = int(get("vlan_id")) if get("vlan_id") else None
            except ValueError:
                raise ValueError("Choose an SSID and enter a whole-number VLAN ID if needed.") from None
            message = {"network_id": get("network_id"), "ssid_number": number}
            if kind == "ssids":
                message.update(portal_type=get("portal_type"), portal_url=get("portal_url").strip(),
                               auth_mode=get("auth_mode"), prepare_wpn=get("prepare_wpn") == "1", vlan_id=vlan,
                               walled_garden_ranges=[r.strip() for r in get("walled_garden_ranges").splitlines() if r.strip()])
            else:
                message.update(mac=get("mac"), owner=get("owner"), passphrase=get("passphrase"), group_id=get("group_id"))
            self.meraki_resident_scope(message)
            command = "configuration_plan" if kind == "ssids" else "client_key_plan"
            plan = ipsk.core_call({**message, "type": "step_ca_scep/ipsk/" + command})[0]
            token = remember(owner, kind, message, plan)
            body = '<p>Review changes for organization ' + esc(plan["organization_id"]) + ', network ' + esc(plan["network_id"]) + ', SSID ' + esc(plan["ssid_name"]) + '.</p>'
            if kind == "ssids":
                labels = {"authMode": "Authentication", "splashPage": "Captive portal", "wpaEncryptionMode": "WPA encryption",
                          "dot11r": "802.11r", "ipAssignmentMode": "IP assignment", "useVlanTagging": "VLAN tagging",
                          "defaultVlanId": "Default VLAN", "walledGardenEnabled": "Walled garden",
                          "walledGardenRanges": "Allowed hosts and ranges", "useSplashUrl": "Use custom portal URL", "splashUrl": "Portal URL"}
                def display(value):
                    if value is None:
                        return "Not set"
                    if isinstance(value, bool):
                        return "Enabled" if value else "Disabled"
                    if isinstance(value, list):
                        return ', '.join(str(v) for v in value) or "None"
                    if isinstance(value, dict):
                        return display(value.get("enabled"))
                    return str(value)
                rows = ''
                for desired, before in ((plan["ssid_changes"], plan["before"]),
                                        (plan["splash_changes"], plan["before"]["splash_settings"])):
                    rows += ''.join('<tr><td>' + esc(labels.get(k, k)) + '</td><td>' + esc(display(before.get(k)))
                                    + '</td><td>' + esc(display(v)) + '</td></tr>' for k, v in desired.items())
                body += '<section class="card"><div class="table-wrap"><table><thead><tr><th>Setting</th><th>Current</th><th>Planned</th></tr></thead><tbody>' + rows + '</tbody></table></div></section>'
            else:
                fields = (("Operation", plan["operation"]), ("Hardware MAC", plan["mac"]), ("Owner", plan["owner"]),
                          ("Client group", plan["group"]["name"]), ("Client iPSK", "Will be assigned; hidden in preview"))
                body += '<section class="card"><dl class="rows">' + ''.join(ui.kv_row(esc(k), esc(v)) for k, v in fields) + '</dl></section>'
            body += '<section class="card"><div class="card-content">'
            body += ''.join('<p class="hint">' + esc(step) + '</p>' for step in plan.get("manual_steps", []))
            body += '<p class="hint">This preview makes no changes. Applying can disconnect clients. It expires in 10 minutes and can be applied once.</p>'
            body += f'<form method="post" action="{esc(self.url(ROOT + kind + "/apply"))}">{self.meraki_csrf()}<input type="hidden" name="preview_token" value="{esc(token)}"><button class="btn" type="submit">Apply to Meraki</button></form>'
            body += f'<a class="btn text" href="{esc(self.url(ROOT + kind + "?" + urlencode({"network": message["network_id"]})))}">Cancel and return</a></div></section>'
            self.page("Review Meraki changes", body)
        except Exception as err:
            error = str(err) if isinstance(err, ValueError) else "Meraki did not confirm the request. Check the connection, API permissions and organization features. Check Dashboard before retrying an apply."
            draft = {k: str(v[0])[:4096] for k, v in form.items() if k not in ("csrf", "api_key", "passphrase", "preview_token")}
            self.meraki_page(kind, notice=ui.alert("error", esc(error), "Could not complete request"), draft=draft)

    def meraki_resident_scope(self, message):
        if message.get("portal_type") != "resident":
            return
        config = resident_access.settings()
        if not config.get("enabled") or message["network_id"] != config.get("network_id"):
            raise ValueError("Save and restart Step CA with this resident Meraki network before assigning its setup portal.")
        if config.get("key_backend") == "access_manager":
            rows = ipsk.get_options(message["network_id"]).get("active_ssids", [])
            setup = next((s for s in rows if s["number"] == message["ssid_number"]), {})
            if (message["ssid_number"] == config.get("ssid_number") or not config.get("setup_ssid")
                    or setup.get("name") != config["setup_ssid"] or setup.get("auth_mode") not in ("psk", "open", "ipsk-without-radius")):
                raise ValueError("Choose the separate setup SSID saved under Guest and setup networks, in the resident Meraki network. Keep the Access Manager resident SSID for individual keys.")
            if message.get("auth_mode", "preserve") != "preserve":
                raise ValueError("Keep current authentication on the resident setup SSID; its existing setup credentials must remain valid.")
        elif message["ssid_number"] != config.get("ssid_number"):
            raise ValueError("Choose the running legacy resident SSID before assigning its portal.")
        expected = "ipsk-with-nac" if config.get("key_backend") == "access_manager" else "ipsk-without-radius"
        mode = message.get("auth_mode", "preserve")
        if mode == "preserve" and config.get("key_backend") != "access_manager":
            rows = ipsk.get_options(message["network_id"]).get("active_ssids", [])
            mode = next((s.get("auth_mode") for s in rows if s["number"] == message["ssid_number"]), None)
        if config.get("key_backend") != "access_manager" and mode != expected:
            raise ValueError("Choose SSID authentication matching the running resident key service in Network and onboarding.")
        parsed = urlsplit(message["portal_url"])
        if parsed.path != "/api/step_ca_scep/portal" or parsed.query:
            raise ValueError("Use the public Home Assistant HTTPS URL ending in /api/step_ca_scep/portal.")
