"""Certificate and resident network management for the Step CA add-on.

Served through Home Assistant ingress, so Home Assistant handles login, and
limited to Home Assistant administrators (ingress itself admits any user). The
certificate inventory is read from step-ca's MariaDB database; revocation goes
through step-ca's API so the CRL is regenerated.

Additional listeners serve one-time device enrollment and resident Wi-Fi
onboarding through Home Assistant, plus a loopback-only SCEP challenge webhook.
"""

import asyncio
import base64
import datetime
import email
import email.policy
import html
import io
import json
import os
import re
import secrets
import signal
import ssl
import subprocess
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aiohttp
import pymysql
import qrcode
import qrcode.image.svg
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import ExtensionOID, NameOID

import enroll
import ipsk
import guidance
import ui
import identity_settings
import portal_skin
from settings_menu import SettingsMixin, canonical_url, legacy_path

STEP_PATH = os.environ.get("STEPPATH", "/data/step")
ROOT_CERT = f"{STEP_PATH}/certs/root_ca.crt"
INTERMEDIATE_CERT = f"{STEP_PATH}/certs/intermediate_ca.crt"
PROVISIONER_PASSWORD = f"{STEP_PATH}/secrets/provisioner_password"
ROOT_KEY = f"{STEP_PATH}/secrets/root_ca_key"
CA_PASSWORD = f"{STEP_PATH}/secrets/password"
CA_URL = "https://localhost:9000"
CRL_URL = "http://127.0.0.1:9080/crl?pem"
SCEP_PROVISIONER = os.environ.get("SCEP_PROVISIONER", "scep")
LISTEN_PORT = int(os.environ.get("ADMIN_PORT", "8099"))
# Only Home Assistant's ingress proxy may talk to this server.
ALLOWED_CLIENTS = set(os.environ.get("ADMIN_ALLOWED_CLIENTS", "172.30.32.2").split(","))
CSRF_TOKEN = secrets.token_urlsafe(32)
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_URL = os.environ.get("SUPERVISOR_URL", "http://supervisor")
CORE_WEBSOCKET = os.environ.get("CORE_WEBSOCKET", "ws://supervisor/core/websocket")
ADMIN_GROUP = "system-admin"
ADMIN_CACHE_SECONDS = 60
ADMIN_REFRESH_SECONDS = 5
SUBJECT_POLICY = os.environ.get("SUBJECT_POLICY", "")
CA_NAME = os.environ.get("CA_NAME", "Home Assistant CA")
SCEP_CHALLENGE = os.environ.get("SCEP_CHALLENGE", "")
ENROLL_PORT = int(os.environ.get("ENROLL_PORT", "8100"))
RESIDENT_PORTAL_PORT = int(os.environ.get("RESIDENT_PORTAL_PORT", "8102"))
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8101"))
WEBHOOK_CERT = os.environ.get("WEBHOOK_CERT", f"{STEP_PATH}/enroll/webhook.crt")
WEBHOOK_KEY = os.environ.get("WEBHOOK_KEY", f"{STEP_PATH}/enroll/webhook.key")
# Home Assistant Core's address on the Supervisor network.
ENROLL_ALLOWED_CLIENTS = set(os.environ.get("ENROLL_ALLOWED_CLIENTS", "172.30.32.1").split(","))
ENROLL_PUBLIC_URL = os.environ.get("ENROLL_PUBLIC_URL", "")
ENROLL_LINK_HOURS = int(os.environ.get("ENROLL_LINK_HOURS", "24"))
try:
    WIFI_OPTIONS = json.loads(os.environ.get("WIFI_JSON") or "{}")
except ValueError:
    WIFI_OPTIONS = {}
# Certificate groups: {name: {"name", "ou", "challenge", "duration", "require_email"}}. Each has
# its own SCEP provisioner (named after the group) whose certificates carry
# the group's OU.
try:
    GROUPS = {g["name"]: g for g in json.loads(os.environ.get("GROUPS_JSON") or "[]")}
except (ValueError, TypeError, KeyError):
    GROUPS = {}
LINKS = enroll.LinkStore()
DOWNLOADS = enroll.Downloads()
SIGNER = enroll.ProfileSigner([
    ("public", os.environ.get("PROFILE_SSL_CERT", ""), os.environ.get("PROFILE_SSL_KEY", "")),
    ("ca", os.environ.get("PROFILE_CA_CERT", ""), os.environ.get("PROFILE_CA_KEY", "")),
])
PUBLIC_SIGNER_LABEL = os.environ.get("PROFILE_SSL_LABEL", "")
SERIAL_RE = re.compile(r"^[0-9]{1,80}$")
ENROLL_SELF_FILE_RE = re.compile(r"/enroll/self/([A-Za-z0-9_-]{32,64})/(file/[A-Za-z0-9_-]{20,64}|root_ca\.crt)")
INGRESS_PATH_RE = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9_-]+$")

REASONS = {
    0: "Unspecified",
    1: "Key compromise",
    3: "Affiliation changed",
    4: "Superseded",
    5: "Cessation of operation",
    6: "Certificate hold",
    9: "Privilege withdrawn",
}


def db_enabled():
    return bool(os.environ.get("DB_HOST"))


def db_connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT") or 3306),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ.get("DB_NAME", "stepca"),
        connect_timeout=5,
        read_timeout=10,
    )


async def _fetch_admin_ids():
    """Return the ids of Home Assistant owners and administrators."""
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(CORE_WEBSOCKET) as ws:
            if (await ws.receive_json()).get("type") != "auth_required":
                raise RuntimeError("unexpected websocket greeting")
            await ws.send_json({"type": "auth", "access_token": SUPERVISOR_TOKEN})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise RuntimeError("websocket authentication failed")
            await ws.send_json({"id": 1, "type": "config/auth/list"})
            msg = await ws.receive_json()
            if not msg.get("success"):
                raise RuntimeError("could not list users")
            return {
                user["id"]
                for user in msg["result"]
                if user.get("is_active", True)
                and (user.get("is_owner") or ADMIN_GROUP in (user.get("group_ids") or []))
            }


async def _core_call(*messages):
    """Send commands over Core's websocket; returns each result, or None when one fails."""
    async with asyncio.timeout(10):
        return await _core_exchange(*messages)


async def _core_exchange(*messages):
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.ws_connect(CORE_WEBSOCKET) as ws:
            if (await ws.receive_json()).get("type") != "auth_required":
                raise RuntimeError("unexpected websocket greeting")
            await ws.send_json({"type": "auth", "access_token": SUPERVISOR_TOKEN})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise RuntimeError("websocket authentication failed")
            results = []
            for number, message in enumerate(messages, 1):
                await ws.send_json({"id": number, **message})
                while True:
                    reply = await ws.receive_json()
                    if reply.get("id") == number and reply.get("type") == "result":
                        break
                results.append(reply.get("result") if reply.get("success") else None)
            return results


def _fetch_core_urls():
    """(external, cloud, internal) Home Assistant URLs from Core."""
    config, cloud = asyncio.run(_core_call({"type": "get_config"}, {"type": "cloud/status"}))
    config = config or {}
    cloud_url = ""
    # Home Assistant Cloud remote access: External URL stays empty and the
    # nabu.casa address is used instead.
    if isinstance(cloud, dict) and cloud.get("logged_in") and cloud.get("remote_enabled") \
            and cloud.get("remote_domain"):
        cloud_url = f"https://{cloud['remote_domain']}"
    return (enroll.normalize_base_url(config.get("external_url") or ""),
            enroll.normalize_base_url(cloud_url),
            enroll.normalize_base_url(config.get("internal_url") or ""))


class AdminCache:
    """Home Assistant admin user ids, refreshed periodically. Fails closed."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ids = frozenset()
        self._fetched = 0.0

    def _refresh(self):
        try:
            self._ids = frozenset(asyncio.run(_fetch_admin_ids()))
        except Exception as err:  # noqa: BLE001 - any failure denies access
            print(f"Could not read Home Assistant users: {err}", flush=True)
            self._ids = frozenset()
        self._fetched = time.monotonic()

    def is_admin(self, user_id):
        if not user_id:
            return False
        with self._lock:
            age = time.monotonic() - self._fetched
            # Refresh on expiry, or early for an unknown user who may have just
            # been promoted, but not more often than every few seconds.
            if age > ADMIN_CACHE_SECONDS or (user_id not in self._ids and age > ADMIN_REFRESH_SECONDS):
                self._refresh()
            return user_id in self._ids


ADMINS = AdminCache()

_parsed = {}


def parse_cert(der):
    cert = _parsed.get(der)
    if cert is None:
        cert = x509.load_der_x509_certificate(der)
        if len(_parsed) > 5000:
            _parsed.clear()
        _parsed[der] = cert
    return cert


def cert_summary(serial, der, data, revoked):
    cert = parse_cert(der)
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        sans = [str(v.value) if hasattr(v, "value") else str(v) for v in san]
    except x509.ExtensionNotFound:
        sans = []
    now = datetime.datetime.now(datetime.timezone.utc)
    not_after = cert.not_valid_after_utc
    if revoked is not None:
        status = "revoked"
    elif not_after < now:
        status = "expired"
    else:
        status = "active"
    provisioner = (data or {}).get("provisioner") or {}
    ou = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
    return {
        "ou": ", ".join(str(a.value) for a in ou),
        "serial": serial,
        "cn": cn[0].value if cn else "",
        "subject": cert.subject.rfc4514_string(),
        "issuer": cert.issuer.rfc4514_string(),
        "sans": sans,
        "not_before": cert.not_valid_before_utc,
        "not_after": not_after,
        "status": status,
        "provisioner": provisioner.get("name", ""),
        "provisioner_type": provisioner.get("type", ""),
        "revoked": revoked,
        "cert": cert,
    }


def load_json(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return {}


def fetch_certs(serial=None):
    """Return certificate summaries from step-ca's tables, newest first."""
    query = (
        "SELECT c.nkey, c.nvalue, d.nvalue, r.nvalue FROM x509_certs c "
        "LEFT JOIN x509_certs_data d ON d.nkey = c.nkey "
        "LEFT JOIN revoked_x509_certs r ON r.nkey = c.nkey"
    )
    args = ()
    if serial is not None:
        query += " WHERE c.nkey = %s"
        args = (serial.encode(),)
    conn = db_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(query, args)
            rows = cur.fetchall()
    finally:
        conn.close()
    certs = []
    for key, der, data, revoked in rows:
        try:
            certs.append(
                cert_summary(key.decode(), bytes(der), load_json(data), load_json(revoked))
            )
        except ValueError:
            continue
    certs.sort(key=lambda c: c["not_before"], reverse=True)
    return certs


def revoke(serial, reason_code, reason):
    """Revoke through step-ca's API using a one-time token from the admin provisioner."""
    common = ["--ca-url", CA_URL, "--root", ROOT_CERT]
    token = subprocess.run(
        ["step", "ca", "token", serial, "--revoke", "--provisioner", "admin",
         "--password-file", PROVISIONER_PASSWORD, *common],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if token.returncode != 0:
        return token.stderr.strip() or "Could not create a revocation token."
    args = ["step", "ca", "revoke", serial, "--token", token.stdout.strip(),
            "--reasonCode", str(reason_code), *common]
    if reason:
        args += ["--reason", reason]
    result = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        return result.stderr.strip() or "Revocation failed."
    return None


def fmt_time(value):
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else ""


def esc(value):
    return html.escape(str(value), quote=True)


def qr_svg(text):
    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathFillImage, border=4)
    svg = image.to_string(encoding="unicode")
    return svg[svg.index("<svg"):]


def cert_chain():
    root = x509.load_pem_x509_certificate(open(ROOT_CERT, "rb").read())
    inter = x509.load_pem_x509_certificate(open(INTERMEDIATE_CERT, "rb").read())
    return root, inter


def ca_chain():
    """This CA's chain, intermediate then root, as one PEM file."""
    root, inter = cert_chain()
    return enroll.chain_pem(inter, [root])


def extra_chain(cert):
    """An uploaded CA with its uploaded issuers, as one PEM file."""
    return enroll.chain_pem(cert, enroll.load_extra_cas())


def full_bundle():
    """Root, intermediate, and uploaded extra CAs as one PEM file."""
    return enroll.ca_bundle([*cert_chain(), *enroll.load_extra_cas()])


def default_networks():
    """The networks in every profile: enrollment links, Enroll this device, and MDM "all networks"."""
    return [w for w in WIFI_NETWORKS if w["include_by_default"]]


def wifi_enabled():
    return bool(default_networks())


def wifi_names():
    """The default networks' names for a sentence, such as <b>Home</b> and <b>Guest</b>."""
    names = [f"<b>{esc(enroll.wifi_name(w))}</b>" for w in default_networks()]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


_core_urls = {"at": float("-inf"), "external": "", "cloud": "", "internal": ""}


def default_base_url(headers):
    """Best guess at the URL devices use to reach Home Assistant."""
    return detect_base_url(headers)[0]


def detect_base_url(headers):
    """(url, where it came from) for the URL devices use to reach Home Assistant."""
    if ENROLL_PUBLIC_URL:
        return enroll.normalize_base_url(ENROLL_PUBLIC_URL), "the enrollment.public_url option"
    if time.monotonic() - _core_urls["at"] > 300:
        try:
            external, cloud, internal = _fetch_core_urls()
        except Exception as err:  # noqa: BLE001 - fall back to the request's host
            print(f"Could not read the Home Assistant URLs from Core: {err}", flush=True)
            external = cloud = internal = ""
        found = {"external": external, "cloud": cloud, "internal": internal}
        if found != {k: _core_urls[k] for k in found}:
            print(f"Home Assistant URLs: external={external or '-'} cloud={cloud or '-'} "
                  f"internal={internal or '-'}", flush=True)
        _core_urls.update(at=time.monotonic(), **found)
    if _core_urls["external"]:
        return _core_urls["external"], "Home Assistant's External URL"
    if _core_urls["cloud"]:
        return _core_urls["cloud"], "Home Assistant Cloud remote access"
    # No External URL set: use the hostname the admin opened Home Assistant
    # with, which is the public one when they are not at home.
    host = headers.get("X-Forwarded-Host", "")
    proto = headers.get("X-Forwarded-Proto", "http")
    if host:
        return (enroll.normalize_base_url(f"{proto}://{host}"),
                "the address you opened Home Assistant with, because no External URL is set")
    if _core_urls["internal"]:
        return _core_urls["internal"], "Home Assistant's Internal URL, because no External URL is set"
    return "", ""


def base_url_hint(url, source):
    """Explain where the default enrollment URL came from."""
    hint = f"From {esc(source)}." if source else "No Home Assistant URL was found."
    if not url.startswith("https://"):
        hint += (" Devices away from home need a public HTTPS URL: set the <b>External URL</b> under "
                 "Settings &rsaquo; System &rsaquo; Network, or the <b>enrollment.public_url</b> add-on "
                 "option, or type it here.")
    return f'<p class="hint">{hint}</p>'


def signer_status():
    """(ok, html) describing which certificate signs profiles."""
    try:
        label, cert, _, _ = SIGNER.signer()
    except RuntimeError as err:
        return False, ui.alert("error", esc(err), "Profiles cannot be signed")
    issuer = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
    issuer = issuer[0].value if issuer else cert.issuer.rfc4514_string()
    who = (f'<span class="mono">{esc(cert.subject.rfc4514_string())}</span><br>'
           f"Issued by {esc(issuer)}, valid until {esc(fmt_time(cert.not_valid_after_utc))}.")
    if label == "public":
        return True, ui.alert("success", who, "Profiles are signed and verified")
    return False, ui.alert(
        "warning",
        f"{who} Signed by this CA because no publicly trusted certificate is available"
        + (f" ({esc(PUBLIC_SIGNER_LABEL)} was not found)" if PUBLIC_SIGNER_LABEL else "")
        + ", so devices show the profile as <b>Not Verified</b>. Install and start the <b>Let&#39;s "
        "Encrypt</b> add-on; its certificate in /ssl is picked up within an hour.",
        "Profiles are signed but not verified",
    )


def group_provisioner(group):
    return group if group in GROUPS else SCEP_PROVISIONER


def parse_group(value):
    """The group chosen in a form ("" for the default), or ValueError."""
    value = (value or "").strip()
    if value and value not in GROUPS:
        raise ValueError("Unknown certificate group.")
    return value


def group_label(group):
    if group in GROUPS:
        return f"{group} (OU={GROUPS[group]['ou']})"
    match = re.search(r"(?:^|, )OU=([^,]+)", SUBJECT_POLICY)
    return f"Default (OU={match.group(1)})" if match else "Default"


def group_requires_email(group):
    return bool((GROUPS.get(group) or {}).get("require_email"))


def check_group_email(group, sans):
    """ValueError when the group requires an email name and sans has none."""
    if group_requires_email(group) and not enroll.split_sans(sans)[0]:
        raise ValueError(f"The group {group} requires an email address in the alternative names, "
                         "for example the user's sign-in email (Entra UPN).")


def csr_has_email(csr):
    """Whether a webhook's x509CertificateRequest has an email alternative name."""
    if csr.get("emailAddresses"):
        return True
    if any(isinstance(san, dict) and san.get("type") == "email" and san.get("value")
           for san in csr.get("sans") or []):
        return True
    try:
        request = x509.load_der_x509_csr(base64.b64decode(csr.get("raw") or ""))
        names = request.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        return bool(names.get_values_for_type(x509.RFC822Name))
    except (ValueError, TypeError, x509.ExtensionNotFound):
        return False


def group_select(field_id, selected="", hint=""):
    """A <select> of the groups, or "" when no groups are configured."""
    if not GROUPS:
        return ""
    options = "".join(
        f'<option value="{esc(g)}"{" selected" if g == selected else ""}'
        f'{" data-require-email" if group_requires_email(g) else ""}>{esc(group_label(g))}'
        f'{", email required" if group_requires_email(g) else ""}</option>'
        for g in ["", *GROUPS]
    )
    return (f'<div class="field"><label for="{field_id}">Group (OU)</label>'
            f'<select id="{field_id}" name="group">{options}</select>'
            + (f'<p class="hint">{hint}</p>' if hint else "") + "</div>")


# -- add-on options through the Supervisor ----------------------------------------

GROUP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
DURATION_RE = re.compile(r"^[0-9]+(h|m)$")


def supervisor(method, path, payload=None):
    """Call the Supervisor API; returns its data or raises RuntimeError."""
    if not SUPERVISOR_TOKEN:
        raise RuntimeError("The Supervisor API is not available.")
    request = urllib.request.Request(
        f"{SUPERVISOR_URL}{path}", method=method,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            body = json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        try:
            message = json.loads(err.read() or b"{}").get("message") or err.reason
        except ValueError:
            message = err.reason
        raise RuntimeError(f"The Supervisor refused the request: {message}") from err
    except (OSError, ValueError) as err:
        raise RuntimeError(f"Could not reach the Supervisor: {err}") from err
    if body.get("result") != "ok":
        raise RuntimeError(f"The Supervisor refused the request: {body.get('message') or 'unknown error'}")
    return body.get("data") or {}


WIFI_SECURITY = ("WPA2", "WPA3", "Any")
WIFI_PROXY = ("none", "manual", "auto")
WIFI_QOS = ("default", "allowlist", "off")
SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9*][A-Za-z0-9*._-]{0,252}$")
HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$|^\[?[0-9A-Fa-f:.]+\]?$")
BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
RCOI_RE = re.compile(r"^[0-9A-Fa-f]{6}([0-9A-Fa-f]{4})?$")
MCC_MNC_RE = re.compile(r"^[0-9]{6}$")
HESSID_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
WIFI_LISTS = ("radius_server_names", "qos_apps", "passpoint_roaming_consortium_ois", "passpoint_nai_realms",
              "passpoint_mcc_mncs")


def wifi_settings(option):
    """One saved Wi-Fi network option with every setting filled in."""
    option = option or {}
    text = lambda name: str(option.get(name) or "").strip()  # noqa: E731
    flag = lambda name, default=False: bool(option.get(name, default))  # noqa: E731
    settings = {
        "name": text("name"), "include_by_default": flag("include_by_default", True),
        "ssid": str(option.get("ssid") or ""), "authentication": text("authentication") or "eap_tls",
        "password": str(option.get("password") or ""), "security": text("security") or "WPA2",
        "eap_username": text("eap_username"), "eap_password": str(option.get("eap_password") or ""),
        "eap_outer_identity": text("eap_outer_identity"),
        "eap_password_per_connection": flag("eap_password_per_connection"),
        "eap_client_certificate": flag("eap_client_certificate"),
        "ttls_inner_authentication": text("ttls_inner_authentication") or "MSCHAPv2",
        "tls_minimum": text("tls_minimum") or "1.2", "tls_maximum": text("tls_maximum"),
        "eap_fast_use_pac": flag("eap_fast_use_pac"), "eap_fast_provision_pac": flag("eap_fast_provision_pac"),
        "eap_sim_rands": int(option.get("eap_sim_rands") or 3),
        "hidden": flag("hidden"), "auto_join": flag("auto_join", True),
        "disable_mac_randomization": flag("disable_mac_randomization"),
        "radius_server": text("radius_server") or "custom",
        "proxy": text("proxy") or "none", "proxy_server": text("proxy_server"),
        "proxy_port": int(option.get("proxy_port") or 0) or None, "proxy_username": text("proxy_username"),
        "proxy_password": str(option.get("proxy_password") or ""), "proxy_pac_url": text("proxy_pac_url"),
        "proxy_pac_fallback": flag("proxy_pac_fallback"),
        "captive_bypass": flag("captive_bypass"), "mac_login_window": flag("mac_login_window"),
        "qos_marking": text("qos_marking") or "default", "qos_apple_calls": flag("qos_apple_calls", True),
        "passpoint": flag("passpoint"), "passpoint_domain": text("passpoint_domain"),
        "passpoint_operator_name": text("passpoint_operator_name"), "passpoint_hessid": text("passpoint_hessid"),
        "passpoint_roaming": flag("passpoint_roaming"),
    }
    for name in WIFI_LISTS:
        settings[name] = [str(n).strip() for n in option.get(name) or [] if n and str(n).strip()]
    return settings


def wifi_networks(options):
    """The Wi-Fi networks in the add-on options: wifi_networks, or the older single wifi option."""
    networks = [wifi_settings(n) for n in options.get("wifi_networks") or []]
    networks = [n for n in networks if enroll.wifi_name(n)]
    if not networks and (options.get("wifi") or {}).get("ssid"):
        networks = [wifi_settings(options["wifi"])]
    return networks


def wifi_option(wifi):
    """A network as saved in wifi_networks: empty text settings left out, as the schema allows."""
    return {k: v for k, v in wifi.items() if v not in ("", None)}


def check_wifi_option(wifi, others=()):
    """Raise ValueError when a Wi-Fi network would not pass the add-on's schema or would not install."""
    name = enroll.wifi_name(wifi)
    if not name:
        raise ValueError("Enter the network name (SSID), or a Passpoint domain for a Passpoint network.")
    if name.lower() in {enroll.wifi_name(o).lower() for o in others}:
        raise ValueError(f"There is already a network named {name}. Give this one its own name.")
    if len(wifi["name"]) > 64 or (wifi["name"] and not wifi["name"].isprintable()):
        raise ValueError("The name can be at most 64 characters.")
    ssid = enroll.wifi_ssid(wifi)
    clash = next((enroll.wifi_name(o) for o in others if o["include_by_default"] and enroll.wifi_ssid(o) == ssid),
                 None) if wifi["include_by_default"] else None
    if clash:
        raise ValueError(f"The network {clash} has the same SSID and is also in every profile. A profile can set "
                         "up an SSID only once: turn off In every profile for one of them and download it on "
                         "its own from Settings → Enrollment & Wi-Fi → MDM profiles.")
    if not wifi["ssid"] and not wifi["passpoint"]:
        raise ValueError("Enter the network name (SSID), or enable Passpoint and enter its domain.")
    if len(wifi["ssid"].encode()) > 32:
        raise ValueError("The network name (SSID) can be at most 32 bytes.")
    method = wifi["authentication"]
    if method not in enroll.WIFI_AUTH:
        raise ValueError("Choose an authentication method from the list.")
    identity_fields = [("eap_username", "802.1X identity")] if method in (*enroll.TLS_EAP, "leap") else []
    if method in enroll.TUNNELED_EAP:
        identity_fields.append(("eap_outer_identity", "Outer identity"))
    for field, label in identity_fields:
        if len(wifi[field]) > 255 or (wifi[field] and not wifi[field].isprintable()):
            raise ValueError(f"{label} must be at most 255 printable characters.")
    if method in enroll.PASSWORD_EAP and len(wifi["eap_password"]) > 255:
        raise ValueError("The 802.1X password must be at most 255 characters.")
    if method == "eap_ttls" and wifi["ttls_inner_authentication"] not in enroll.TTLS_INNER:
        raise ValueError("Choose a supported EAP-TTLS inner authentication method.")
    if method in enroll.TLS_EAP:
        if wifi["tls_minimum"] not in ("1.2", "1.3") or wifi["tls_maximum"] not in ("", "1.2", "1.3"):
            raise ValueError("Choose TLS 1.2 or TLS 1.3.")
        if wifi["tls_minimum"] == "1.3" and wifi["tls_maximum"] != "1.3":
            raise ValueError("Choose a TLS maximum of 1.3 when the minimum is 1.3.")
        if method in enroll.TUNNELED_EAP and wifi["tls_minimum"] == "1.3" and not wifi["eap_outer_identity"]:
            raise ValueError("Enter an outer identity when using TLS 1.3 with a tunneled EAP method.")
    if method == "eap_fast" and wifi["eap_fast_use_pac"] != wifi["eap_fast_provision_pac"]:
        raise ValueError("Turn on both Use PAC and Provision PAC, or leave both off to use server certificates.")
    if method == "eap_sim" and wifi["eap_sim_rands"] not in (2, 3):
        raise ValueError("Choose two or three EAP-SIM challenges.")
    if wifi["mac_login_window"] and method != "eap_tls":
        raise ValueError("Mac login-window connections in this add-on need EAP-TLS. Turn off that setting "
                         "for password or SIM authentication.")
    if wifi["authentication"] == "psk" and not (
            8 <= len(wifi["password"]) <= 63 and wifi["password"].isascii() and wifi["password"].isprintable()
            or re.fullmatch(r"[0-9A-Fa-f]{64}", wifi["password"])):
        raise ValueError("The Wi-Fi password must be 8 to 63 characters (or 64 hex digits).")
    if wifi["security"] not in WIFI_SECURITY:
        raise ValueError("Choose WPA2, WPA3, or Any for security.")
    if method in enroll.TLS_EAP:
        if wifi["radius_server"] != "custom" and wifi["radius_server"] not in enroll.RADIUS_SERVICES:
            raise ValueError("Choose a RADIUS server from the list.")
        for server in wifi["radius_server_names"]:
            if not SERVER_NAME_RE.fullmatch(server):
                raise ValueError(f"{server!r} is not a server name, such as radius.example.com.")
    if wifi["proxy"] not in WIFI_PROXY:
        raise ValueError("Choose None, Manual, or Automatic for the proxy.")
    if wifi["proxy"] == "manual":
        if not HOST_RE.fullmatch(wifi["proxy_server"]):
            raise ValueError("Enter the proxy server's name or IP address, such as proxy.example.com.")
        if not wifi["proxy_port"] or not 1 <= wifi["proxy_port"] <= 65535:
            raise ValueError("Enter the proxy port, 1 to 65535.")
        if len(wifi["proxy_username"]) > 255 or len(wifi["proxy_password"]) > 255:
            raise ValueError("The proxy user name and password can be at most 255 characters.")
    if wifi["proxy"] == "auto" and wifi["proxy_pac_url"] and not re.fullmatch(
            r"https?://[^\s]{1,2000}", wifi["proxy_pac_url"]):
        raise ValueError("The PAC URL must start with http:// or https://.")
    if wifi["qos_marking"] not in WIFI_QOS:
        raise ValueError("Choose a QoS marking setting from the list.")
    for app in wifi["qos_apps"]:
        if not BUNDLE_ID_RE.fullmatch(app):
            raise ValueError(f"{app!r} is not an app bundle ID, such as com.microsoft.teams.")
    if wifi["passpoint"]:
        if method in ("psk", "leap"):
            raise ValueError("Passpoint needs a supported enterprise EAP method; shared passwords and LEAP "
                             "are not available for Passpoint.")
        if not SERVER_NAME_RE.fullmatch(wifi["passpoint_domain"]) or "*" in wifi["passpoint_domain"]:
            raise ValueError("Enter the Passpoint domain, such as example.com.")
        if len(wifi["passpoint_operator_name"]) > 64:
            raise ValueError("The operator name can be at most 64 characters.")
        if wifi["passpoint_hessid"] and not HESSID_RE.fullmatch(wifi["passpoint_hessid"]):
            raise ValueError("The HESSID is a MAC address, such as 00:11:22:33:44:55.")
        for oi in wifi["passpoint_roaming_consortium_ois"]:
            if not RCOI_RE.fullmatch(oi):
                raise ValueError(f"{oi!r} is not a roaming consortium OI (6 or 10 hex digits, such as 5A03BA).")
        for realm in wifi["passpoint_nai_realms"]:
            if not SERVER_NAME_RE.fullmatch(realm) or "*" in realm:
                raise ValueError(f"{realm!r} is not an NAI realm, such as example.com.")
        for code in wifi["passpoint_mcc_mncs"]:
            if not MCC_MNC_RE.fullmatch(code):
                raise ValueError(f"{code!r} is not an MCC/MNC pair (six digits, such as 310410).")


WIFI_NETWORKS = wifi_networks(WIFI_OPTIONS)


def saved_options():
    """The add-on options as saved (they apply on the next start)."""
    return dict(supervisor("GET", "/addons/self/info").get("options") or {})


def running_group(option):
    """A saved groups entry in the form of GROUPS values."""
    return {"name": option.get("name", ""), "ou": option.get("organizational_unit", ""),
            "challenge": option.get("challenge") or "", "duration": option.get("cert_duration") or "",
            "require_email": bool(option.get("require_email"))}


