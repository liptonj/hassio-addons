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
    return f'<p class="muted">{hint}</p>'


def signer_status():
    """(ok, html) describing which certificate signs profiles."""
    try:
        label, cert, _, _ = SIGNER.signer()
    except RuntimeError as err:
        return False, f'<span class="revoked pill">unavailable</span> {esc(err)}'
    issuer = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
    issuer = issuer[0].value if issuer else cert.issuer.rfc4514_string()
    who = f"{esc(cert.subject.rfc4514_string())} <span class=muted>issued by {esc(issuer)}, " \
          f"valid until {esc(fmt_time(cert.not_valid_after_utc))}</span>"
    if label == "public":
        return True, f'<span class="active pill">Verified</span> {who}'
    return False, (
        f'<span class="expired pill">Not Verified</span> {who}<br><span class="muted">Signed by '
        "this CA because no publicly trusted certificate is available"
        + (f" ({esc(PUBLIC_SIGNER_LABEL)} was not found)" if PUBLIC_SIGNER_LABEL else "")
        + ". Install and start the <b>Let&#39;s Encrypt</b> add-on; its certificate in /ssl is picked up "
        "within an hour.</span>"
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


def sans_input(value=""):
    return (
        '<label for="sans">Alternative names (optional)</label>'
        f'<input id="sans" name="sans" maxlength="2000" value="{esc(value)}" '
        'placeholder="e.g. josh@example.com, host.example.com, 192.0.2.10" autocapitalize="off">'
        '<p class="muted">Email addresses, DNS names, and IP addresses, separated by commas. '
        "Apple profiles support email and DNS names only.</p>"
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
        '<div class="card"><h2 style="margin-top:0">Connect to Wi-Fi</h2><dl>'
        + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows) + "</dl></div>"
    )


