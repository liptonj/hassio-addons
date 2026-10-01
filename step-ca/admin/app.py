"""Small certificate management page for the Step CA SCEP add-on.

Served through Home Assistant ingress, so Home Assistant handles login, and
limited to Home Assistant administrators (ingress itself admits any user). The
certificate inventory is read from step-ca's MariaDB database; revocation goes
through step-ca's API so the CRL is regenerated.

Two more listeners serve device enrollment (see enroll.py): a public one that
Home Assistant forwards /api/step_ca_scep/enroll/<token> to, limited to the Home
Assistant container, and a loopback-only SCEPCHALLENGE webhook for step-ca.
"""

import asyncio
import datetime
import email
import email.policy
import html
import json
import os
import re
import secrets
import ssl
import subprocess
import threading
import time
import traceback
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aiohttp
import pymysql
import qrcode
import qrcode.image.svg
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import ExtensionOID, NameOID

import enroll
import ui

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
CORE_WEBSOCKET = os.environ.get("CORE_WEBSOCKET", "ws://supervisor/core/websocket")
ADMIN_GROUP = "system-admin"
ADMIN_CACHE_SECONDS = 60
ADMIN_REFRESH_SECONDS = 5
SUBJECT_POLICY = os.environ.get("SUBJECT_POLICY", "")
CA_NAME = os.environ.get("CA_NAME", "Home Assistant CA")
SCEP_CHALLENGE = os.environ.get("SCEP_CHALLENGE", "")
ENROLL_PORT = int(os.environ.get("ENROLL_PORT", "8100"))
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8101"))
WEBHOOK_CERT = os.environ.get("WEBHOOK_CERT", f"{STEP_PATH}/enroll/webhook.crt")
WEBHOOK_KEY = os.environ.get("WEBHOOK_KEY", f"{STEP_PATH}/enroll/webhook.key")
# Home Assistant Core's address on the Supervisor network.
ENROLL_ALLOWED_CLIENTS = set(os.environ.get("ENROLL_ALLOWED_CLIENTS", "172.30.32.1").split(","))
ENROLL_PUBLIC_URL = os.environ.get("ENROLL_PUBLIC_URL", "")
ENROLL_LINK_HOURS = int(os.environ.get("ENROLL_LINK_HOURS", "24"))
try:
    WIFI = json.loads(os.environ.get("WIFI_JSON") or "{}")
except ValueError:
    WIFI = {}
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
    return {
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
    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, border=2)
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


def wifi_enabled():
    return bool(WIFI.get("ssid"))


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


def profile_for(cn, challenge, base_url, wifi, sans=()):
    root, inter = cert_chain()
    organization = ""
    match = re.search(r"(?:^|, )O=([^,]+)", SUBJECT_POLICY)
    if match:
        organization = match.group(1)
    xml = enroll.build_profile(
        cn=cn, challenge=challenge,
        scep_url=f"{base_url}{enroll.PUBLIC_BASE}/scep/{SCEP_PROVISIONER}",
        ca_name=CA_NAME, organization=organization, root=root, intermediate=inter,
        wifi=WIFI if wifi else None, extra_cas=enroll.load_extra_cas(), sans=sans,
    )
    return SIGNER.sign(xml)


MDM_CN_RE = re.compile(r"^[A-Za-z0-9 ._@$%{}()-]{1,64}$")
MDM_PLATFORMS = {"ios": "iOS and iPadOS", "macos": "macOS"}
MDM_CONTENTS = ("trust", "scep", "wifi")


def mdm_profile(platform, contents, cn, base_url, email=""):
    """Unsigned .mobileconfig for an MDM to upload as a custom profile.

    Unsigned because MDMs (Meraki, Jamf, ...) substitute variables such as
    $DEVICESERIAL in the profile, which a signature would forbid.
    Returns (data, filename) or raises ValueError.
    """
    if platform not in MDM_PLATFORMS or contents not in MDM_CONTENTS:
        raise ValueError("Unknown platform or profile contents.")
    if contents == "wifi" and not wifi_enabled():
        raise ValueError("Wi-Fi is not configured; set wifi.ssid in the add-on options.")
    if contents != "trust":
        if not SCEP_CHALLENGE:
            raise ValueError("Set the scep_challenge add-on option before creating an MDM SCEP profile.")
        if not cn:
            raise ValueError("Enter a certificate name, such as your MDM's serial number variable.")
        if email and not MDM_CN_RE.fullmatch(email):
            raise ValueError("The email address must be 1-64 letters, digits, spaces, or . _ @ $ % { } ( ) -")
        if not MDM_CN_RE.fullmatch(cn):
            raise ValueError("The certificate name must be 1-64 letters, digits, spaces, or . _ @ $ % { } ( ) -")
        if not base_url.startswith("https://"):
            raise ValueError("Devices need a public HTTPS Home Assistant URL for SCEP; set the External URL "
                             "or the enrollment.public_url add-on option.")
    root, inter = cert_chain()
    match = re.search(r"(?:^|, )O=([^,]+)", SUBJECT_POLICY)
    names = {"trust": "CA certificates", "scep": "SCEP certificate", "wifi": f"Wi-Fi {WIFI.get('ssid', '')}"}
    xml = enroll.build_profile(
        cn=cn or "device", challenge=SCEP_CHALLENGE,
        scep_url=f"{base_url}{enroll.PUBLIC_BASE}/scep/{SCEP_PROVISIONER}",
        ca_name=CA_NAME, organization=match.group(1) if match else "", root=root, intermediate=inter,
        wifi=WIFI if contents == "wifi" else None, extra_cas=enroll.load_extra_cas(),
        include_scep=contents != "trust", system_scope=platform == "macos", email_sans=[email],
        identifier=f"mdm.{contents}.{platform}",
        display_name=f"{CA_NAME}: {names[contents]} ({MDM_PLATFORMS[platform]})",
    )
    return xml, f"{safe_filename(CA_NAME)}-{contents}-{platform}.mobileconfig"