def option_group(group):
    """A GROUPS value in the form of a saved groups entry."""
    option = {"name": group["name"], "organizational_unit": group["ou"]}
    if group.get("challenge"):
        option["challenge"] = group["challenge"]
    if group.get("duration"):
        option["cert_duration"] = group["duration"]
    if group.get("require_email"):
        option["require_email"] = True
    return option


def group_key(group):
    return (group["ou"], group.get("challenge") or "", group.get("duration") or "",
            bool(group.get("require_email")))


CA_CONFIG = f"{STEP_PATH}/config/ca.json"
LEAF_TEMPLATE = f"{STEP_PATH}/templates/scep_leaf.tpl"
LEAF_TEMPLATE_DATA = f"{STEP_PATH}/templates/scep_leaf.json"
APPLY_LOCK = threading.Lock()


def go_minutes(value):
    """Minutes in a Go duration such as 720h, 90m, or 8760h0m0s."""
    parts = re.findall(r"([0-9.]+)(h|m|s)", value or "")
    return sum(float(n) * {"h": 60, "m": 1, "s": 1 / 60}[unit] for n, unit in parts)


def step_ca_pid():
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/comm", encoding="utf-8") as handle:
                    if handle.read().strip() == "step-ca":
                        return int(entry)
            except OSError:
                continue
    return None


def running_provisioners():
    """Names of the provisioners step-ca is serving."""
    context = ssl.create_default_context(cafile=ROOT_CERT)
    with urllib.request.urlopen(f"{CA_URL}/provisioners?limit=1000", context=context, timeout=5) as resp:
        return {p["name"]: p for p in json.loads(resp.read()).get("provisioners") or []}