STYLE = """
:root { color-scheme: light dark; --bg:#fafafa; --fg:#1c1c1c; --muted:#6b6b6b;
  --card:#fff; --line:#e3e3e3; --accent:#03a9f4; --ok:#2e7d32; --warn:#b26a00; --bad:#c62828; }
@media (prefers-color-scheme: dark) { :root { --bg:#111; --fg:#e6e6e6; --muted:#9a9a9a;
  --card:#1c1c1c; --line:#333; --ok:#66bb6a; --warn:#ffa726; --bad:#ef5350; } }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background:var(--bg); color:var(--fg); }
main { max-width:1100px; margin:0 auto; padding:16px; }
h1 { font-size:20px; margin:4px 0 16px; }
h2 { font-size:16px; margin:24px 0 8px; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:16px; }
.bar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.grow { flex:1; }
input, select, button { font:inherit; padding:6px 10px; border:1px solid var(--line); border-radius:6px;
  background:var(--card); color:var(--fg); }
button { cursor:pointer; }
button.danger { background:var(--bad); color:#fff; border-color:var(--bad); }
.tabs a { padding:4px 10px; border-radius:6px; color:var(--fg); }
.tabs a.on { background:var(--accent); color:#fff; }
.tablewrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; }
th, td { text-align:left; padding:8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; }
.mono { font-family:ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12px; word-break:break-all; }
.muted { color:var(--muted); }
.pill { display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; font-weight:600; }
.active { color:var(--ok); border:1px solid var(--ok); }
.expired { color:var(--warn); border:1px solid var(--warn); }
.revoked { color:var(--bad); border:1px solid var(--bad); }
dl { display:grid; grid-template-columns:max-content 1fr; gap:6px 16px; margin:0; }
dt { color:var(--muted); }
dd { margin:0; word-break:break-word; }
.msg { padding:10px 14px; border-radius:6px; margin-bottom:16px; border:1px solid var(--line); }
.msg.error { border-color:var(--bad); color:var(--bad); }
.msg.ok { border-color:var(--ok); color:var(--ok); }
pre { white-space:pre-wrap; margin:0; }
.qr { background:#fff; padding:12px; border-radius:8px; display:inline-block; }
.qr svg { width:240px; height:240px; display:block; }
.big { font-size:18px; font-weight:600; letter-spacing:1px; }
label { display:block; margin:12px 0 4px; font-weight:600; }
.choice { display:flex; gap:8px; align-items:flex-start; margin:8px 0; font-weight:normal; }
input[type=text], input[type=url], input:not([type]) { width:100%; }
.btn { display:inline-block; padding:8px 14px; border-radius:6px; background:var(--accent); color:#fff; }
"""


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

    def send(self, status, body, content_type="text/html; charset=utf-8", headers=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'self'",
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

    def page(self, title, body, status=200):
        nav = (
            f'<div class="bar" style="margin-bottom:8px"><a href="{esc(self.url("/"))}">Certificates</a>'
            f'<span class="muted">·</span><a href="{esc(self.url("/enroll"))}">Enroll devices</a>'
            f'<span class="muted">·</span><a href="{esc(self.url("/ca"))}">CA &amp; downloads</a></div>'
        )
        self.send(
            status,
            f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f'<meta name=viewport content="width=device-width, initial-scale=1">'
            f"<title>{esc(title)}</title><style>{STYLE}</style></head>"
            f"<body><main>{nav}{body}</main></body></html>",
        )

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
                self.ca_page(query)
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
                    self.page("Not found", "<h1>Not found</h1>", 404)
                else:
                    self.download(extra_chain(certs[0]),
                                  f"{safe_filename(enroll.common_name(certs[0]))}.pem", "application/x-pem-file")
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
                self.page("Not found", "<h1>Not found</h1>", 404)
        except Exception as err:  # noqa: BLE001 - shown on the page
            self.error_page(err)

    def error_page(self, err):
        # Home Assistant shows "The app is starting" and retries for 5xx
        # ingress responses, hiding the error, so errors are shown with 200.
        traceback.print_exc()
        title = "Database error" if isinstance(err, pymysql.MySQLError) else "Error"
        self.page(title, f'<h1>{title}</h1><div class="msg error">{esc(err)}</div>'
                  '<p class="muted">Details are in the add-on log.</p>')

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
            self.redirect("/ca")
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
            '<div class="msg">The certificate list needs step-ca to store its records in MariaDB. '
            "Set the add-on option <b>database</b> to <b>mariadb</b> and install the MariaDB add-on. "
            'CA certificates and the CRL are still available under '
            f'<a href="{esc(self.url("/ca"))}">CA &amp; downloads</a>.</div>'
        )

    def list_page(self, query):
        if not db_enabled():
            self.page("Certificates", "<h1>Certificates</h1>" + self.no_db())
            return
        status = query.get("status", ["active"])[0]
        if status not in ("all", "active", "expired", "revoked"):
            status = "active"
        search = query.get("q", [""])[0].strip()
        certs = fetch_certs()
        counts = {s: sum(1 for c in certs if c["status"] == s) for s in ("active", "expired", "revoked")}
        counts["all"] = len(certs)
        shown = [c for c in certs if status == "all" or c["status"] == status]
        if search:
            needle = search.lower()
            shown = [
                c for c in shown
                if needle in c["cn"].lower() or needle in c["serial"]
                or needle in c["subject"].lower() or any(needle in s.lower() for s in c["sans"])
            ]

        tabs = "".join(
            f'<a class="{"on" if s == status else ""}" '
            f'href="{esc(self.url("/") + "?" + urllib.parse.urlencode({"status": s, "q": search}))}">'
            f"{s.title()} ({counts[s]})</a>"
            for s in ("active", "expired", "revoked", "all")
        )
        rows = "".join(
            f"<tr><td><a href=\"{esc(self.url('/cert/' + c['serial']))}\">{esc(c['cn'] or '(no CN)')}</a>"
            f"<div class=\"muted\">{esc(', '.join(c['sans'][:3]))}</div></td>"
            f"<td><span class=\"pill {c['status']}\">{c['status']}</span></td>"
            f"<td>{esc(fmt_time(c['not_before']))}</td><td>{esc(fmt_time(c['not_after']))}</td>"
            f"<td>{esc(c['provisioner'])}</td>"
            f"<td class=\"mono\">{esc(c['serial'][:24])}{'…' if len(c['serial']) > 24 else ''}</td></tr>"
            for c in shown
        ) or '<tr><td colspan="6" class="muted">No certificates.</td></tr>'
        body = (
            "<h1>Certificates</h1>"
            '<div class="card"><form class="bar" method="get" action="'
            f'{esc(self.url("/"))}"><input type="hidden" name="status" value="{esc(status)}">'
            f'<input class="grow" type="search" name="q" value="{esc(search)}" '
            'placeholder="Search name, SAN, or serial"><button>Search</button></form>'
            f'<div class="bar tabs" style="margin-top:12px">{tabs}</div></div>'
            '<div class="card tablewrap"><table><thead><tr><th>Name</th><th>Status</th>'
            "<th>Issued</th><th>Expires</th><th>Provisioner</th><th>Serial</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        )
        self.page("Certificates", body)

    def detail_page(self, serial, query):
        if not db_enabled():
            self.page("Certificate", self.no_db())
            return
        certs = fetch_certs(serial)
        if not certs:
            self.page("Not found", "<h1>Certificate not found</h1>", 404)
            return
        c = certs[0]
        msg = ""
        if "error" in query:
            msg = f'<div class="msg error">Revocation failed: {esc(query["error"][0])}</div>'
        elif "revoked" in query:
            msg = '<div class="msg ok">Certificate revoked. The CRL has been updated.</div>'
        fingerprint = c["cert"].fingerprint(hashes.SHA256()).hex()
        details = [
            ("Status", f'<span class="pill {c["status"]}">{c["status"]}</span>'),
            ("Subject", esc(c["subject"])),
            ("SANs", esc(", ".join(c["sans"])) or '<span class="muted">none</span>'),
            ("Issuer", esc(c["issuer"])),
            ("Valid from", esc(fmt_time(c["not_before"]))),
            ("Valid until", esc(fmt_time(c["not_after"]))),
            ("Provisioner", esc(c["provisioner"] + (f' ({c["provisioner_type"]})' if c["provisioner_type"] else ""))),
            ("Serial", f'<span class="mono">{esc(c["serial"])}</span>'),
            ("SHA-256", f'<span class="mono">{esc(fingerprint)}</span>'),
        ]
        if c["revoked"]:
            r = c["revoked"]
            code = r.get("ReasonCode", 0)
            details += [
                ("Revoked at", esc(r.get("RevokedAt", ""))),
                ("Reason", esc(f'{REASONS.get(code, code)}' + (f' — {r["Reason"]}' if r.get("Reason") else ""))),
            ]
        dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in details)
        revoke_form = ""
        if c["status"] != "revoked":
            options = "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in REASONS.items())
            revoke_form = (
                '<div class="card"><h2 style="margin-top:0">Revoke</h2>'
                '<p class="muted">Revocation cannot be undone. Relying systems such as RADIUS must '
                "load the updated CRL to reject the certificate.</p>"
                f'<form class="bar" method="post" action="{esc(self.url("/cert/" + serial + "/revoke"))}">'
                f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
                f'<select name="reasonCode">{options}</select>'
                '<input class="grow" name="reason" maxlength="200" placeholder="Note (optional)">'
                '<button class="danger">Revoke certificate</button></form></div>'
            )
        body = (
            f"<h1>{esc(c['cn'] or '(no CN)')}</h1>{msg}"
            f'<div class="card"><dl>{dl}</dl>'
            f'<div class="bar" style="margin-top:16px"><a href="{esc(self.url("/cert/" + serial + ".pem"))}">'
            "Download certificate (PEM)</a></div></div>"
            f"{revoke_form}"
        )
        self.page(c["cn"] or "Certificate", body)

    def cert_pem(self, serial):
        if not db_enabled() or not SERIAL_RE.match(serial):
            self.page("Not found", "<h1>Not found</h1>", 404)
            return
        certs = fetch_certs(serial)
        if not certs:
            self.page("Not found", "<h1>Certificate not found</h1>", 404)
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
        return ('<div class="msg">Home Assistant is open over HTTP, so your browser may warn that '
                f"the download is insecure. Choose <b>Keep</b>{https}.</div>")

    def gone(self):
        self.page("Link not valid", "<h1>This enrollment link is not valid</h1>"
                  "<p>It may have expired, been used already, or been cancelled. Ask your "
                  "Home Assistant administrator for a new one.</p>", 404)

    def enroll_file(self, token, sub):
        if sub == "root_ca.crt":
            der = cert_chain()[0].public_bytes(serialization.Encoding.DER)
            self.download(der, "root_ca.crt", "application/x-x509-ca-cert")
            return
        entry = DOWNLOADS.get(enroll._hash(token), sub[len("file/"):])
        if entry is None:
            self.page("Expired", "<h1>This download has expired</h1><p>Start the enrollment "
                      "again to get a new one.</p>", 404)
            return
        data, filename, content_type = entry
        self.download(data, filename, content_type)

    def form_page(self, action, link, error="", cn="", hidden="", extra=""):
        apple = bool(APPLE_UA_RE.search(self.headers.get("User-Agent", "")))
        cn = link["cn"] or cn
        if link["cn"]:
            name = (f'<p>Certificate name: <b>{esc(link["cn"])}</b></p>'
                    f'<input type="hidden" name="cn" value="{esc(link["cn"])}">')
        else:
            name = ('<label for="cn">Certificate name</label>'
                    f'<input id="cn" name="cn" maxlength="64" required value="{esc(cn)}" '
                    'placeholder="e.g. josh-iphone" autocapitalize="off" autocorrect="off">'
                    '<p class="muted">Letters, digits, spaces, and . _ @ - only.</p>')
        wifi = ""
        if link["wifi"] and wifi_enabled():
            wifi = f' It also sets up Wi-Fi network <b>{esc(WIFI["ssid"])}</b>.'
        body = (
            f"<h1>Get a certificate from {esc(CA_NAME)}</h1>"
            + (f'<div class="msg error">{esc(error)}</div>' if error else "")
            + f'<div class="card"><form method="post" action="{esc(action)}">'
            + hidden + name + extra
            + "<label>Device</label>"
            f'<label class="choice"><input type="radio" name="kind" value="apple"{" checked" if apple else ""}> '
            "<span><b>iPhone, iPad, or Mac</b><br><span class=muted>Installs a profile. The device "
            f"creates its own private key and requests the certificate itself.{wifi}</span></span></label>"
            f'<label class="choice"><input type="radio" name="kind" value="p12"{"" if apple else " checked"}> '
            "<span><b>Other device</b> (Android, Windows, Linux, ...)<br><span class=muted>Downloads a "
            "password-protected .p12 file with the certificate, its key, and the CA chain.</span></span></label>"
            '<div style="margin-top:16px"><button class="btn">Continue</button></div></form></div>'
        )
        self.page("Enroll device", body)

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
            self.page("Error", '<div class="msg error">The profile could not be created. '
                      "Ask your administrator to check the add-on log.</div>", 500)
            return
        download = DOWNLOADS.add(link_id, data, f"{safe_filename(cn)}.mobileconfig",
                                 "application/x-apple-aspen-config")
        href = f"{self.enroll_prefix()}/{token}/file/{download}"
        body = (
            f"<h1>Install the profile</h1>{self.insecure_note()}"
            f'<div class="card"><p><a class="btn" href="{esc(href)}">Download profile</a></p>'
            "<ol>"
            "<li>Tap <b>Download profile</b> and choose <b>Allow</b>.</li>"
            "<li>iPhone / iPad: open <b>Settings</b>, tap <b>Profile Downloaded</b> near the top, "
            "then <b>Install</b>. Mac: open <b>System Settings &rsaquo; General &rsaquo; Device "
            "Management</b> and double-click the profile.</li>"
            "<li>Enter your device passcode and confirm. The device creates its key and requests "
            f"the certificate <b>{esc(cn)}</b>. This needs a connection to Home Assistant.</li>"
            "</ol>"
            '<p class="muted">The profile works once and must be installed within an hour. If the '
            "install fails, start the enrollment again to get a fresh profile.</p></div>"
        )
        self.page("Install the profile", body)

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
            self.page("Error", '<div class="msg error">The certificate could not be issued. '
                      "Ask your administrator to check the add-on log.</div>", 500)
            return
        download = DOWNLOADS.add(link_id, data, f"{safe_filename(cn)}.p12", "application/x-pkcs12")
        bundle = DOWNLOADS.add(link_id, full_bundle(), "ca-bundle.pem", "application/x-pem-file")
        radius = ", including the Wi-Fi (RADIUS) server CA" if enroll.load_extra_cas() else ""
        body = (
            f"<h1>Certificate for {esc(cn)}</h1>{self.insecure_note()}"
            '<div class="card"><p>Password for the .p12 file. Write it down now; it is not shown again:</p>'
            f'<p class="big mono">{esc(password)}</p>'
            f'<p><a class="btn" href="{esc(f"{self.enroll_prefix()}/{token}/file/{download}")}">'
            f"Download {esc(safe_filename(cn))}.p12</a></p>"
            f'<p><a href="{esc(f"{self.enroll_prefix()}/{token}/root_ca.crt")}">Download the root CA '
            "certificate</a> separately if your device asks for a CA certificate"
            + f', or <a href="{esc(f"{self.enroll_prefix()}/{token}/file/{bundle}")}">ca-bundle.pem</a> '
            f"with all CA certificates{radius}"
            + ".</p>"
            '<p class="muted">The download is available for 10 minutes. Android: Settings &rsaquo; '
            "Security &rsaquo; Encryption &amp; credentials &rsaquo; Install a certificate. Windows: "
            "double-click the file, choose <b>Current User</b>, and keep the default store choices. "
            "macOS: open it in Keychain Access.</p></div>"
            + wifi_help()
        )
        self.page(f"Certificate for {cn}", body)

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
                '<label class="choice"><input type="checkbox" name="wifi" value="1" checked> '
                f'Apple profile also configures Wi-Fi <b>{esc(WIFI["ssid"])}</b></label>'
            )
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        rows = ""
        for link in LINKS.all():
            state = link["state"]
            pill = {"pending": "active", "issued": "active", "expired": "expired"}.get(state, "revoked")
            cancel = ""
            if state == "pending":
                cancel = (
                    f'<form method="post" action="{esc(self.url("/enroll/" + link["id"] + "/cancel"))}">'
                    f'{csrf}<button>Cancel</button></form>'
                )
            when = datetime.datetime.fromtimestamp(link["expires"], datetime.timezone.utc)
            rows += (
                f"<tr><td>{esc(link['label'] or '—')}<div class=muted>{esc(link['created_by'])}</div></td>"
                f"<td>{esc(link['issued_cn'] or link['cn'] or 'chosen on device')}"
                + (f"<div class=muted>{esc(', '.join(link['sans']))}</div>" if link.get("sans") else "")
                + f"<div class=muted>{esc(link['method'])}</div></td>"
                f'<td><span class="pill {pill}">{esc(state)}</span></td>'
                f"<td>{esc(fmt_time(when))}</td><td>{cancel}</td></tr>"
            )
        rows = rows or '<tr><td colspan="5" class="muted">No enrollment links yet.</td></tr>'
        body = (
            f"<h1>Enroll devices</h1>{notice}"
            '<div class="card"><h2 style="margin-top:0">This computer</h2>'
            '<p class="muted">Get a certificate for the Mac or Windows PC you are using right now.</p>'
            f'<p><a class="btn" href="{esc(self.url("/enroll/self"))}">Enroll this device</a></p></div>'
            '<div class="card"><h2 style="margin-top:0">New one-time link</h2>'
            '<p class="muted">Creates a link and QR code for one device. Opened on an iPhone, iPad, or '
            "Mac it installs a signed profile: the device creates its own key and gets its certificate "
            "over SCEP. Other devices get a password-protected .p12 file with the full CA chain. "
            "No MDM is needed.</p>"
            f'<form method="post" action="{esc(self.url("/enroll/new"))}">{csrf}'
            '<label for="label">Label</label><input id="label" name="label" maxlength="64" '
            'placeholder="e.g. Josh&#39;s iPhone">'
            '<label for="cn">Certificate name (CN)</label><input id="cn" name="cn" maxlength="64" '
            'placeholder="Leave empty to let the device owner choose">'
            + sans_input() +
            '<label for="base">Home Assistant URL the device will use</label>'
            f'<input id="base" name="base_url" type="url" required value="{esc(base_url)}" '
            'placeholder="https://home.example.com">'
            + base_url_hint(base_url, base_source) +
            '<label for="hours">Valid for (hours)</label>'
            f'<input id="hours" name="hours" type="number" min="1" max="168" value="{ENROLL_LINK_HOURS}" '
            'style="width:120px">'
            f"{wifi_opt}"
            '<div style="margin-top:16px"><button class="btn">Create link</button></div></form></div>'
            '<div class="card"><h2 style="margin-top:0">Profile signing</h2>'
            f"<p>{signer_html}</p></div>"
            '<div class="card"><h2 style="margin-top:0">Issue a certificate now</h2>'
            '<p class="muted">Creates a key and certificate here and gives you a .p12 to hand over.</p>'
            f'<form class="bar" method="post" action="{esc(self.url("/issue"))}">{csrf}'
            '<input class="grow" name="cn" maxlength="64" required placeholder="Certificate name (CN)">'
            "<button>Issue .p12</button>"
            '<input class="grow" name="sans" maxlength="2000" autocapitalize="off" '
            'placeholder="Alternative names (optional): email, DNS names, IP addresses">'
            "</form></div>"
            '<div class="card tablewrap"><h2 style="margin-top:0">Links</h2><table><thead><tr>'
            "<th>Label</th><th>Certificate</th><th>Status</th><th>Expires</th><th></th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
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
            self.enroll_page(f'<div class="msg error">{esc(error)}</div>')
            return
        who = self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or ""
        token = LINKS.create(label=label, cn=cn, base_url=base_url, wifi=field("wifi") == "1" and wifi_enabled(),
                             hours=hours, created_by=who, sans=sans)
        link = f"{base_url}{enroll.PUBLIC_BASE}/enroll/{token}"
        body = (
            f"<h1>Enrollment link{': ' + esc(label) if label else ''}</h1>"
            '<div class="card" style="text-align:center">'
            f'<div class="qr">{qr_svg(link)}</div>'
            f'<p class="mono" style="margin-top:12px">{esc(link)}</p>'
            f"<p>Scan with the device camera, or open the link in its browser. Valid for {hours} hour"
            f"{'s' if hours != 1 else ''}, for one certificate"
            f"{' named <b>' + esc(cn) + '</b>' if cn else ''}.</p>"
            '<p class="muted">This link is shown only once. Anyone with it can enroll a device, so '
            "share it only with the device owner.</p></div>"
            f'<p><a href="{esc(self.url("/enroll"))}">Back to enrollment</a></p>'
        )
        self.page("Enrollment link", body)

    def issue_direct(self, form):
        cn = form.get("cn", [""])[0].strip()
        if not enroll.valid_cn(cn):
            self.enroll_page('<div class="msg error">The certificate name may use letters, digits, '
                             "spaces, and . _ @ - (up to 64).</div>")
            return
        try:
            sans = enroll.parse_sans(form.get("sans", [""])[0])
        except ValueError as err:
            self.enroll_page(f'<div class="msg error">{esc(err)}</div>')
            return
        try:
            data, password, cert = enroll.issue_p12(cn, ca_url=CA_URL, root_cert=ROOT_CERT,
                                                    extra_cas=enroll.load_extra_cas(), sans=sans)
        except (RuntimeError, OSError, subprocess.SubprocessError) as err:
            self.enroll_page(f'<div class="msg error">Could not issue the certificate: {esc(err)}</div>')
            return
        download = DOWNLOADS.add("admin", data, f"{safe_filename(cn)}.p12", "application/x-pkcs12")
        serial = str(cert.serial_number)
        body = (
            f"<h1>Certificate for {esc(cn)}</h1>{self.insecure_note()}"
            '<div class="card"><p>Password for the .p12 file (shown only once):</p>'
            f'<p class="big mono">{esc(password)}</p>'
            f'<p><a class="btn" href="{esc(self.url("/issue/file/" + download))}">Download {esc(safe_filename(cn))}.p12</a></p>'
            '<p class="muted">The download is available for 10 minutes. The file contains the private '
            "key, the certificate, and the intermediate and root CA certificates"
            + (" plus the other trusted CAs" if enroll.load_extra_cas() else "") + ".</p>"
            + (f'<p><a href="{esc(self.url("/cert/" + serial))}">View certificate</a></p>' if db_enabled() else "")
            + "</div>"
        )
        self.page(f"Certificate for {cn}", body)

    def admin_file(self, download_id):
        entry = DOWNLOADS.get("admin", download_id)
        if entry is None:
            self.page("Expired", "<h1>This download has expired</h1>", 404)
            return
        data, filename, content_type = entry
        self.download(data, filename, content_type)

    def extra_ca_add(self, form):
        data = form.get("file", [b""])[0]
        if not data.strip():
            data = str(form.get("pem", [""])[0]).encode()
        if not data.strip():
            self.redirect("/ca?error=" + urllib.parse.quote("Choose a certificate file or paste a PEM."))
            return
        try:
            new = enroll.parse_ca_certs(data if isinstance(data, bytes) else data.encode())
        except ValueError as err:
            self.redirect("/ca?error=" + urllib.parse.quote(str(err)[:300]))
            return
        certs = enroll.load_extra_cas()
        known = {enroll.fingerprint(c) for c in certs}
        certs += [c for c in new if enroll.fingerprint(c) not in known]
        enroll.save_extra_cas(certs)
        self.redirect("/ca?added=1")

    def sign_request(self, form):
        data = form.get("file", [b""])[0]
        if not data.strip():
            data = str(form.get("pem", [""])[0]).encode()
        if not data.strip():
            self.redirect("/ca?error=" + urllib.parse.quote("Choose a certificate request file or paste a PEM."))
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
            self.redirect("/ca?error=" + urllib.parse.quote(str(err)[:300]))
            return
        print(f"Signed {signer} {cert.subject.rfc4514_string()!r} for an uploaded request "
              f"(serial {cert.serial_number}, valid until {cert.not_valid_after_utc:%Y-%m-%d})", flush=True)
        self.download(b"".join(c.public_bytes(serialization.Encoding.PEM) for c in chain),
                      f"{safe_filename(enroll.common_name(cert))}-chain.crt", "application/x-pem-file")

    def ca_page(self, query=None):
        query = query or {}
        root, inter = cert_chain()
        extra = enroll.load_extra_cas()
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'

        def details(cert):
            return (
                f"<dt>Subject</dt><dd>{esc(cert.subject.rfc4514_string())}</dd>"
                f"<dt>Issuer</dt><dd>{esc(cert.issuer.rfc4514_string())}</dd>"
                f"<dt>Valid until</dt><dd>{esc(fmt_time(cert.not_valid_after_utc))}</dd>"
                f'<dt>SHA-256</dt><dd class="mono">{esc(enroll.fingerprint(cert))}</dd>'
            )

        def block(title, cert, link, filename):
            return (
                f'<div class="card"><h2 style="margin-top:0">{title}</h2><dl>{details(cert)}</dl>'
                f'<div style="margin-top:12px"><a href="{esc(self.url(link))}">Download {filename}</a></div></div>'
            )

        extra_rows = "".join(
            f'<div class="card"><dl>{details(cert)}</dl>'
            f'<div style="margin-top:12px"><a href="{esc(self.url(f"/download/extra/{enroll.fingerprint(cert)}.pem"))}">'
            f"Download {esc(safe_filename(enroll.common_name(cert)))}.pem</a></div>"
            f'<form method="post" action="{esc(self.url(f"/ca/extra/{enroll.fingerprint(cert)}/remove"))}" '
            f'style="margin-top:12px">{csrf}<button class="btn">Remove</button></form></div>'
            for cert in extra
        )
        notice = ""
        if query.get("error"):
            notice = f'<div class="msg error">{esc(query["error"][0])}</div>'
        elif query.get("added"):
            notice = '<div class="msg">Certificate added. New profiles and .p12 files include it.</div>'
        base = default_base_url(self.headers) or "&lt;Home Assistant URL&gt;"
        base = esc(base) if not base.startswith("&lt;") else base
        body = (
            "<h1>CA &amp; downloads</h1>" + notice
            + block("Root CA", root, "/download/root_ca.pem", "root_ca.pem")
            + block("Intermediate CA", inter, "/download/intermediate_ca.pem", "intermediate_ca.pem")
            + '<div class="card"><h2 style="margin-top:0">Other trusted CAs (e.g. RADIUS server)</h2>'
            "<p>CA certificates devices must also trust, such as the CA that issued your RADIUS "
            "server's certificate for EAP-TLS Wi-Fi. They are added to Apple profiles (and trusted "
            "for the Wi-Fi network), to .p12 files, and to ca-bundle.pem.</p>"
            f'<form method="post" enctype="multipart/form-data" action="{esc(self.url("/ca/extra"))}">'
            f'{csrf}<label for="file">Certificate file (.pem, .crt, .cer)</label>'
            '<input id="file" type="file" name="file" accept=".pem,.crt,.cer,.der">'
            '<label for="pem">or paste PEM</label>'
            '<textarea id="pem" name="pem" rows="4" class="mono" style="width:100%" '
            'placeholder="-----BEGIN CERTIFICATE-----"></textarea>'
            '<div style="margin-top:12px"><button class="btn">Add</button></div></form></div>'
            + extra_rows
            + '<div class="card"><h2 style="margin-top:0">Certificate chain</h2>'
            f'<p><a href="{esc(self.url("/download/ca-chain.pem"))}">Download ca-chain.pem</a></p>'
            '<p class="muted">The intermediate and root CA in one PEM file (full trusted chain), '
            "for MDMs and RADIUS servers.</p></div>"
            + self.sign_card(csrf)
            + '<div class="card"><h2 style="margin-top:0">Full CA bundle</h2>'
            f'<p><a href="{esc(self.url("/download/ca-bundle.pem"))}">Download ca-bundle.pem</a></p>'
            '<p class="muted">Root, intermediate' + (", and the other trusted CAs" if extra else "")
            + " in one PEM file, for devices and servers that take a CA bundle.</p></div>"
            + '<div class="card"><h2 style="margin-top:0">Certificate revocation list</h2>'
            f'<p><a href="{esc(self.url("/download/crl.pem"))}">Download crl.pem</a></p>'
            f'<p class="muted">Also served without login at <span class=mono>{base}/api/step_ca_scep/crl</span> (DER).</p></div>'
            '<div class="card"><h2 style="margin-top:0">SCEP</h2><dl>'
            f"<dt>URL</dt><dd class=mono>{base}/api/step_ca_scep/scep/{esc(SCEP_PROVISIONER)}</dd>"
            f"<dt>Root download</dt><dd class=mono>{base}/api/step_ca_scep/roots.pem</dd>"
            "<dt>Issued subject</dt><dd>"
            + (esc(SUBJECT_POLICY) if SUBJECT_POLICY else "Taken from the client request")
            + "</dd>"
            "<dt>Storage</dt><dd>" + ("MariaDB" if db_enabled() else "Embedded database") + "</dd>"
            "</dl></div>"
            + self.mdm_card(base, extra)
        )
        self.page("CA & downloads", body)

    def sign_card(self, csrf):
        return (
            '<div class="card"><h2 style="margin-top:0">Sign a certificate request</h2>'
            "<p>Sign a certificate signing request (CSR) created on another system, such as a RADIUS, "
            "web, or VPN server, or another CA such as Meraki Systems Manager's SCEP CA. The download "
            "holds the signed certificate followed by its CA chain.</p>"
            f'<form method="post" enctype="multipart/form-data" action="{esc(self.url("/ca/sign"))}">'
            f"{csrf}"
            '<label class="choice"><input type="radio" name="kind" value="leaf" checked> '
            "<span><b>Server or client certificate</b><br><span class=muted>Signed by the intermediate "
            "CA for server and client authentication, with the Common Name and subject alternative "
            "names from the request, valid for the <b>default_cert_duration</b>. It is listed on "
            "<b>Certificates</b> and can be revoked.</span></span></label>"
            '<label class="choice"><input type="radio" name="kind" value="ca"> '
            "<span><b>Subordinate CA</b> (e.g. Meraki SCEP CA)<br><span class=muted>Signed by the root "
            "CA with the subject kept exactly as requested and the extensions "
            "<span class=mono>basicConstraints = critical,CA:true,pathlen:0</span> and "
            "<span class=mono>keyUsage = critical,keyCertSign,digitalSignature</span>, valid for {enroll.SUBORDINATE_DAYS // 365} years or until the root expires. "
            "Also accepts the other CA's current certificate. For Meraki, download the SCEP CA request "
            "under <b>Organization &gt; MDM</b> and upload the signed file there.</span></span></label>"
            '<label for="signfile">Certificate request (.csr, .req, .pem)</label>'
            '<input id="signfile" type="file" name="file" accept=".csr,.req,.pem,.crt,.cer,.der">'
            '<label for="signpem">or paste PEM</label>'
            '<textarea id="signpem" name="pem" rows="4" class="mono" style="width:100%" '
            'placeholder="-----BEGIN CERTIFICATE REQUEST-----"></textarea>'
            '<p class="muted">Only sign requests from systems you control; every signing is written to '
            "the add-on log.</p>"
            '<div style="margin-top:12px"><button class="btn">Sign and download</button></div></form></div>'
        )

    def mdm_card(self, base, extra):
        """Values for an MDM's SCEP, certificate, and Wi-Fi payloads."""
        certs = [f'<a href="{esc(self.url("/download/ca-chain.pem"))}">ca-chain.pem</a> (this CA: '
                 "intermediate and root)"]
        # One payload per chain: skip uploaded CAs that are an issuer of another upload.
        issuers = {c.issuer for c in extra if c.issuer != c.subject}
        certs += [f'<a href="{esc(self.url(f"/download/extra/{enroll.fingerprint(c)}.pem"))}">'
                  f"{esc(safe_filename(enroll.common_name(c)))}.pem</a>"
                  for c in extra if c.subject not in issuers]
        challenge = ("the <b>scep_challenge</b> add-on option (static)" if SCEP_CHALLENGE else
                     '<span style="color:var(--bad)">none set; set <b>scep_challenge</b> before '
                     "using an MDM</span>")
        wifi = ""
        if wifi_enabled():
            names = ", ".join(WIFI.get("radius_server_names") or []) or "the names in your RADIUS certificate"
            wifi = (f"<dt>Wi-Fi</dt><dd>SSID <b>{esc(WIFI['ssid'])}</b>, EAP-TLS, identity = the SCEP "
                    f"payload, trusted certificates = the certificate payloads above, trusted server "
                    f"names = {esc(names)}</dd>")
        return (
            '<div class="card"><h2 style="margin-top:0">Using an MDM</h2>'
            "<p>Values for an MDM configuration profile (Jamf Pro, Kandji, Mosyle, and other MDMs with a "
            "static SCEP challenge). Intune SCEP profiles are not supported; see the add-on "
            "documentation.</p><dl>"
            f"<dt>Certificate payloads</dt><dd>{'; '.join(certs)}. Each file is a full chain; "
            "upload each as one certificate payload.</dd>"
            f"<dt>SCEP URL</dt><dd class=mono>{base}/api/step_ca_scep/scep/{esc(SCEP_PROVISIONER)}</dd>"
            f"<dt>Challenge</dt><dd>{challenge}</dd>"
            "<dt>Subject</dt><dd class=mono>CN=&lt;unique device variable&gt;, e.g. CN=$SERIALNUMBER</dd>"
            "<dt>Key</dt><dd>RSA, 2048 bits or more, usage signing and encryption, not exportable</dd>"
            "<dt>Fingerprint</dt><dd>Leave empty</dd>"
            + wifi +
            "</dl></div>"
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

    def page(self, title, body, status=200):
        self.send(
            status,
            f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f'<meta name=viewport content="width=device-width, initial-scale=1">'
            f'<meta name="referrer" content="no-referrer">'
            f"<title>{esc(title)}</title><style>{STYLE}</style></head>"
            f"<body><main>{body}</main></body></html>",
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