def sans_input(value=""):
    return (
        '<div class="field"><label for="sans">Alternative names (optional)</label>'
        f'<input id="sans" name="sans" maxlength="2000" value="{esc(value)}" '
        'placeholder="e.g. josh@example.com, host.example.com, 192.0.2.10" autocapitalize="off">'
        '<p class="hint">Email addresses, DNS names, and IP addresses, separated by commas. '
        "Apple profiles support email and DNS names only.</p></div>"
    )


def safe_filename(cn):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", cn).strip("_") or "device"


def wifi_help():
    """Manual Wi-Fi settings for devices that installed a .p12."""
    if not wifi_enabled():
        return ""
    names = WIFI.get("radius_server_names") or []
    rows = [
        ("Network (SSID)", esc(WIFI["ssid"])),
        ("Security", f'{esc(WIFI.get("security", "WPA2"))} Enterprise, EAP method <b>TLS</b>'),
        ("CA certificate", "ca-bundle.pem above (Android: install it as a CA certificate)"
         if enroll.load_extra_cas() else
         "the root CA above (Android: install it as a CA certificate)"),
        ("Identity", "your certificate name"),
    ]
    if names:
        rows.append(("Domain / server name", esc(names[0])))
    return (
        '<div class="card"><div class="card-header"><h2>Connect to Wi-Fi</h2></div>'
        '<dl class="card-content flush rows">'
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


class Handler(BaseHTTPRequestHandler):
    server_version = "step-ca-admin"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    # -- helpers -----------------------------------------------------------

    def base(self):
        prefix = self.headers.get("X-Ingress-Path", "")
        return prefix if INGRESS_PATH_RE.match(prefix) else ""

    def url(self, path):
        return f"{self.base()}/{path.lstrip('/')}"

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
            ("/ca", "Authority", "shield-check"), ("/tools", "Tools", "wrench"))

    def current_tab(self):
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith(("/enroll", "/issue")):
            return "/enroll"
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
            f'<body class="{body_class}">{body}<script nonce="{nonce}">{ui.SCRIPT}</script></body></html>',
            nonce=nonce,
        )

    def page(self, title, body, status=200, back=None, narrow=False, heading=None):
        """A panel page: tabs on top-level pages, a back arrow on subpages."""
        if back:
            bar = (f'<a class="icon-btn back" href="{esc(self.url(back))}" aria-label="Back">'
                   f'{ui.icon("arrow-left")}</a><h1 class="toolbar-title">{esc(heading or title)}</h1>')
        else:
            current = self.current_tab()
            tabs = "".join(
                f'<a class="tab" href="{esc(self.url(path))}"'
                f'{" aria-current=page" if path == current else ""}>{ui.icon(icon)}<span>{label}</span></a>'
                for path, label, icon in self.TABS
            )
            bar = f'<h1 class="toolbar-title">Certificates</h1><nav class="tabs" aria-label="Sections">{tabs}</nav>'
        self.document(
            title,
            f'<header class="toolbar">{bar}</header>'
            f'<main class="content{" narrow" if narrow else ""}">{body}</main>',
            status, body_class="" if back else "has-tabs",
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
            if path == "/":
                self.list_page(query)
            elif path == "/ca":
                self.ca_page()
            elif path == "/tools":
                self.tools_page(query)
            elif path == "/enroll":
                self.enroll_page()
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
        path = urllib.parse.urlsplit(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        if length > (UPLOAD_LIMIT if path in ("/ca/extra", "/ca/sign") else 4096):
            self.send(413, "Request too large", "text/plain")
            return
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            form = parse_multipart(content_type, body)
        else:
            form = urllib.parse.parse_qs(body.decode(errors="replace"))
        if not secrets.compare_digest(str(form.get("csrf", [""])[0]), CSRF_TOKEN):
            self.send(403, "Invalid form token; reload the page and try again.", "text/plain")
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
            self.redirect("/tools#trusted")
            return
        if path == "/enroll/self":
            self.self_enroll(form)
            return
        if path == "/enroll/new":
            self.enroll_create(form)
            return
        if path == "/issue":
            self.issue_direct(form)
            return
        if m := re.fullmatch(r"/enroll/([0-9a-f]{64})/cancel", path):
            LINKS.cancel(m.group(1))
            self.redirect("/enroll")
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

    def health(self, certs, counts, now):
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
            + tile("neutral", "cancel", f'{counts["revoked"]} revoked', "listed on the CRL", "revoked")
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
        certs = fetch_certs()
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
                f'<td class="hide-mobile">{esc(c["provisioner"])}</td>'
                f'<td class="hide-mobile mono nowrap">{esc(c["serial"][:12])}{"…" if len(c["serial"]) > 12 else ""}</td>'
                "</tr>"
            )

        empty_titles = {"active": "No active certificates", "expiring": "Nothing expires soon",
                        "expired": "No expired certificates", "revoked": "No revoked certificates",
                        "all": "No certificates yet"}
        if shown:
            rows = "".join(row(c) for c in shown)
        elif search:
            rows = (f'<tr><td colspan="6">{ui.empty_state("magnify", "No certificates match", f"Nothing matches “{esc(search)}” here. Try All.")}</td></tr>')
        else:
            rows = (f'<tr><td colspan="6">{ui.empty_state("certificate", empty_titles[status], "Enroll a device to issue one." if status in ("active", "all") else "")}</td></tr>')
        rows += (f'<tr class="no-match" hidden><td colspan="6">'
                 f'{ui.empty_state("magnify", "No certificates match", "Try another name, alternative name, or serial.")}</td></tr>')
        body = (
            self.health(certs, counts, now)
            + '<div class="card">'
            f'<form class="list-tools" method="get" action="{esc(self.url("/"))}" role="search">'
            f'<input type="hidden" name="status" value="{esc(status)}">'
            f'<div class="search">{ui.icon("magnify")}'
            f'<input type="search" name="q" value="{esc(search)}" aria-label="Search certificates" '
            'placeholder="Search name, alternative name, or serial" data-filter-table="certs" autocomplete="off"></div>'
            f'<a class="btn" href="{esc(self.url("/enroll"))}">{ui.icon("plus")}Enroll device</a></form>'
            f'<nav class="filters" aria-label="Status">{filters}</nav>'
            '<div class="table-wrap"><table id="certs"><thead><tr><th>Name</th><th>Status</th>'
            '<th class="hide-mobile">Expires</th><th class="hide-mobile">Issued</th>'
            '<th class="hide-mobile">Provisioner</th><th class="hide-mobile">Serial</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></div>"
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
        dl = "".join(f'<div class="kv"><dt>{k}</dt><dd>{v}</dd>{b or "<span></span>"}</div>' for k, v, b in details)

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
            + revoke_form
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

    def form_page(self, action, link, error="", cn="", hidden="", extra=""):
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
            wifi = f' It also sets up Wi-Fi network <b>{esc(WIFI["ssid"])}</b>.'
        body = (
            (ui.alert("error", esc(error)) if error else "")
            + f'<form class="card" method="post" action="{esc(action)}">'
            f'<div class="card-header"><h1>Get a certificate</h1>'
            f'<p class="muted">From {esc(CA_NAME)}. Pick the kind of device you are enrolling.</p></div>'
            '<div class="card-content">' + hidden + name + extra
            + '<fieldset class="field"><legend class="label">Device</legend><div class="choices">'
            f'<label class="choice"><input type="radio" name="kind" value="apple"{" checked" if apple else ""}>'
            f'<span class="choice-icon">{ui.icon("apple")}</span><span>'
            '<span class="choice-title">iPhone, iPad, or Mac</span><span class="muted">Installs a profile. '
            f"The device creates its own private key and requests the certificate itself.{wifi}</span></span></label>"
            f'<label class="choice"><input type="radio" name="kind" value="p12"{"" if apple else " checked"}>'
            f'<span class="choice-icon">{ui.icon("cellphone")}</span><span>'
            '<span class="choice-title">Other device</span><span class="muted">Android, Windows, Linux, and others. '
            "Downloads a password-protected .p12 file with the certificate, its key, and the CA chain."
            "</span></span></label></div></fieldset></div>"
            '<div class="card-actions"><button class="btn">Continue</button></div></form>'
        )
        self.page("Enroll device", body, back="/enroll", narrow=True)

    def apple_result(self, token, link_id, link, cn):
        challenge = LINKS.new_challenge(link_id, cn)
        if challenge is None:
            self.gone()
            return
        try:
            data = profile_for(cn, challenge, link["base_url"], link["wifi"] and wifi_enabled(),
                               link.get("sans") or ())
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
        )
        self.page("Install the profile", body, back="/enroll", narrow=True)

    def p12_result(self, token, link_id, link, cn):
        if not LINKS.claim(link_id, cn, ".p12 download"):
            self.gone()
            return
        try:
            data, password, _ = enroll.issue_p12(cn, ca_url=CA_URL, root_cert=ROOT_CERT,
                                                 extra_cas=enroll.load_extra_cas(),
                                                 sans=link.get("sans") or ())
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
        self.page(f"Certificate for {cn}", body, back="/enroll", narrow=True)

    # -- enrollment (admin) ------------------------------------------------------

    def self_enroll_page(self, error="", cn="", sans=""):
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        self.form_page(self.url("/enroll/self"), {"cn": "", "wifi": wifi_enabled()}, error, cn,
                       csrf, sans_input(sans))

    def self_enroll(self, form):
        """Enroll the computer the panel is open on (e.g. a Mac or Windows PC)."""
        cn = form.get("cn", [""])[0].strip()
        sans_text = form.get("sans", [""])[0].strip()
        if not enroll.valid_cn(cn):
            self.self_enroll_page("Enter a certificate name using letters, digits, spaces, "
                                  "and . _ @ - (up to 64 characters).", cn, sans_text)
            return
        try:
            sans = enroll.parse_sans(sans_text)
        except ValueError as err:
            self.self_enroll_page(str(err), cn, sans_text)
            return
        base_url = default_base_url(self.headers)
        if not base_url:
            self.self_enroll_page("Set enrollment.public_url in the add-on options first.", cn)
            return
        who = self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or ""
        token = LINKS.create(label="This device (panel)", cn=cn, base_url=base_url,
                             wifi=wifi_enabled(), hours=1, created_by=who, sans=sans)
        link_id, link = LINKS.get(token)
        if form.get("kind", [""])[0] == "apple":
            self.apple_result(token, link_id, link, cn)
        else:
            self.p12_result(token, link_id, link, cn)

    def enroll_page(self, notice=""):
        base_url, base_source = detect_base_url(self.headers)
        signer_ok, signer_html = signer_status()
        wifi_opt = ""
        if wifi_enabled():
            wifi_opt = (
                '<div class="field"><label class="check"><input type="checkbox" name="wifi" value="1" checked>'
                f'Apple profiles also configure Wi-Fi <b>{esc(WIFI["ssid"])}</b></label></div>'
            )
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        now = datetime.datetime.now(datetime.timezone.utc)
        rows = ""
        for link in LINKS.all():
            state = link["state"]
            kind = {"pending": "info", "issued": "ok", "expired": "neutral"}.get(state, "bad")
            cancel = ""
            if state == "pending":
                cancel = (
                    f'<form method="post" action="{esc(self.url("/enroll/" + link["id"] + "/cancel"))}">'
                    f'{csrf}<button class="btn text danger">Cancel</button></form>'
                )
            expires = datetime.datetime.fromtimestamp(link["expires"], datetime.timezone.utc)
            rows += (
                f"<tr><td>{esc(link['label'] or 'Untitled link')}"
                + (f'<span class="sub">{esc(link["created_by"])}</span>' if link["created_by"] else "")
                + f"</td><td>{esc(link['issued_cn'] or link['cn'] or 'Chosen on the device')}"
                + (f'<span class="sub">{esc(", ".join(link["sans"]))}</span>' if link.get("sans") else "")
                + (f'<span class="sub">{esc(link["method"])}</span>' if link["method"] else "")
                + f"</td><td>{ui.chip(kind, state.title())}</td>"
                f'<td class="hide-mobile nowrap">{ui.when(expires, now)}</td>'
                f'<td class="actions">{cancel}</td></tr>'
            )
        rows = rows or (f'<tr><td colspan="5">{ui.empty_state("link-variant", "No enrollment links yet", "Links you create appear here until they expire.")}</td></tr>')
        advanced_open = " open" if not base_url.startswith("https://") else ""
        body = (
            notice
            + '<div class="grid"><div>'
            f'<form class="card" method="post" action="{esc(self.url("/enroll/new"))}">{csrf}'
            '<div class="card-header"><h2>New one-time link</h2>'
            '<p class="muted">A link and QR code for one device. On an iPhone, iPad, or Mac it installs a signed '
            "profile, so the device creates its own key and gets its certificate over SCEP. Other devices get a "
            "password-protected .p12 file with the full CA chain. No MDM is needed.</p></div>"
            f'<div class="inline-alert">{signer_html}</div>'
            '<div class="card-content"><div class="field-row">'
            '<div class="field"><label for="label">Label</label><input id="label" name="label" maxlength="64" '
            'placeholder="e.g. Josh&#39;s iPhone"></div>'
            '<div class="field"><label for="cn">Certificate name (CN)</label><input id="cn" name="cn" maxlength="64" '
            'autocapitalize="off" placeholder="Chosen on the device"></div></div></div>'
            f'<details class="expand"{advanced_open}><summary><span class="summary-text">'
            '<span class="summary-title">More options</span>'
            f'<span class="summary-sub">Alternative names, Home Assistant URL, validity'
            f'{", Wi-Fi" if wifi_enabled() else ""}</span></span>{ui.icon("chevron-down", "chev")}</summary>'
            '<div class="expand-body">'
            + sans_input()
            + '<div class="field"><label for="base">Home Assistant URL the device will use</label>'
            f'<input id="base" name="base_url" type="url" required value="{esc(base_url)}" '
            'placeholder="https://home.example.com">'
            + base_url_hint(base_url, base_source) + "</div>"
            '<div class="field"><label for="hours">Valid for (hours)</label>'
            f'<input id="hours" name="hours" type="number" min="1" max="168" value="{ENROLL_LINK_HOURS}" '
            'class="input-short"></div>'
            + wifi_opt + "</div></details>"
            f'<div class="card-actions"><button class="btn">{ui.icon("qrcode")}Create link</button></div></form>'
            '<div class="card"><div class="card-header"><h2>Links</h2></div>'
            '<div class="table-wrap"><table><thead><tr>'
            '<th>Label</th><th>Certificate</th><th>Status</th><th class="hide-mobile">Expires</th>'
            '<th><span class="visually-hidden">Actions</span></th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></div>"
            "</div><div>"
            '<div class="card"><div class="row">'
            f'<span class="row-icon">{ui.icon("laptop")}</span><span class="row-text">'
            '<span class="row-title">This computer</span>'
            '<span class="row-sub">A certificate for the Mac or Windows PC you are using now</span></span>'
            f'<span class="row-actions"><a class="btn text" href="{esc(self.url("/enroll/self"))}">Enroll</a>'
            "</span></div></div>"
            f'<form class="card" method="post" action="{esc(self.url("/issue"))}">{csrf}'
            '<div class="card-header"><h2>Issue a certificate now</h2>'
            '<p class="muted">Creates the key here and gives you a .p12 file to hand over.</p></div>'
            '<div class="card-content"><div class="field"><label for="issue-cn">Certificate name (CN)</label>'
            '<input id="issue-cn" name="cn" maxlength="64" required autocapitalize="off" placeholder="e.g. printer"></div>'
            '<div class="field"><label for="issue-sans">Alternative names (optional)</label>'
            '<input id="issue-sans" name="sans" maxlength="2000" autocapitalize="off" '
            'placeholder="Email, DNS names, IP addresses"></div></div>'
            f'<div class="card-actions"><button class="btn text">{ui.icon("key-variant")}Issue .p12</button></div></form>'
            "</div></div>"
        )
        self.page("Enroll devices", body)

    def enroll_create(self, form):
        field = lambda name: form.get(name, [""])[0].strip()
        label, cn = field("label")[:64], field("cn")
        base_url = enroll.normalize_base_url(field("base_url"))
        try:
            hours = min(max(int(field("hours") or ENROLL_LINK_HOURS), 1), 168)
        except ValueError:
            hours = ENROLL_LINK_HOURS
        error = ""
        if cn and not enroll.valid_cn(cn):
            error = "The certificate name may use letters, digits, spaces, and . _ @ - (up to 64)."
        elif not base_url:
            error = "Enter the Home Assistant URL as scheme and host only, e.g. https://home.example.com."
        sans = []
        if not error:
            try:
                sans = enroll.parse_sans(field("sans"))
            except ValueError as err:
                error = str(err)
        if error:
            self.enroll_page(ui.alert("error", esc(error), "The link was not created"))
            return
        who = self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or ""
        token = LINKS.create(label=label, cn=cn, base_url=base_url, wifi=field("wifi") == "1" and wifi_enabled(),
                             hours=hours, created_by=who, sans=sans)
        link = f"{base_url}{enroll.PUBLIC_BASE}/enroll/{token}"
        expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
        body = (
            '<div class="card result"><div class="card-header"><h2>'
            f"{esc(label) if label else 'Enrollment link'}</h2>"
            '<p class="muted">Scan with the device camera, or open the link in its browser.</p></div>'
            f'<div class="card-content"><div class="qr">{qr_svg(link)}</div>'
            + ui.copy_field(link, "link")
            + f'<p class="muted">One certificate{" named <b>" + esc(cn) + "</b>" if cn else ""}. '
            f"Valid for {hours} hour{'s' if hours != 1 else ''}, until {ui.when(expires)}.</p></div></div>"
            + ui.alert("warning", "Anyone with this link can enroll a device, so share it only with the device "
                       "owner. It is not shown again.", "Shown only once")
        )
        self.page("Enrollment link", body, back="/enroll", narrow=True)

    def issue_direct(self, form):
        cn = form.get("cn", [""])[0].strip()
        if not enroll.valid_cn(cn):
            self.enroll_page(ui.alert("error", "The certificate name may use letters, digits, "
                                      "spaces, and . _ @ - (up to 64).", "Nothing was issued"))
            return
        try:
            sans = enroll.parse_sans(form.get("sans", [""])[0])
        except ValueError as err:
            self.enroll_page(ui.alert("error", esc(err), "Nothing was issued"))
            return
        try:
            data, password, cert = enroll.issue_p12(cn, ca_url=CA_URL, root_cert=ROOT_CERT,
                                                    extra_cas=enroll.load_extra_cas(), sans=sans)
        except (RuntimeError, OSError, subprocess.SubprocessError) as err:
            self.enroll_page(ui.alert("error", esc(err), "Could not issue the certificate"))
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
        self.page(f"Certificate for {cn}", body, back="/enroll", narrow=True)

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
            self.redirect("/tools?error=" + urllib.parse.quote("Choose a certificate file or paste a PEM.") + "#trusted")
            return
        try:
            new = enroll.parse_ca_certs(data if isinstance(data, bytes) else data.encode())
        except ValueError as err:
            self.redirect("/tools?error=" + urllib.parse.quote(str(err)[:300]) + "#trusted")
            return
        certs = enroll.load_extra_cas()
        known = {enroll.fingerprint(c) for c in certs}
        certs += [c for c in new if enroll.fingerprint(c) not in known]
        enroll.save_extra_cas(certs)
        self.redirect("/tools?added=1#trusted")

    def sign_request(self, form):
        data = form.get("file", [b""])[0]
        if not data.strip():
            data = str(form.get("pem", [""])[0]).encode()
        if not data.strip():
            self.redirect("/tools?error=" + urllib.parse.quote("Choose a certificate request file or paste a PEM.") + "#sign")
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
            self.redirect("/tools?error=" + urllib.parse.quote(str(err)[:300]) + "#sign")
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
            return f'<div class="kv"><dt>{label}</dt><dd>{value}</dd>{button}</div>'

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

        def authority(title, cert, link, filename, opened):
            left = cert.not_valid_after_utc - now
            chip = (ui.chip("bad", "Expired") if left.days < 0 else
                    ui.chip("warn", "Renew soon") if left.days < 180 else ui.chip("ok", "Valid"))
            return (
                f'<details class="expand"{" open" if opened else ""}><summary>'
                f'<span class="row-icon">{ui.icon("shield-check")}</span><span class="summary-text">'
                f'<span class="summary-title">{title}</span>'
                f'<span class="summary-sub">{esc(enroll.common_name(cert))}</span></span>{chip}'
                f'{ui.icon("chevron-down", "chev")}</summary>'
                f'<dl class="expand-body flush rows">{details(cert)}'
                f'<div class="kv"><dt>File</dt><dd><a href="{esc(self.url(link))}" download>{esc(filename)}</a></dd>'
                f'<a class="icon-btn" href="{esc(self.url(link))}" aria-label="Download {esc(filename)}" '
                f'title="Download {esc(filename)}">{ui.icon("download")}</a></div></dl></details>'
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
            + authority("Root CA", root, "/download/root_ca.pem", "root_ca.pem", False)
            + authority("Intermediate CA", inter, "/download/intermediate_ca.pem", "intermediate_ca.pem", False)
            + '<h3 class="subhead">Downloads</h3><div class="rows">'
            + download_row("file-certificate-outline", "CA chain",
                           "Intermediate and root, for MDMs and RADIUS servers",
                           "/download/ca-chain.pem", "ca-chain.pem")
            + download_row("file-certificate-outline", "CA bundle",
                           "Root, intermediate" + (", and the other trusted CAs" if extra else ""),
                           "/download/ca-bundle.pem", "ca-bundle.pem")
            + download_row("cancel", "Certificate revocation list", "Revoked certificates",
                           "/download/crl.pem", "crl.pem")
            + "</div></div>"
            "</div><div>"
            '<div class="card"><div class="card-header"><h2>Endpoints</h2>'
            '<p class="muted">Served without login through Home Assistant.</p></div><dl class="rows">'
            + url_row("SCEP URL", scep_url)
            + url_row("Root download", f"{base}/api/step_ca_scep/roots.pem")
            + url_row("CRL (DER)", f"{base}/api/step_ca_scep/crl")
            + "</dl></div></div></div>"
        )
        self.page("Authority", body)

    def tools_page(self, query):
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
        notice = ""
        if query.get("error"):
            notice = ui.alert("error", esc(query["error"][0]), "That did not work")
        elif query.get("added"):
            notice = ui.alert("success", "New profiles and .p12 files include it.", "Certificate added")
        base = default_base_url(self.headers) or "&lt;Home Assistant URL&gt;"
        base = esc(base) if not base.startswith("&lt;") else base
        add_form = (
            f'<form class="expand-body" method="post" enctype="multipart/form-data" action="{esc(self.url("/ca/extra"))}">'
            f'{csrf}<p class="muted">CA certificates devices must also trust, such as the CA that issued your RADIUS '
            "server's certificate for EAP-TLS Wi-Fi. They are added to Apple profiles (and trusted for the "
            "Wi-Fi network), to .p12 files, and to ca-bundle.pem.</p>"
            '<div class="field"><label for="file">Certificate file (.pem, .crt, .cer)</label>'
            '<input id="file" type="file" name="file" accept=".pem,.crt,.cer,.der"></div>'
            '<div class="field"><label for="pem">Or paste PEM</label>'
            '<textarea id="pem" name="pem" rows="4" placeholder="-----BEGIN CERTIFICATE-----"></textarea></div>'
            f'<button class="btn">{ui.icon("plus")}Add certificate</button></form>'
        )
        trusted = (
            '<details class="expand" id="trusted"><summary>'
            f'<span class="row-icon">{ui.icon("server-security")}</span><span class="summary-text">'
            '<span class="summary-title">Other trusted CAs</span>'
            f'<span class="summary-sub">{len(extra) or "None"} added · trusted by enrolled devices</span></span>'
            f'{ui.icon("chevron-down", "chev")}</summary>'
            + (f'<div class="rows">{extra_rows}</div>' if extra else "")
            + add_form + "</details>"
        )
        def option(label, value):
            return f'<div class="kv"><dt>{label}</dt><dd>{value}</dd><span></span></div>'

        challenge = (ui.chip("ok", "Set") if SCEP_CHALLENGE else
                     ui.chip("warn", "Not set") + " Needed for MDM profiles")
        wifi = (f"<b>{esc(WIFI['ssid'])}</b>, EAP-TLS" if wifi_enabled() else "Off")
        body = (
            notice
            + '<div class="grid"><div>'
            '<div class="card"><div class="card-header"><h2>Tools</h2></div>'
            + self.sign_card(csrf) + trusted + self.mdm_card(base, extra)
            + "</div></div><div>"
            '<div class="card"><div class="card-header"><h2>Options</h2>'
            "<p class=\"muted\">Change these on the add-on's Configuration tab in Home Assistant.</p></div>"
            '<dl class="rows">'
            + option("Issued subject", esc(SUBJECT_POLICY) if SUBJECT_POLICY else "Taken from the client request")
            + option("SCEP challenge", challenge)
            + option("Wi-Fi", wifi)
            + option("Storage", "MariaDB" if db_enabled() else "Embedded database")
            + "</dl></div></div></div>"
        )
        self.page("Tools", body)

    def sign_card(self, csrf):
        years = enroll.SUBORDINATE_DAYS // 365

        def detail(rows):
            return '<dl class="choice-detail">' + "".join(
                f'<div class="kv"><dt>{k}</dt><dd>{v}</dd></div>' for k, v in rows) + "</dl>"

        return (
            '<details class="expand" id="sign"><summary>'
            f'<span class="row-icon">{ui.icon("file-sign")}</span><span class="summary-text">'
            '<span class="summary-title">Sign a request</span>'
            "<span class=\"summary-sub\">CSRs from servers, VPNs, or another CA such as Meraki's SCEP CA</span>"
            f'</span>{ui.icon("chevron-down", "chev")}</summary>'
            f'<form class="expand-body" method="post" enctype="multipart/form-data" action="{esc(self.url("/ca/sign"))}">'
            f"{csrf}"
            '<p class="muted">The download holds the signed certificate followed by its CA chain.</p>'
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
            f'<button class="btn">{ui.icon("file-sign")}Sign and download</button></form></details>'
        )

    def mdm_download(self, query):
        first = lambda name: (query.get(name) or [""])[0].strip()  # noqa: E731
        try:
            data, filename = mdm_profile(first("platform"), first("contents"), first("cn"),
                                         default_base_url(self.headers), first("email"))
        except ValueError as err:
            self.redirect("/tools?" + urllib.parse.urlencode({"error": str(err)}) + "#mdm")
            return
        print(f"Downloaded MDM profile {filename}", flush=True)
        self.download(data, filename, "application/x-apple-aspen-config")

    def mdm_card(self, base, extra):
        """Values for an MDM's SCEP, certificate, and Wi-Fi payloads."""
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
            ("Challenge", challenge, None),
            ("Subject", '<span class="mono">CN=&lt;unique device variable&gt;</span>, e.g. '
             '<span class="mono">CN=$SERIALNUMBER</span>', None),
            ("Key", "RSA, 2048 bits or more, usage signing and encryption, not exportable", None),
            ("Fingerprint", "Leave empty", None),
        ]
        if wifi_enabled():
            names = ", ".join(WIFI.get("radius_server_names") or []) or "the names in your RADIUS certificate"
            rows.append(("Wi-Fi", f"SSID <b>{esc(WIFI['ssid'])}</b>, EAP-TLS, identity = the SCEP payload, trusted "
                         f"certificates = the certificate payloads above, trusted server names = {esc(names)}", None))
        dl = "".join(
            f'<div class="kv"><dt>{k}</dt><dd>{v}</dd>'
            + (ui.copy_button(c, k) if c else "<span></span>") + "</div>"
            for k, v, c in rows
        )
        return (
            '<details class="expand" id="mdm"><summary>'
            f'<span class="row-icon">{ui.icon("cellphone")}</span><span class="summary-text">'
            '<span class="summary-title">Using an MDM</span>'
            '<span class="summary-sub">SCEP values and ready-made profiles for Jamf Pro, Kandji, Mosyle, '
            "Meraki, and other MDMs with a static challenge</span></span>"
            f'{ui.icon("chevron-down", "chev")}</summary>'
            '<div class="expand-body flush"><p class="muted expand-note">Intune SCEP profiles are not '
            "supported; see the add-on documentation.</p>"
            f'<dl class="rows">{dl}</dl>' + self.mdm_profile_form() + "</div></details>"
        )

    def mdm_profile_form(self):
        """Ready-made, unsigned profiles to upload to an MDM instead of entering the values."""
        options = [("scep", "Certificates and SCEP" + ("" if SCEP_CHALLENGE else " (needs scep_challenge)")),
                   ("trust", "Certificates only")]
        if wifi_enabled():
            options.insert(0, ("wifi", f"Certificates, SCEP, and Wi-Fi {esc(WIFI['ssid'])}"))
        contents = "".join(f'<option value="{v}">{label}</option>' for v, label in options)
        platforms = "".join(f'<option value="{v}">{label}</option>' for v, label in MDM_PLATFORMS.items())
        return (
            f'<form class="mdm-form" method="get" action="{esc(self.url("/download/mdm.mobileconfig"))}">'
            '<h3>Download a profile for your MDM</h3>'
            '<p class="muted">A standard, unsigned Apple configuration profile (.mobileconfig) with the payloads '
            "above. Upload it to any MDM as a custom profile; it is unsigned so the MDM can replace device "
            "variables and sign it. The macOS profile installs for the whole Mac (System keychain).</p>"
            '<div class="field-row">'
            f'<div class="field"><label for="mdm-platform">Platform</label><select id="mdm-platform" name="platform">{platforms}</select></div>'
            f'<div class="field"><label for="mdm-contents">Contents</label><select id="mdm-contents" name="contents">{contents}</select></div>'
            "</div>"
            '<div class="field"><label for="mdm-cn">Certificate name (Common Name)</label>'
            '<input id="mdm-cn" name="cn" maxlength="64" autocapitalize="off" '
            'placeholder="Your MDM\'s serial number or user name variable">'
            '<p class="hint">Your MDM\'s variable for a unique value, which it replaces on each device: the '
            'serial number for a device certificate (<span class="mono">$SERIALNUMBER</span> in Jamf, '
            '<span class="mono">$DEVICESERIAL</span> in Meraki, <span class="mono">$SERIAL_NUMBER</span> in '
            'Kandji) or the user name for a user certificate (<span class="mono">$USERNAME</span> in Jamf, '
            '<span class="mono">$OWNERUSERNAME</span> in Meraki). Not needed for Certificates only.</p></div>'
            '<div class="field"><label for="mdm-email">Email address (optional)</label>'
            '<input id="mdm-email" name="email" maxlength="64" autocapitalize="off" '
            'placeholder="Your MDM\'s email variable">'
            '<p class="hint">Added to the certificate as an email alternative name, e.g. '
            '<span class="mono">$EMAIL</span> in Jamf or <span class="mono">$OWNEREMAIL</span> in Meraki. '
            "The device must have a user assigned in the MDM.</p></div>"
            + ui.alert("warning", "SCEP profiles contain the challenge, so keep them private.")
            + f'<div class="form-submit"><button class="btn">{ui.icon("download")}Download .mobileconfig</button></div></form>'
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
ENROLL_PATH_RE = re.compile(r"^/enroll/([A-Za-z0-9_-]{32,64})(?:/(file/[A-Za-z0-9_-]{20,64}|root_ca\.crt))?$")


class EnrollHandler(Handler):
    """Public enrollment pages, reached through the integration's proxy.

    Only Home Assistant Core may connect; the one-time token in the path is
    the credential.
    """

    def public(self, path):
        return f"{enroll.PUBLIC_BASE}/{path.lstrip('/')}"

    def page(self, title, body, status=200, back=None, narrow=False, heading=None):
        self.document(
            title,
            '<main class="public"><div class="brand">'
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
            self.form_page(self.public(f"/enroll/{token}"), link)

    def do_POST(self):
        if not self.allowed():
            return
        token, sub = self.route()
        if token is None or sub:
            self.send(404, "Not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > 4096:
            self.send(413, "Request too large", "text/plain")
            return
        form = urllib.parse.parse_qs(self.rfile.read(length).decode(errors="replace"))
        link_id, link = LINKS.get(token)
        if link is None:
            self.gone()
            return
        cn = (link["cn"] or form.get("cn", [""])[0]).strip()
        if not enroll.valid_cn(cn):
            self.form_page(self.public(f"/enroll/{token}"), link, "Enter a certificate name using letters, digits, spaces, "
                           "and . _ @ - (up to 64 characters).", cn)
            return
        if form.get("kind", [""])[0] == "apple":
            self.apple_result(token, link_id, link, cn)
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
        if self.path != "/scep-challenge":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(min(length, 1 << 20)))
            challenge = str(request.get("scepChallenge") or "")
            csr = request.get("x509CertificateRequest") or {}
            cn = str((csr.get("subject") or {}).get("commonName") or "")
        except (ValueError, AttributeError):
            self.reply(False)
            return
        if LINKS.consume_challenge(challenge, cn):
            print(f"Enrollment link used: SCEP certificate for {cn!r}", flush=True)
            self.reply(True)
        elif not SCEP_CHALLENGE:
            self.reply(True)
        else:
            self.reply(bool(challenge) and secrets.compare_digest(challenge.encode(), SCEP_CHALLENGE.encode()))


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
        serve(("127.0.0.1", WEBHOOK_PORT), WebhookHandler, "SCEP challenge webhook",
              tls=(WEBHOOK_CERT, WEBHOOK_KEY)),
    ]
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