def apply_groups(option_groups):
    """Give step-ca one SCEP provisioner per group and reload it, without a restart.

    The add-on's start script builds the same provisioners from the saved
    options, so a restart gives the same result. Raises RuntimeError.
    """
    global GROUPS
    groups = [running_group(g) for g in option_groups]
    with APPLY_LOCK:
        try:
            with open(CA_CONFIG, encoding="utf-8") as handle:
                config = json.load(handle)
            with open(LEAF_TEMPLATE_DATA, encoding="utf-8") as handle:
                policy = json.load(handle).get("subjectPolicy") or {}
        except (OSError, ValueError) as err:
            raise RuntimeError(f"Could not read step-ca's configuration: {err}") from err
        provisioners = config.get("authority", {}).get("provisioners") or []
        base = next((p for p in provisioners if p.get("type") == "SCEP" and p.get("name") == SCEP_PROVISIONER), None)
        if base is None:
            raise RuntimeError(f"step-ca has no SCEP provisioner named {SCEP_PROVISIONER}.")
        claims = base.get("claims") or {}
        base_default = claims.get("defaultTLSCertDuration") or "24h"
        base_max = claims.get("maxTLSCertDuration") or base_default
        webhook = ((base.get("options") or {}).get("webhooks") or [{}])[0].get("url") or ""
        longest = go_minutes(base_max)
        made = []
        for g in groups:
            entry = json.loads(json.dumps(base))
            entry["name"] = g["name"]
            entry.pop("challenge", None)
            entry["claims"] = dict(claims, defaultTLSCertDuration=g["duration"] or base_default,
                                   maxTLSCertDuration=g["duration"] or base_max)
            options = entry.setdefault("options", {})
            options["x509"] = {"templateFile": LEAF_TEMPLATE,
                               "templateData": {"subjectPolicy": dict(policy, organizationalUnit=[g["ou"]])}}
            if webhook:
                options["webhooks"] = [dict(options["webhooks"][0], url=f"{webhook}/{g['name']}")]
            longest = max(longest, go_minutes(g["duration"]))
            made.append(entry)
        kept = [p for p in provisioners if p is base or p.get("type") != "SCEP"]
        for p in kept:
            # .p12 issuing for a group must be allowed the group's lifetime.
            if p.get("type") == "JWK" and p.get("name") == enroll.ENROLL_PROVISIONER:
                p_claims = p.setdefault("claims", {})
                p_claims["maxTLSCertDuration"] = f"{int(longest)}m" if longest > go_minutes(base_max) else base_max
        at = kept.index(base) + 1
        config["authority"]["provisioners"] = kept[:at] + made + kept[at:]

        pid = step_ca_pid()
        if pid is None:
            raise RuntimeError("step-ca is not running.")
        tmp = f"{CA_CONFIG}.tmp"
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2)
            os.replace(tmp, CA_CONFIG)
        except OSError as err:
            raise RuntimeError(f"Could not write step-ca's configuration: {err}") from err
        # The challenge webhook answers for the new groups before step-ca asks.
        GROUPS = {g["name"]: g for g in groups}
        os.kill(pid, signal.SIGHUP)
        wanted = {SCEP_PROVISIONER, *GROUPS}
        deadline = time.monotonic() + 15
        while True:
            time.sleep(0.5)
            try:
                running = running_provisioners()
                scep = {name for name, p in running.items() if p.get("type") == "SCEP"}
                if scep == wanted:
                    break
            except (OSError, ValueError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("step-ca did not load the new groups; see the add-on log, "
                                   "or restart the add-on to apply them.")
    print(f"Applied certificate groups without a restart: {', '.join(GROUPS) or 'none'}", flush=True)


def check_group_option(entry, others, options):
    """ValueError when a groups entry is invalid or clashes with the others."""
    name, ou = entry["name"], entry["organizational_unit"]
    if not GROUP_NAME_RE.fullmatch(name):
        raise ValueError("The name must be 1-32 lowercase letters, digits, _ or -, starting with a letter or digit.")
    taken = {g.get("name") for g in others}
    if name in taken:
        raise ValueError(f"There is already a group named {name}.")
    if name in (options.get("scep_provisioner_name") or SCEP_PROVISIONER, "enrollment"):
        raise ValueError(f"The name {name} is used by a built-in provisioner; choose another.")
    if not 1 <= len(ou) <= 64 or any(ord(c) < 32 for c in ou):
        raise ValueError("The OU must be 1-64 characters.")
    if len(entry.get("challenge", "")) > 255 or any(ord(c) < 32 for c in entry.get("challenge", "")):
        raise ValueError("The challenge must be up to 255 characters without line breaks.")
    if entry.get("cert_duration") and not DURATION_RE.fullmatch(entry["cert_duration"]):
        raise ValueError("Enter the lifetime in hours or minutes, such as 720h.")


# Common MDM variables: (key, name, certificate name variables, email variables).
MDM_VARIABLES = (
    ("meraki", "Cisco Meraki Systems Manager",
     [("$DEVICESERIAL", "Serial number"), ("$OWNERUSERNAME", "Owner user name"), ("$OWNEREMAIL", "Owner email"),
      ("$DEVICENAME", "Device name"), ("$UDID", "UDID"), ("$DEVICEID", "Device ID"),
      ("$MACADDRESS", "MAC address"), ("$IMEI", "IMEI")],
     [("$OWNEREMAIL", "Owner email")]),
    ("jamf", "Jamf Pro",
     [("$SERIALNUMBER", "Serial number"), ("$USERNAME", "User name"), ("$EMAIL", "User email"),
      ("$DEVICENAME", "Device name"), ("$UDID", "UDID"), ("$MANAGEMENTID", "Management ID"),
      ("$ASSET_TAG", "Asset tag"), ("$MACADDRESS", "MAC address"), ("$JSSID", "Jamf Pro ID")],
     [("$EMAIL", "User email")]),
    ("kandji", "Kandji (Iru)",
     [("$SERIAL_NUMBER", "Serial number"), ("$USERNAME", "User name"), ("$EMAIL", "User email"),
      ("$DEVICE_NAME", "Device name"), ("$UDID", "UDID"), ("$DEVICE_ID", "Device ID"),
      ("$ASSET_TAG", "Asset tag")],
     [("$EMAIL", "User email")]),
    ("intune", "Microsoft Intune (custom profile)",
     [("{{serialnumber}}", "Serial number"), ("{{userprincipalname}}", "User principal name"),
      ("{{deviceid}}", "Intune device ID"), ("{{aaddeviceid}}", "Entra device ID"),
      ("{{username}}", "User name"), ("{{mail}}", "Email"), ("{{partialupn}}", "UPN prefix")],
     [("{{userprincipalname}}", "User principal name (UPN)"), ("{{mail}}", "Email")]),
)


def update_link(token, link_id, link, cn):
    """URL of the update link a profile for this link carries, creating one if needed.

    An update link reinstalls the newest profile for cn; it starts working for
    longer once the profile that carries it is installed (see LinkStore).
    """
    if not link.get("renewable"):
        token = LINKS.create(label=f"Updates: {cn}", cn=cn, base_url=link["base_url"], wifi=link["wifi"],
                             hours=1, created_by=link.get("created_by", ""), sans=link.get("sans") or (),
                             group=link.get("group", ""), parent=link_id)
    return f"{link['base_url']}{enroll.PUBLIC_BASE}/enroll/{token}"


def profile_for(cn, challenge, base_url, wifi, sans=(), group="", update_url=None, platform=None):
    root, inter = cert_chain()
    organization = ""
    match = re.search(r"(?:^|, )O=([^,]+)", SUBJECT_POLICY)
    if match:
        organization = match.group(1)
    xml = enroll.build_profile(
        cn=cn, challenge=challenge,
        scep_url=f"{base_url}{enroll.PUBLIC_BASE}/scep/{group_provisioner(group)}",
        ca_name=CA_NAME, organization=organization, root=root, intermediate=inter,
        wifi=default_networks() if wifi else None, extra_cas=enroll.load_extra_cas(), sans=sans,
        update_url=update_url, platform=platform,
    )
    return SIGNER.sign(xml)


MDM_CN_RE = re.compile(r"^[A-Za-z0-9 ._@$%{}()-]{1,64}$")
MDM_PLATFORMS = {"ios": "iPhone and iPad", "macos": "Mac"}
MDM_CONTENTS = ("trust", "scep", "wifi")


def mdm_contents():
    """(value, label) for each profile an MDM can download: wifi is every default network,
    wifi:<name> one network on its own."""
    options = [("scep", "Certificates and SCEP" + ("" if SCEP_CHALLENGE or GROUPS else " (needs scep_challenge)")),
               ("trust", "Certificates only")]
    defaults = default_networks()
    singles = [w for w in WIFI_NETWORKS if len(defaults) > 1 or w not in defaults]
    options[:0] = [("wifi:" + enroll.wifi_name(w), f"Certificates, SCEP, and Wi-Fi {enroll.wifi_name(w)}"
                    + ("" if enroll.wifi_name(w) == enroll.wifi_ssid(w) else f" (SSID {enroll.wifi_ssid(w)})"))
                   for w in singles]
    if defaults:
        options.insert(0, ("wifi", "Certificates, SCEP, and Wi-Fi "
                           + ", ".join(enroll.wifi_name(w) for w in defaults)
                           + (" (every network in every profile)" if singles else "")))
    return options


def mdm_profile(platform, contents, cn, base_url, email="", group=""):
    """Unsigned .mobileconfig for an MDM to upload as a custom profile.

    Unsigned because MDMs (Meraki, Jamf, ...) substitute variables such as
    $DEVICESERIAL in the profile, which a signature would forbid.
    Returns (data, filename) or raises ValueError.
    """
    networks = None
    if contents.startswith("wifi:"):
        networks = [w for w in WIFI_NETWORKS if enroll.wifi_name(w) == contents[5:]]
        if not networks:
            raise ValueError(f"There is no Wi-Fi network named {contents[5:]}; it may have been removed.")
        contents = "wifi"
    elif contents == "wifi":
        networks = default_networks()
        if not networks:
            raise ValueError("Wi-Fi is not configured; add a network under Settings → Enrollment & Wi-Fi → Wi-Fi profiles.")
    if platform not in MDM_PLATFORMS or contents not in MDM_CONTENTS:
        raise ValueError("Unknown platform or profile contents.")
    group = parse_group(group)
    challenge = GROUPS[group]["challenge"] if group else SCEP_CHALLENGE
    if contents != "trust":
        if not challenge and group:
            raise ValueError(f"Set a challenge for the group {group} in the add-on options before creating "
                             "an MDM SCEP profile for it.")
        if not challenge:
            raise ValueError("Set the scep_challenge add-on option before creating an MDM SCEP profile.")
        if not cn:
            raise ValueError("Enter a certificate name, such as your MDM's serial number variable.")
        if not email and group_requires_email(group):
            raise ValueError(f"The group {group} requires an email address; choose your MDM's email "
                             "or UPN variable.")
        if email and not MDM_CN_RE.fullmatch(email):
            raise ValueError("The email address must be 1-64 letters, digits, spaces, or . _ @ $ % { } ( ) -")
        if not MDM_CN_RE.fullmatch(cn):
            raise ValueError("The certificate name must be 1-64 letters, digits, spaces, or . _ @ $ % { } ( ) -")
        if not base_url.startswith("https://"):
            raise ValueError("Devices need a public HTTPS Home Assistant URL for SCEP; set the External URL "
                             "or the enrollment.public_url add-on option.")
    root, inter = cert_chain()
    match = re.search(r"(?:^|, )O=([^,]+)", SUBJECT_POLICY)
    wifi_label = ", ".join(enroll.wifi_name(w) for w in networks or [])
    names = {"trust": "CA certificates", "scep": "SCEP certificate", "wifi": "Wi-Fi " + wifi_label}
    # Certificates only is the same for every group.
    group = group if contents != "trust" else ""
    # A single network's profile gets its own identifier, so it installs beside the others.
    kind = contents if networks is None or networks == default_networks() else f"wifi-{enroll._identifier_part(wifi_label)}"
    xml = enroll.build_profile(
        cn=cn or "device", challenge=challenge,
        scep_url=f"{base_url}{enroll.PUBLIC_BASE}/scep/{group_provisioner(group)}",
        ca_name=CA_NAME, organization=match.group(1) if match else "", root=root, intermediate=inter,
        wifi=networks, extra_cas=enroll.load_extra_cas(),
        include_scep=contents != "trust", system_scope=platform == "macos", email_sans=[email], platform=platform,
        identifier=f"mdm.{group + '.' if group else ''}{kind}.{platform}",
        display_name=f"{CA_NAME}: {names[contents]}{', ' + group if group else ''} ({MDM_PLATFORMS[platform]})",
    )
    return xml, f"{safe_filename(CA_NAME)}-{group + '-' if group else ''}{safe_filename(kind)}-{platform}.mobileconfig"


def mdm_bundle(cn, base_url, email="", group=""):
    """Every MDM profile for both device types as one .zip: (data, filename) or ValueError."""
    contents = [value for value, _ in mdm_contents()]
    group = parse_group(group)
    if not (GROUPS[group]["challenge"] if group else SCEP_CHALLENGE):
        contents = ["trust"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        skipped = []
        for platform, label in MDM_PLATFORMS.items():
            for value in contents:
                try:
                    xml, filename = mdm_profile(platform, value, cn, base_url, email, group)
                except enroll.UnsupportedWifiPlatform as err:
                    skipped.append(f"{label} / {value}: {err}")
                    continue
                archive.writestr(f"{label}/{filename}", xml)
        if skipped:
            archive.writestr("README.txt", "Some Wi-Fi profiles were omitted because their authentication "
                             "method is not available on that platform. iOS versions and supported Mac "
                             "profiles are included.\n\n" + "\n".join(skipped) + "\n")
    return buffer.getvalue(), f"{safe_filename(CA_NAME)}-{group + '-' if group else ''}mdm-profiles.zip"


def group_issue_args(group):
    """issue_p12 keyword arguments for a group's OU and lifetime."""
    if group not in GROUPS:
        return {}
    return {"ou": GROUPS[group]["ou"], "not_after": GROUPS[group]["duration"]}


def email_input(field_id, value=""):
    return (
        f'<div class="field"><label for="{field_id}">Email address</label>'
        f'<input id="{field_id}" name="email" type="email" maxlength="254" value="{esc(value)}" data-email-field '
        'placeholder="e.g. josh@example.com" autocapitalize="off" autocorrect="off">'
        '<p class="hint">Added to the certificate as an email alternative name, for example the user&#39;s '
        "sign-in email (Entra UPN)."
        + (" Required for groups that require an email." if any(map(group_requires_email, GROUPS)) else " Optional.")
        + "</p></div>"
    )


def sans_input(field_id, value=""):
    return (
        f'<div class="field"><label for="{field_id}">Other alternative names (optional)</label>'
        f'<input id="{field_id}" name="sans" maxlength="2000" value="{esc(value)}" '
        'placeholder="e.g. host.example.com, 192.0.2.10" autocapitalize="off">'
        '<p class="hint">More email addresses, DNS names, and IP addresses, separated by commas. '
        "Apple profiles support email and DNS names only.</p></div>"
    )


def form_sans(form):
    """The email field and other alternative names as one SAN list, or ValueError."""
    email_text = str(form.get("email", [""])[0]).strip()
    if email_text and not enroll.EMAIL_RE.match(email_text):
        raise ValueError(f"{email_text[:64]} is not an email address.")
    return enroll.parse_sans(f'{email_text} {form.get("sans", [""])[0]}')


def safe_filename(cn):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", cn).strip("_") or "device"


def wifi_help():
    """Manual Wi-Fi settings for devices that installed a .p12."""
    return "".join(network_help(w) for w in default_networks())


def mdm_wifi_settings(wifi):
    """Plain-text reference settings, with no saved passwords exposed."""
    method = wifi.get("authentication") or "eap_tls"
    label = enroll.WIFI_AUTH.get(method, ("Unknown method",))[0]
    security = wifi.get("security") or "WPA2"
    if method == "psk":
        return f"{security} Personal, {label}, use the saved network password"
    parts = [f"{security} Enterprise", label]
    if method == "eap_tls":
        parts += ["client certificate = the SCEP payload",
                  "802.1X identity = " + (wifi.get("eap_username") or "the certificate name")]
    elif method in enroll.PASSWORD_EAP:
        parts += ["802.1X identity = " + (wifi.get("eap_username") or "ask for the RADIUS account on the device"),
                  "password = " + ("ask on every connection" if method in enroll.TUNNELED_EAP
                                    and wifi.get("eap_password_per_connection") else
                                    "the saved RADIUS account password" if wifi.get("eap_password") else
                                    "ask on the device")]
        if method in enroll.TUNNELED_EAP:
            if wifi.get("eap_outer_identity"):
                parts.append("outer identity = " + wifi["eap_outer_identity"])
            parts.append("also require client certificate = the SCEP payload" if wifi.get("eap_client_certificate")
                         else "client certificate not required for Wi-Fi")
        if method == "eap_ttls":
            parts.append("inner authentication = " + (wifi.get("ttls_inner_authentication") or "MSCHAPv2"))
        if method == "eap_fast":
            parts.append("authenticated PAC provisioning" if wifi.get("eap_fast_use_pac")
                         else "PAC disabled; use the server certificate")
        if method == "leap":
            parts.append("legacy method; no TLS tunnel or server-certificate trust")
    elif method in ("eap_sim", "eap_aka"):
        parts.append("identity = a compatible carrier SIM on iPhone or iPad; no SCEP identity for Wi-Fi")
    if method in enroll.TLS_EAP:
        names = list(wifi.get("radius_server_names") or [])
        service = enroll.radius_service(wifi)
        if service:
            names += [name for name in service["server_names"] if name not in names]
        parts.append("trusted certificates = the CA certificate payloads" +
                     (" and " + enroll.common_name(service["roots"][0]) if service else ""))
        parts.append("trusted server names = " + (", ".join(names) or "any name under those trusted CAs"))
    return "; ".join(parts)


def network_help(wifi):
    title = f'<div class="card"><div class="card-header"><h2>Connect to Wi-Fi {esc(enroll.wifi_ssid(wifi))}</h2></div>'
    if wifi.get("authentication") == "psk":
        rows = [("Network (SSID)", esc(wifi["ssid"])),
                ("Security", f'{esc(wifi.get("security", "WPA2"))} Personal'),
                ("Password", f'<span class="mono">{esc(wifi.get("password", ""))}</span>')]
        return (
            title + '<dl class="card-content flush rows">'
            + "".join(f'<div class="kv"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows) + "</dl></div>"
        )
    method = wifi.get("authentication") or "eap_tls"
    method_name = enroll.WIFI_AUTH.get(method, ("Unknown method",))[0]
    names = list(wifi.get("radius_server_names") or [])
    service = enroll.radius_service(wifi)
    if service:
        names += [n for n in service["server_names"] if n not in names]
        ca = (f'{esc(enroll.common_name(service["roots"][0]))}, a public root '
              "(Android: Use system certificates)")
    elif enroll.load_extra_cas():
        ca = "ca-bundle.pem above (Android: install it as a CA certificate)"
    else:
        ca = "the root CA above (Android: install it as a CA certificate)"
    rows = [
        ("Network (SSID)", esc(wifi["ssid"]) if wifi["ssid"] else f'Passpoint, domain {esc(wifi["passpoint_domain"])}'),
        ("Security", f'{esc(wifi.get("security", "WPA2"))} Enterprise'),
        ("EAP method", esc(method_name)),
    ]
    if method in enroll.TLS_EAP:
        rows.append(("CA certificate", ca))
        if names:
            rows.append(("Domain / server name", esc(", ".join(names))))
    if method == "eap_tls":
        rows.append(("Identity", esc(wifi.get("eap_username") or "your certificate name")))
        rows.append(("Client certificate", "the certificate you just installed"))
    elif method in enroll.PASSWORD_EAP:
        rows.append(("Identity", esc(wifi.get("eap_username") or "your RADIUS account user name")))
        rows.append(("Password", "your RADIUS account password"))
        if wifi.get("eap_outer_identity") and method in enroll.TUNNELED_EAP:
            rows.append(("Anonymous / outer identity", esc(wifi["eap_outer_identity"])))
        if method == "eap_ttls":
            rows.append(("Inner authentication", esc(wifi.get("ttls_inner_authentication") or "MSCHAPv2")))
        if method == "peap":
            rows.append(("Phase 2 authentication", "Match your RADIUS server (usually MSCHAPv2)."))
        if method in enroll.TUNNELED_EAP and wifi.get("eap_client_certificate"):
            rows.append(("Client certificate", "the certificate you just installed, also required by RADIUS"))
    else:
        rows.append(("Identity", "provided by a compatible carrier SIM; device and carrier support required"))
    if wifi.get("proxy") == "manual":
        rows.append(("Proxy", f'{esc(wifi["proxy_server"])}:{wifi["proxy_port"]}'))
    elif wifi.get("proxy") == "auto":
        rows.append(("Proxy", f'Automatic{", " + esc(wifi["proxy_pac_url"]) if wifi["proxy_pac_url"] else ""}'))
    return (
        title + '<dl class="card-content flush rows">'
        + "".join(f'<div class="kv"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows) + "</dl></div>"
    )


def expiring(c, now=None):
    """True for an active certificate that expires within EXPIRING_DAYS."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return c["status"] == "active" and c["not_after"] - now < datetime.timedelta(days=EXPIRING_DAYS)


def status_chip(c, now=None):
    if c["status"] == "active":
        return ui.chip("warn", "Expiring") if expiring(c, now) else ui.chip("ok", "Active")
    return ui.chip("bad" if c["status"] == "revoked" else "neutral", c["status"].title())


EXPIRING_DAYS = 30
DELETABLE = ("revoked", "expired")


class DeletedCerts:
    """Serials of revoked or expired certificates deleted from the panel's list.

    step-ca's records are left alone: a revoked certificate must stay on the
    CRL until it expires, and the panel only has read access to the database.
    """

    def __init__(self, path=f"{STEP_PATH}/enroll/deleted_certs.json"):
        self._path = path
        self._lock = threading.Lock()

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as handle:
                serials = json.load(handle)
            return set(serials) if isinstance(serials, list) else set()
        except (OSError, ValueError):
            return set()

    def _save(self, serials):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(sorted(serials), handle)
        os.replace(tmp, self._path)

    def all(self):
        with self._lock:
            return self._load()

    def add(self, serials):
        with self._lock:
            current = self._load()
            new = set(serials) - current
            if new:
                self._save(current | new)
        return len(new)

    def restore(self, serial):
        with self._lock:
            current = self._load()
            if serial in current:
                current.discard(serial)
                self._save(current)


DELETED = DeletedCerts()


class Handler(SettingsMixin, BaseHTTPRequestHandler):
    server_version = "step-ca-admin"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    # -- helpers -----------------------------------------------------------

    def base(self):
        prefix = self.headers.get("X-Ingress-Path", "")
        return prefix if INGRESS_PATH_RE.match(prefix) else ""

    def url(self, path):
        return f"{self.base()}/{canonical_url(path).lstrip('/')}"

    def send(self, status, body, content_type="text/html; charset=utf-8", headers=None, nonce=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        script = f" script-src 'nonce-{nonce}';" if nonce else ""
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'none'; style-src 'unsafe-inline';{script} img-src data:; form-action 'self'; "
            "frame-ancestors 'self'",
        )
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def redirect(self, path):
        self.send_response(303)
        self.send_header("Location", self.url(path))
        self.send_header("Content-Length", "0")
        self.end_headers()

    TABS = (("/", "Certificates", "certificate"), ("/enroll", "Enroll", "qrcode"),
            ("/ipsk", "IPSK", "wifi"),
            ("/ca", "Authority", "shield-check"), ("/settings", "Settings", "cog"))

    SECTION_PAGES = {
        "/": (("/?status=all", "All certificates", "certificate"),
              ("/?status=active", "Active", "check-circle-outline"),
              ("/?status=expiring", "Expiring", "clock-alert-outline"),
              ("/?status=expired", "Expired", "clock-alert-outline"),
              ("/?status=revoked", "Revoked", "cancel"),
              ("/settings/certificates", "Certificate settings", "cog")),
        "/enroll": (("/enroll", "Enrollment overview", "qrcode"),
                    ("/enroll/new", "New one-time link", "link-variant"),
                    ("/enroll/links", "Enrollment links", "link-variant"),
                    ("/enroll/self", "Enroll this computer", "laptop"),
                    ("/enroll/issue", "Issue a certificate", "key-variant"),
                    ("/settings/enrollment", "Enrollment & Wi-Fi settings", "cog")),
        "/ipsk": (("/ipsk", "Wi-Fi keys", "key-variant"),
                  ("/ipsk/devices", "Registered devices", "laptop"),
                  ("/ipsk/invitations", "Invitations", "account-group"),
                  ("/ipsk/join-codes", "Join codes", "qrcode"),
                  ("/ipsk/create", "Create a Wi-Fi key", "plus"),
                  ("/settings/ipsk", "IPSK settings", "cog")),
        "/ca": (("/ca", "Authority overview", "shield-check"),
                ("/ca#root-ca", "Root CA", "shield-check"),
                ("/ca#intermediate-ca", "Intermediate CA", "shield-check"),
                ("/ca#authority-downloads", "Downloads", "download"),
                ("/ca#authority-endpoints", "Endpoints", "link-variant"),
                ("/settings/certificates/trust", "Trust certificates", "cog")),
    }

    def section_dropdown(self, section, label, glyph, selected=False):
        if section == "/settings":
            return self.settings_dropdown(selected)
        parsed = urllib.parse.urlsplit(self.path)
        path = canonical_url(parsed.path)
        if path == "/issue":
            path = "/enroll/issue"
        query = urllib.parse.parse_qs(parsed.query)
        status = query.get("status", ["active"])[0]
        if status not in ("all", "active", "expiring", "expired", "revoked"):
            status = "active"
        links = ""
        for target, title, icon in self.SECTION_PAGES[section]:
            location = urllib.parse.urlsplit(target)
            current = selected and path == location.path and not location.fragment
            if section == "/":
                current = current and urllib.parse.parse_qs(location.query).get("status") == [status]
            links += (
                f'<a href="{esc(self.url(target))}"'
                + (' class="menu-divider"' if target.startswith("/settings/") else "")
                + (' aria-current="page"' if current else "")
                + f'>{ui.icon(icon)}<span>{esc(title)}</span></a>'
            )
        return ui.navigation_dropdown(label, glyph, links, selected)

    def current_tab(self):
        path = canonical_url(urllib.parse.urlsplit(self.path).path)
        if path.startswith("/settings"):
            return "/settings"
        if path.startswith(("/enroll", "/issue")):
            return "/enroll"
        if path.startswith(("/ipsk", "/residents")):
            return "/ipsk"
        if path.startswith("/ca"):
            return "/ca"
        if path.startswith("/tools"):
            return "/tools"
        return "/"

    def document(self, title, body, status=200, head="", body_class=""):
        nonce = secrets.token_urlsafe(16)
        self.send(
            status,
            f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f'<meta name=viewport content="width=device-width, initial-scale=1">{head}'
            f"<title>{esc(title)}</title><style>{ui.STYLE}</style></head>"
            f'<body class="{body_class}">{ui.DIRECTION}<a class="skip-link" href="#main-content">Skip to content</a>'
            f'{body}<script nonce="{nonce}">{ui.SCRIPT}</script></body></html>',
            nonce=nonce,
        )

    def page(self, title, body, status=200, back=None, narrow=False, heading=None, head=""):
        """A panel page: tabs on top-level pages, a back arrow on subpages."""
        if back:
            bar = (f'<a class="icon-btn back" href="{esc(self.url(back))}" aria-label="Back">'
                   f'{ui.icon("arrow-left")}</a><h1 class="toolbar-title">{esc(heading or title)}</h1>')
        else:
            current = self.current_tab()
            tabs = "".join(
                self.section_dropdown(path, label, icon, path == current)
                for path, label, icon in self.TABS
            )
            section_title = next((label for path, label, _ in self.TABS if path == current), title)
            bar = f'<h1 class="toolbar-title">{esc(heading or section_title)}</h1><nav class="tabs" aria-label="Sections">{tabs}</nav>'
        if not back and self.current_tab() == "/settings":
            body = self.settings_shell(title, body)
            narrow = False
        self.document(
            title,
            f'<header class="toolbar">{bar}</header>'
            f'<main id="main-content" tabindex="-1" class="content{" narrow" if narrow else ""}">'
            + body + '</main>',
            status, head=head, body_class="" if back else "has-tabs",
        )

    def not_found(self, title="Not found", body="The page you asked for does not exist."):
        self.page(title, '<div class="card">' + ui.empty_state("alert-circle-outline", title, body)
                  + "</div>", 404, back="/")

    def download(self, data, filename, content_type):
        self.send(200, data, content_type,
                  {"Content-Disposition": f'attachment; filename="{filename}"'})

    def allowed(self):
        if self.client_address[0] not in ALLOWED_CLIENTS:
            self.send(403, "Forbidden", "text/plain")
            return False
        # The ingress proxy sets this header and strips any client-supplied copy.
        if not ADMINS.is_admin(self.headers.get("X-Remote-User-Id", "")):
            self.send(403, "Only Home Assistant administrators can manage certificates.", "text/plain")
            return False
        return True

    # -- routing -------------------------------------------------------------

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.allowed():
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)
        try:
            canonical = canonical_url(path)
            if canonical != path:
                self.redirect(canonical + ("?" + parsed.query if parsed.query else ""))
            elif path.startswith("/settings") and self.settings_get(path, query, lambda: supervisor("GET", "/addons/self/info")):
                pass
            elif path == "/":
                self.list_page(query)
            elif path == "/ca":
                self.ca_page()
            elif path == "/tools":
                self.tools_page()
            elif path == "/tools/groups":
                self.groups_page(query)
            elif path == "/tools/mdm":
                self.mdm_page(query)
            elif path == "/tools/sign":
                self.sign_page(query)
            elif path == "/tools/cas":
                self.cas_page(query)
            elif path == "/tools/wifi":
                self.wifi_page(query)
            elif path == "/tools/options":
                self.options_page()
            elif path == "/tools/setup":
                self.setup_page(query)
            elif path == "/tools/help":
                self.help_page(query)
            elif path == "/enroll":
                if any(key in query for key in ("links", "page", "deleted")):
                    self.redirect("/enroll/links?" + parsed.query)
                else:
                    self.enroll_page()
            elif path == "/enroll/new":
                self.enroll_new_page()
            elif path == "/enroll/links":
                self.enrollment_links_page(query)
            elif path == "/enroll/issue":
                self.enroll_issue_page()
            elif path == "/issue":
                self.redirect("/enroll/issue")
            elif path == "/residents":
                self.redirect("/ipsk" + ("?" + parsed.query if parsed.query else ""))
            elif path in ("/ipsk", "/ipsk/devices", "/ipsk/create", "/ipsk/invitations",
                          "/ipsk/join-codes", "/ipsk/join-codes/settings", "/ipsk/access"):
                self.residents_page(query, section=path.removeprefix("/ipsk/") if path != "/ipsk" else "keys")
            elif path == "/enroll/self":
                self.self_enroll_page()
            elif m := ENROLL_SELF_FILE_RE.fullmatch(path):
                self.enroll_file(m.group(1), m.group(2))
            elif m := re.fullmatch(r"/issue/file/([A-Za-z0-9_-]{20,64})", path):
                self.admin_file(m.group(1))
            elif path == "/download/root_ca.pem":
                self.download(open(ROOT_CERT, "rb").read(), "root_ca.pem", "application/x-pem-file")
            elif path == "/download/intermediate_ca.pem":
                self.download(open(INTERMEDIATE_CERT, "rb").read(), "intermediate_ca.pem",
                              "application/x-pem-file")
            elif m := re.fullmatch(r"/download/extra/([0-9a-f]{64})\.pem", path):
                certs = [c for c in enroll.load_extra_cas() if enroll.fingerprint(c) == m.group(1)]
                if not certs:
                    self.not_found()
                else:
                    self.download(extra_chain(certs[0]),
                                  f"{safe_filename(enroll.common_name(certs[0]))}.pem", "application/x-pem-file")
            elif path == "/download/mdm.mobileconfig":
                self.mdm_download(query)
            elif path == "/download/ca-chain.pem":
                self.download(ca_chain(), "ca-chain.pem", "application/x-pem-file")
            elif path == "/download/meraki-ca-chain.crt":
                self.download(ca_chain(), f"{safe_filename(CA_NAME)}-ca-chain.crt", "application/x-pem-file")
            elif path == "/download/ca-bundle.pem":
                self.download(full_bundle(), "ca-bundle.pem", "application/x-pem-file")
            elif path == "/download/crl.pem":
                with urllib.request.urlopen(CRL_URL, timeout=10) as resp:
                    self.download(resp.read(), "crl.pem", "application/x-pem-file")
            elif m := re.fullmatch(r"/cert/([0-9]+)\.pem", path):
                self.cert_pem(m.group(1))
            elif m := re.fullmatch(r"/cert/([0-9]+)", path):
                self.detail_page(m.group(1), query)
            else:
                self.not_found()
        except Exception as err:  # noqa: BLE001 - shown on the page
            self.error_page(err)

    def error_page(self, err):
        # Home Assistant shows "The app is starting" and retries for 5xx
        # ingress responses, hiding the error, so errors are shown with 200.
        traceback.print_exc()
        title = "Database error" if isinstance(err, pymysql.MySQLError) else "Something went wrong"
        self.page(title, ui.alert("error", f"{esc(err)}<br>Details are in the add-on log.", title))

    def do_POST(self):
        if not self.allowed():
            return
        try:
            self.handle_post()
        except Exception as err:  # noqa: BLE001 - shown on the page
            self.error_page(err)

    def handle_post(self):
        path = legacy_path(urllib.parse.urlsplit(self.path).path)
        # Keep older form URLs working while the panel uses the IPSK routes.
        path = {"/ipsk/create": "/residents/ipsk/create",
                "/ipsk/key/action": "/residents/ipsk/action"}.get(path, path)
        if path.startswith("/ipsk/"):
            path = "/residents/" + path.removeprefix("/ipsk/")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.send(400, "Invalid request size", "text/plain")
            return
        if length < 0:
            self.send(400, "Invalid request size", "text/plain")
            return
        if length > (portal_skin.UPLOAD_LIMIT if path.startswith("/settings/captive-portal/") else UPLOAD_LIMIT if path in ("/ca/extra", "/ca/sign") else 16384 if path == "/tools/wifi/save"
                     else 4096):
            self.send(413, "Request too large", "text/plain")
            return
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            form = parse_multipart(content_type, body)
        else:
            form = urllib.parse.parse_qs(body.decode(errors="replace"), keep_blank_values=path.startswith(("/settings/identity/", "/settings/captive-portal/")))
        if any(len(values) != 1 for values in form.values()):
            self.send(400, "Submit each form field once.", "text/plain")
            return
        if not secrets.compare_digest(str(form.get("csrf", [""])[0]), CSRF_TOKEN):
            self.send(403, "Invalid form token; reload the page and try again.", "text/plain")
            return
        if path in ("/settings/captive-portal/appearance/save", "/settings/captive-portal/content/save"):
            self.portal_skin_save(path.split("/")[3], form)
            return
        if path in ("/settings/identity/authentication/save", "/settings/identity/directory/save"):
            self.identity_save(path.split("/")[3], form)
            return
        if urllib.parse.urlsplit(self.path).path == "/settings/ipsk/access/save":
            self.access_policy_save(form)
            return
        if path == "/ca/extra":
            self.extra_ca_add(form)
            return
        if path == "/ca/sign":
            self.sign_request(form)
            return
        if m := re.fullmatch(r"/ca/extra/([0-9a-f]{64})/remove", path):
            enroll.save_extra_cas([c for c in enroll.load_extra_cas()
                                   if enroll.fingerprint(c) != m.group(1)])
            self.redirect("/tools/cas")
            return
        if path == "/tools/wifi/save":
            self.wifi_save(form)
            return
        if path == "/tools/wifi/delete":
            self.wifi_delete(form)
            return
        if path == "/residents/invite":
            label = str(form.get("label", [""])[0]).strip()
            if not os.environ.get("PORTAL_DB_HOST"):
                self.residents_page({}, error="Invitations require the MariaDB database used by Step CA.", section="invitations")
            else:
                try:
                    code = ipsk.create_invite(self.headers.get("X-Remote-User-Id", "Home Assistant administrator"), label)
                    self.residents_page({}, invite_code=code, section="invitations")
                except Exception as err:
                    self.residents_page({}, error=err, section="invitations", draft={"label": label[:100]})
            return
        if path == "/residents/qr/settings":
            try:
                options = saved_options()
                settings = dict(options.get("resident_onboarding") or {})
                for kind in ("guest", "setup"):
                    ssid = str(form.get(kind + "_ssid", [""])[0])
                    password = str(form.get(kind + "_psk", [""])[0])
                    if not ssid:
                        settings[kind + "_ssid"] = settings[kind + "_psk"] = ""
                    else:
                        password = password or str(settings.get(kind + "_psk") or "")
                        try:
                            ipsk.validate_wifi_credentials(ssid, password)
                        except ValueError as err:
                            raise guidance.FieldError(kind + ("_ssid" if not ssid or len(ssid.encode("utf-8")) > 32 else "_psk"), str(err)) from err
                        settings[kind + "_ssid"], settings[kind + "_psk"] = ssid, password
                if (settings.get("guest_ssid") and settings.get("setup_ssid")
                        and (settings["guest_ssid"], settings["guest_psk"])
                        == (settings["setup_ssid"], settings["setup_psk"])):
                    raise ValueError("Use different guest and setup credentials so guests can bypass registration.")
                options["resident_onboarding"] = settings
                supervisor("POST", "/addons/self/options", {"options": options})
                self.residents_page({"qr_saved": ["1"]}, section="join-codes/settings")
            except Exception as err:  # noqa: BLE001 - the authenticated panel explains the failure
                self.residents_page({}, error=err, section="join-codes/settings",
                                    draft={key: str(form.get(key, [""])[0])[:100] for key in ("guest_ssid", "setup_ssid")})
            return
        if path == "/residents/access/settings":
            access = ipsk.resident_access
            try:
                options = saved_options()
                settings = dict(options.get("resident_onboarding") or {})
                for key in access.BOOL_FIELDS:
                    settings[key] = form.get(key, [""])[0] == "1"
                for key in access.TEXT_FIELDS:
                    if key in form:
                        settings[key] = str(form[key][0]).strip()
                for key in access.SECRET_FIELDS:
                    settings[key] = str(form.get(key, [""])[0]) or settings.get(key, "")
                try:
                    settings["max_devices_per_resident"] = int(form.get("max_devices_per_resident", ["5"])[0])
                except ValueError as err:
                    raise guidance.FieldError("max_devices_per_resident", "Choose a device limit from 1 to 50.") from err
                access.validate_settings(settings)
                options["resident_onboarding"] = settings
                supervisor("POST", "/addons/self/options", {"options": options})
                access.SETTINGS_OVERRIDE = settings
                self.residents_page({"access_saved": ["1"]}, section="access")
            except Exception as err:
                draft = {key: str(form[key][0])[:512] for key in access.TEXT_FIELDS if key in form}
                draft.update({key: form.get(key, [""])[0] == "1" for key in access.BOOL_FIELDS})
                draft["max_devices_per_resident"] = str(form.get("max_devices_per_resident", ["5"])[0])[:8]
                kind = next((kind for kind, fields in identity_settings.FIELDS.items() if getattr(err, "field", "") in fields), None)
                if kind:
                    self.path = "/settings/identity/" + kind
                    self.identity_page(kind, error=err, draft={key: value for key, value in draft.items() if key in identity_settings.FIELDS[kind]})
                else:
                    self.residents_page({}, error=err, section="access", draft=draft)
            return
        if path == "/residents/ipsk/create":
            values = {key: str(items[0]).strip() for key, items in form.items() if items}
            try:
                name = values.get("name", "")
                network_id = values.get("network_id", "")
                try:
                    ssid_number = int(values.get("ssid_number", "-1"))
                except ValueError as err:
                    raise guidance.FieldError("ssid_number", "Choose an available Wi-Fi network (SSID).") from err
                try:
                    duration = int(values.get("duration_hours", "0"))
                except ValueError as err:
                    raise guidance.FieldError("duration_hours", "Enter a whole number of hours from 0 to 87,600.") from err
                # Spaces can be part of a Wi-Fi password.
                passphrase = str(form.get("passphrase", [""])[0])
                if not name or len(name) > 100 or not name.isprintable():
                    raise guidance.FieldError("name", "Enter a key name of 1 to 100 printable characters.")
                if duration < 0 or duration > 87600:
                    raise guidance.FieldError("duration_hours", "Choose a duration between 0 and 87,600 hours.")
                if passphrase and not (8 <= len(passphrase) <= 63 and passphrase.isascii()
                                       and passphrase.isprintable() or re.fullmatch(r"[0-9A-Fa-f]{64}", passphrase)):
                    raise guidance.FieldError("passphrase", "Passphrases must be 8–63 printable ASCII characters or 64 hexadecimal digits.")
                options = ipsk.get_options(network_id)
                networks = options.get("networks") or []
                ssids = options.get("ssids") or []
                if not any(str(item.get("id")) == network_id for item in networks):
                    raise guidance.FieldError("network_id", "Choose a network available in Home Assistant.")
                if not any(int(item.get("number", -1)) == ssid_number for item in ssids):
                    raise guidance.FieldError("ssid_number", "Choose an SSID available in Home Assistant.")
                for field, limit in (("user", 254), ("unit", 80)):
                    value = values.get(field, "")
                    if len(value) > limit or (value and not value.isprintable()):
                        raise guidance.FieldError(field, f"Use at most {limit} printable characters.")
                if not any(str(item.get("id")) == values.get("group_policy_id", "") for item in options.get("group_policies") or []):
                    raise guidance.FieldError("group_policy_id", "Choose a group policy available in this network.")
                created = ipsk.create_admin_ipsk(
                    name, network_id, ssid_number, passphrase, duration,
                    values.get("group_policy_id", ""), values.get("unit", ""), values.get("user", ""),
                )
                ident = str(created.get("id") or created.get("psk_group_id") or "")
                if not ident:
                    raise RuntimeError("Home Assistant did not return the new key ID.")
                try:
                    join_key = ipsk.ipsk_join_details(ident)
                except Exception as err:
                    self.residents_page({}, error=f"The key was created, but its QR is unavailable: {err}", created_key=ident, section="create")
                else:
                    self.residents_page({}, created_key=ident, join_key=join_key, section="create")
            except Exception as err:  # noqa: BLE001 - shown in the admin panel
                self.residents_page({"network": [values.get("network_id", "")]}, error=err, section="create",
                                    draft={key: values.get(key, "")[:254] for key in
                                           ("name", "user", "unit", "ssid_number", "group_policy_id", "duration_hours")})
            return
        if path == "/residents/invite/revoke":
            ipsk.revoke_invite(form.get("invite_id", [""])[0])
            self.redirect("/ipsk/invitations?invite_revoked=1")
            return
        if path == "/residents/ipsk/action":
            ident = str(form.get("ipsk_id", [""])[0])
            action = str(form.get("action", [""])[0])
            key_query = {key: [str(form[key][0])[:254]] for key in
                         ("key_id", "device_q", "device_sort", "device_page") if key in form}
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,191}", ident) or action not in ("reveal", "qr", "revoke", "delete"):
                self.residents_page({}, error="Choose a valid iPSK action.")
                return
            if action == "qr":
                try:
                    self.residents_page(key_query, join_key=ipsk.ipsk_join_details(ident))
                except Exception as err:
                    self.residents_page(key_query, error=str(err))
            elif action == "reveal":
                try:
                    self.residents_page(key_query, revealed=(ident, ipsk.reveal_ipsk(ident)))
                except Exception as err:
                    self.residents_page(key_query, error=str(err))
            else:
                ipsk.set_ipsk_status(ident, action)
                if os.environ.get("PORTAL_DB_HOST"):
                    with ipsk.db_connect() as conn, conn.cursor() as cursor:
                        cursor.execute("UPDATE stepca_resident_devices SET active = FALSE WHERE ipsk_id = %s", (ident,))
                        cursor.execute("UPDATE stepca_residents SET active = FALSE WHERE ipsk_id = %s", (ident,))
                        conn.commit()
                key_query["ipsk_" + action + "d"] = ["1"]
                self.redirect("/ipsk?" + urllib.parse.urlencode(key_query, doseq=True))
            return
        if path == "/tools/groups/save":
            self.group_save(form)
            return
        if m := re.fullmatch(r"/tools/groups/([a-z0-9][a-z0-9_-]{0,31})/delete", path):
            self.group_delete(m.group(1))
            return
        if path == "/tools/groups/apply":
            self.groups_apply()
            return
        if path == "/tools/restart":
            self.restart_addon()
            return
        if path == "/enroll/self":
            self.self_enroll(form)
            return
        if path == "/enroll/new":
            self.enroll_create(form)
            return
        if path in ("/issue", "/enroll/issue"):
            self.issue_direct(form)
            return
        if m := re.fullmatch(r"/enroll/([0-9a-f]{64})/cancel", path):
            LINKS.cancel(m.group(1))
            self.redirect(self.links_return(form))
            return
        if m := re.fullmatch(r"/enroll/([0-9a-f]{64})/delete", path):
            LINKS.delete([m.group(1)])
            self.redirect(self.links_return(form))
            return
        if path == "/enroll/links/delete":
            view = form.get("view", [""])[0]
            ids = [link["id"] for link in LINKS.all() if link["state"] in self.LINK_VIEWS.get(view, ())]
            n = LINKS.delete(ids)
            self.redirect(f"/enroll/links?{urllib.parse.urlencode({'links': view, 'deleted': n})}")
            return
        if path == "/certs/delete":
            status = form.get("status", [""])[0]
            if status not in DELETABLE or not db_enabled():
                self.redirect("/")
                return
            n = DELETED.add(c["serial"] for c in fetch_certs() if c["status"] == status)
            self.redirect(f"/?{urllib.parse.urlencode({'status': status, 'deleted': n})}")
            return
        if m := re.fullmatch(r"/cert/([0-9]{1,80})/(delete|restore)", path):
            serial, action = m.groups()
            if action == "restore":
                DELETED.restore(serial)
                self.redirect(f"/cert/{serial}?restored=1")
                return
            certs = fetch_certs(serial) if db_enabled() else []
            if certs and certs[0]["status"] in DELETABLE:
                DELETED.add([serial])
            back = form.get("back", [""])[0]
            self.redirect(f"/?{urllib.parse.urlencode({'status': back if back in DELETABLE else 'active', 'deleted': 1})}")
            return
        m = re.fullmatch(r"/cert/([0-9]+)/revoke", path)
        if not m or not SERIAL_RE.match(m.group(1)):
            self.send(404, "Not found", "text/plain")
            return
        serial = m.group(1)
        try:
            reason_code = int(form.get("reasonCode", ["0"])[0])
        except ValueError:
            reason_code = 0
        if reason_code not in REASONS:
            reason_code = 0
        reason = form.get("reason", [""])[0].strip()[:200]
        error = revoke(serial, reason_code, reason)
        if error:
            self.redirect(f"/cert/{serial}?error={urllib.parse.quote(error[:300])}")
        else:
            self.redirect(f"/cert/{serial}?revoked=1")

    # -- pages -----------------------------------------------------------------

    def no_db(self):
        return (
            '<div class="card">' + ui.empty_state(
                "certificate", "The certificate list needs MariaDB",
                "Set the add-on option <b>database</b> to <b>mariadb</b> and install the MariaDB add-on. "
                "CA certificates and the CRL are still available under "
                f'<a href="{esc(self.url("/ca"))}">Authority</a>.') + "</div>"
        )

    def health(self, counts, now, on_crl):
        """One row of tiles: the CA's validity, then what needs attention."""
        try:
            root, inter = cert_chain()
            until = min(root.not_valid_after_utc, inter.not_valid_after_utc)
            left = until - now
            kind, glyph = ("ok", "shield-check")
            if left.days < 0:
                kind, glyph = ("bad", "shield-alert-outline")
            elif left.days < 180:
                kind, glyph = ("warn", "shield-alert-outline")
            ca = (f'<a class="tile {kind}" href="{esc(self.url("/ca"))}"><span class="tile-icon">{ui.icon(glyph)}</span>'
                  f'<span class="tile-text"><span class="tile-primary">'
                  f'{"Authority expired" if left.days < 0 else "Authority valid"}</span>'
                  f'<span class="tile-secondary">until {until:%Y-%m-%d}</span></span></a>')
        except (OSError, ValueError):
            ca = (f'<div class="tile bad"><span class="tile-icon">{ui.icon("shield-alert-outline")}</span>'
                  '<span class="tile-text"><span class="tile-primary">Authority unavailable</span>'
                  '<span class="tile-secondary">see the add-on log</span></span></div>')

        def tile(kind, glyph, primary, secondary, status):
            href = esc(self.url("/") + "?" + urllib.parse.urlencode({"status": status}))
            return (f'<a class="tile {kind}" href="{href}"><span class="tile-icon">{ui.icon(glyph)}</span>'
                    f'<span class="tile-text"><span class="tile-primary">{primary}</span>'
                    f'<span class="tile-secondary">{secondary}</span></span></a>')

        soon = counts["expiring"]
        return (
            '<section class="card health" aria-label="Health">' + ca
            + tile("info", "certificate", f'{counts["active"]} active', "certificates in use", "active")
            + tile("warn" if soon else "neutral", "clock-alert-outline", f"{soon} expiring",
                   f"within {EXPIRING_DAYS} days", "expiring")
            + tile("neutral", "cancel", f'{counts["revoked"]} revoked',
                   "listed on the CRL" if on_crl == counts["revoked"] else f"{on_crl} on the CRL", "revoked")
            + "</section>"
        )

    def list_page(self, query):
        if not db_enabled():
            self.page("Certificates", self.no_db())
            return
        status = query.get("status", ["active"])[0]
        if status not in ("all", "active", "expiring", "expired", "revoked"):
            status = "active"
        search = query.get("q", [""])[0].strip()
        deleted = DELETED.all()
        every = fetch_certs()
        on_crl = sum(1 for c in every if c["status"] == "revoked")
        certs = [c for c in every if c["serial"] not in deleted]
        now = datetime.datetime.now(datetime.timezone.utc)
        counts = {s: sum(1 for c in certs if c["status"] == s) for s in ("active", "expired", "revoked")}
        counts["expiring"] = sum(1 for c in certs if expiring(c, now))
        counts["all"] = len(certs)
        if status == "expiring":
            shown = sorted((c for c in certs if expiring(c, now)), key=lambda c: c["not_after"])
        else:
            shown = [c for c in certs if status == "all" or c["status"] == status]
        if search:
            needle = search.lower()
            shown = [
                c for c in shown
                if needle in c["cn"].lower() or needle in c["serial"]
                or needle in c["subject"].lower() or any(needle in s.lower() for s in c["sans"])
            ]

        labels = {"active": "Active", "expiring": "Expiring", "expired": "Expired", "revoked": "Revoked", "all": "All"}
        filters = "".join(
            f'<a class="filter" href="{esc(self.url("/") + "?" + urllib.parse.urlencode({"status": s, "q": search}))}"'
            f'{" aria-current=true" if s == status else ""}>'
            f'{ui.icon("check") if s == status else ""}{labels[s]} <span class="count">{counts[s]}</span></a>'
            for s in labels
        )

        def row(c):
            soon = expiring(c, now)
            rel_class = "warn" if soon else "bad" if c["status"] == "expired" else ""
            expires = ui.when(c["not_after"], now).replace('class="rel"', f'class="rel {rel_class}"')
            haystack = " ".join([c["cn"], c["serial"], c["subject"], *c["sans"]]).lower()
            sans = ", ".join(c["sans"][:3]) + (f" +{len(c['sans']) - 3}" if len(c["sans"]) > 3 else "")
            return (
                f'<tr class="link-row" data-search="{esc(haystack)}">'
                f"<td><a class=\"row-link\" href=\"{esc(self.url('/cert/' + c['serial']))}\">"
                f"{esc(c['cn'] or '(no name)')}</a>"
                + (f'<span class="sub">{esc(sans)}</span>' if sans else "")
                + f'<span class="sub only-mobile">Expires {expires}</span></td>'
                f"<td>{status_chip(c, now)}</td>"
                f'<td class="hide-mobile nowrap">{expires}</td>'
                f'<td class="hide-mobile nowrap">{c["not_before"]:%Y-%m-%d}</td>'
                f'<td class="hide-mobile">{esc(c["ou"]) or "—"}'
                f'<span class="sub">{esc(c["provisioner"])}</span></td>'
                f'<td class="hide-mobile mono nowrap">{esc(c["serial"][:12])}{"…" if len(c["serial"]) > 12 else ""}</td>'
                f'<td class="actions">{delete_form(c)}</td></tr>'
            )

        def delete_form(c):
            if c["status"] not in DELETABLE:
                return ""
            return (f'<form method="post" action="{esc(self.url("/cert/" + c["serial"] + "/delete"))}" '
                    f'data-confirm="delete-cert-dialog" data-confirm-name="{esc(c["cn"] or "this certificate")}">'
                    f'{csrf}<input type="hidden" name="back" value="{esc(status)}">'
                    f'<button class="icon-btn" aria-label="Delete {esc(c["cn"] or "certificate")} from the list" '
                    f'title="Delete from the list">{ui.icon("delete-outline")}</button></form>')

        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'

        empty_titles = {"active": "No active certificates", "expiring": "Nothing expires soon",
                        "expired": "No expired certificates", "revoked": "No revoked certificates",
                        "all": "No certificates yet"}
        if shown:
            rows = "".join(row(c) for c in shown)
        elif search:
            rows = (f'<tr><td colspan="7">{ui.empty_state("magnify", "No certificates match", f"Nothing matches “{esc(search)}” here. Try All.")}</td></tr>')
        else:
            rows = (f'<tr><td colspan="7">{ui.empty_state("certificate", empty_titles[status], "Enroll a device to issue one." if status in ("active", "all") else "")}</td></tr>')
        rows += (f'<tr class="no-match" hidden><td colspan="7">'
                 f'{ui.empty_state("magnify", "No certificates match", "Try another name, alternative name, or serial.")}</td></tr>')
        notice = ""
        if "deleted" in query:
            n = query["deleted"][0]
            notice = ui.alert("success", "Revoked certificates stay on the CRL until they expire. "
                              "Open a deleted certificate by its serial to restore it.",
                              f"Deleted {esc(n)} certificate{'' if n == '1' else 's'} from the list")
        bar = ""
        if status in DELETABLE and counts[status]:
            n = counts[status]
            bar = (
                '<div class="list-bar"><span class="muted">'
                + ("Revoked certificates stay on the CRL until they expire, also when deleted here."
                   if status == "revoked" else "Expired certificates are no longer accepted anywhere.")
                + f'</span><form method="post" action="{esc(self.url("/certs/delete"))}" data-confirm="delete-all-dialog">'
                f'{csrf}<input type="hidden" name="status" value="{esc(status)}">'
                f'<button class="btn text danger">{ui.icon("delete-outline")}Delete all {n} {status}</button></form></div>'
                f'<dialog id="delete-all-dialog" aria-labelledby="delete-all-title">'
                f'<h2 id="delete-all-title">Delete all {n} {status} certificates from the list?</h2>'
                "<p>They are removed from this list only. "
                + ("They stay on the CRL, so they remain revoked. " if status == "revoked" else "")
                + "You can restore one by opening it by its serial.</p>"
                '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                '<button type="button" class="btn danger" data-confirm-yes>Delete</button></div></dialog>'
            )
        body = (
            notice + self.health(counts, now, on_crl)
            + '<div class="card">'
            f'<form class="list-tools" method="get" action="{esc(self.url("/"))}" role="search">'
            f'<input type="hidden" name="status" value="{esc(status)}">'
            f'<div class="search">{ui.icon("magnify")}'
            f'<input type="search" name="q" value="{esc(search)}" aria-label="Search certificates" '
            'placeholder="Search name, alternative name, or serial" data-filter-table="certs" autocomplete="off"></div>'
            f'<a class="btn" href="{esc(self.url("/enroll"))}">{ui.icon("plus")}Enroll device</a></form>'
            f'<nav class="filters" aria-label="Status">{filters}</nav>'
            + bar
            + '<div class="table-wrap"><table id="certs"><thead><tr><th>Name</th><th>Status</th>'
            '<th class="hide-mobile">Expires</th><th class="hide-mobile">Issued</th>'
            '<th class="hide-mobile">Group (OU)</th><th class="hide-mobile">Serial</th>'
            '<th><span class="visually-hidden">Actions</span></th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></div>"
            '<dialog id="delete-cert-dialog" aria-labelledby="delete-cert-title">'
            '<h2 id="delete-cert-title">Delete <span data-confirm-name>this certificate</span> from the list?</h2>'
            "<p>It is removed from this list only. A revoked certificate stays on the CRL until it expires.</p>"
            '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
            '<button type="button" class="btn danger" data-confirm-yes>Delete</button></div></dialog>'
        )
        self.page("Certificates", body)

    def detail_page(self, serial, query):
        if not db_enabled():
            self.page("Certificate", self.no_db(), back="/")
            return
        certs = fetch_certs(serial)
        if not certs:
            self.not_found("Certificate not found", "No certificate has this serial number.")
            return
        c = certs[0]
        now = datetime.datetime.now(datetime.timezone.utc)
        msg = ""
        if "error" in query:
            msg = ui.alert("error", esc(query["error"][0]), "Revocation failed")
        elif "revoked" in query:
            msg = ui.alert("success", "The CRL has been updated.", "Certificate revoked")
        elif "restored" in query:
            msg = ui.alert("success", "It is shown in the certificate list again.", "Certificate restored")
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        if serial in DELETED.all():
            msg += ui.alert(
                "info", "It is hidden from the certificate list. "
                f'<form method="post" action="{esc(self.url("/cert/" + serial + "/restore"))}" class="alert-action">'
                f'{csrf}<button class="btn text">Restore to the list</button></form>',
                "Deleted from the list")
        fingerprint = c["cert"].fingerprint(hashes.SHA256()).hex()
        details = [
            ("Subject", f'<span class="mono">{esc(c["subject"])}</span>', ""),
            ("Alternative names", esc(", ".join(c["sans"])) or '<span class="muted">None</span>', ""),
            ("Issuer", f'<span class="mono">{esc(c["issuer"])}</span>', ""),
            ("Valid from", esc(fmt_time(c["not_before"])), ""),
            ("Valid until", esc(fmt_time(c["not_after"])), ""),
            ("Provisioner", esc(c["provisioner"] + (f' ({c["provisioner_type"]})' if c["provisioner_type"] else "")), ""),
            ("Serial", f'<span class="mono">{esc(c["serial"])}</span>', ui.copy_button(c["serial"], "serial")),
            ("SHA-256", f'<span class="mono">{esc(fingerprint)}</span>', ui.copy_button(fingerprint, "SHA-256 fingerprint")),
        ]
        revoked_note = ""
        if c["revoked"]:
            r = c["revoked"]
            code = r.get("ReasonCode", 0)
            reason = f"{REASONS.get(code, code)}" + (f' — {r["Reason"]}' if r.get("Reason") else "")
            details += [("Revoked at", esc(r.get("RevokedAt", "")), ""), ("Reason", esc(reason), "")]
            revoked_note = ui.alert("error", f"Reason: {esc(reason)}. Relying systems reject it once they load the CRL.",
                                    "This certificate is revoked")
        dl = "".join(ui.kv_row(k, v, b) for k, v, b in details)

        span = (c["not_after"] - c["not_before"]).total_seconds() or 1
        done = min(max((now - c["not_before"]).total_seconds() / span, 0), 1)
        bar = ("var(--secondary-text-color)" if c["status"] == "revoked" else "var(--error-color)"
               if c["status"] == "expired" else "var(--warning-color)" if expiring(c, now) else "var(--primary-color)")
        ends = "Expired" if c["not_after"] < now else "Expires"
        validity = (
            f'<div class="validity" style="--bar:{bar}"><div class="validity-track" role="img" '
            f'aria-label="{round(done * 100)}% of the validity period has passed">'
            f'<div class="validity-fill" style="width:{done * 100:.1f}%"></div>'
            + (f'<div class="validity-now" style="left:{done * 100:.1f}%"></div>' if 0 < done < 1 else "")
            + f'</div><div class="validity-labels"><span>Issued {c["not_before"]:%Y-%m-%d}</span>'
            f'<span>{ends} {ui.when(c["not_after"], now)}</span></div></div>'
        )

        revoke_form = ""
        if c["status"] != "revoked":
            options = "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in REASONS.items())
            name = esc(c["cn"] or "this certificate")
            revoke_form = (
                '<div class="card danger-zone"><div class="card-header"><h2>Revoke certificate</h2></div>'
                '<div class="card-content"><p class="muted">Revocation cannot be undone. Relying systems such as '
                "RADIUS must load the updated CRL to reject the certificate.</p>"
                f'<form class="revoke-form" method="post" action="{esc(self.url("/cert/" + serial + "/revoke"))}" '
                'data-confirm="revoke-dialog">'
                f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
                f'<div class="field"><label for="reasonCode">Reason</label><select id="reasonCode" name="reasonCode">{options}</select></div>'
                '<div class="field"><label for="reason">Note (optional)</label>'
                '<input id="reason" name="reason" maxlength="200" placeholder="e.g. phone lost"></div>'
                '<button class="btn danger">Revoke</button></form></div></div>'
                '<dialog id="revoke-dialog" aria-labelledby="revoke-title">'
                f'<h2 id="revoke-title">Revoke {name}?</h2>'
                "<p>This cannot be undone. The CRL is regenerated, and relying systems such as RADIUS "
                "reject the certificate once they load it.</p>"
                '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                '<button type="button" class="btn danger" data-confirm-yes>Revoke</button></div></dialog>'
            )
        delete_card = ""
        if c["status"] in DELETABLE and serial not in DELETED.all():
            delete_card = (
                '<div class="card"><div class="card-header"><h2>Delete from the list</h2>'
                '<p class="muted">Removes this certificate from the certificate list. '
                + ("It stays on the CRL until it expires, so it remains revoked. " if c["status"] == "revoked" else "")
                + "You can restore it here later.</p></div>"
                f'<div class="card-actions"><form method="post" action="{esc(self.url("/cert/" + serial + "/delete"))}" '
                'data-confirm="delete-cert-dialog">'
                f'{csrf}<input type="hidden" name="back" value="{esc(c["status"])}">'
                f'<button class="btn text danger">{ui.icon("delete-outline")}Delete</button></form></div></div>'
                '<dialog id="delete-cert-dialog" aria-labelledby="delete-cert-title">'
                f'<h2 id="delete-cert-title">Delete {esc(c["cn"] or "this certificate")} from the list?</h2>'
                "<p>" + ("It stays on the CRL, so it remains revoked. " if c["status"] == "revoked" else "")
                + "You can restore it from this page.</p>"
                '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                '<button type="button" class="btn danger" data-confirm-yes>Delete</button></div></dialog>'
            )
        body = (
            msg + revoked_note
            + '<div class="card"><div class="cert-head">'
            f"<h2>{esc(c['cn'] or '(no name)')}</h2>"
            f'<div class="cert-meta">{status_chip(c, now)}'
            + (f'<span class="muted">Issued by provisioner {esc(c["provisioner"])}</span>' if c["provisioner"] else "")
            + f"</div>{validity}</div>"
            f'<div class="card-actions"><a class="btn text" href="{esc(self.url("/cert/" + serial + ".pem"))}">'
            f'{ui.icon("download")}Download PEM</a></div></div>'
            '<div class="card"><div class="card-header"><h2>Details</h2></div>'
            f'<dl class="card-content flush rows">{dl}</dl></div>'
            + revoke_form + delete_card
        )
        self.page(c["cn"] or "Certificate", body, back="/", narrow=True, heading="Certificate")

    def cert_pem(self, serial):
        if not db_enabled() or not SERIAL_RE.match(serial):
            self.not_found()
            return
        certs = fetch_certs(serial)
        if not certs:
            self.not_found("Certificate not found", "No certificate has this serial number.")
            return
        pem = certs[0]["cert"].public_bytes(serialization.Encoding.PEM)
        self.download(pem, f"{serial}.pem", "application/x-pem-file")

    # -- enrollment flow shared by the public pages and the panel -------------

    def enroll_prefix(self):
        """URL prefix under which /<token>/file/<id> and /<token>/root_ca.crt are served."""
        return self.url("/enroll/self")

    def insecure_note(self):
        """Browsers flag downloads from a Home Assistant opened over plain HTTP."""
        if self.headers.get("X-Forwarded-Proto", "http") != "http":
            return ""
        base_url = default_base_url(self.headers)
        https = (f' or open Home Assistant at <a href="{esc(base_url)}">{esc(base_url)}</a>'
                 if base_url.startswith("https://") else "")
        return ui.alert("info", "Home Assistant is open over HTTP, so your browser may warn that "
                        f"the download is insecure. Choose <b>Keep</b>{https}.")

    def gone(self):
        self.page("Link not valid", '<div class="card">' + ui.empty_state(
            "link-variant", "This enrollment link is not valid",
            "It may have expired, been used already, or been cancelled. Ask your "
            "Home Assistant administrator for a new one.") + "</div>", 404)

    def enroll_file(self, token, sub):
        if sub == "root_ca.crt":
            der = cert_chain()[0].public_bytes(serialization.Encoding.DER)
            self.download(der, "root_ca.crt", "application/x-x509-ca-cert")
            return
        entry = DOWNLOADS.get(enroll._hash(token), sub[len("file/"):])
        if entry is None:
            self.page("Download expired", '<div class="card">' + ui.empty_state(
                "clock-alert-outline", "This download has expired",
                "Start the enrollment again to get a new one.") + "</div>", 404)
            return
        data, filename, content_type = entry
        self.download(data, filename, content_type)

    def form_page(self, action, link, error="", cn="", hidden="", extra="", panel=False):
        apple = bool(APPLE_UA_RE.search(self.headers.get("User-Agent", "")))
        cn = link["cn"] or cn
        if link["cn"]:
            name = (f'<div class="field"><span class="label">Certificate name</span>'
                    f'<span class="mono">{esc(link["cn"])}</span></div>'
                    f'<input type="hidden" name="cn" value="{esc(link["cn"])}">')
        else:
            name = ('<div class="field"><label for="cn">Certificate name</label>'
                    f'<input id="cn" name="cn" maxlength="64" required value="{esc(cn)}" '
                    'placeholder="e.g. josh-iphone" autocapitalize="off" autocorrect="off">'
                    '<p class="hint">Letters, digits, spaces, and . _ @ - only.</p></div>')
        if extra:
            extra = f'<div class="field">{extra}</div>' if 'class="field"' not in extra else extra
        wifi = ""
        if link["wifi"] and wifi_enabled():
            wifi = f" It also sets up Wi-Fi {wifi_names()}."
        body = (
            (ui.alert("error", esc(error)) if error else "")
            + f'<form class="card" method="post" action="{esc(action)}">'
            + ('<div class="card-header"><h2>Enroll this computer</h2>' if panel else '<div class="card-header"><h1>Get a certificate</h1>')
            + f'<p class="muted">From {esc(CA_NAME)}. Pick the kind of device you are enrolling.</p></div>'
            '<div class="card-content">' + hidden + '<input type="hidden" name="touch" data-touch>' + name + extra
            + '<fieldset class="field"><legend class="label">Device</legend><div class="choices">'
            f'<label class="choice"><input type="radio" name="kind" value="apple"{" checked" if apple else ""}>'
            f'<span class="choice-icon">{ui.icon("apple")}</span><span>'
            '<span class="choice-title">iPhone, iPad, or Mac</span><span class="muted">Installs a profile '
            f"that sets up the certificate on your device.{wifi}</span></span></label>"
            f'<label class="choice"><input type="radio" name="kind" value="p12"{"" if apple else " checked"}>'
            f'<span class="choice-icon">{ui.icon("cellphone")}</span><span>'
            '<span class="choice-title">Other device</span><span class="muted">Android, Windows, Linux, and others. '
            "Downloads a password-protected certificate file (.p12). Installation steps follow."
            "</span></span></label></div></fieldset></div>"
            '<div class="card-actions"><button class="btn">Continue</button></div></form>'
        )
        self.page("Enroll this computer" if panel else "Enroll device", body, back=None if panel else "/enroll", narrow=True)

    @staticmethod
    def update_note(update_url, ios):
        """How to install this profile again later, from its update link."""
        if ios:
            return ui.alert("info", "The profile also adds an <b>Update</b> icon to the Home Screen. Tap it "
                            "to install the newest profile, for example to renew the certificate or pick up "
                            "Wi-Fi changes.", "Updates")
        return ui.alert("info", "To install the newest profile later, for example to renew the certificate "
                        "or pick up Wi-Fi changes, open this link on this device. Bookmark it; it works "
                        f'for 400 days after each install.<br><span class="mono">{esc(update_url)}</span>'
                        + ui.copy_button(update_url, "update link"), "Updates")

    def update_page(self, action, link, error=""):
        """Page of an update link: install the newest profile for its certificate."""
        wifi = f" and Wi-Fi {wifi_names()}" if link["wifi"] and wifi_enabled() else ""
        body = (
            (ui.alert("error", esc(error)) if error else "")
            + f'<form class="card" method="post" action="{esc(action)}">'
            '<input type="hidden" name="kind" value="apple"><input type="hidden" name="touch" data-touch>'
            f'<div class="card-header"><h1>Update the profile</h1>'
            f'<p class="muted">Installs the newest profile from {esc(CA_NAME)} for <b>{esc(link["cn"])}</b>, '
            f"with a new certificate{wifi}. It replaces the one installed now.</p></div>"
            '<div class="card-actions"><button class="btn">Continue</button></div></form>'
        )
        self.page("Update the profile", body, narrow=True)

    @staticmethod
    def name_error(cn):
        """Why the certificate name chosen on the device form cannot be used, or ""."""
        if not enroll.valid_cn(cn):
            return "Enter a certificate name using letters, digits, spaces, and . _ @ - (up to 64 characters)."
        return ""

    def is_ios(self, form):
        """Whether the form came from an iPhone or iPad (iPadOS Safari says it is a Mac)."""
        return bool(IOS_UA_RE.search(self.headers.get("User-Agent", ""))) or form.get("touch", [""])[0] == "1"

    def apple_result(self, token, link_id, link, cn, ios=False):
        """ios: the profile also gets a Home Screen icon that installs the newest profile."""
        challenge = LINKS.new_challenge(link_id, cn)
        if challenge is None:
            self.gone()
            return
        update_url = update_link(token, link_id, link, cn)
        try:
            data = profile_for(cn, challenge, link["base_url"], link["wifi"] and wifi_enabled(),
                               link.get("sans") or (), link.get("group", ""),
                               update_url if ios else None, platform="ios" if ios else "macos")
        except enroll.UnsupportedWifiPlatform as err:
            self.page("Wi-Fi is not available on this device", ui.alert(
                "error", esc(err) + " Ask your administrator for a profile without the carrier network.",
                "This network requires an iPhone or iPad"), 400)
            return
        except (RuntimeError, OSError, ValueError) as err:
            print(f"Could not build profile: {err}", flush=True)
            self.page("Error", ui.alert("error", "Ask your administrator to check the add-on log.",
                                        "The profile could not be created"), 500)
            return
        download = DOWNLOADS.add(link_id, data, f"{safe_filename(cn)}.mobileconfig",
                                 "application/x-apple-aspen-config")
        href = f"{self.enroll_prefix()}/{token}/file/{download}"
        body = (
            self.insecure_note()
            + '<div class="card"><div class="card-header"><h1>Install the profile</h1>'
            f'<p class="muted">For the certificate <b>{esc(cn)}</b>.</p></div>'
            '<div class="card-content"><ol class="steps">'
            f'<li>Tap <b>Download profile</b> and choose <b>Allow</b>.<p class="step-action">'
            f'<a class="btn" href="{esc(href)}">{ui.icon("download")}Download profile</a></p></li>'
            "<li>iPhone or iPad: open <b>Settings</b>, tap <b>Profile Downloaded</b> near the top, "
            "then <b>Install</b>. Mac: open <b>System Settings &rsaquo; General &rsaquo; Device "
            "Management</b> and double-click the profile.</li>"
            "<li>Enter your device passcode and confirm. The device creates its key and requests "
            "the certificate. This needs a connection to Home Assistant.</li>"
            "</ol></div></div>"
            + ui.alert("info", "The profile works once and must be installed within an hour. If the "
                       "install fails, start the enrollment again to get a fresh profile.")
            + self.update_note(update_url, ios)
        )
        self.page("Install the profile", body, back="/enroll/self", narrow=True)

    def p12_result(self, token, link_id, link, cn):
        if not LINKS.claim(link_id, cn, ".p12 download"):
            self.gone()
            return
        try:
            data, password, _ = enroll.issue_p12(cn, ca_url=CA_URL, root_cert=ROOT_CERT,
                                                 extra_cas=enroll.load_extra_cas(),
                                                 sans=link.get("sans") or (),
                                                 **group_issue_args(link.get("group", "")))
        except (RuntimeError, OSError, subprocess.SubprocessError) as err:
            LINKS.release(link_id)
            print(f"Could not issue certificate for {cn!r}: {err}", flush=True)
            self.page("Error", ui.alert("error", "Ask your administrator to check the add-on log.",
                                        "The certificate could not be issued"), 500)
            return
        download = DOWNLOADS.add(link_id, data, f"{safe_filename(cn)}.p12", "application/x-pkcs12")
        bundle = DOWNLOADS.add(link_id, full_bundle(), "ca-bundle.pem", "application/x-pem-file")
        radius = ", including the Wi-Fi (RADIUS) server CA" if enroll.load_extra_cas() else ""
        body = (
            self.insecure_note()
            + '<div class="card"><div class="card-header"><h1>Your certificate is ready</h1>'
            f'<p class="muted">For <b>{esc(cn)}</b>.</p></div><div class="card-content">'
            '<div class="field"><span class="label">Password for the .p12 file</span>'
            + ui.copy_field(password, "password", "secret") + "</div>"
            + ui.alert("warning", "Write the password down now. It is not shown again.")
            + '<ol class="steps steps-gap">'
            f'<li>Download the file. It is available for 10 minutes.<p class="step-action">'
            f'<a class="btn" href="{esc(f"{self.enroll_prefix()}/{token}/file/{download}")}">'
            f'{ui.icon("download")}Download {esc(safe_filename(cn))}.p12</a></p></li>'
            "<li>Install it. Android: Settings &rsaquo; Security &rsaquo; Encryption &amp; credentials "
            "&rsaquo; Install a certificate. Windows: double-click the file, choose <b>Current User</b>, and "
            "keep the default store choices. macOS: open it in Keychain Access.</li>"
            "<li>If your device asks for a CA certificate, use "
            f'<a href="{esc(f"{self.enroll_prefix()}/{token}/root_ca.crt")}">the root CA certificate</a>, or '
            f'<a href="{esc(f"{self.enroll_prefix()}/{token}/file/{bundle}")}">ca-bundle.pem</a> '
            f"with all CA certificates{radius}.</li></ol></div></div>"
            + wifi_help()
        )
        self.page(f"Certificate for {cn}", body, back="/enroll/self", narrow=True)

    # -- enrollment (admin) ------------------------------------------------------

    def self_enroll_page(self, error="", cn="", sans="", group="", email=""):
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        self.form_page(self.url("/enroll/self"), {"cn": "", "wifi": wifi_enabled()}, error, cn, csrf,
                       email_input("self-email", email) + group_select("self-group", group)
                       + sans_input("self-sans", sans), panel=True)

    def self_enroll(self, form):
        """Enroll the computer the panel is open on (e.g. a Mac or Windows PC)."""
        cn = form.get("cn", [""])[0].strip()
        sans_text = form.get("sans", [""])[0].strip()
        email_text = form.get("email", [""])[0].strip()
        group_text = form.get("group", [""])[0]
        if error := self.name_error(cn):
            self.self_enroll_page(error, cn, sans_text, group_text, email_text)
            return
        try:
            sans = form_sans(form)
            group = parse_group(group_text)
            check_group_email(group, sans)
        except ValueError as err:
            self.self_enroll_page(str(err), cn, sans_text, group_text, email_text)
            return
        base_url = default_base_url(self.headers)
        if not base_url:
            self.self_enroll_page("Set enrollment.public_url in the add-on options first.", cn, sans_text, group_text, email_text)
            return
        who = self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or ""
        token = LINKS.create(label="This device (panel)", cn=cn, base_url=base_url,
                             wifi=wifi_enabled(), hours=1, created_by=who, sans=sans, group=group)
        link_id, link = LINKS.get(token)
        if form.get("kind", [""])[0] == "apple":
            self.apple_result(token, link_id, link, cn, self.is_ios(form))
        else:
            self.p12_result(token, link_id, link, cn)

    LINK_VIEWS = {"waiting": ("pending",), "used": ("issued",), "updates": ("update",),
                  "ended": ("expired", "cancelled"), "all": ("pending", "issued", "update", "expired", "cancelled")}
    LINKS_PER_PAGE = 10

    def links_return(self, form):
        """Where to go back to after acting on a link: the view and page it was done from."""
        view = form.get("view", [""])[0]
        page = form.get("page", [""])[0]
        params = {"links": view if view in self.LINK_VIEWS else "waiting"}
        if page.isdigit() and page != "1":
            params["page"] = page
        return "/enroll/links?" + urllib.parse.urlencode(params)

    def enroll_page(self):
        tasks = (("new-link", "/enroll/new", "New one-time link", "link-variant",
                  "Create a link and QR code for a phone, tablet or someone else's device."),
                 ("links", "/enroll/links", "Enrollment links", "link-variant",
                  "Review, cancel and delete existing enrollment links."),
                 ("self-enrollment", "/enroll/self", "Enroll this computer", "laptop",
                  "Install a certificate on the Mac or Windows PC you are using."),
                 ("issue-certificate", "/enroll/issue", "Issue a certificate", "key-variant",
                  "Create a password-protected .p12 file to install on another device."))
        rows = "".join(
            f'<a class="row settings-row" id="{anchor}" data-enroll-task href="{esc(self.url(path))}">'
            f'<span class="row-icon">{ui.icon(glyph)}</span><span class="row-text">'
            f'<span class="row-title">{esc(title)}</span><span class="row-sub">{esc(description)}</span>'
            f'</span>{ui.icon("chevron-right")}</a>'
            for anchor, path, title, glyph, description in tasks
        )
        body = (
            '<div class="page-head"><h2>Enrollment</h2></div>'
            '<p class="settings-intro">Choose an enrollment task. Each opens its own page.</p>'
            f'<nav class="card" aria-label="Enrollment tasks">{rows}</nav>'
            f'<p><a class="btn text" href="{esc(self.url("/settings/enrollment"))}">'
            f'{ui.icon("cog")}Enrollment &amp; Wi-Fi settings</a></p>'
        )
        self.page("Enrollment", body, narrow=True)

    def enroll_new_page(self, error="", draft=None):
        base_url, base_source = detect_base_url(self.headers)
        _, signer_html = signer_status()
        def value(name, default=""):
            return str((draft or {}).get(name, [default])[0])[:2000]
        base_url = value("base_url", base_url)
        wifi_opt = ""
        if wifi_enabled():
            checked = draft is None or value("wifi") == "1"
            wifi_opt = (
                '<div class="field"><label class="check"><input type="checkbox" name="wifi" value="1"'
                + (' checked' if checked else '')
                + f'>Apple profiles also configure Wi-Fi {wifi_names()}</label></div>'
            )
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        advanced_open = " open" if error or not base_url.startswith("https://") else ""
        body = (
            (ui.alert("error", esc(error), "The link was not created") if error else "")
            +
            f'<form class="card" id="new-link" method="post" action="{esc(self.url("/enroll/new"))}">{csrf}'
            '<div class="card-header"><h2>New one-time link</h2>'
            '<p class="muted">A link and QR code for one device. On an iPhone, iPad, or Mac it installs a signed '
            "profile, so the device creates its own key and gets its certificate over SCEP. Other devices get a "
            "password-protected .p12 file with the full CA chain. No MDM is needed.</p></div>"
            f'<div class="inline-alert">{signer_html}</div>'
            '<div class="card-content"><div class="field-row">'
            f'<div class="field"><label for="label">Label</label><input id="label" name="label" maxlength="64" value="{esc(value("label"))}" '
            'placeholder="e.g. Josh&#39;s iPhone"></div>'
            '<div class="field"><label for="cn">Certificate name (CN)</label>'
            '<input id="cn" name="cn" maxlength="64" '
            f'autocapitalize="off" value="{esc(value("cn"))}" placeholder="Chosen on the device"></div></div>'
            + email_input("email", value("email"))
            + group_select("group", value("group"), hint="The certificate gets this group&#39;s OU and lifetime.")
            + "</div>"
            f'<details class="expand"{advanced_open}><summary><span class="summary-text">'
            '<span class="summary-title">More options</span>'
            f'<span class="summary-sub">Other alternative names, Home Assistant URL, validity'
            f'{", Wi-Fi" if wifi_enabled() else ""}</span></span>{ui.icon("chevron-down", "chev")}</summary>'
            '<div class="expand-body">'
            + sans_input("sans", value("sans"))
            + '<div class="field"><label for="base">Home Assistant URL the device will use</label>'
            f'<input id="base" name="base_url" type="url" required value="{esc(base_url)}" '
            'placeholder="https://home.example.com">'
            + base_url_hint(base_url, base_source) + "</div>"
            '<div class="field"><label for="hours">Valid for (hours)</label>'
            f'<input id="hours" name="hours" type="number" min="1" max="168" value="{esc(value("hours", str(ENROLL_LINK_HOURS)))}" '
            'class="input-short"></div>'
            + wifi_opt + "</div></details>"
            f'<div class="card-actions"><button class="btn">{ui.icon("qrcode")}Create link</button></div></form>'
        )
        self.page("New one-time link", body, narrow=True)

    def enrollment_links_page(self, query=None):
        query = query or {}
        notice = ""
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        now = datetime.datetime.now(datetime.timezone.utc)
        links = LINKS.all()
        view = query.get("links", ["waiting"])[0]
        if view not in self.LINK_VIEWS:
            view = "waiting"
        counts = {v: sum(link["state"] in states for link in links) for v, states in self.LINK_VIEWS.items()}
        shown = [link for link in links if link["state"] in self.LINK_VIEWS[view]]
        pages = max(1, -(-len(shown) // self.LINKS_PER_PAGE))
        try:
            page = min(max(int(query.get("page", ["1"])[0]), 1), pages)
        except ValueError:
            page = 1
        shown = shown[(page - 1) * self.LINKS_PER_PAGE:page * self.LINKS_PER_PAGE]
        where = (f'<input type="hidden" name="view" value="{view}">'
                 f'<input type="hidden" name="page" value="{page}">')
        rows = ""
        for link in shown:
            state = link["state"]
            kind = {"pending": "info", "issued": "ok", "update": "ok", "expired": "neutral"}.get(state, "bad")
            name = link["label"] or link["cn"] or "this link"
            if state in ("pending", "update"):
                cancel = (
                    f'<form method="post" action="{esc(self.url("/enroll/" + link["id"] + "/cancel"))}">'
                    f'{csrf}{where}<button class="btn text danger">Cancel</button></form>'
                )
            else:
                cancel = (
                    f'<form method="post" action="{esc(self.url("/enroll/" + link["id"] + "/delete"))}" '
                    f'data-confirm="delete-link-dialog" data-confirm-name="{esc(name)}">{csrf}{where}'
                    f'<button class="icon-btn" aria-label="Delete {esc(name)}" title="Delete">'
                    f'{ui.icon("delete-outline")}</button></form>'
                )
            expires = datetime.datetime.fromtimestamp(link["expires"], datetime.timezone.utc)
            rows += (
                f"<tr><td>{esc(link['label'] or 'Untitled link')}"
                + (f'<span class="sub">{esc(link["created_by"])}</span>' if link["created_by"] else "")
                + f"</td><td>{esc(link['issued_cn'] or link['cn'] or 'Chosen on the device')}"
                + (f'<span class="sub">{esc(", ".join(link["sans"]))}</span>' if link.get("sans") else "")
                + (f'<span class="sub">Group {esc(link["group"])}</span>' if link.get("group") else "")
                + (f'<span class="sub">{esc(link["method"])}</span>' if link["method"] else "")
                + f"</td><td>{ui.chip(kind, state.title())}</td>"
                f'<td class="hide-mobile nowrap">{ui.when(expires, now)}</td>'
                f'<td class="actions">{cancel}</td></tr>'
            )
        empty = {"waiting": ("No links waiting", "Links you create appear here until they are used or expire."),
                 "used": ("No used links", "Links appear here once a device has enrolled."),
                 "updates": ("No update links", "An iPhone or iPad that installs its profile gets an Update "
                             "icon; its link appears here, and cancelling it turns the icon off."),
                 "ended": ("No expired or cancelled links", ""),
                 "all": ("No enrollment links yet", "Links you create appear here.")}[view]
        rows = rows or (f'<tr><td colspan="5">{ui.empty_state("link-variant", *empty)}</td></tr>')
        labels = {"waiting": "Waiting", "used": "Used", "updates": "Update links",
                  "ended": "Expired or cancelled", "all": "All"}
        link_filters = "".join(
            f'<a class="filter" href="{esc(self.url("/enroll/links") + "?" + urllib.parse.urlencode({"links": v}))}"'
            f'{" aria-current=true" if v == view else ""}>'
            f'{ui.icon("check") if v == view else ""}{labels[v]} <span class="count">{counts[v]}</span></a>'
            for v in labels
        )
        if "deleted" in query:
            n = query["deleted"][0]
            notice += ui.alert("success", "", f"Deleted {esc(n)} link{'' if n == '1' else 's'}")
        bar = ""
        if view in ("used", "ended") and counts[view]:
            n = counts[view]
            what = "used" if view == "used" else "expired or cancelled"
            bar = (
                f'<div class="list-bar"><span class="muted">Deleting a link does not affect its certificate.</span>'
                f'<form method="post" action="{esc(self.url("/enroll/links/delete"))}" data-confirm="delete-links-dialog">'
                f'{csrf}<input type="hidden" name="view" value="{view}">'
                f'<button class="btn text danger">{ui.icon("delete-outline")}Delete all {n} {what}</button></form></div>'
                '<dialog id="delete-links-dialog" aria-labelledby="delete-links-title">'
                f'<h2 id="delete-links-title">Delete all {n} {what} links?</h2>'
                "<p>Certificates issued through them are not affected.</p>"
                '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                '<button type="button" class="btn danger" data-confirm-yes>Delete</button></div></dialog>'
            )
        pager = ""
        if pages > 1:
            def page_link(n, icon, label):
                if n < 1 or n > pages:
                    return f'<span class="icon-btn" aria-disabled="true">{ui.icon(icon)}</span>'
                href = self.url("/enroll/links") + "?" + urllib.parse.urlencode({"links": view, "page": n})
                return f'<a class="icon-btn" href="{esc(href)}" aria-label="{label}" title="{label}">{ui.icon(icon)}</a>'
            pager = (
                '<nav class="pager" aria-label="Pages">'
                + page_link(page - 1, "chevron-left", "Previous page")
                + f"<span>Page {page} of {pages}</span>"
                + page_link(page + 1, "chevron-right", "Next page") + "</nav>"
            )
        body = (
            notice + '<div class="card" id="links"><div class="card-header">'
            '<h2>Enrollment links</h2><p class="muted">Manage waiting, used and update links. '
            'Cancelling a link prevents its use; deleting a link leaves its certificate unchanged.</p>'
            f'<a class="btn" href="{esc(self.url("/enroll/new"))}">{ui.icon("plus")}New one-time link</a></div>'
            f'<nav class="filters" aria-label="Link status">{link_filters}</nav>'
            + bar + '<div class="table-wrap"><table><thead><tr>'
            '<th>Label</th><th>Certificate</th><th>Status</th><th class="hide-mobile">Expires</th>'
            '<th><span class="visually-hidden">Actions</span></th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>{pager}</div>'
            '<dialog id="delete-link-dialog" aria-labelledby="delete-link-title">'
            '<h2 id="delete-link-title">Delete <span data-confirm-name></span>?</h2>'
            '<p>The link is removed from the list. Its certificate is not affected.</p>'
            '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
            '<button type="button" class="btn danger" data-confirm-yes>Delete</button></div></dialog>'
        )
        self.page("Enrollment links", body)

    def enroll_issue_page(self, error="", draft=None):
        def value(name):
            return str((draft or {}).get(name, [""])[0])[:2000]
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        body = (
            (ui.alert("error", esc(error), "Nothing was issued") if error else "")
            +
            f'<form class="card" id="issue-certificate" method="post" action="{esc(self.url("/enroll/issue"))}">{csrf}'
            '<div class="card-header"><h2>Issue a certificate now</h2>'
            '<p class="muted">Creates the key here and gives you a .p12 file to hand over.</p></div>'
            '<div class="card-content"><div class="field"><label for="issue-cn">Certificate name (CN)</label>'
            f'<input id="issue-cn" name="cn" maxlength="64" required value="{esc(value("cn"))}" autocapitalize="off" placeholder="e.g. printer"></div>'
            + email_input("issue-email", value("email")) + group_select("issue-group", value("group")) + sans_input("issue-sans", value("sans")) + "</div>"
            + f'<div class="card-actions"><button class="btn text">{ui.icon("key-variant")}Issue .p12</button></div></form>'
        )
        self.page("Issue a certificate", body, narrow=True)

    def enroll_create(self, form):
        def field(name):
            return form.get(name, [""])[0].strip()
        label, cn = field("label")[:64], field("cn")
        base_url = enroll.normalize_base_url(field("base_url"))
        try:
            hours = min(max(int(field("hours") or ENROLL_LINK_HOURS), 1), 168)
        except ValueError:
            hours = ENROLL_LINK_HOURS
        error = ""
        try:
            group = parse_group(field("group"))
        except ValueError as err:
            group, error = "", str(err)
        if not error and cn and not enroll.valid_cn(cn):
            error = "The certificate name may use letters, digits, spaces, and . _ @ - (up to 64)."
        elif not error and not base_url:
            error = "Enter the Home Assistant URL as scheme and host only, e.g. https://home.example.com."
        sans = []
        if not error:
            try:
                sans = form_sans(form)
                check_group_email(group, sans)
            except ValueError as err:
                error = str(err)
        if error:
            self.enroll_new_page(error, form)
            return
        who = self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or ""
        token = LINKS.create(label=label, cn=cn, base_url=base_url, wifi=field("wifi") == "1" and wifi_enabled(),
                             hours=hours, created_by=who, sans=sans, group=group)
        link = f"{base_url}{enroll.PUBLIC_BASE}/enroll/{token}"
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
        body = (
            '<div class="card result"><div class="card-header"><h2>'
            f"{esc(label) if label else 'Enrollment link'}</h2>"
            '<p class="muted">Scan with the device camera, or open the link in its browser.</p></div>'
            f'<div class="card-content"><div class="qr">{qr_svg(link)}</div>'
            + ui.copy_field(link, "link")
            + f'<p class="muted">One certificate{" named <b>" + esc(cn) + "</b>" if cn else ""}'
            f'{" in the group <b>" + esc(group) + "</b>" if group else ""}. '
            f"Valid for {hours} hour{'s' if hours != 1 else ''}, until {ui.when(expires)}.</p></div></div>"
            + ui.alert("warning", "Anyone with this link can enroll a device, so share it only with the device "
                       "owner. It is not shown again.", "Shown only once")
        )
        body += (f'<p><a class="btn text" href="{esc(self.url("/enroll/links"))}">Manage enrollment links</a></p>')
        self.page("Enrollment link", body, back="/enroll/new", narrow=True)

    def issue_direct(self, form):
        cn = form.get("cn", [""])[0].strip()
        if not enroll.valid_cn(cn):
            self.enroll_issue_page("The certificate name may use letters, digits, "
                                   "spaces, and . _ @ - (up to 64).", form)
            return
        try:
            sans = form_sans(form)
            group = parse_group(form.get("group", [""])[0])
            check_group_email(group, sans)
        except ValueError as err:
            self.enroll_issue_page(str(err), form)
            return
        try:
            data, password, cert = enroll.issue_p12(cn, ca_url=CA_URL, root_cert=ROOT_CERT,
                                                    extra_cas=enroll.load_extra_cas(), sans=sans,
                                                    **group_issue_args(group))
        except (RuntimeError, OSError, subprocess.SubprocessError) as err:
            self.enroll_issue_page(str(err), form)
            return
        download = DOWNLOADS.add("admin", data, f"{safe_filename(cn)}.p12", "application/x-pkcs12")
        serial = str(cert.serial_number)
        body = (
            self.insecure_note()
            + '<div class="card"><div class="card-header"><h2>Certificate issued</h2>'
            f'<p class="muted">For <b>{esc(cn)}</b>. The file holds the private key, the certificate, and the '
            "intermediate and root CA certificates"
            + (" plus the other trusted CAs" if enroll.load_extra_cas() else "") + ".</p></div>"
            '<div class="card-content"><div class="field"><span class="label">Password for the .p12 file</span>'
            + ui.copy_field(password, "password", "secret") + "</div>"
            + ui.alert("warning", "The password is shown only once, and the download is available for 10 minutes.")
            + "</div>"
            '<div class="card-actions">'
            + (f'<a class="btn text" href="{esc(self.url("/cert/" + serial))}">View certificate</a>' if db_enabled() else "")
            + f'<a class="btn" href="{esc(self.url("/issue/file/" + download))}">{ui.icon("download")}'
            f"Download {esc(safe_filename(cn))}.p12</a></div></div>"
        )
        self.page(f"Certificate for {cn}", body, back="/enroll/issue", narrow=True)

    def admin_file(self, download_id):
        entry = DOWNLOADS.get("admin", download_id)
        if entry is None:
            self.not_found("Download expired", "Downloads are available for 10 minutes. Issue the certificate again.")
            return
        data, filename, content_type = entry
        self.download(data, filename, content_type)

    def extra_ca_add(self, form):
        data = form.get("file", [b""])[0]
        if not data.strip():
            data = str(form.get("pem", [""])[0]).encode()
        if not data.strip():
            self.tools_error("/tools/cas", "Choose a certificate file or paste a PEM.")
            return
        try:
            new = enroll.parse_ca_certs(data if isinstance(data, bytes) else data.encode())
        except ValueError as err:
            self.tools_error("/tools/cas", err)
            return
        certs = enroll.load_extra_cas()
        known = {enroll.fingerprint(c) for c in certs}
        certs += [c for c in new if enroll.fingerprint(c) not in known]
        enroll.save_extra_cas(certs)
        self.redirect("/tools/cas?added=1")

    def sign_request(self, form):
        data = form.get("file", [b""])[0]
        if not data.strip():
            data = str(form.get("pem", [""])[0]).encode()
        if not data.strip():
            self.tools_error("/tools/sign", "Choose a certificate request file or paste a PEM.")
            return
        data = data if isinstance(data, bytes) else data.encode()
        try:
            if form.get("kind", ["leaf"])[0] == "ca":
                with open(ROOT_CERT, "rb") as cert_file, open(ROOT_KEY, "rb") as key_file, \
                        open(CA_PASSWORD, "rb") as password_file:
                    root = x509.load_pem_x509_certificate(cert_file.read())
                    key = serialization.load_pem_private_key(key_file.read(), password_file.read().strip())
                cert = enroll.sign_subordinate(data, root, key)
                chain = [cert, root]
                signer = "subordinate CA"
            else:
                chain = enroll.sign_csr(enroll.parse_csr(data)[1], ca_url=CA_URL, root_cert=ROOT_CERT)
                cert = chain[0]
                signer = "certificate"
        except (ValueError, RuntimeError) as err:
            self.tools_error("/tools/sign", err)
            return
        print(f"Signed {signer} {cert.subject.rfc4514_string()!r} for an uploaded request "
              f"(serial {cert.serial_number}, valid until {cert.not_valid_after_utc:%Y-%m-%d})", flush=True)
        self.download(b"".join(c.public_bytes(serialization.Encoding.PEM) for c in chain),
                      f"{safe_filename(enroll.common_name(cert))}-chain.crt", "application/x-pem-file")

    def ca_page(self):
        root, inter = cert_chain()
        extra = enroll.load_extra_cas()
        now = datetime.datetime.now(datetime.timezone.utc)

        def kv(label, value, copy=None):
            button = ui.copy_button(copy, label) if copy else "<span></span>"
            return ui.kv_row(label, value, button if copy else "")

        def details(cert):
            fp = enroll.fingerprint(cert)
            return (
                kv("Subject", f'<span class="mono">{esc(cert.subject.rfc4514_string())}</span>')
                + kv("Issuer", f'<span class="mono">{esc(cert.issuer.rfc4514_string())}</span>')
                + kv("Valid until", ui.when(cert.not_valid_after_utc, now))
                + kv("SHA-256", f'<span class="mono">{esc(fp)}</span>', fp)
            )

        def download_row(glyph, title, sub, link, filename):
            return (
                f'<div class="row"><span class="row-icon">{ui.icon(glyph)}</span>'
                f'<span class="row-text"><span class="row-title">{title}</span>'
                f'<span class="row-sub">{sub}</span></span><span class="row-actions">'
                f'<a class="icon-btn" href="{esc(self.url(link))}" aria-label="Download {esc(filename)}" '
                f'title="Download {esc(filename)}">{ui.icon("download")}</a></span></div>'
            )

        def authority(title, cert, link, filename, opened, anchor):
            left = cert.not_valid_after_utc - now
            chip = (ui.chip("bad", "Expired") if left.days < 0 else
                    ui.chip("warn", "Renew soon") if left.days < 180 else ui.chip("ok", "Valid"))
            return (
                f'<details class="expand" id="{anchor}"{" open" if opened else ""}><summary>'
                f'<span class="row-icon">{ui.icon("shield-check")}</span><span class="summary-text">'
                f'<span class="summary-title">{title}</span>'
                f'<span class="summary-sub">{esc(enroll.common_name(cert))}</span></span>{chip}'
                f'{ui.icon("chevron-down", "chev")}</summary>'
                f'<dl class="expand-body flush rows">{details(cert)}'
                '<div class="kv"><dt>File</dt><dd class="kv-value"><span class="kv-content">'
                f'<a href="{esc(self.url(link))}" download>{esc(filename)}</a></span>'
                f'<a class="icon-btn" href="{esc(self.url(link))}" aria-label="Download {esc(filename)}" '
                f'title="Download {esc(filename)}">{ui.icon("download")}</a></dd></div></dl></details>'
            )

        base = default_base_url(self.headers) or "&lt;Home Assistant URL&gt;"
        base = esc(base) if not base.startswith("&lt;") else base
        scep_url = f"{base}/api/step_ca_scep/scep/{esc(SCEP_PROVISIONER)}"
        copyable = not base.startswith("&lt;")

        def url_row(label, url):
            return kv(label, f'<span class="mono">{url}</span>', html.unescape(url) if copyable else None)

        body = (
            '<div class="grid"><div>'
            '<div class="card"><div class="card-header"><h2>' + esc(CA_NAME) + "</h2>"
            '<p class="muted">The root signs the intermediate; the intermediate signs device certificates.</p></div>'
            + authority("Root CA", root, "/download/root_ca.pem", "root_ca.pem", False, "root-ca")
            + authority("Intermediate CA", inter, "/download/intermediate_ca.pem", "intermediate_ca.pem", False, "intermediate-ca")
            + '<h3 class="subhead" id="authority-downloads">Downloads</h3><div class="rows">'
            + download_row("file-certificate-outline", "CA chain",
                           "Intermediate and root, for MDMs and RADIUS servers",
                           "/download/ca-chain.pem", "ca-chain.pem")
            + download_row("file-certificate-outline", "Meraki Access Manager",
                           "The CA chain as one .crt for Access Manager > Certificates. Upload it as a "
                           "single entry, set Enabled and Trusted Anchor, and choose Subject Alternative "
                           "Name RFC822 as the identity field",
                           "/download/meraki-ca-chain.crt", f"{safe_filename(CA_NAME)}-ca-chain.crt")
            + download_row("file-certificate-outline", "CA bundle",
                           "Root, intermediate" + (", and the other trusted CAs" if extra else ""),
                           "/download/ca-bundle.pem", "ca-bundle.pem")
            + download_row("cancel", "Certificate revocation list", "Revoked certificates",
                           "/download/crl.pem", "crl.pem")
            + "</div></div>"
            "</div><div>"
            '<div class="card" id="authority-endpoints"><div class="card-header"><h2>Endpoints</h2>'
            '<p class="muted">Served without login through Home Assistant.</p></div><dl class="rows">'
            + url_row("SCEP URL", scep_url)
            + "".join(url_row(f"SCEP URL, {esc(g)}", f"{base}/api/step_ca_scep/scep/{esc(g)}") for g in GROUPS)
            + url_row("Root download", f"{base}/api/step_ca_scep/roots.pem")
            + url_row("CRL (DER)", f"{base}/api/step_ca_scep/crl")
            + "</dl></div></div></div>"
        )
        self.page("Authority", body)

    TOOLS_MENU = (
        ("/tools/sign", "Sign a request", "file-sign", "Sign a server, client or subordinate CA request"),
        ("/tools/mdm", "MDM profiles", "cellphone", "Download profiles or copy SCEP values for your MDM"),
    )

    def tools_page(self):
        rows = "".join(
            f'<a class="row" href="{esc(self.url(path))}"><span class="row-icon">{ui.icon(glyph)}</span>'
            f'<span class="row-text"><span class="row-title">{label}</span><span class="row-sub">{sub}</span></span>'
            f'{ui.icon("chevron-right", "row-icon")}</a>'
            for path, label, glyph, sub in self.TOOLS_MENU
        )
        self.page("Certificate tools", f'<div class="card"><div class="card-header"><h2>Certificate tools</h2></div>'
                  f'<div class="rows">{rows}</div></div>', narrow=True)

    def setup_page(self, query=None):
        query = query or {}
        check = (query.get("check") or [""])[0] == "1"
        config = ipsk.resident_access.settings()
        options_available = False
        if SUPERVISOR_TOKEN:
            try:
                saved_options()
                options_available = True
            except RuntimeError:
                pass
        database_state = "Not configured"
        database_detail = "Install/start MariaDB and select MariaDB in the add-on options, then restart Step CA."
        if os.environ.get("PORTAL_DB_HOST"):
            database_state = "Not checked"
            database_detail = "MariaDB connection details are present. Check connections to confirm portal-table access."
            if check:
                try:
                    with ipsk.db_connect() as conn, conn.cursor() as cursor:
                        for table in ("stepca_residents", "stepca_resident_accounts", "stepca_resident_devices", "stepca_invites", "stepca_ipsks"):
                            cursor.execute("SELECT 1 FROM " + table + " LIMIT 1")
                    database_state = "Reachable"
                    database_detail = "The portal account can read all five resident tables in Step CA’s MariaDB. Backup and deployed CA behavior still need verification."
                except Exception:
                    database_state = "Needs attention"
                    database_detail = "Could not read the resident tables. Start MariaDB, restart Step CA to initialize its schema, then check again. Review add-on logs if this persists."
        provider_state = "Not connected" if not SUPERVISOR_TOKEN else "Not checked"
        provider_detail = "Install the Step CA companion and Meraki HA integration, then restart Home Assistant."
        network_state = "Not configured"
        network_detail = "Choose the network, SSID and policy under Settings → IPSK → Network and onboarding."
        selected = config.get("network_id") and config.get("group_policy_id")
        if selected:
            network_state = "Configured; not checked"
            network_detail = "Network, SSID and resident policy are selected. Check connections to validate their availability."
        if check and SUPERVISOR_TOKEN:
            try:
                choices = ipsk.get_options(str(config.get("network_id") or ""))
                if not isinstance(choices.get("networks"), list):
                    raise RuntimeError("Invalid options response")
                provider_state = "Reachable" if choices["networks"] else "No Meraki networks"
                provider_detail = "The Step CA companion answered through Home Assistant’s existing Meraki connection. Key creation and captive behavior remain unverified."
                if selected:
                    found_network = any(str(row.get("id")) == str(config["network_id"]) for row in choices.get("networks", []))
                    found_ssid = any(str(row.get("number")) == str(config.get("ssid_number", 0)) for row in choices.get("ssids", []))
                    found_policy = any(str(row.get("id")) == str(config["group_policy_id"]) for row in choices.get("group_policies", []))
                    network_state = "Available" if found_network and found_ssid and found_policy else "Needs attention"
                    network_detail = ("Selected network, enabled iPSK-without-RADIUS SSID and resident policy are available. Check captive settings on a physical device after installation."
                                      if network_state == "Available" else "The selected network, enabled iPSK SSID or policy is unavailable. Check Meraki permissions and the configured IDs, then restart Step CA after saving options.")
            except Exception:
                provider_state = "Needs attention"
                provider_detail = "The companion or Meraki options could not be reached. Install/restart the integrations and check Meraki permissions. These checks do not create keys."
        public_url = str(ENROLL_PUBLIC_URL or "")
        if check and not public_url and SUPERVISOR_TOKEN:
            try:
                external, cloud, _ = _fetch_core_urls()
                public_url = external or cloud or ""
            except Exception:
                pass
        try:
            parsed = urllib.parse.urlsplit(public_url.strip())
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError("Invalid port")
        except ValueError:
            parsed = urllib.parse.urlsplit("")
        https_configured = parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and not any(c.isspace() for c in public_url)
        https_state = "Configured; not verified" if https_configured else "Needs HTTPS URL"
        https_detail = ("A public HTTPS URL is configured. Confirm certificate trust, reachability and the Meraki walled garden from a device."
                        if https_configured else "Set enrollment.public_url or Home Assistant’s external HTTPS URL. Check connections to read Home Assistant’s URL; local request addresses are not treated as public HTTPS evidence.")
        identity_state = "No identity verification"
        identity_detail = "Residents enter their details. This attributes a key but does not prove identity."
        if config.get("sign_in_required") or config.get("no_sign_in_user_list"):
            try:
                ipsk.resident_access.validate_settings(config)
                identity_state = "Configured; not verified"
                identity_detail = ("Duo factor verification and permitted-group checks are configured. Verify the callback and an allowed/denied resident after installation."
                                   if config.get("sign_in_required") else "Only the configured Duo group supplies account choices. Selection does not verify identity; check actual group permissions after installation.")
            except (ValueError, TypeError):
                identity_state = "Needs attention"
                identity_detail = "Complete the permitted Duo group and required Admin API settings; verification also needs Universal SDK credentials and the exact public callback URL."
        qr_state = "Configured; not verified" if all(config.get(key) for key in ("guest_ssid", "guest_psk", "setup_ssid", "setup_psk")) else "Not fully configured"
        qr_detail = "Save guest/setup network credentials under Settings → IPSK → Guest and setup networks. Guest policy must bypass splash; setup policy must open the captive portal. Physical QR scans remain a deployment check."
        rows = (("MariaDB", database_state, database_detail), ("Meraki connection", provider_state, provider_detail),
                ("Resident network and policy", network_state, network_detail), ("Public HTTPS", https_state, https_detail),
                ("Resident identity", identity_state, identity_detail), ("Guest and setup QR codes", qr_state, qr_detail))
        states = ''.join('<section class="row"><div class="row-text"><h3 class="row-title">' + esc(label)
                         + '</h3><p class="setup-state"><b>' + esc(state) + '</b></p><p>' + esc(detail) + '</p></div></section>'
                         for label, state, detail in rows)
        body = ('<div class="card"><div class="card-header"><h2>Prepare your installation</h2></div><div class="card-content">'
                '<p>Follow the steps below, then check the running connections. Checks read configuration and service metadata; they do not issue certificates, create keys or change network settings.</p>'
                '<ol><li>Install MariaDB and Step CA; select MariaDB and restart the add-on.</li>'
                '<li>Install/restart the Step CA companion and Meraki integration in Home Assistant.</li>'
                '<li>Configure the resident network, default setup key and registered-resident policy.</li>'
                '<li>Choose resident identity/invitation settings and save guest/setup QR credentials.</li>'
                '<li>After installation, verify real devices, Duo callbacks, HTTPS and certificate enrollment.</li></ol>'
                + ('<p class="hint">Saved settings were read from Supervisor. Checks use the running settings; restart Step CA after changing add-on options.</p>'
                   if options_available else '<p class="hint">Saved Supervisor options are unavailable. This page shows running settings and the steps needed before connections can be checked.</p>')
                + f'<form method="get" data-readiness-check action="{esc(self.url("/tools/setup"))}"><input type="hidden" name="check" value="1">'
                '<button class="btn" type="submit">Check connections</button></form>'
                '<p class="hint">Checks run only when requested and may take a few minutes if services time out. Results describe this request, not continuous monitoring.</p>'
                + f'<p><a href="{esc(self.url("/ipsk/access"))}">IPSK access settings</a> · '
                + f'<a href="{esc(self.url("/tools/options"))}">View running options</a> · '
                + f'<a href="{esc(self.url("/tools/help"))}">Setup help</a></p></div></div>'
                + '<div class="card" id="setup-readiness"><div class="card-header"><h2>Connection readiness</h2></div><div class="rows">' + states + '</div></div>')
        if not ipsk.PORTAL_ENABLED:
            body = ui.alert("info", "Resident onboarding is currently off. Turn it on only after its network and policy are configured.", "Portal disabled") + body
        self.page("Setup and checks", body, narrow=True)

    def help_page(self, query=None):
        query = query or {}
        search = str((query.get("q") or [""])[0])[:254].strip()
        topics = guidance.help_topics(search)
        controls = ('<div class="card"><div class="card-header"><h2>Find a connection guide</h2></div><div class="card-content">'
                    + f'<form method="get" action="{esc(self.url("/tools/help"))}"><label for="help-search">Search help</label>'
                    + f'<input id="help-search" type="search" name="q" maxlength="254" value="{esc(search)}">'
                    + '<button class="btn text" type="submit">Search help</button></form>'
                    + (f'<a class="btn text" href="{esc(self.url("/tools/help"))}">Clear search</a>' if search else '')
                    + f'<p class="hint">{len(topics)} guides. Read connection status under <a href="{esc(self.url("/tools/setup"))}">Setup and checks</a>.</p></div></div>')
        articles = ''.join('<section class="card" id="' + esc(slug) + '"><details class="expand"'
                           + (' open' if search else '') + '><summary>' + esc(title) + '</summary><div class="card-content">'
                           + body + '</div></details></section>' for slug, title, _, body in topics)
        if not articles:
            articles = '<div class="card"><div class="empty"><h2>No matching guides</h2><p>Try Wi-Fi, invitation, private MAC, password or certificate; or clear the search.</p></div></div>'
        self.page("Help and troubleshooting", controls + articles, narrow=True)

    def portal_skin_page(self, kind, query=None, error=None, draft=None, logo=None, preview=False):
        title = "Appearance" if kind == "appearance" else "Content"
        try:
            config = portal_skin.normalize(saved_options().get("captive_portal") or {})
        except (RuntimeError, ValueError):
            self.page(title, ui.alert("warning", "Saved portal settings could not be read. Check the Home Assistant connection and try again.", "Settings unavailable"))
            return
        config.update(draft or {})
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        body = portal_skin.form(config, kind, csrf, self.url(f"/settings/captive-portal/{kind}/save"), logo)
        if error:
            body = ui.alert("error", esc(error), "Could not apply settings") + guidance.form_error(body, error)
        elif preview:
            body = ui.alert("info", "The preview shows your draft. Save to apply it to the public portal.", "Preview only") + body
        elif (query or {}).get("saved"):
            body = ui.alert("success", "Changes are live on new portal page loads.", "Portal settings saved") + body
        self.page(title, body)

    def portal_skin_save(self, kind, form):
        config, logo = None, None
        try:
            options = saved_options()
            config, logo = portal_skin.draft(options.get("captive_portal") or portal_skin.DEFAULTS, kind, form)
            if form.get("intent", ["save"])[0] == "preview":
                self.portal_skin_page(kind, draft=config, logo=logo, preview=True)
                return
            if logo:
                portal_skin.store_logo(logo)
            options["captive_portal"] = config
            supervisor("POST", "/addons/self/options", {"options": options})
            portal_skin.SETTINGS_OVERRIDE = config
            self.portal_skin_page(kind, {"saved": ["1"]})
        except Exception as err:
            # Preserve bounded text and a validated draft logo on validation or storage failure.
            if config is None:
                config = {key: str(form[key][0])[:portal_skin.LIMITS.get(key, 7)] for key in portal_skin.FIELDS[kind] if key != "logo_file" and key in form}
            error = err if isinstance(err, ValueError) else RuntimeError("Could not save portal settings. Check the Home Assistant connection and try again.")
            self.portal_skin_page(kind, error=error, draft=config, logo=logo)

    def identity_page(self, kind, query=None, error=None, draft=None):
        title = "Authentication" if kind == "authentication" else "User directory"
        try:
            config = dict(saved_options().get("resident_onboarding") or {})
        except RuntimeError:
            self.page(title, ui.alert("warning", "Saved identity settings could not be read. Check the Home Assistant connection and try again.", "Settings unavailable"))
            return
        config.update(draft or {})
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        other = "directory" if kind == "authentication" else "authentication"
        body = identity_settings.form(config, kind, csrf, self.url(f"/settings/identity/{kind}/save"), self.url(f"/settings/identity/{other}"))
        if error:
            body = ui.alert("error", esc(error), "Could not save settings") + '<p class="hint">Your other details are kept. Re-enter any new secret before saving.</p>' + guidance.form_error(body, error)
        elif (query or {}).get("saved"):
            body = ui.alert("success", f"{title} settings were saved.", "Settings saved") + body
        self.page(title, body)

    def identity_save(self, kind, form):
        access = ipsk.resident_access
        try:
            options = saved_options()
            config = identity_settings.merge(options.get("resident_onboarding") or {}, kind, form)
            required = bool(config.get("sign_in_required") or (kind == "directory" and config.get("no_sign_in_user_list")))
            identity_settings.validate(config, kind, required=required)
            options["resident_onboarding"] = config
            supervisor("POST", "/addons/self/options", {"options": options})
            access.SETTINGS_OVERRIDE = config
            self.identity_page(kind, {"saved": ["1"]})
        except Exception as err:
            draft = {key: str(form[key][0])[:512] for key in identity_settings.FIELDS[kind] if key not in identity_settings.SECRET_FIELDS and key in form}
            error = err if isinstance(err, ValueError) else RuntimeError("Could not save identity settings. Check the Home Assistant connection and try again.")
            self.identity_page(kind, error=error, draft=draft)

    def access_policy_save(self, form):
        access = ipsk.resident_access
        try:
            options = saved_options()
            config = dict(options.get("resident_onboarding") or {})
            for key in access.BOOL_FIELDS:
                config[key] = form.get(key, [""])[0] == "1"
            try:
                config["max_devices_per_resident"] = int(form.get("max_devices_per_resident", ["5"])[0])
            except ValueError as err:
                raise guidance.FieldError("max_devices_per_resident", "Choose a device limit from 1 to 50.") from err
            access.validate_settings(config)
            options["resident_onboarding"] = config
            supervisor("POST", "/addons/self/options", {"options": options})
            access.SETTINGS_OVERRIDE = config
            self.residents_page({"access_saved": ["1"]}, section="access")
        except Exception as err:
            draft = {key: form.get(key, [""])[0] == "1" for key in access.BOOL_FIELDS}
            draft["max_devices_per_resident"] = str(form.get("max_devices_per_resident", ["5"])[0])[:8]
            self.residents_page({}, error=err, section="access", draft=draft)

    def residents_page(self, query=None, error="", invite_code="", revealed=None, created_key="", join_key=None, section="keys", draft=None):
        """Render one focused IPSK task; existing POST handlers share feedback here."""
        page_path = "/ipsk" if section == "keys" else "/ipsk/" + section
        query = query or {}
        draft = draft or {}
        key_id = str((query.get("key_id") or [""])[0])[:191]
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,191}", key_id):
            key_id = ""
        key_context = {key: str(query[key][0])[:254] for key in
                       ("device_q", "device_sort", "device_page") if key in query}
        if key_id:
            key_context["key_id"] = key_id
        context_fields = "".join(f'<input type="hidden" name="{key}" value="{esc(value)}">' for key, value in key_context.items())
        search = str((query.get("q") or [""])[0])[:254].strip()
        record_sort = str((query.get("record_sort") or ["newest"])[0])
        if record_sort not in ("newest", "oldest", "name", "unit"):
            record_sort = "newest"
        key_sort = str((query.get("key_sort") or ["name"])[0])
        if key_sort not in ("name", "network", "resident", "status"):
            key_sort = "name"
        record_page = guidance.page_number((query.get("record_page") or ["1"])[0])
        key_page = guidance.page_number((query.get("key_page") or ["1"])[0])
        inventory = {"rows": [], "total": 0, "matched": 0, "page": 1, "pages": 1, "size": 25}
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        notice = ""
        if error:
            notice = ui.alert("error", esc(error), "Could not complete the action")
            if draft and section in ("create", "access", "join-codes/settings"):
                notice += '<p class="hint">Your other details are kept. Re-enter any new passwords or secrets before saving.</p>'
        elif created_key:
            notice = ui.alert("success", f"Created iPSK {esc(created_key)}.", "Key created")
        elif query.get("invite_revoked"):
            notice = ui.alert("success", "The unused invitation was revoked.", "Invitation updated")
        elif query.get("ipsk_revoked"):
            notice = ui.alert("success", "The key was revoked in Home Assistant.", "iPSK updated")
        elif query.get("ipsk_deleted"):
            notice = ui.alert("success", "The key was deleted in Home Assistant.", "iPSK updated")
        elif query.get("qr_saved"):
            notice = ui.alert("success", "The guest and registration QR settings were saved.", "QR settings saved")
        elif query.get("access_saved"):
            notice = ui.alert("success", "Wi-Fi device access settings were saved.", "Access settings saved")
        elif invite_code:
            notice = ui.alert(
                "success",
                f"<p>Copy this invitation code and give it to one resident. It is shown only once.</p>"
                f'<div class="copy-field"><span class="mono">{esc(invite_code)}</span>'
                f'{ui.copy_button(invite_code, "invitation code")}</div>',
                "Invitation created",
            )
        if revealed:
            notice += ui.alert(
                "info",
                f'<p>Passphrase for key <code>{esc(revealed[0])}</code>:</p>'
                f'<div class="copy-field"><span class="mono">{esc(revealed[1])}</span>'
                f'{ui.copy_button(revealed[1], "Wi-Fi passphrase")}</div>',
                "Passphrase revealed",
            )
        if key_id and section == "keys":
            device_query = {"q": key_context.get("device_q", ""), "record_sort": key_context.get("device_sort", "newest"),
                            "record_page": guidance.page_number(key_context.get("device_page", "1"))}
            back_to_devices = self.url("/ipsk/devices") + "?" + urllib.parse.urlencode(device_query)
            notice += (f'<p><a class="btn text" href="{esc(back_to_devices)}">Back to registered devices</a></p>'
                       + f'<p class="hint">Showing key <code>{esc(key_id)}</code>. '
                       + f'<a href="{esc(self.url("/ipsk"))}">View all Wi-Fi keys</a></p>')
        if join_key:
            notice += ipsk.wifi_join_card(
                "Join with " + join_key["name"], join_key["ssid"], join_key["passphrase"],
                "Scan this QR on the other device to join with its individual Wi-Fi key. "
                "Keep private or randomized addressing off for the resident network.",
                filename="device-wifi.svg", show_password=True,
            )
        if section == "access" and not ipsk.PORTAL_ENABLED:
            notice += ui.alert(
                "info",
                "Resident onboarding is turned off. Enable it in the add-on's Resident onboarding options.",
                "Resident portal disabled",
            )
        if section in ("devices", "invitations", "create", "access") and not os.environ.get("PORTAL_DB_HOST"):
            notice += ui.alert(
                "warning",
                "Resident and invitation records share Step CA's MariaDB database. Select MariaDB in the add-on options to use this page.",
                "MariaDB required",
            )
        if section in ("keys", "devices", "create", "access") and not SUPERVISOR_TOKEN:
            notice += ui.alert(
                "warning",
                "Home Assistant has not provided its service connection. iPSK actions are unavailable until the add-on is connected to Home Assistant.",
                "Home Assistant connection unavailable",
            )

        try:
            if section == "devices" and os.environ.get("PORTAL_DB_HOST"):
                inventory = ipsk.resident_inventory(search, record_sort, record_page)
            residents = inventory["rows"]
            invites = ipsk.list_invites() if section == "invitations" and os.environ.get("PORTAL_DB_HOST") else []
        except Exception:  # noqa: BLE001 - surfaced in the admin panel
            residents, invites = [], []
            inventory = {"rows": [], "total": 0, "matched": 0, "page": 1, "pages": 1, "size": 25}
            notice += ui.alert("error", "Could not read resident records. Check MariaDB under Setup and checks, then reload this page.", "Resident database unavailable")

        try:
            keys = ipsk.list_ipsks() if section in ("keys", "devices") and SUPERVISOR_TOKEN else []
            keys = [dict(row, status=row.get("status") if row.get("status") in ("active", "revoked", "expired") else "unknown") for row in keys]
            inactive = ipsk.inactive_ipsk_ids(keys) if section == "devices" else []
            if inactive and os.environ.get("PORTAL_DB_HOST"):
                with ipsk.db_connect() as conn, conn.cursor() as cursor:
                    ipsk.sync_inactive_keys(cursor, inactive)
                    conn.commit()
                inventory = ipsk.resident_inventory(search, record_sort, record_page)
                residents = inventory["rows"]
        except Exception as err:  # noqa: BLE001 - surfaced in the admin panel
            keys = []
            notice += ui.alert("warning", f"{esc(err)}", "Could not load live iPSKs")

        selected_network = str((query.get("network") or [""])[0] or
                               ipsk.resident_access.settings().get("network_id") or "")
        try:
            options = ipsk.get_options(selected_network) if section == "create" and SUPERVISOR_TOKEN else {}
            networks = options.get("networks") or []
            ssids = options.get("ssids") or []
            policies = options.get("group_policies") or []
        except Exception as err:  # noqa: BLE001 - admin can still inspect existing resident data
            networks, ssids, policies = [], [], []
            notice += ui.alert("warning", f"{esc(err)}", "Could not load iPSK options")

        try:
            qr_settings = dict(saved_options().get("resident_onboarding") or {}) if section in ("access", "join-codes", "join-codes/settings") else {}
        except RuntimeError as err:
            qr_settings = {}
            notice += ui.alert("warning", esc(err), "QR settings unavailable")
        qr_settings.update(draft)
        resident_count, key_count = inventory["total"], len(keys)
        status = str((query.get("key_status") or ["all"])[0])
        if status not in ("all", "active", "revoked", "expired", "unknown"):
            status = "all"
        def matches(row, fields):
            return not search or search.casefold() in " ".join(str(row.get(field) or "") for field in fields).casefold()
        keys = [row for row in keys if matches(row, ("id", "psk_group_id", "name", "ssid_name", "associated_user", "associated_unit"))
                and (status == "all" or str(row.get("status") or "unknown") == status)
                and (not key_id or str(row.get("id") or row.get("psk_group_id") or "") == key_id)]
        key_sort_field = {"name": "name", "network": "ssid_name", "resident": "associated_user", "status": "status"}[key_sort]
        keys.sort(key=lambda row: (str(row.get(key_sort_field) or "").casefold(), str(row.get("id") or row.get("psk_group_id") or "")))
        matched_keys = len(keys)
        key_pages = max(1, (matched_keys + 24) // 25)
        key_page = min(key_page, key_pages)
        keys = keys[(key_page - 1) * 25:key_page * 25]
        def inventory_link(number, field, anchor):
            values = {"network": selected_network, "q": search, **key_context}
            if section == "devices":
                values["record_sort"] = record_sort
            else:
                values.update(key_status=status, key_sort=key_sort)
            values[field] = number
            return self.url(page_path) + "?" + urllib.parse.urlencode(values) + anchor
        key_pager = guidance.pagination(key_page, key_pages, (key_page - 1) * 25 + 1,
                                       min(key_page * 25, matched_keys), matched_keys,
                                       lambda number: inventory_link(number, "key_page", "#device-keys"), "Wi-Fi key pages")
        record_pager = guidance.pagination(inventory["page"], inventory["pages"], (inventory["page"] - 1) * inventory["size"] + 1,
                                          min(inventory["page"] * inventory["size"], inventory["matched"]), inventory["matched"],
                                          lambda number: inventory_link(number, "record_page", "#registered-devices"), "Registered device pages")
        is_devices = section == "devices"
        sort_field = "record_sort" if is_devices else "key_sort"
        sort_value = record_sort if is_devices else key_sort
        sort_choices = (("newest", "Newest first"), ("oldest", "Oldest first"), ("name", "Resident name"), ("unit", "Unit or room")) if is_devices else (
            ("name", "Key name"), ("network", "Network name"), ("resident", "Resident"), ("status", "Status"))
        status_field = '' if is_devices else '<label>Key status<select name="key_status">' + "".join(
            f'<option value="{value}"' + (' selected' if status == value else '') + f'>{label}</option>'
            for value, label in (("all", "All keys"), ("active", "Active"), ("revoked", "Revoked"),
                                ("expired", "Expired"), ("unknown", "Unknown"))) + '</select></label>'
        management = (
            '<div class="ipsk-filters">'
            f'<form method="get" action="{esc(self.url(page_path))}">'
            + context_fields +
            f'<input type="hidden" name="network" value="{esc(selected_network)}">'
            '<div class="field-row"><label>Search ' + ('resident or device' if is_devices else 'key, resident or network')
            + f'<input type="search" name="q" maxlength="254" value="{esc(search)}"></label>' + status_field
            + '</div><details class="sorting-options"><summary>Sorting options</summary><label>Sort by'
            f'<select name="{sort_field}">'
            + "".join(f'<option value="{value}"' + (' selected' if sort_value == value else '') + f'>{label}</option>'
                      for value, label in sort_choices)
            + '</select></label></details><div class="row-actions"><button class="btn text" type="submit">Apply filters</button>'
            + (f'<a class="btn text" href="{esc(self.url(page_path))}">Clear filters</a>'
               if search or (not is_devices and status != "all") or sort_value != ("newest" if is_devices else "name") else '')
            + '</div></form></div>'
        )
        qr_cards = []
        access_settings_card = ipsk.resident_access.admin_settings_card(
            ipsk, qr_settings, csrf, self.url("/ipsk/access/settings"), standalone=True,
            identity_urls=(("Authentication", self.url("/settings/identity/authentication")), ("User directory", self.url("/settings/identity/directory")))) if section == "access" else ""
        for kind, title, description in (
            ("guest", "Guest access", "Scan to join with the guest password. No resident registration is required."),
            ("setup", "Join and create a key", "Scan to join the setup network, then open Wi-Fi sign-in to register and receive your individual key."),
        ) if section == "join-codes" else ():
            ssid, password = str(qr_settings.get(kind + "_ssid") or ""), str(qr_settings.get(kind + "_psk") or "")
            try:
                if not ssid or not password:
                    raise ValueError("Set this network’s name and password in QR network settings to generate its join code.")
                qr_cards.append(ipsk.wifi_join_card(title, ssid, password, description,
                                                  filename=kind + "-wifi.svg"))
            except ValueError as err:
                qr_cards.append(
                    '<section class="card"><div class="card-header"><h2>' + esc(title)
                    + '</h2></div><div class="card-content"><p>' + esc(description) + '</p><p>'
                    + esc(err) + f'</p><a href="{esc(self.url("/ipsk/join-codes/settings"))}">QR network settings</a></div></section>'
                )
        qr_network_fields = ""
        for kind, title in (("guest", "Guest access"), ("setup", "Registration setup")):
            qr_network_fields += (
                f'<fieldset><legend>{title}</legend><div class="field-row">'
                f'<label>Network name<input id="{kind}_ssid" name="{kind}_ssid" value="{esc(qr_settings.get(kind + "_ssid") or "")}" maxlength="32" autocomplete="off">'
                '<small class="muted">Leave empty to remove this QR.</small></label>'
                f'<label>Wi-Fi password<input id="{kind}_psk" type="password" name="{kind}_psk" autocomplete="new-password" maxlength="64" '
                'placeholder="Keep the saved password">'
                '<small class="muted">Blank keeps the saved password. Enter one for a new network.</small></label>'
                '</div></fieldset>'
            )
        qr_settings_card = (
            '<div class="card" id="qr-settings"><div class="card-header"><h2>QR network settings</h2></div>'
            '<div class="card-content"><p>Enter the credentials already configured in Meraki. '
            'The guest key needs a policy that bypasses splash; the setup key needs the captive portal.</p>'
            f'<form method="post" action="{esc(self.url("/ipsk/qr/settings"))}">{csrf}'
            + qr_network_fields + '<button class="btn" type="submit">Save QR settings</button></form>'
            '</div></div>'
        )
        portal_url = ipsk.PUBLIC_BASE
        intro = (
            '<div class="card"><details class="expand" id="resident-setup"><summary>Captive portal setup</summary>'
            '<div class="card-content">'
            '<p>Residents register once and receive an individual Meraki iPSK. Their Wi-Fi details are stored here; '
            'certificate issuance and renewal stay in Step CA.</p>'
            f'<p><b>Custom splash URL:</b> <a href="{esc(portal_url)}">{esc(portal_url)}</a></p>'
            '<p>Use this path on your public Home Assistant URL as the Meraki click-through splash page '
            'for the default setup PSK. New residents must arrive through the captive portal. '
            'Private or randomized MAC addresses are blocked before registration.</p>'
            '</div></details></div>'
        )
        network_options = "".join(
            f'<option value="{esc(item.get("id"))}"' + (' selected' if str(item.get("id")) == selected_network else '')
            + f'>{esc(item.get("name") or item.get("id"))}</option>'
            for item in networks
        )
        ssid_options = "".join(
            f'<option value="{int(item.get("number", 0))}"'
            + (' selected' if str(item.get("number", 0)) == str(draft.get("ssid_number", "")) else '')
            + f'>{esc(item.get("name") or "SSID " + str(item.get("number")))}</option>'
            for item in ssids
        )
        policy_options = "".join(
            f'<option value="{esc(item.get("id"))}"'
            + (' selected' if str(item.get("id")) == str(draft.get("group_policy_id", "")) else '')
            + f'>{esc(item.get("name") or item.get("id"))}</option>'
            for item in policies
        )
        create_form = (
            '<div class="card" id="create-device-key"><div class="card-header"><h2>Create a Wi-Fi key</h2></div>'
            '<div class="card-content"><p>Create an individual Wi-Fi key for a device or resident.</p>'
            f'<form method="get" action="{esc(self.url("/ipsk/create"))}"><label>Meraki network<select id="network_id" name="network" required>'
            + '<option value="">Choose a network</option>' + network_options
            + '</select></label><button class="btn text" type="submit">Load Wi-Fi networks and policies</button></form>'
            '<p class="hint">Load the Meraki network first. Its Wi-Fi networks and access policies appear below.</p>'
            f'<form method="post" action="{esc(self.url("/ipsk/create"))}">{csrf}'
            f'<input type="hidden" name="network_id" value="{esc(selected_network)}">'
            '<div class="field-row">'
            f'<label>Device or key name<input id="name" name="name" maxlength="100" required autocomplete="off" placeholder="Living room TV" value="{esc(draft.get("name", ""))}"></label>'
            f'<label>Resident name or email<input id="user" name="user" maxlength="254" autocomplete="off" value="{esc(draft.get("user", ""))}" aria-describedby="resident-attribution-help">'
            '<small id="resident-attribution-help" class="muted">Optional label for your records; this does not select or verify a resident account.</small></label>'
            '</div><div class="field-row">'
            '<label>Wi-Fi network (SSID)<select id="ssid_number" name="ssid_number" required>'
            + ('<option value="">Choose a Wi-Fi network</option>' + ssid_options if ssid_options else '<option value="">No Wi-Fi networks available</option>')
            + '</select></label></div><div class="field-row">'
            f'<label>Unit or room<input id="unit" name="unit" maxlength="80" autocomplete="off" value="{esc(draft.get("unit", ""))}"></label>'
            '<label>Access policy<select id="group_policy_id" name="group_policy_id" required aria-describedby="policy-help"><option value="">Choose an access policy</option>'
            + policy_options + '</select><small id="policy-help" class="muted">The Meraki group policy determines the access this key receives.</small></label>'
            '</div><div class="field-row">'
            '<label>Wi-Fi password<input id="passphrase" type="password" name="passphrase" autocomplete="new-password" minlength="8" maxlength="64" '
            r'pattern="[\x20-\x7E]{8,63}|[0-9A-Fa-f]{64}" aria-describedby="passphrase-help" placeholder="Generate one automatically">'
            '<small id="passphrase-help" class="muted">Leave blank to generate a password. Otherwise use 8–63 printable ASCII characters or 64 hexadecimal digits. Passwords are not kept after an error.</small></label>'
            '<label>Expires after<select class="preset js-only" data-for="duration_hours" aria-label="Expires after">'
            '<option value="0">No expiry</option><option value="24">1 day</option><option value="168">1 week</option>'
            '<option value="720">30 days</option><option value="" data-custom>Custom duration</option></select>'
            f'<input id="duration_hours" name="duration_hours" type="number" min="0" max="87600" step="1" required value="{esc(draft.get("duration_hours", "0"))}" aria-label="Custom duration in hours" aria-describedby="duration-help">'
            '<small id="duration-help" class="muted">Custom duration uses hours, up to 87,600; 0 means no expiry. No expiry keeps the key active until revoked.</small></label></div>'
            '<button class="btn" type="submit"' + (" disabled" if not os.environ.get("PORTAL_DB_HOST") or not selected_network or not ssid_options or not policy_options else "") + '>Create key and QR</button></form></div></div>'
        )
        create_form = guidance.form_error(create_form, error)
        invite_rows = []
        invite_dialogs = []
        for invite in invites:
            invite_label = invite.get("label") or f'Invitation #{int(invite["id"])}'
            status = "Used" if invite.get("used_at") else "Ready"
            revoke = "" if invite.get("used_at") else (
                f'<form method="post" action="{esc(self.url("/ipsk/invite/revoke"))}" data-confirm="invite-{int(invite["id"])}">{csrf}'
                f'<input type="hidden" name="invite_id" value="{int(invite["id"])}">'
                f'<button class="btn text danger" type="submit" aria-label="Revoke {esc(invite_label)}">Revoke</button></form>'
            )
            if not invite.get("used_at"):
                dialog_id = f"invite-{int(invite['id'])}"
                invite_dialogs.append(
                    f'<dialog id="{dialog_id}" aria-labelledby="{dialog_id}-title">'
                    f'<h2 id="{dialog_id}-title">Revoke {esc(invite_label)}?</h2>'
                    '<p>The unused code will stop working. You can create a new code at any time.</p>'
                    '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                    '<button type="button" class="btn danger" data-confirm-yes>Revoke</button></div></dialog>'
                )
            invite_rows.append(
                f'<tr><td data-label="Invitation">{esc(invite_label)}</td><td data-label="Created">{esc(fmt_time(invite["created_at"]))}</td><td data-label="By">{esc(invite["created_by"])}</td>'
                f'<td data-label="Status">{status}</td><td class="actions">{revoke}</td></tr>'
            )
        invites_card = (
            '<div class="card"><div class="card-header"><h2>Invitation codes</h2></div>'
            + f'<div class="card-content"><p>Create a single-use code for a resident who needs access.</p><form method="post" action="{esc(self.url("/ipsk/invite"))}">{csrf}'
            + f'<label>Resident or purpose<input id="label" name="label" maxlength="100" value="{esc(draft.get("label", ""))}" aria-describedby="invite-label-help"></label>'
            + '<p class="hint" id="invite-label-help">An optional label helps you identify the code later. It does not limit who can use it.</p>'
            + '<button class="btn" type="submit"' + (' disabled' if not os.environ.get('PORTAL_DB_HOST') else '') + '>Create invitation code</button></form></div>'
            + (f'<div class="table-wrap"><table class="ipsk-table"><thead><tr><th>Invitation</th><th>Created</th><th>By</th><th>Status</th><th>Actions</th></tr></thead>'
               f'<tbody>{"".join(invite_rows)}</tbody></table></div>' if invite_rows else
               '<div class="empty"><p class="empty-title">No active invitations</p><p class="muted">Create a code for a resident who needs access.</p></div>')
            + '</div>'
        )
        invites_card = guidance.form_error(invites_card, error)
        def device_key_link(row):
            ident = str(row.get("ipsk_id") or "")
            label = esc(row.get("ipsk_name") or ident or "—")
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,191}", ident):
                return label
            target = self.url("/ipsk") + "?" + urllib.parse.urlencode({"key_id": ident, "device_q": search,
                                                                       "device_sort": record_sort, "device_page": inventory["page"]})
            return f'<a href="{esc(target)}" aria-label="Manage key {label}">{label}</a>'
        resident_rows = "".join(
            f'<tr><td data-label="Resident">{esc(row["name"])}</td><td data-label="Email">{esc(row["email"])}</td><td data-label="Unit">{esc(row["unit"]) or "—"}</td>'
            f'<td data-label="Wi-Fi key">{device_key_link(row)}</td><td data-label="Device MAC"><code>{esc(row.get("mac_address")) or "—"}</code></td>'
            f'<td data-label="Registered">{esc(fmt_time(row["created_at"]))}</td></tr>' for row in residents
        )
        residents_card = (
            '<div class="card" id="registered-devices"><div class="card-header"><h2>Registered devices</h2>'
            + f'<p class="muted">{resident_count} registered device {"record" if resident_count == 1 else "records"}</p></div>'
            + management
            + (f'<div class="table-wrap"><table class="ipsk-table"><thead><tr><th>Name</th><th>Email</th><th>Unit</th><th>Wi-Fi key</th><th>Device MAC</th><th>Registered</th></tr></thead>'
               f'<tbody>{resident_rows}</tbody></table></div>' if resident_rows else
               '<div class="empty"><p class="empty-title">' + ('No matching device records' if search and resident_count else 'No residents registered')
               + '</p><p class="muted">' + ('Change or clear the search above.' if search and resident_count else 'New registrations will appear here.') + '</p></div>')
            + record_pager + '</div>'
        )
        key_rows = []
        key_dialogs = []
        for index, key in enumerate(keys):
            ident = str(key.get("id") or key.get("psk_group_id") or "")
            name = key.get("name") or "Unnamed key"
            state = str(key.get("status") or "unknown")
            chip_kind = "ok" if state == "active" else "bad" if state == "revoked" else "neutral"
            action_forms = ""
            if ident:
                actions = [("reveal", "Reveal")]
                if state == "active":
                    actions.append(("qr", "Show QR"))
                    actions.append(("revoke", "Revoke"))
                actions.append(("delete", "Delete"))
                for action, label in actions:
                    klass = ' class="btn text danger"' if action in ("revoke", "delete") else ' class="btn text"'
                    confirm_id = f"ipsk-{index}-{action}"
                    action_forms += (
                        f'<form method="post" action="{esc(self.url("/ipsk/key/action"))}"'
                        + (f' data-confirm="{confirm_id}"' if action in ("revoke", "delete") else "")
                        + f'>{csrf}' + context_fields +
                        f'<input type="hidden" name="ipsk_id" value="{esc(ident)}">'
                        f'<input type="hidden" name="action" value="{action}">'
                        f'<button{klass} type="submit" aria-label="{label} {esc(name)}">{label}</button></form>'
                    )
                    if action in ("revoke", "delete"):
                        operation = "Revoke" if action == "revoke" else "Delete"
                        consequence = "This will immediately remove the key's Wi-Fi access." if action == "revoke" else "This permanently removes the key from Meraki."
                        key_dialogs.append(
                            f'<dialog id="{confirm_id}" aria-labelledby="{confirm_id}-title">'
                            f'<h2 id="{confirm_id}-title">{operation} {esc(name)}?</h2>'
                            f'<p>{consequence}</p><div class="dialog-actions">'
                            '<button type="button" class="btn text" data-confirm-no>Cancel</button>'
                            f'<button type="button" class="btn danger" data-confirm-yes>{operation}</button>'
                            '</div></dialog>'
                        )
            assoc = key.get("associated_user") or key.get("associated_unit") or "—"
            key_rows.append(
                f'<tr><td data-label="Key">{esc(name)}<small class="muted">{esc(ident)}</small></td>'
                f'<td data-label="Wi-Fi network">{esc(key.get("ssid_name") or "—")}</td><td data-label="Resident">{esc(assoc)}</td>'
                f'<td data-label="Status">{ui.chip(chip_kind, state)}</td><td class="actions"><div class="row-actions">{action_forms}</div></td></tr>'
            )
        keys_card = (
            '<div class="card" id="device-keys"><div class="card-header"><h2>Wi-Fi keys</h2>'
            + f'<a class="btn" href="{esc(self.url("/ipsk/create"))}">{ui.icon("plus")}Create a key</a>'
            + f'<p class="muted">{key_count} Wi-Fi {"key" if key_count == 1 else "keys"} · Manage individual network access.</p></div>'
            + management
            + (f'<div class="table-wrap"><table class="ipsk-table"><thead><tr><th>Name / ID</th><th>SSID</th><th>Resident</th><th>Status</th><th>Actions</th></tr></thead>'
               f'<tbody>{"".join(key_rows)}</tbody></table></div>' if key_rows else
               '<div class="empty"><p class="empty-title">' + ('No matching keys' if key_count and (search or status != "all") else 'No iPSKs found')
               + '</p><p class="muted">' + ('Change or clear the filters above.' if key_count and (search or status != "all") else 'Keys created through resident registration will appear here.') + '</p></div>')
            + key_pager + '</div>'
        )
        content = {
            "keys": keys_card + "".join(key_dialogs),
            "devices": residents_card,
            "create": create_form,
            "invitations": invites_card + "".join(invite_dialogs),
            "join-codes": '<div class="page-head"><h2>Join codes</h2>'
                + f'<a class="btn text" href="{esc(self.url("/ipsk/join-codes/settings"))}">QR network settings</a></div>'
                + '<p class="muted">Share guest access or guide a resident to registration.</p>'
                + '<div class="wifi-join-grid" id="join-codes">' + "".join(qr_cards) + '</div>',
            "join-codes/settings": f'<p><a href="{esc(self.url("/ipsk/join-codes"))}">Back to join codes</a></p>' + qr_settings_card,
            "access": access_settings_card + intro,
        }[section]
        title = {"keys": "Wi-Fi keys", "devices": "Registered devices", "create": "Create a Wi-Fi key",
                 "invitations": "Invitations", "join-codes": "Join codes", "join-codes/settings": "QR network settings",
                 "access": "Access settings"}[section]
        if section == "create":
            content = f'<p><a href="{esc(self.url("/ipsk"))}">Back to Wi-Fi keys</a></p>' + content
        if section == "access":
            content += (f'<p class="hint"><a href="{esc(self.url("/tools/setup"))}">Setup and checks</a> · '
                        f'<a href="{esc(self.url("/tools/help"))}">Connection help</a></p>')
        content = guidance.form_error(content, error) if section in ("access", "join-codes/settings") else content
        # Keep table semantics explicit when phone layouts stack the cells.
        content = re.sub(r'<(table|thead|tbody|tr|th|td)(?=[\s>])',
                         lambda match: match[0] + ' role="' + {"table": "table", "thead": "rowgroup", "tbody": "rowgroup",
                                                              "tr": "row", "th": "columnheader", "td": "cell"}[match[1]] + '"', content)
        self.page("IPSK · " + title, notice + content, head="""<style>
                  #device-keys .card-header > p { max-width:none; width:100%; }
                  #device-keys td:first-child small { display:block; margin-top:4px; overflow-wrap:anywhere; }
                  .ipsk-table { width:100%; table-layout:fixed; }
                  .ipsk-table td { overflow-wrap:anywhere; white-space:normal; }
                  .ipsk-table td.actions { width:auto; }
                  .ipsk-table .row-actions { flex-wrap:wrap; }
                  #device-keys th:last-child { width:38%; }
                  .ipsk-filters { padding:8px 16px 16px; border-bottom:1px solid var(--divider-color); }
                  .ipsk-filters form { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:8px 16px; align-items:start; }
                  .ipsk-filters .field-row { grid-column:1 / -1; }
                  .ipsk-filters .sorting-options { margin:0; }
                  .ipsk-filters .sorting-options[open] { grid-column:1 / -1; }
                  .ipsk-filters .row-actions { justify-content:flex-end; flex-wrap:wrap; }
                  .ipsk-filters .sorting-options summary { cursor:pointer; min-height:44px; display:flex; align-items:center; color:var(--accent-ink); }
                  .ipsk-filters .sorting-options label { max-width:320px; }
                  .ipsk-nav { margin-bottom:24px; }
                  #create-device-key, #qr-settings, #resident-access-settings { max-width:760px; margin-inline:auto; }
                  #qr-settings fieldset + fieldset { margin-top:24px; }
                  .wifi-join-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }
                  .wifi-join-card code { overflow-wrap:anywhere; }
                  .wifi-join-card img { max-width:100%; height:auto; display:block; }
                  .wifi-join-card .btn { min-height:44px; }
                  #resident-access-settings .check { min-height:44px; }
                  #resident-access-settings fieldset { margin-top:24px; }
                  #resident-access-settings legend { font-weight:500; margin-bottom:12px; }
                  @media (max-width:640px) {
                    .wifi-join-grid { grid-template-columns:minmax(0,1fr); gap:0; }
                    main input, main select { font-size:16px; }
                    main .btn { min-height:44px; }
                    .ipsk-table, .ipsk-table tbody { display:block; width:100%; }
                    .ipsk-table thead { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
                    .ipsk-table tr { display:grid; grid-template-columns:minmax(0,1fr) auto; padding:16px; gap:8px 12px; border-bottom:1px solid var(--divider-color); }
                    .ipsk-table tr:last-child { border-bottom:0; }
                    .ipsk-table td { grid-column:1 / -1; padding:0; border:0; white-space:normal; overflow-wrap:anywhere; min-width:0; }
                    .ipsk-table td:first-child { font-size:16px; line-height:24px; font-weight:500; }
                    .ipsk-table tr:has(td[data-label="Status"]) > td:first-child { grid-column:1; }
                    .ipsk-table td[data-label="Status"] { grid-column:2; grid-row:1; }
                    .ipsk-table td[data-label]:not(:first-child):not([data-label="Status"]) { display:grid; grid-template-columns:90px minmax(0,1fr); gap:12px; }
                    .ipsk-table td[data-label]:not(:first-child):not([data-label="Status"])::before { content:attr(data-label); color:var(--secondary-text-color); font-weight:400; }
                    .ipsk-table .actions { width:auto; margin-top:8px; text-align:start; }
                    .ipsk-table .row-actions { justify-content:flex-start; flex-wrap:wrap; gap:4px; }
                    .ipsk-table .row-actions form { margin:0; }
                  }
                  </style>""")

    def tools_notice(self, query, added=""):
        if query.get("error"):
            return ui.alert("error", esc(query["error"][0]), "That did not work")
        if added and query.get("added"):
            return ui.alert("success", esc(added), "Done")
        return ""

    def tools_error(self, path, message):
        self.redirect(f"{path}?" + urllib.parse.urlencode({"error": str(message)[:300]}))

    # -- groups ------------------------------------------------------------------

    def groups_page(self, query, error="", values=None):
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        notice = ui.alert("error", esc(error), "The group was not saved") if error else ""
        failed = query.get("apply_error", [""])[0]
        if query.get("saved"):
            notice = ui.alert("success", f"Saved the group <b>{esc(query['saved'][0])}</b>."
                              + ("" if failed else " Devices can enroll in it now."), "Saved")
        elif query.get("deleted"):
            notice = ui.alert("success", f"Removed the group <b>{esc(query['deleted'][0])}</b>."
                              + ("" if failed else " Its SCEP URL no longer issues certificates."), "Removed")
        elif query.get("applied"):
            notice = ui.alert("success", "step-ca now uses the saved groups.", "Applied")
        elif query.get("error"):
            notice = ui.alert("error", esc(query["error"][0]), "That did not work")
        try:
            options = saved_options()
            groups = options.get("groups") or []
            readable = True
        except RuntimeError as err:
            options, readable = {}, False
            groups = [option_group(g) for g in GROUPS.values()]
            notice += ui.alert("warning", f"{esc(err)}<br>These are the running groups; saving is unavailable.",
                               "Could not read the saved add-on options")
        running = {g["name"]: group_key(g) for g in GROUPS.values()}
        saved = {g.get("name", ""): group_key(running_group(g)) for g in groups}
        if readable and saved != running:
            reason = (f"Applying them failed: {esc(failed)}<br>" if failed
                      else "The saved groups differ from the ones step-ca is using, for example after an edit "
                           "in the Configuration tab. ")
            notice += ui.alert(
                "warning",
                f"{reason}Apply them now, or restart the add-on if that keeps failing."
                f'<span class="alert-action">'
                f'<form method="post" action="{esc(self.url("/tools/groups/apply"))}">{csrf}'
                f'<button class="btn">{ui.icon("check")}Apply now</button></form>'
                f'<form method="post" action="{esc(self.url("/tools/restart"))}">{csrf}'
                f'<button class="btn text">{ui.icon("restart")}Restart add-on</button></form></span>',
                "Groups not applied")
        base = default_base_url(self.headers)

        rows = ""
        dialogs = ""
        for index, g in enumerate(groups):
            name = g.get("name", "")
            details = [f"OU={esc(g.get('organizational_unit', ''))}",
                       f"valid {esc(g['cert_duration'])}" if g.get("cert_duration") else "default lifetime",
                       "challenge set" if g.get("challenge") else "one-time links only"]
            if g.get("require_email"):
                details.append("email required")
            state = ""
            if readable and running.get(name) != saved.get(name):
                state = ui.chip("warn", "New" if name not in running else "Changed")
            scep = f"{base}/api/step_ca_scep/scep/{name}" if base else f".../api/step_ca_scep/scep/{name}"
            rows += (
                f'<div class="row"><span class="row-icon">{ui.icon("account-group")}</span>'
                f'<span class="row-text"><span class="row-title"><b>{esc(name)}</b> {state}</span>'
                f'<span class="row-sub">{" · ".join(details)}</span>'
                f'<span class="row-sub mono">{esc(scep)}</span></span><span class="row-actions">'
                + (ui.copy_button(g["challenge"], f"challenge for {name}") if g.get("challenge") else "")
                + (ui.copy_button(scep, f"SCEP URL for {name}") if base else "")
            )
            if readable:
                rows += (
                    f'<a class="icon-btn" href="{esc(self.url("/tools/groups?" + urllib.parse.urlencode({"edit": name})))}#group-form" '
                    f'aria-label="Edit {esc(name)}" title="Edit">{ui.icon("pencil")}</a>'
                    f'<form method="post" action="{esc(self.url(f"/tools/groups/{name}/delete"))}" '
                    f'data-confirm="delete-group-{index}">{csrf}'
                    f'<button class="icon-btn" aria-label="Remove {esc(name)}" title="Remove">'
                    f'{ui.icon("delete-outline")}</button></form>'
                )
                dialogs += (
                    f'<dialog id="delete-group-{index}" aria-labelledby="delete-group-{index}-title">'
                    f'<h2 id="delete-group-{index}-title">Remove the group {esc(name)}?</h2>'
                    "<p>After the restart its SCEP URL stops working, so devices and MDM profiles that use it "
                    "cannot get or renew certificates. Certificates already issued stay valid.</p>"
                    '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                    '<button type="button" class="btn danger" data-confirm-yes>Remove</button></div></dialog>'
                )
            rows += "</span></div>"
        rows = rows or ui.empty_state("account-group", "No groups yet",
                                      "Without groups every certificate uses the default SCEP URL and OU.")

        edit = (query.get("edit") or [""])[0]
        current = next((g for g in groups if g.get("name") == edit), None) if edit else None
        if values is None:
            values = {
                "original": edit if current else "",
                "name": (current or {}).get("name", ""),
                "ou": (current or {}).get("organizational_unit", ""),
                "challenge": (current or {}).get("challenge", ""),
                "cert_duration": (current or {}).get("cert_duration", ""),
                "require_email": "1" if (current or {}).get("require_email") else "",
            }
        form = self.group_form(csrf, values, options) if readable else ""
        body = (
            notice
            + '<div class="grid"><div>'
            '<div class="card"><div class="card-header"><h2>Certificate groups</h2>'
            '<p class="muted">Each group has its own SCEP URL and challenge, and every certificate it issues '
            "carries the group's OU, so your RADIUS server or Meraki Access Manager can tell adults, kids, and "
            "guests apart. Choose the group when you create enrollment links, issue .p12 files, or download "
            "MDM profiles.</p></div>"
            f'<div class="rows">{rows}</div></div>'
            "</div><div>" + form + "</div></div>" + dialogs
        )
        self.page("Groups", body)

    def group_form(self, csrf, values, options):
        v = lambda name: esc(values.get(name, ""))  # noqa: E731
        original = values.get("original", "")
        default = options.get("default_cert_duration") or "the default"
        durations = [("", f"Default ({esc(default)})"), ("168h", "7 days"), ("720h", "30 days"),
                     ("2160h", "90 days"), ("8760h", "1 year"), ("17520h", "2 years")]
        presets = "".join(f'<option value="{value}">{label}</option>' for value, label in durations)
        return (
            f'<form class="card" id="group-form" method="post" action="{esc(self.url("/tools/groups/save"))}">'
            f'{csrf}<input type="hidden" name="original" value="{v("original")}">'
            f'<div class="card-header"><h2>{"Edit " + esc(original) if original else "Add a group"}</h2>'
            '<p class="muted">Saved to the add-on options and applied to step-ca immediately.</p></div>'
            '<div class="card-content">'
            '<div class="field-row">'
            '<div class="field"><label for="g-name">Name</label>'
            f'<input id="g-name" name="name" required maxlength="32" pattern="[a-z0-9][a-z0-9_-]{{0,31}}" '
            f'autocapitalize="off" spellcheck="false" value="{v("name")}" placeholder="e.g. kids">'
            '<p class="hint">Lowercase letters, digits, _ and -. It ends the SCEP URL'
            + (", so renaming changes the URL in your MDM profiles" if original else "") + ".</p></div>"
            '<div class="field"><label for="g-ou">Organizational unit (OU)</label>'
            f'<input id="g-ou" name="ou" required maxlength="64" value="{v("ou")}" placeholder="e.g. Kids">'
            '<p class="hint">Every certificate in the group gets this OU.</p></div></div>'
            '<div class="field"><label for="g-challenge">Challenge</label><div class="input-action">'
            f'<input id="g-challenge" name="challenge" class="mono" maxlength="255" autocomplete="off" '
            f'autocapitalize="off" spellcheck="false" value="{v("challenge")}" placeholder="One-time links only">'
            f'<button type="button" class="btn text js-only" data-generate="g-challenge">{ui.icon("key-variant")}'
            "Generate</button></div>"
            '<p class="hint">The shared secret MDM profiles send to get a certificate in this group. Leave it '
            "empty to accept only one-time enrollment links. Changing it breaks profiles that use the old one."
            "</p></div>"
            '<div class="field"><label for="g-duration">Certificate lifetime</label>'
            f'<select class="preset js-only" data-for="g-duration" aria-label="Certificate lifetime">{presets}'
            '<option value="" data-custom>Custom…</option></select>'
            f'<input id="g-duration" name="cert_duration" maxlength="12" pattern="[0-9]+(h|m)" '
            f'autocapitalize="off" value="{v("cert_duration")}" placeholder="e.g. 720h; empty for the default">'
            '<p class="hint">Hours or minutes, such as 720h. Empty uses <b>default_cert_duration</b>.</p></div>'
            '<div class="field"><label class="check"><input type="checkbox" name="require_email" value="1"'
            f'{" checked" if values.get("require_email") else ""}>Require an email address</label>'
            '<p class="hint">Refuse certificate requests in this group without an email alternative name, for '
            "example when Meraki Access Manager matches the certificate's email to the user's Entra UPN. "
            "Enrollment links, .p12 files, and MDM profiles for the group then need an email.</p></div>"
            "</div><div class=\"card-actions\">"
            + (f'<a class="btn text" href="{esc(self.url("/tools/groups"))}">Cancel</a>' if original else "")
            + f'<button class="btn">{ui.icon("check")}Save group</button></div></form>'
        )

    def group_save(self, form):
        field = lambda name: str(form.get(name, [""])[0]).strip()  # noqa: E731
        values = {name: field(name) for name in ("original", "name", "ou", "challenge", "cert_duration",
                                                 "require_email")}
        original = values["original"]
        entry = {"name": values["name"], "organizational_unit": values["ou"]}
        if values["challenge"]:
            entry["challenge"] = values["challenge"]
        if values["cert_duration"]:
            entry["cert_duration"] = values["cert_duration"]
        if values["require_email"] == "1":
            entry["require_email"] = True
        try:
            options = saved_options()
            groups = list(options.get("groups") or [])
            if original and original not in [g.get("name") for g in groups]:
                raise ValueError(f"The group {original} no longer exists; it may have been removed elsewhere.")
            check_group_option(entry, [g for g in groups if g.get("name") != original], options)
            options["groups"] = ([entry if g.get("name") == original else g for g in groups]
                                 if original else groups + [entry])
            supervisor("POST", "/addons/self/options", {"options": options})
        except (ValueError, RuntimeError) as err:
            self.groups_page({}, str(err), values)
            return
        print(f"Saved the certificate group {entry['name']!r} (OU={entry['organizational_unit']})", flush=True)
        self.redirect("/tools/groups?" + urllib.parse.urlencode({"saved": entry["name"],
                                                                  **self.apply_saved(options["groups"])}))

    def group_delete(self, name):
        try:
            options = saved_options()
            groups = options.get("groups") or []
            options["groups"] = [g for g in groups if g.get("name") != name]
            if len(options["groups"]) != len(groups):
                supervisor("POST", "/addons/self/options", {"options": options})
        except RuntimeError as err:
            self.tools_error("/tools/groups", err)
            return
        print(f"Removed the certificate group {name!r}", flush=True)
        self.redirect("/tools/groups?" + urllib.parse.urlencode({"deleted": name,
                                                                  **self.apply_saved(options["groups"])}))

    @staticmethod
    def apply_saved(groups):
        """Apply saved groups to step-ca; the query to report a failure with."""
        try:
            apply_groups(groups)
        except RuntimeError as err:
            print(f"Could not apply the certificate groups: {err}", flush=True)
            return {"apply_error": str(err)}
        return {}

    def groups_apply(self):
        try:
            groups = saved_options().get("groups") or []
        except RuntimeError as err:
            self.tools_error("/tools/groups", err)
            return
        failed = self.apply_saved(groups)
        self.redirect("/tools/groups?" + urllib.parse.urlencode(failed or {"applied": "1"}))

    def restart_addon(self):
        if not SUPERVISOR_TOKEN:
            self.tools_error("/tools/groups", "The Supervisor API is not available.")
            return
        print("Restarting the add-on from the management page", flush=True)
        back = self.url("/tools/groups")
        self.page(
            "Restarting",
            '<div class="card">' + ui.empty_state(
                "restart", "Restarting the add-on",
                "This takes about a minute. The page reloads by itself; if Home Assistant shows that the app "
                f'is starting, wait and then <a href="{esc(back)}">open Groups</a> again.') + "</div>",
            narrow=True, head=f'<meta http-equiv="refresh" content="45;url={esc(back)}">')

        def restart():
            time.sleep(1)
            try:
                supervisor("POST", "/addons/self/restart")
            except RuntimeError as err:
                print(f"Could not restart the add-on: {err}", flush=True)

        threading.Thread(target=restart, name="restart", daemon=True).start()

    # -- Wi-Fi network ------------------------------------------------------------

    def wifi_page(self, query, error="", values=None):
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        notice = ui.alert("error", esc(error), "The network was not saved") if error else ""
        later = (" Profiles already on devices or uploaded to an MDM keep the old settings until you replace "
                 "them.")
        if query.get("saved"):
            notice = ui.alert("success", f"New profiles set up <b>{esc(query['saved'][0])}</b> with these "
                              f"settings now.{later}", "Saved")
        elif query.get("deleted"):
            notice = ui.alert("success", f"New profiles leave out <b>{esc(query['deleted'][0])}</b>.{later}",
                              "Removed")
        elif query.get("error"):
            notice = ui.alert("error", esc(query["error"][0]), "That did not work")
        try:
            networks = wifi_networks(saved_options())
            readable = True
        except RuntimeError as err:
            networks, readable = list(WIFI_NETWORKS), False
            notice += ui.alert("warning", f"{esc(err)}<br>These are the running settings; saving is "
                               "unavailable.", "Could not read the saved add-on options")
        rows = dialogs = ""
        for index, w in enumerate(networks):
            name = enroll.wifi_name(w)
            service = enroll.radius_service(w)
            details = [esc(enroll.WIFI_AUTH.get(w["authentication"], ("Unknown method",))[0]) + f" · {esc(w['security'])}"]
            if service and w["authentication"] != "psk":
                details.append(esc(service["label"]))
            details += [label for flag, label in (
                (w["passpoint"], "Passpoint"), (w["hidden"], "hidden"), (not w["auto_join"], "no auto-join"),
                (w["disable_mac_randomization"], "fixed Wi-Fi address"), (w["proxy"] != "none", f"{w['proxy']} proxy"),
                (w["captive_bypass"], "captive portal bypass"), (w["mac_login_window"], "Mac login window"),
                (w["qos_marking"] != "default", f"QoS {'off' if w['qos_marking'] == 'off' else 'listed apps'}"))
                if flag]
            if name != enroll.wifi_ssid(w):
                details.insert(0, f"SSID {esc(enroll.wifi_ssid(w))}")
            if not w["include_by_default"]:
                details.append("own profile only")
            edit = self.url("/tools/wifi?" + urllib.parse.urlencode({"edit": name}))
            rows += (
                f'<div class="row"><span class="row-icon">{ui.icon("wifi")}</span>'
                f'<span class="row-text"><span class="row-title"><b>{esc(name)}</b></span>'
                f'<span class="row-sub">{" · ".join(details)}</span></span><span class="row-actions">'
            )
            if readable:
                rows += (
                    f'<a class="icon-btn" href="{esc(edit)}#wifi-form" aria-label="Edit {esc(name)}" title="Edit">'
                    f'{ui.icon("pencil")}</a>'
                    f'<form method="post" action="{esc(self.url("/tools/wifi/delete"))}" '
                    f'data-confirm="delete-wifi-{index}">{csrf}<input type="hidden" name="name" value="{esc(name)}">'
                    f'<button class="icon-btn" aria-label="Remove {esc(name)}" title="Remove">'
                    f'{ui.icon("delete-outline")}</button></form>'
                )
                dialogs += (
                    f'<dialog id="delete-wifi-{index}" aria-labelledby="delete-wifi-{index}-title">'
                    f'<h2 id="delete-wifi-{index}-title">Remove the network {esc(name)}?</h2>'
                    "<p>New profiles leave it out. Devices that already have a profile keep the network until "
                    "they install a new one or remove the profile.</p>"
                    '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
                    '<button type="button" class="btn danger" data-confirm-yes>Remove</button></div></dialog>'
                )
            rows += "</span></div>"
        rows = rows or ui.empty_state("wifi", "No Wi-Fi networks",
                                      "Profiles install the certificate only. Add a network to set up Wi-Fi too.")
        edit = (query.get("edit") or [""])[0]
        current = next((w for w in networks if enroll.wifi_name(w) == edit), None) if edit else None
        if values is None:
            values = dict(current or wifi_settings({}), original=edit if current else "")
        form = self.wifi_form(csrf, values) if readable else ""
        body = (
            notice
            + '<nav class="page-jumps" aria-label="Wi-Fi setup"><a href="#wifi-form">Network editor</a>'
            '<a href="#saved-networks">Saved networks &amp; guide</a></nav>'
            '<div class="network-layout"><div>' + form + '</div>'
            '<aside id="saved-networks" aria-label="Saved networks and setup guide">'
            '<div class="card"><div class="card-header"><h2>Saved networks</h2>'
            '<p class="muted">Apple profiles configure these networks. Other devices receive setup instructions.</p>'
            f'<a class="btn text" href="{esc(self.url("/tools/wifi"))}#wifi-form">'
            f'{ui.icon("plus")}Add network</a></div><div class="rows">{rows}</div></div>'
            + self.wifi_guide() + '</aside></div>' + dialogs
        )
        self.page("Wi-Fi networks", body)

    def wifi_guide(self):
        methods = "".join(
            f'<div class="method-row"><b>{esc(label)}</b><span class="muted">{esc(credential)}</span></div>'
            for label, _, credential in enroll.WIFI_AUTH.values())
        return (
            '<div class="card"><div class="card-header"><h2>Before you enroll</h2></div>'
            '<div class="card-content"><ol class="steps">'
            '<li>Match the SSID, security, and EAP method to your wireless network.</li>'
            '<li>For TLS methods, trust the RADIUS server CA and check its certificate names.</li>'
            '<li>Save, download a new profile, then test it on one device before sharing it.</li></ol>'
            f'<p class="step-action"><a href="{esc(self.url("/tools/mdm"))}">Download an MDM profile</a></p>'
            '<p class="hint">Saving changes future profiles. Installed profiles need to be replaced. '
            'These settings configure clients; they do not configure your access point or RADIUS server.</p>'
            '</div><details class="expand"><summary><span class="summary-text">'
            '<span class="summary-title">Choose an authentication method</span></span>'
            f'{ui.icon("chevron-down", "chev")}</summary><div class="expand-body">{methods}'
            '<p class="hint">SIM/AKA need a compatible carrier SIM on iPhone or iPad. LEAP is for legacy networks. '
            'TEAP, EAP-PWD, and EAP-AKA′ are not offered by Apple’s managed Wi-Fi payload.</p>'
            '</div></details></div>'
        )

    def wifi_form(self, csrf, values):
        values = dict(wifi_settings(values), original=values.get("original", ""))
        original = values["original"]
        v = lambda name: esc(values.get(name) or "")  # noqa: E731
        lines = lambda name: esc(chr(10).join(values[name]))  # noqa: E731
        check = lambda name: " checked" if values.get(name) else ""  # noqa: E731
        select = lambda name, choices: "".join(  # noqa: E731
            f'<option value="{key}"{" selected" if values[name] == key else ""}>{esc(label)}</option>'
            for key, label in choices)

        def checkbox(name, label, hint="", field_id=""):
            return (f'<div class="field"><label class="check"><input type="checkbox" name="{name}" value="1"'
                    f'{f" id={chr(34)}{field_id}{chr(34)}" if field_id else ""}{check(name)}>{label}</label>'
                    + (f'<p class="hint">{hint}</p>' if hint else "") + "</div>")

        def text(name, label, hint="", placeholder="", field_id="", **attrs):
            extra = "".join(f' {k.replace("_", "-")}="{esc(val)}"' for k, val in attrs.items())
            return (f'<div class="field"><label for="{field_id or "w-" + name}">{label}</label>'
                    f'<input id="{field_id or "w-" + name}" name="{name}" value="{v(name)}" '
                    f'placeholder="{esc(placeholder)}" spellcheck="false"{extra}>'
                    + (f'<p class="hint">{hint}</p>' if hint else "") + "</div>")

        def textarea(name, label, hint, placeholder):
            return (f'<div class="field"><label for="w-{name}">{label}</label>'
                    f'<textarea id="w-{name}" name="{name}" rows="2" class="mono" autocapitalize="off" '
                    f'spellcheck="false" placeholder="{esc(placeholder)}">{lines(name)}</textarea>'
                    f'<p class="hint">{hint}</p></div>')

        def section(title, content, open_=False):
            return (f'<details class="form-section"{" open" if open_ else ""}>'
                    f'<summary><span class="summary-title">{title}</span>{ui.icon("chevron-down", "chev")}</summary>'
                    f'<div class="section-body">{content}</div></details>')

        auth = select("authentication", [(key, f"{label} — {credential}")
                                         for key, (label, _, credential) in enroll.WIFI_AUTH.items()])
        security = select("security", (("WPA2", "WPA2"), ("WPA3", "WPA3"), ("Any", "Any (includes legacy WPA / WEP)")))
        radius = select("radius_server", [("custom", "My own RADIUS server")]
                        + [(key, service["label"]) for key, service in enroll.RADIUS_SERVICES.items()])
        proxy = select("proxy", (("none", "None"), ("manual", "Manual"), ("auto", "Automatic")))
        qos = select("qos_marking", (("default", "All apps (default)"), ("allowlist", "Only the apps below"),
                                     ("off", "Off")))
        saved_password = bool(original and values["password"])
        saved_proxy_password = bool(original and values["proxy_password"])
        saved_eap_password = bool(original and values["eap_password"])
        credentials = (
            '<div data-show-when="w-auth=eap_tls|peap|eap_ttls|eap_fast|leap">'
            + text("eap_username", "802.1X identity (optional)",
                   "For EAP-TLS, empty uses the certificate name. For password methods, empty asks for a "
                   "RADIUS account on the device.",
                   "e.g. alex@example.com", maxlength="255", autocomplete="off")
            + '<div data-show-when="w-auth=peap|eap_ttls|eap_fast|leap">'
            '<div class="field"><label for="w-eap_password">802.1X password (optional)</label>'
            '<input id="w-eap_password" name="eap_password" type="password" maxlength="255" '
            'autocomplete="new-password" placeholder="'
            + ("Leave empty to keep the saved password" if saved_eap_password else "Ask on the device") + '">'
            '<p class="hint">A saved password is included in every downloaded profile using this network. '
            'Leave it empty for individual accounts.</p></div>'
            + (checkbox("clear_eap_password", "Remove the saved 802.1X password",
                        "The next profile asks for a password on the device.") if saved_eap_password else "")
            + '<div data-show-when="w-auth=peap|eap_ttls|eap_fast">'
            + checkbox("eap_password_per_connection", "Ask for a password on every connection",
                       "For per-connection credentials. This removes any saved 802.1X password.")
            + text("eap_outer_identity", "Outer identity (optional)",
                   "Hides the account name outside the encrypted tunnel. Match your RADIUS realm; required "
                   "when the minimum TLS version is 1.3.", "anonymous@example.com", maxlength="255")
            + checkbox("eap_client_certificate", "Also require the device certificate",
                       "Use only when RADIUS requires both a certificate and account credentials.")
            + '</div></div></div><div data-show-when="w-auth=eap_ttls" class="field">'
            '<label for="w-inner">Inner authentication</label>'
            f'<select id="w-inner" name="ttls_inner_authentication">'
            f'{select("ttls_inner_authentication", [(x, x) for x in enroll.TTLS_INNER])}</select>'
            '<p class="hint">Match the method inside the TTLS tunnel on your RADIUS server.</p></div>'
            '<div data-show-when="w-auth=eap_fast">'
            + checkbox("eap_fast_use_pac", "Use a Protected Access Credential (PAC)",
                       "Leave off to authenticate the server with its certificate.")
            + checkbox("eap_fast_provision_pac", "Provision PAC from the server",
                       "Enable together with Use PAC. Anonymous provisioning is disabled.")
            + '</div><div data-show-when="w-auth=eap_sim|eap_aka">'
            + ui.alert("info", "Requires an iPhone or iPad with a compatible carrier SIM and a RADIUS service "
                       "that supports this method. The SIM supplies the identity; the issued certificate "
                       "does not sign the device into Wi-Fi.", "Carrier authentication")
            + '</div><div class="field" data-show-when="w-auth=eap_sim">'
            '<label for="w-rands">Minimum SIM challenges (RANDs)</label>'
            f'<select id="w-rands" name="eap_sim_rands">'
            f'{select("eap_sim_rands", [(3, "3 (default)"), (2, "2 (carrier compatibility)")])}</select></div>'
            '<div data-show-when="w-auth=leap">'
            + ui.alert("warning", "Use only for an existing network that requires LEAP. It has no TLS tunnel "
                       "and does not use the server-certificate trust settings below.", "Legacy authentication")
            + '</div>'
        )
        return (
            f'<form class="card" id="wifi-form" method="post" action="{esc(self.url("/tools/wifi/save"))}">{csrf}'
            f'<input type="hidden" name="original" value="{v("original")}">'
            f'<div class="card-header"><h2>{"Edit " + esc(original) if original else "Add a network"}</h2>'
            '<p class="muted">Configure the device profile to match your access point and RADIUS server. '
            'Saving applies to new downloads immediately.</p></div>'
            '<div class="network-summary" aria-live="polite" data-network-summary></div>'
            '<div class="card-content network-fields">'
            + section("Network details", text("name", "Profile name (optional)",
                   "Tells networks apart here and in the MDM downloads, so one SSID can have several profiles "
                   "(for example Office iPhone and Office Mac). Empty uses the SSID.", "e.g. Office Mac",
                   maxlength="64", autocapitalize="sentences")
            + text("ssid", "Network name (SSID)", "Exactly as the network broadcasts it, including case.",
                   "e.g. Home", maxlength="32")
            + checkbox("include_by_default", "Include in every profile",
                       "Enrollment links, Enroll this device, and the MDM profile with every network set it up. "
                       "Turn off for a network you download on its own from Tools > MDM profiles."), True)
            + section("Authentication", '<div class="field"><label for="w-auth">802.1X / network authentication</label>'
            f'<select id="w-auth" name="authentication">{auth}</select>'
            '<p class="hint">Match the method enabled on RADIUS. EAP-TLS uses the certificate from this CA; '
            'password methods use a RADIUS account; a pre-shared key uses one network password.</p></div>'
            '<div class="field"><label for="w-security">Security</label>'
            f'<select id="w-security" name="security">{security}</select>'
            '<p class="hint">WPA2 permits WPA2/WPA3 on current Apple devices. WPA3 requires WPA3. '
            'Any also permits legacy WPA/WEP; use only when needed.</p></div>'
            '<div class="field" data-show-when="w-auth=psk"><label for="w-password">Password</label>'
            '<input id="w-password" name="password" type="password" maxlength="64" autocomplete="new-password" '
            f'placeholder="{"Leave empty to keep the saved password" if saved_password else "8 to 63 characters"}">'
            '<p class="hint">The shared password is included in profiles using this network.</p></div>'
            + credentials, True)
            + section("Connection behavior", checkbox("auto_join", "Join automatically")
            + checkbox("hidden", "Hidden network", "Turn on when the SSID is not broadcast.")
            + checkbox("disable_mac_randomization", "Fixed Wi-Fi address",
                       "Turns off Private Wi-Fi Address for this network, so the device always uses its real MAC "
                       "address here (for DHCP reservations or MAC-based rules). iOS 14 and macOS 15 or later; "
                       "devices show a privacy warning for the network."), bool(values["hidden"] or values["disable_mac_randomization"]))
            + '<div data-show-when="w-auth=eap_tls|peap|eap_ttls|eap_fast">'
            + section("Server trust & TLS", '<div>'
            '<div class="field"><label for="w-radius">RADIUS server</label>'
            f'<select id="w-radius" name="radius_server">{radius}</select>'
            '<p class="hint">With Cisco Meraki Access Manager, profiles trust its server '
            "(eap.meraki.com, under IdenTrust Commercial Root CA 1) without anything else to add. With your "
            f'own server, add the CA that issued its certificate under <a href="{esc(self.url("/tools/cas"))}">'
            "Other trusted CAs</a> if it is not this CA.</p></div>"
            + textarea(
                "radius_server_names", "RADIUS server names (optional)",
                "List the names on the RADIUS server certificate, one per line. Empty accepts any name under "
                "the trusted CAs. Set names to restrict trust, especially for a public CA. Meraki's name is "
                "included automatically.", "radius.example.com")
            + '<div class="field-row"><div class="field"><label for="w-tls-min">Minimum TLS version</label>'
            f'<select id="w-tls-min" name="tls_minimum">'
            f'{select("tls_minimum", [("1.2", "TLS 1.2"), ("1.3", "TLS 1.3")])}</select></div>'
            '<div class="field"><label for="w-tls-max">Maximum TLS version</label>'
            f'<select id="w-tls-max" name="tls_maximum">'
            f'{select("tls_maximum", [("", "Device default"), ("1.2", "TLS 1.2"), ("1.3", "TLS 1.3")])}</select>'
            '</div></div><p class="hint">TLS 1.2 is the compatibility default. To require TLS 1.3, set both '
            'limits to 1.3 and check support on your devices and RADIUS server.</p></div>', True)
            + "</div>"
            + section("Proxy", (
                '<div class="field"><label for="w-proxy">Proxy</label>'
                f'<select id="w-proxy" name="proxy">{proxy}</select>'
                '<p class="hint">A web proxy for this network only. iPhone and iPad; Macs take the manual server '
                "and the PAC URL too.</p></div>"
                '<div data-show-when="w-proxy=manual"><div class="field-row">'
                + text("proxy_server", "Server", "", "proxy.example.com", maxlength="253")
                + text("proxy_port", "Port", "", "8080", inputmode="numeric", maxlength="5")
                + "</div><div class=\"field-row\">"
                + text("proxy_username", "User name (optional)", "", "", maxlength="255", autocomplete="off")
                + '<div class="field"><label for="w-proxy_password">Password (optional)</label>'
                '<input id="w-proxy_password" name="proxy_password" type="password" maxlength="255" '
                'autocomplete="new-password" placeholder="'
                + ("Leave empty to keep the saved password" if saved_proxy_password else "") + '"></div>'
                "</div></div>"
                '<div data-show-when="w-proxy=auto">'
                + text("proxy_pac_url", "PAC URL (optional)", "Empty finds the proxy with WPAD.",
                       "http://wpad.example.com/proxy.pac", maxlength="2000")
                + checkbox("proxy_pac_fallback", "Connect directly when the PAC file cannot be reached")
                + "</div>"), values["proxy"] != "none")
            + section("Device-specific behavior", (
                checkbox("captive_bypass", "Skip captive portal detection",
                         "The device does not check for a sign-in page on this network or show the captive portal "
                         "sheet. iPhone and iPad.")
                + checkbox("mac_login_window", "Mac: connect at the login window",
                           "The Mac joins before anyone signs in, using the certificate in the System keychain, so "
                           "network accounts can connect. Requires EAP-TLS; the profile installs for the whole "
                           "Mac and needs administrator approval. This does not enable Wi-Fi in FileVault preboot.")), values["captive_bypass"] or values["mac_login_window"])
            + section("QoS (Cisco Fast Lane)", (
                '<div class="field"><label for="w-qos">QoS marking</label>'
                f'<select id="w-qos" name="qos_marking">{qos}</select>'
                '<p class="hint">On Cisco and Meraki networks with Fast Lane, apps can mark their traffic for '
                "priority. Off makes the device ignore Fast Lane on this network.</p></div>"
                '<div data-show-when="w-qos=allowlist">'
                + checkbox("qos_apple_calls", "Include FaceTime and Wi-Fi Calling")
                + textarea("qos_apps", "App bundle IDs", "One per line.", "com.microsoft.teams\ncom.cisco.webex.meetings")
                + "</div>"), values["qos_marking"] != "default")
            + section("Passpoint (Hotspot 2.0)", (
                checkbox("passpoint", "Passpoint network",
                         "Devices find and join the network by its Passpoint domain or roaming consortium instead of "
                         "only its SSID. Use an enterprise EAP method; the SSID is then optional. Shared keys and LEAP are unsupported.", "w-passpoint")
                + '<div data-show-when="w-passpoint=1">'
                + text("passpoint_domain", "Domain", "The Passpoint (home operator) domain name.", "example.com",
                       maxlength="253")
                + text("passpoint_operator_name", "Operator name (optional)", "Shown when connected.",
                       "Example Wi-Fi", maxlength="64", autocapitalize="sentences")
                + textarea("passpoint_roaming_consortium_ois", "Roaming consortium OIs (optional)",
                           "One per line, 6 or 10 hex digits.", "5A03BA")
                + textarea("passpoint_nai_realms", "NAI realms (optional)", "One per line.", "example.com")
                + textarea("passpoint_mcc_mncs", "MCC/MNC pairs (optional)",
                           "One per line, six digits. iPhone and iPad.", "310410")
                + text("passpoint_hessid", "HESSID (optional)", "iPhone and iPad.", "00:11:22:33:44:55",
                       maxlength="17")
                + checkbox("passpoint_roaming", "Allow roaming to partner service providers")
                + "</div>"), values["passpoint"])
            + '</div><div class="card-actions">'
            + (f'<a class="btn text" href="{esc(self.url("/tools/wifi"))}">Cancel</a>' if original else "")
            + f'<button class="btn">{ui.icon("check")}Save network</button></div></form>'
        )

    def wifi_save(self, form):
        field = lambda name: str(form.get(name, [""])[0])  # noqa: E731
        listed = lambda name: list(dict.fromkeys(  # noqa: E731
            n.strip() for n in re.split(r"[\s,]+", field(name)) if n.strip()))
        original = field("original")
        port = field("proxy_port").strip()
        values = {
            "original": original, "name": field("name").strip(), "ssid": field("ssid"), "authentication": field("authentication"),
            "password": field("password"), "security": field("security"),
            "proxy": field("proxy"), "proxy_server": field("proxy_server"),
            "proxy_port": int(port) if port.isdigit() and len(port) <= 5 else (-1 if port else None),
            "proxy_username": field("proxy_username"), "proxy_password": field("proxy_password"),
            "proxy_pac_url": field("proxy_pac_url"), "qos_marking": field("qos_marking"),
            "passpoint_domain": field("passpoint_domain"), "passpoint_operator_name": field("passpoint_operator_name"),
            "passpoint_hessid": field("passpoint_hessid"),
            **{name: field(name) == "1" for name in (
                "include_by_default", "hidden", "auto_join", "disable_mac_randomization", "proxy_pac_fallback", "captive_bypass",
                "mac_login_window", "qos_apple_calls", "passpoint", "passpoint_roaming")},
            **{name: listed(name) for name in WIFI_LISTS},
        }
        values["radius_server"] = field("radius_server")
        values.update({name: field(name) for name in ("eap_username", "eap_password", "eap_outer_identity",
                                                     "ttls_inner_authentication", "tls_minimum", "tls_maximum")})
        values.update({name: field(name) == "1" for name in ("eap_password_per_connection", "eap_client_certificate",
                                                            "eap_fast_use_pac", "eap_fast_provision_pac")})
        rands = field("eap_sim_rands") or "3"
        values["eap_sim_rands"] = int(rands) if rands in ("2", "3") else -1
        try:
            options = saved_options()
            networks = wifi_networks(options)
            names = [enroll.wifi_name(n) for n in networks]
            if original and original not in names:
                raise ValueError(f"The network {original} no longer exists; it may have been removed elsewhere.")
            saved = networks[names.index(original)] if original else {}
            for secret in ("password", "proxy_password", "eap_password"):
                if not values[secret] and saved:
                    values[secret] = saved[secret]
            if values["proxy_port"] == -1:
                raise ValueError("Enter the proxy port, 1 to 65535.")
            network = wifi_settings(values)
            network["proxy_port"] = values["proxy_port"]
            if network["authentication"] not in enroll.TUNNELED_EAP:
                network["eap_password_per_connection"] = False
                network["eap_client_certificate"] = False
            others = [n for n in networks if enroll.wifi_name(n) != original]
            check_wifi_option(network, others)
            if network["authentication"] != "psk":
                network["password"] = ""
            if network["authentication"] not in enroll.PASSWORD_EAP or (
                    network["authentication"] in enroll.TUNNELED_EAP and network["eap_password_per_connection"]):
                network["eap_password"] = ""
            if field("clear_eap_password") == "1":
                network["eap_password"] = ""
            networks = ([network if enroll.wifi_name(n) == original else n for n in networks]
                        if original else networks + [network])
            self.save_wifi_networks(options, networks)
        except (ValueError, RuntimeError) as err:
            self.wifi_page({}, str(err), values)
            return
        name = enroll.wifi_name(network)
        print(f"Saved the Wi-Fi network {name!r} ({network['authentication']}, {network['security']}"
              + (f", RADIUS {network['radius_server']}" if network["authentication"] != "psk" else "") + ")",
              flush=True)
        self.redirect("/tools/wifi?" + urllib.parse.urlencode({"saved": name}))

    def wifi_delete(self, form):
        name = str(form.get("name", [""])[0])
        try:
            options = saved_options()
            networks = wifi_networks(options)
            remaining = [n for n in networks if enroll.wifi_name(n) != name]
            if len(remaining) != len(networks):
                self.save_wifi_networks(options, remaining)
        except RuntimeError as err:
            self.tools_error("/tools/wifi", err)
            return
        print(f"Removed the Wi-Fi network {name!r}", flush=True)
        self.redirect("/tools/wifi?" + urllib.parse.urlencode({"deleted": name}))

    @staticmethod
    def save_wifi_networks(options, networks):
        """Save the networks to the add-on options and use them right away."""
        options["wifi_networks"] = [wifi_option(n) for n in networks]
        if (options.get("wifi") or {}).get("ssid"):
            # The older single-network option, now moved into wifi_networks.
            options["wifi"] = {**options["wifi"], "ssid": ""}
        supervisor("POST", "/addons/self/options", {"options": options})
        WIFI_NETWORKS[:] = [wifi_settings(n) for n in networks]

    # -- other tools ---------------------------------------------------------------

    def options_page(self):
        def option(label, value):
            return ui.kv_row(label, value)

        challenge = (ui.chip("ok", "Set") if SCEP_CHALLENGE else
                     ui.chip("warn", "Not set") + " Needed for MDM profiles in the default group")
        wifi = "<br>".join(
            f"<b>{esc(enroll.wifi_name(w))}</b>, " + esc(enroll.WIFI_AUTH.get(w["authentication"], ("Unknown method",))[0])
            + (f", RADIUS {esc(service['label'])} ({esc(', '.join(service['server_names']))})"
               if (service := enroll.radius_service(w)) and w["authentication"] in enroll.TLS_EAP else "")
            for w in WIFI_NETWORKS) or "Off"
        groups = "<br>".join(
            f"<b>{esc(g['name'])}</b>: OU={esc(g['ou'])}, "
            + (f"valid {esc(g['duration'])}, " if g["duration"] else "")
            + ("challenge set" if g["challenge"] else "one-time links only")
            + (", email required" if g.get("require_email") else "")
            for g in GROUPS.values()) or "None"
        body = (
            '<div class="card"><div class="card-header"><h2>Running configuration</h2>'
            f'<p class="muted">The running configuration. Edit groups under <a href="{esc(self.url("/tools/groups"))}">'
            f'Groups</a> and the networks under <a href="{esc(self.url("/tools/wifi"))}">Wi-Fi networks</a>; '
            "change the rest on the add-on's Configuration tab in Home Assistant.</p></div>"
            '<dl class="rows">'
            + option("Issued subject", esc(SUBJECT_POLICY) if SUBJECT_POLICY else "Taken from the client request")
            + option("SCEP challenge", challenge)
            + option("Groups", groups)
            + option("Wi-Fi", wifi)
            + option("Storage", "MariaDB" if db_enabled() else "Embedded database")
            + "</dl></div>"
        )
        self.page("Add-on options", body, narrow=True)

    def cas_page(self, query):
        extra = enroll.load_extra_cas()
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'

        def issuer_name(cert):
            cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
            return cn[0].value if cn else cert.issuer.rfc4514_string()

        extra_rows = "".join(
            f'<div class="row"><span class="row-icon">{ui.icon("server-security")}</span>'
            f'<span class="row-text"><span class="row-title">{esc(enroll.common_name(cert))}</span>'
            f'<span class="row-sub">Issued by {esc(issuer_name(cert))}'
            f' · until {cert.not_valid_after_utc:%Y-%m-%d}</span>'
            f'<span class="row-sub mono">{esc(enroll.fingerprint(cert)[:32])}…</span></span>'
            '<span class="row-actions">'
            f'<a class="icon-btn" href="{esc(self.url(f"/download/extra/{enroll.fingerprint(cert)}.pem"))}" '
            f'aria-label="Download {esc(safe_filename(enroll.common_name(cert)))}.pem" title="Download">{ui.icon("download")}</a>'
            f'<form method="post" action="{esc(self.url(f"/ca/extra/{enroll.fingerprint(cert)}/remove"))}">{csrf}'
            f'<button class="icon-btn" aria-label="Remove {esc(enroll.common_name(cert))}" title="Remove">'
            f'{ui.icon("delete-outline")}</button></form></span></div>'
            for cert in extra
        )
        body = (
            self.tools_notice(query, "New profiles and .p12 files include the certificate.")
            + '<div class="card"><div class="card-header"><h2>Device trust certificates</h2>'
            '<p class="muted">CA certificates devices must also trust, such as the CA that issued your RADIUS '
            "server's certificate for enterprise Wi-Fi. They are added to Apple profiles (and trusted for the "
            "Wi-Fi network), to .p12 files, and to ca-bundle.pem.</p></div>"
            + (f'<div class="rows">{extra_rows}</div>' if extra else "")
            + f'<form class="card-content" method="post" enctype="multipart/form-data" action="{esc(self.url("/ca/extra"))}">'
            f"{csrf}"
            '<div class="field"><label for="file">Certificate file (.pem, .crt, .cer)</label>'
            '<input id="file" type="file" name="file" accept=".pem,.crt,.cer,.der"></div>'
            '<div class="field"><label for="pem">Or paste PEM</label>'
            '<textarea id="pem" name="pem" rows="4" placeholder="-----BEGIN CERTIFICATE-----"></textarea></div>'
            f'<button class="btn">{ui.icon("plus")}Add certificate</button></form></div>'
        )
        self.page("Other trusted CAs", body, narrow=True)

    def sign_page(self, query):
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        years = enroll.SUBORDINATE_DAYS // 365

        def detail(rows):
            return '<dl class="choice-detail">' + "".join(
                f'<div class="kv"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows) + "</dl>"

        body = (
            self.tools_notice(query)
            + '<div class="card"><div class="card-header"><h2>Upload a certificate request</h2>'
            "<p class=\"muted\">CSRs from servers, VPNs, or another CA such as Meraki's SCEP CA. The download "
            "holds the signed certificate followed by its CA chain.</p></div>"
            f'<form class="card-content" method="post" enctype="multipart/form-data" action="{esc(self.url("/ca/sign"))}">'
            f"{csrf}"
            '<div class="choices field">'
            '<label class="choice"><input type="radio" name="kind" value="leaf" checked>'
            f'<span class="choice-icon">{ui.icon("server-security")}</span><span>'
            '<span class="choice-title">Server or client certificate</span>'
            '<span class="muted">For RADIUS, web, VPN, and other servers and clients.</span>'
            + detail([
                ("Signed by", "The intermediate CA"),
                ("Names", "The name and alternative names from the request"),
                ("Valid for", "The <b>default_cert_duration</b>"),
                ("Use", "Server and client authentication. Listed on Certificates and can be revoked."),
            ])
            + "</span></label>"
            '<label class="choice"><input type="radio" name="kind" value="ca">'
            f'<span class="choice-icon">{ui.icon("shield-check")}</span><span>'
            '<span class="choice-title">Subordinate CA</span>'
            "<span class=\"muted\">Another CA, for example Meraki's SCEP CA.</span>"
            + detail([
                ("Signed by", "The root CA"),
                ("Subject", "Kept exactly as requested"),
                ("Extensions", '<span class="mono">basicConstraints = critical,CA:true,pathlen:0</span><br>'
                 '<span class="mono">keyUsage = critical,keyCertSign,digitalSignature</span>'),
                ("Valid for", f"{years} years or until the root expires"),
                ("Also accepts", "The other CA's current certificate"),
                ("Meraki", "Download the SCEP CA request under <b>Organization &rsaquo; MDM</b> and upload the "
                 "signed file there."),
            ])
            + "</span></label></div>"
            '<div class="field"><label for="signfile">Certificate request (.csr, .req, .pem)</label>'
            '<input id="signfile" type="file" name="file" accept=".csr,.req,.pem,.crt,.cer,.der"></div>'
            '<div class="field"><label for="signpem">Or paste PEM</label>'
            '<textarea id="signpem" name="pem" rows="4" placeholder="-----BEGIN CERTIFICATE REQUEST-----"></textarea>'
            '<p class="hint">Only sign requests from systems you control. Every signing is written to the add-on log.</p>'
            "</div>"
            f'<button class="btn">{ui.icon("file-sign")}Sign and download</button></form></div>'
        )
        self.page("Sign a request", body, narrow=True)

    def mdm_download(self, query):
        first = lambda name: (query.get(name) or [""])[0].strip()  # noqa: E731
        try:
            if first("platform") == "all":
                data, filename = mdm_bundle(first("cn"), default_base_url(self.headers), first("email"),
                                            first("group"))
            else:
                data, filename = mdm_profile(first("platform"), first("contents"), first("cn"),
                                             default_base_url(self.headers), first("email"), first("group"))
        except ValueError as err:
            self.tools_error("/tools/mdm", err)
            return
        print(f"Downloaded MDM profile {filename}", flush=True)
        self.download(data, filename, "application/zip" if filename.endswith(".zip")
                      else "application/x-apple-aspen-config")

    def mdm_page(self, query):
        """Values for an MDM's SCEP, certificate, and Wi-Fi payloads, and ready-made profiles."""
        extra = enroll.load_extra_cas()
        base = default_base_url(self.headers) or "&lt;Home Assistant URL&gt;"
        base = esc(base) if not base.startswith("&lt;") else base
        certs = [f'<a href="{esc(self.url("/download/ca-chain.pem"))}">ca-chain.pem</a> (this CA: '
                 "intermediate and root)"]
        # One payload per chain: skip uploaded CAs that are an issuer of another upload.
        issuers = {c.issuer for c in extra if c.issuer != c.subject}
        certs += [f'<a href="{esc(self.url(f"/download/extra/{enroll.fingerprint(c)}.pem"))}">'
                  f"{esc(safe_filename(enroll.common_name(c)))}.pem</a>"
                  for c in extra if c.subject not in issuers]
        challenge = ("The <b>scep_challenge</b> add-on option (static)" if SCEP_CHALLENGE else
                     ui.chip("bad", "Not set") + " Set <b>scep_challenge</b> before using an MDM")
        scep_url = f"{base}/api/step_ca_scep/scep/{esc(SCEP_PROVISIONER)}"
        rows = [
            ("Certificate payloads", f"{'; '.join(certs)}. Each file is a full chain; upload each as one "
             "certificate payload.", None),
            ("SCEP URL", f'<span class="mono">{scep_url}</span>',
             None if base.startswith("&lt;") else html.unescape(scep_url)),
            *((f"SCEP URL, {esc(g)}", f'<span class="mono">{base}/api/step_ca_scep/scep/{esc(g)}</span>',
               None if base.startswith("&lt;") else html.unescape(f"{base}/api/step_ca_scep/scep/{g}"))
              for g in GROUPS),
            ("Challenge", challenge + (" Each group uses its own challenge (see Groups)." if GROUPS else ""),
             None),
            ("Subject", '<span class="mono">CN=&lt;unique device or user variable&gt;</span>, e.g. '
             '<span class="mono">CN=$SERIALNUMBER</span>', None),
            ("Email name", "Your MDM's user email or UPN variable, when your RADIUS server or Meraki Access "
             "Manager matches users by email", None),
            ("Key", "RSA, 2048 bits or more, usage signing and encryption, not exportable", None),
            ("Fingerprint", "Leave empty", None),
        ]
        for wifi in WIFI_NETWORKS:
            label = f"<b>{esc(enroll.wifi_ssid(wifi))}</b>" + (
                f" ({esc(wifi['name'])})" if wifi["name"] and wifi["name"] != enroll.wifi_ssid(wifi) else "")
            rows.append(("Wi-Fi", f"{'Passpoint ' if not wifi['ssid'] else 'SSID '}{label}, "
                         + esc(mdm_wifi_settings(wifi)), None))
        dl = "".join(ui.kv_row(k, v, ui.copy_button(c, k) if c else "") for k, v, c in rows)
        body = (
            self.tools_notice(query)
            + '<div class="grid"><div>'
            + self.mdm_profile_form()
            + "</div><div>"
            '<div class="card"><div class="card-header"><h2>SCEP values</h2>'
            '<p class="muted">To build the profile in your MDM yourself instead. In Microsoft Intune, upload the '
            "downloaded profile as a custom profile; Intune's own SCEP certificate profile is not supported "
            "because it needs Microsoft's certificate connector.</p></div>"
            f'<dl class="rows">{dl}</dl></div>'
            "</div></div>"
        )
        self.page("MDM profiles", body)

    def mdm_profile_form(self):
        """Ready-made, unsigned profiles to upload to an MDM instead of entering the values."""
        contents = "".join(f'<option value="{esc(v)}">{esc(label)}</option>' for v, label in mdm_contents())
        buttons = "".join(
            f'<button class="btn" name="platform" value="{v}">{ui.icon(icon)}{esc(label)} profile</button>'
            for (v, label), icon in zip(MDM_PLATFORMS.items(), ("cellphone", "laptop")))
        buttons += (f'<button class="btn outlined" name="platform" value="all">{ui.icon("download")}'
                    "Download all (.zip)</button>")
        mdms = "".join(f'<option value="{key}">{esc(name)}</option>' for key, name, _, _ in MDM_VARIABLES)

        def presets(index):
            return "".join(
                f'<option value="{esc(value)}" data-mdm="{key}">{esc(label)} ({esc(value)})</option>'
                for key, _, *lists in MDM_VARIABLES for value, label in lists[index]
            )

        email_groups = [g for g in GROUPS if group_requires_email(g)]
        return (
            f'<form class="card" method="get" action="{esc(self.url("/download/mdm.mobileconfig"))}">'
            '<div class="card-header"><h2>Download a profile for your MDM</h2>'
            '<p class="muted">A standard, unsigned Apple configuration profile (.mobileconfig) with the CA '
            "certificates, the SCEP payload, and optionally Wi-Fi. Upload it to your MDM as a custom profile; "
            "it is unsigned so the MDM can replace its variables and sign it.</p>"
            '<p class="muted">Download one for each device type and assign each to those devices in your MDM. '
            "The iPhone and iPad profile installs for the user and leaves out Mac-only settings (login window). "
            "The Mac profile installs for the whole Mac (System keychain) and leaves out iPhone-only settings "
            "(captive portal bypass, Passpoint MCC/MNC and HESSID). <b>Download all</b> gets every profile in "
            "the Contents menu for both device types in one .zip, with the settings below.</p></div><div class=\"card-content\">"
            f'<div class="field"><label for="mdm-contents">Contents</label><select id="mdm-contents" name="contents">{contents}</select></div>'
            '<div class="field js-only"><label for="mdm-kind">Your MDM</label>'
            f'<select id="mdm-kind" data-mdm-switch>{mdms}<option value="other">Another MDM</option></select>'
            '<p class="hint">Lists its variables below. The MDM replaces them with each device&#39;s or '
            "user&#39;s values.</p></div>"
            + group_select("mdm-group", hint="Each group has its own SCEP URL and challenge, and its "
                           "certificates get the group&#39;s OU. Upload one profile per group and assign it "
                           "to that group of devices or users in your MDM.")
            + '<div class="field"><label for="mdm-cn">Certificate name (Common Name)</label>'
            '<select class="preset js-only" data-for="mdm-cn" aria-label="Certificate name variable">'
            f'{presets(0)}<option value="" data-custom>Custom…</option></select>'
            '<input id="mdm-cn" name="cn" maxlength="64" autocapitalize="off" spellcheck="false" '
            'placeholder="Your MDM\'s serial number or user name variable">'
            '<p class="hint">A value unique to each device or user: the serial number for a device '
            "certificate, the user name or UPN for a user certificate. Choose Custom… to type a variable "
            "that is not listed. Not needed for Certificates only.</p></div>"
            '<div class="field"><label for="mdm-email">Email address'
            + ("" if email_groups else " (optional)") + "</label>"
            '<select class="preset js-only" data-for="mdm-email" aria-label="Email variable">'
            f'<option value="">None</option>{presets(1)}<option value="" data-custom>Custom…</option></select>'
            '<input id="mdm-email" name="email" maxlength="64" autocapitalize="off" spellcheck="false" '
            'data-email-field placeholder="Your MDM\'s email variable">'
            '<p class="hint">Added to the certificate as an email alternative name, which Meraki Access Manager '
            "and RADIUS servers can match to the user (for example the Entra UPN). The device needs a user "
            "assigned in the MDM."
            + (f" Required for the group{'s' if len(email_groups) > 1 else ''} "
               + ", ".join(f"<b>{esc(g)}</b>" for g in email_groups) + "." if email_groups else "")
            + "</p></div>"
            + ui.alert("warning", "SCEP profiles contain the challenge, so keep them private.")
            + f'</div><div class="card-actions">{buttons}</div></form>'
        )


UPLOAD_LIMIT = 65536


def parse_multipart(content_type, body):
    """Parse a multipart/form-data body into {name: [value]}; files stay bytes."""
    message = email.message_from_bytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body, policy=email.policy.HTTP)
    form = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        value = data if part.get_filename() is not None else data.decode(errors="replace")
        form.setdefault(name, []).append(value)
    return form


APPLE_UA_RE = re.compile(r"iPhone|iPad|iPod|Macintosh|Mac OS X")
IOS_UA_RE = re.compile(r"iPhone|iPad|iPod")
ENROLL_PATH_RE = re.compile(
    r"^/enroll/([A-Za-z0-9_-]{32,64})(?:/(file/[A-Za-z0-9_-]{20,64}|root_ca\.crt))?$")


class EnrollHandler(Handler):
    """Public enrollment pages, reached through the integration's proxy.

    Only Home Assistant Core may connect; the one-time token in the path is
    the credential.
    """

    def public(self, path):
        return f"{enroll.PUBLIC_BASE}/{path.lstrip('/')}"

    def page(self, title, body, status=200, back=None, narrow=False, heading=None, head=""):
        self.document(
            title,
            '<main id="main-content" tabindex="-1" class="public"><div class="brand">'
            f'<span class="brand-mark">{ui.icon("certificate")}</span><span>{esc(CA_NAME)}</span></div>'
            f"{body}</main>",
            status, head='<meta name="referrer" content="no-referrer">',
        )

    def allowed(self):
        if self.client_address[0] not in ENROLL_ALLOWED_CLIENTS:
            self.send(403, "Forbidden", "text/plain")
            return False
        return True

    def enroll_prefix(self):
        return self.public("/enroll")

    def insecure_note(self):
        return ""

    def route(self):
        match = ENROLL_PATH_RE.match(urllib.parse.urlsplit(self.path).path.rstrip("/"))
        return (match.group(1), match.group(2)) if match else (None, None)

    def do_GET(self):
        if not self.allowed():
            return
        token, sub = self.route()
        if token is None:
            self.send(404, "Not found", "text/plain")
        elif sub:
            self.enroll_file(token, sub)
        else:
            link_id, link = LINKS.get(token)
            if link is None:
                self.gone()
                return
            if link.get("renewable"):
                self.update_page(self.public(f"/enroll/{token}"), link)
                return
            self.form_page(self.public(f"/enroll/{token}"), link)

    def do_POST(self):
        if not self.allowed():
            return
        token, sub = self.route()
        if token is None or sub:
            self.send(404, "Not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.send(400, "Invalid request size", "text/plain")
            return
        if length < 0:
            self.send(400, "Invalid request size", "text/plain")
            return
        if length > 4096:
            self.send(413, "Request too large", "text/plain")
            return
        form = urllib.parse.parse_qs(self.rfile.read(length).decode(errors="replace"))
        if any(len(values) != 1 for values in form.values()):
            self.send(400, "Submit each form field once.", "text/plain")
            return
        link_id, link = LINKS.get(token)
        if link is None:
            self.gone()
            return
        if link.get("renewable"):
            # An update link only reinstalls the profile for its certificate.
            self.apple_result(token, link_id, link, link["cn"], self.is_ios(form))
            return
        cn = (link["cn"] or form.get("cn", [""])[0]).strip()
        if error := self.name_error(cn):
            self.form_page(self.public(f"/enroll/{token}"), link, error, cn)
            return
        if form.get("kind", [""])[0] == "apple":
            self.apple_result(token, link_id, link, cn, self.is_ios(form))
        else:
            self.p12_result(token, link_id, link, cn)


class WebhookHandler(BaseHTTPRequestHandler):
    """step-ca's SCEPCHALLENGE webhook, on loopback only."""

    server_version = "step-ca-admin"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    def reply(self, allow):
        data = json.dumps({"allow": allow}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # /scep-challenge for the default provisioner, /scep-challenge/<group> for a group's.
        group = self.path.removeprefix("/scep-challenge/") if self.path.startswith("/scep-challenge/") else ""
        if self.path != "/scep-challenge" and group not in GROUPS:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 <= length <= 1 << 20:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            challenge = str(request.get("scepChallenge") or "")
            csr = request.get("x509CertificateRequest") or {}
            cn = str((csr.get("subject") or {}).get("commonName") or "")
        except (ValueError, AttributeError):
            self.reply(False)
            return
        # Checked first so a refused request does not use up an enrollment link.
        if group_requires_email(group) and not csr_has_email(csr):
            print(f"Refused a SCEP request for {cn!r} in group {group}: no email address", flush=True)
            self.reply(False)
            return
        if LINKS.consume_challenge(challenge, cn, group):
            print(f"Enrollment link used: SCEP certificate for {cn!r}"
                  + (f" in group {group}" if group else ""), flush=True)
            self.reply(True)
            return
        # A group without a challenge only accepts one-time enrollment links.
        static = GROUPS[group]["challenge"] if group else SCEP_CHALLENGE
        if not static and not group:
            self.reply(True)
        else:
            self.reply(bool(challenge and static)
                       and secrets.compare_digest(challenge.encode(), static.encode()))


def serve(address, handler, label, tls=None):
    server = ThreadingHTTPServer(address, handler)
    server.daemon_threads = True
    if tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(*tls)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"{label} listening on {address[0]}:{address[1]}", flush=True)
    thread = threading.Thread(target=server.serve_forever, name=label, daemon=True)
    thread.start()
    return thread


def main():
    threads = [
        serve(("0.0.0.0", LISTEN_PORT), Handler, "Management page"),
        serve(("0.0.0.0", ENROLL_PORT), EnrollHandler, "Enrollment pages"),
        serve(("0.0.0.0", RESIDENT_PORTAL_PORT), ipsk.PublicPortalHandler, "Resident Wi-Fi portal"),
        serve(("127.0.0.1", WEBHOOK_PORT), WebhookHandler, "SCEP challenge webhook",
              tls=(WEBHOOK_CERT, WEBHOOK_KEY)),
    ]
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
