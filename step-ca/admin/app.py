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
import base64
import datetime
import email
import email.policy
import html
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
SUPERVISOR_URL = os.environ.get("SUPERVISOR_URL", "http://supervisor")
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


def profile_for(cn, challenge, base_url, wifi, sans=(), group=""):
    root, inter = cert_chain()
    organization = ""
    match = re.search(r"(?:^|, )O=([^,]+)", SUBJECT_POLICY)
    if match:
        organization = match.group(1)
    xml = enroll.build_profile(
        cn=cn, challenge=challenge,
        scep_url=f"{base_url}{enroll.PUBLIC_BASE}/scep/{group_provisioner(group)}",
        ca_name=CA_NAME, organization=organization, root=root, intermediate=inter,
        wifi=WIFI if wifi else None, extra_cas=enroll.load_extra_cas(), sans=sans,
    )
    return SIGNER.sign(xml)


MDM_CN_RE = re.compile(r"^[A-Za-z0-9 ._@$%{}()-]{1,64}$")
MDM_PLATFORMS = {"ios": "iOS and iPadOS", "macos": "macOS"}
MDM_CONTENTS = ("trust", "scep", "wifi")


def mdm_profile(platform, contents, cn, base_url, email="", group=""):
    """Unsigned .mobileconfig for an MDM to upload as a custom profile.

    Unsigned because MDMs (Meraki, Jamf, ...) substitute variables such as
    $DEVICESERIAL in the profile, which a signature would forbid.
    Returns (data, filename) or raises ValueError.
    """
    if platform not in MDM_PLATFORMS or contents not in MDM_CONTENTS:
        raise ValueError("Unknown platform or profile contents.")
    if contents == "wifi" and not wifi_enabled():
        raise ValueError("Wi-Fi is not configured; set wifi.ssid in the add-on options.")
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
    names = {"trust": "CA certificates", "scep": "SCEP certificate", "wifi": f"Wi-Fi {WIFI.get('ssid', '')}"}
    # Certificates only is the same for every group.
    group = group if contents != "trust" else ""
    xml = enroll.build_profile(
        cn=cn or "device", challenge=challenge,
        scep_url=f"{base_url}{enroll.PUBLIC_BASE}/scep/{group_provisioner(group)}",
        ca_name=CA_NAME, organization=match.group(1) if match else "", root=root, intermediate=inter,
        wifi=WIFI if contents == "wifi" else None, extra_cas=enroll.load_extra_cas(),
        include_scep=contents != "trust", system_scope=platform == "macos", email_sans=[email],
        identifier=f"mdm.{group + '.' if group else ''}{contents}.{platform}",
        display_name=f"{CA_NAME}: {names[contents]}{', ' + group if group else ''} ({MDM_PLATFORMS[platform]})",
    )
    return xml, f"{safe_filename(CA_NAME)}-{group + '-' if group else ''}{contents}-{platform}.mobileconfig"


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
    if not wifi_enabled():
        return ""
    names = WIFI.get("radius_server_names") or []
    service = enroll.radius_service(WIFI)
    if service:
        names = names + [n for n in service["server_names"] if n not in names]
        ca = (f'{esc(enroll.common_name(service["roots"][0]))}, a public root '
              "(Android: Use system certificates)")
    elif enroll.load_extra_cas():
        ca = "ca-bundle.pem above (Android: install it as a CA certificate)"
    else:
        ca = "the root CA above (Android: install it as a CA certificate)"
    rows = [
        ("Network (SSID)", esc(WIFI["ssid"])),
        ("Security", f'{esc(WIFI.get("security", "WPA2"))} Enterprise, EAP method <b>TLS</b>'),
        ("CA certificate", ca),
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

    def page(self, title, body, status=200, back=None, narrow=False, heading=None, head=""):
        """A panel page: tabs on top-level pages, a back arrow on subpages."""
        if back:
            bar = (f'<a class="icon-btn back" href="{esc(self.url(back))}" aria-label="Back">'
                   f'{ui.icon("arrow-left")}</a><h1 class="toolbar-title">{esc(heading or title)}</h1>')
        else:
            current = self.current_tab()
            tabs = "".join(
                self.tools_menu(current) if path == "/tools" else
                f'<a class="tab" href="{esc(self.url(path))}"'
                f'{" aria-current=page" if path == current else ""}>{ui.icon(icon)}<span>{label}</span></a>'
                for path, label, icon in self.TABS
            )
            bar = f'<h1 class="toolbar-title">Certificates</h1><nav class="tabs" aria-label="Sections">{tabs}</nav>'
        self.document(
            title,
            f'<header class="toolbar">{bar}</header>'
            f'<main class="content{" narrow" if narrow else ""}">{body}</main>',
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
            if path == "/":
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
            elif path == "/tools/options":
                self.options_page()
            elif path == "/enroll":
                self.enroll_page(query=query)
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
            self.redirect("/tools/cas")
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
        if path == "/issue":
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
            self.redirect(f"/enroll?{urllib.parse.urlencode({'links': view, 'deleted': n})}")
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
                               link.get("sans") or (), link.get("group", ""))
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
        self.page(f"Certificate for {cn}", body, back="/enroll", narrow=True)

    # -- enrollment (admin) ------------------------------------------------------

    def self_enroll_page(self, error="", cn="", sans="", group="", email=""):
        csrf = f'<input type="hidden" name="csrf" value="{esc(CSRF_TOKEN)}">'
        self.form_page(self.url("/enroll/self"), {"cn": "", "wifi": wifi_enabled()}, error, cn, csrf,
                       email_input("self-email", email) + group_select("self-group", group)
                       + sans_input("self-sans", sans))

    def self_enroll(self, form):
        """Enroll the computer the panel is open on (e.g. a Mac or Windows PC)."""
        cn = form.get("cn", [""])[0].strip()
        sans_text = form.get("sans", [""])[0].strip()
        email_text = form.get("email", [""])[0].strip()
        group_text = form.get("group", [""])[0]
        if not enroll.valid_cn(cn):
            self.self_enroll_page("Enter a certificate name using letters, digits, spaces, "
                                  "and . _ @ - (up to 64 characters).", cn, sans_text, group_text, email_text)
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
            self.self_enroll_page("Set enrollment.public_url in the add-on options first.", cn)
            return
        who = self.headers.get("X-Remote-User-Display-Name") or self.headers.get("X-Remote-User-Name") or ""
        token = LINKS.create(label="This device (panel)", cn=cn, base_url=base_url,
                             wifi=wifi_enabled(), hours=1, created_by=who, sans=sans, group=group)
        link_id, link = LINKS.get(token)
        if form.get("kind", [""])[0] == "apple":
            self.apple_result(token, link_id, link, cn)
        else:
            self.p12_result(token, link_id, link, cn)

    LINK_VIEWS = {"waiting": ("pending",), "used": ("issued",), "ended": ("expired", "cancelled"),
                  "all": ("pending", "issued", "expired", "cancelled")}
    LINKS_PER_PAGE = 10

    def links_return(self, form):
        """Where to go back to after acting on a link: the view and page it was done from."""
        view = form.get("view", [""])[0]
        page = form.get("page", [""])[0]
        params = {"links": view if view in self.LINK_VIEWS else "waiting"}
        if page.isdigit() and page != "1":
            params["page"] = page
        return "/enroll?" + urllib.parse.urlencode(params)

    def enroll_page(self, notice="", query=None):
        query = query or {}
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
            kind = {"pending": "info", "issued": "ok", "expired": "neutral"}.get(state, "bad")
            name = link["label"] or link["cn"] or "this link"
            if state == "pending":
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
                 "ended": ("No expired or cancelled links", ""),
                 "all": ("No enrollment links yet", "Links you create appear here.")}[view]
        rows = rows or (f'<tr><td colspan="5">{ui.empty_state("link-variant", *empty)}</td></tr>')
        labels = {"waiting": "Waiting", "used": "Used", "ended": "Expired or cancelled", "all": "All"}
        link_filters = "".join(
            f'<a class="filter" href="{esc(self.url("/enroll") + "?" + urllib.parse.urlencode({"links": v}))}"'
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
                href = self.url("/enroll") + "?" + urllib.parse.urlencode({"links": view, "page": n})
                return f'<a class="icon-btn" href="{esc(href)}" aria-label="{label}" title="{label}">{ui.icon(icon)}</a>'
            pager = (
                '<nav class="pager" aria-label="Pages">'
                + page_link(page - 1, "chevron-left", "Previous page")
                + f"<span>Page {page} of {pages}</span>"
                + page_link(page + 1, "chevron-right", "Next page") + "</nav>"
            )
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
            'autocapitalize="off" placeholder="Chosen on the device"></div></div>'
            + email_input("email")
            + group_select("group", hint="The certificate gets this group&#39;s OU and lifetime.")
            + "</div>"
            f'<details class="expand"{advanced_open}><summary><span class="summary-text">'
            '<span class="summary-title">More options</span>'
            f'<span class="summary-sub">Other alternative names, Home Assistant URL, validity'
            f'{", Wi-Fi" if wifi_enabled() else ""}</span></span>{ui.icon("chevron-down", "chev")}</summary>'
            '<div class="expand-body">'
            + sans_input("sans")
            + '<div class="field"><label for="base">Home Assistant URL the device will use</label>'
            f'<input id="base" name="base_url" type="url" required value="{esc(base_url)}" '
            'placeholder="https://home.example.com">'
            + base_url_hint(base_url, base_source) + "</div>"
            '<div class="field"><label for="hours">Valid for (hours)</label>'
            f'<input id="hours" name="hours" type="number" min="1" max="168" value="{ENROLL_LINK_HOURS}" '
            'class="input-short"></div>'
            + wifi_opt + "</div></details>"
            f'<div class="card-actions"><button class="btn">{ui.icon("qrcode")}Create link</button></div></form>'
            '<div class="card" id="links"><div class="card-header"><h2>Links</h2></div>'
            f'<nav class="filters" aria-label="Link status">{link_filters}</nav>'
            + bar
            + '<div class="table-wrap"><table><thead><tr>'
            '<th>Label</th><th>Certificate</th><th>Status</th><th class="hide-mobile">Expires</th>'
            '<th><span class="visually-hidden">Actions</span></th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>{pager}</div>"
            '<dialog id="delete-link-dialog" aria-labelledby="delete-link-title">'
            '<h2 id="delete-link-title">Delete <span data-confirm-name></span>?</h2>'
            "<p>The link is removed from the list. Its certificate is not affected.</p>"
            '<div class="dialog-actions"><button type="button" class="btn text" data-confirm-no>Cancel</button>'
            '<button type="button" class="btn danger" data-confirm-yes>Delete</button></div></dialog>'
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
            + email_input("issue-email") + group_select("issue-group") + sans_input("issue-sans") + "</div>"
            + f'<div class="card-actions"><button class="btn text">{ui.icon("key-variant")}Issue .p12</button></div></form>'
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
            self.enroll_page(ui.alert("error", esc(error), "The link was not created"))
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
        self.page("Enrollment link", body, back="/enroll", narrow=True)

    def issue_direct(self, form):
        cn = form.get("cn", [""])[0].strip()
        if not enroll.valid_cn(cn):
            self.enroll_page(ui.alert("error", "The certificate name may use letters, digits, "
                                      "spaces, and . _ @ - (up to 64).", "Nothing was issued"))
            return
        try:
            sans = form_sans(form)
            group = parse_group(form.get("group", [""])[0])
            check_group_email(group, sans)
        except ValueError as err:
            self.enroll_page(ui.alert("error", esc(err), "Nothing was issued"))
            return
        try:
            data, password, cert = enroll.issue_p12(cn, ca_url=CA_URL, root_cert=ROOT_CERT,
                                                    extra_cas=enroll.load_extra_cas(), sans=sans,
                                                    **group_issue_args(group))
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
                           "Intermediate and root, for MDMs and RADIUS servers. In Meraki Access "
                           "Manager, upload it as one entry under Certificates, Enabled, with Trusted "
                           "Anchor on",
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
            + "".join(url_row(f"SCEP URL, {esc(g)}", f"{base}/api/step_ca_scep/scep/{esc(g)}") for g in GROUPS)
            + url_row("Root download", f"{base}/api/step_ca_scep/roots.pem")
            + url_row("CRL (DER)", f"{base}/api/step_ca_scep/crl")
            + "</dl></div></div></div>"
        )
        self.page("Authority", body)

    TOOLS_MENU = (
        ("/tools/groups", "Groups", "account-group", "OUs, SCEP URLs, and challenges"),
        ("/tools/mdm", "MDM profiles", "cellphone", "SCEP values and ready-made profiles"),
        ("/tools/sign", "Sign a request", "file-sign", "CSRs from servers or another CA"),
        ("/tools/cas", "Other trusted CAs", "server-security", "CAs enrolled devices also trust"),
        ("/tools/options", "Add-on options", "cog", "The running configuration"),
    )

    def tools_menu(self, current):
        """The Tools tab: a menu of the tool pages (a <details>, so it works without the script)."""
        here = urllib.parse.urlsplit(self.path).path.rstrip("/")
        links = "".join(
            f'<a href="{esc(self.url(path))}"{" aria-current=page" if path == here else ""}>{ui.icon(glyph)}'
            f'<span class="menu-text"><span>{label}</span><span class="menu-sub">{sub}</span></span></a>'
            for path, label, glyph, sub in self.TOOLS_MENU
        )
        return (
            f'<details class="tab-menu"><summary class="tab{" current" if current == "/tools" else ""}">'
            f'{ui.icon("wrench")}<span>Tools</span>{ui.icon("menu-down", "caret")}</summary>'
            f'<nav class="menu" aria-label="Tools">{links}</nav></details>'
        )

    def tools_page(self):
        rows = "".join(
            f'<a class="row" href="{esc(self.url(path))}"><span class="row-icon">{ui.icon(glyph)}</span>'
            f'<span class="row-text"><span class="row-title">{label}</span><span class="row-sub">{sub}</span></span>'
            f'{ui.icon("chevron-right", "row-icon")}</a>'
            for path, label, glyph, sub in self.TOOLS_MENU
        )
        self.page("Tools", f'<div class="card"><div class="card-header"><h2>Tools</h2></div>'
                  f'<div class="rows">{rows}</div></div>', narrow=True)

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
            '<p class="muted">Saved to the add-on options. Restart the add-on to apply.</p></div>'
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

    # -- other tools ---------------------------------------------------------------

    def options_page(self):
        def option(label, value):
            return f'<div class="kv"><dt>{label}</dt><dd>{value}</dd><span></span></div>'

        challenge = (ui.chip("ok", "Set") if SCEP_CHALLENGE else
                     ui.chip("warn", "Not set") + " Needed for MDM profiles in the default group")
        service = enroll.radius_service(WIFI)
        wifi = (f"<b>{esc(WIFI['ssid'])}</b>, EAP-TLS"
                + (f", RADIUS {esc(service['label'])} ({esc(', '.join(service['server_names']))})"
                   if service else "")
                if wifi_enabled() else "Off")
        groups = "<br>".join(
            f"<b>{esc(g['name'])}</b>: OU={esc(g['ou'])}, "
            + (f"valid {esc(g['duration'])}, " if g["duration"] else "")
            + ("challenge set" if g["challenge"] else "one-time links only")
            + (", email required" if g.get("require_email") else "")
            for g in GROUPS.values()) or "None"
        body = (
            '<div class="card"><div class="card-header"><h2>Add-on options</h2>'
            f'<p class="muted">The running configuration. Edit groups under <a href="{esc(self.url("/tools/groups"))}">'
            "Groups</a>; change the rest on the add-on's Configuration tab in Home Assistant.</p></div>"
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
            + '<div class="card"><div class="card-header"><h2>Other trusted CAs</h2>'
            '<p class="muted">CA certificates devices must also trust, such as the CA that issued your RADIUS '
            "server's certificate for EAP-TLS Wi-Fi. They are added to Apple profiles (and trusted for the "
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
            + '<div class="card"><div class="card-header"><h2>Sign a request</h2>'
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
            data, filename = mdm_profile(first("platform"), first("contents"), first("cn"),
                                         default_base_url(self.headers), first("email"), first("group"))
        except ValueError as err:
            self.tools_error("/tools/mdm", err)
            return
        print(f"Downloaded MDM profile {filename}", flush=True)
        self.download(data, filename, "application/x-apple-aspen-config")

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
        if wifi_enabled():
            names = ", ".join(WIFI.get("radius_server_names") or []) or "the names in your RADIUS certificate"
            rows.append(("Wi-Fi", f"SSID <b>{esc(WIFI['ssid'])}</b>, EAP-TLS, identity = the SCEP payload, trusted "
                         f"certificates = the certificate payloads above, trusted server names = {esc(names)}", None))
        dl = "".join(
            f'<div class="kv"><dt>{k}</dt><dd>{v}</dd>'
            + (ui.copy_button(c, k) if c else "<span></span>") + "</div>"
            for k, v, c in rows
        )
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
        options = [("scep", "Certificates and SCEP" + ("" if SCEP_CHALLENGE or GROUPS else " (needs scep_challenge)")),
                   ("trust", "Certificates only")]
        if wifi_enabled():
            options.insert(0, ("wifi", f"Certificates, SCEP, and Wi-Fi {esc(WIFI['ssid'])}"))
        contents = "".join(f'<option value="{v}">{label}</option>' for v, label in options)
        platforms = "".join(f'<option value="{v}">{label}</option>' for v, label in MDM_PLATFORMS.items())
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
            "it is unsigned so the MDM can replace its variables and sign it. The macOS profile installs for "
            "the whole Mac (System keychain).</p></div><div class=\"card-content\">"
            '<div class="field-row">'
            f'<div class="field"><label for="mdm-platform">Platform</label><select id="mdm-platform" name="platform">{platforms}</select></div>'
            f'<div class="field"><label for="mdm-contents">Contents</label><select id="mdm-contents" name="contents">{contents}</select></div>'
            "</div>"
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
            + f'</div><div class="card-actions"><button class="btn">{ui.icon("download")}Download .mobileconfig'
            "</button></div></form>"
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

    def page(self, title, body, status=200, back=None, narrow=False, heading=None, head=""):
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
        # /scep-challenge for the default provisioner, /scep-challenge/<group> for a group's.
        group = self.path.removeprefix("/scep-challenge/") if self.path.startswith("/scep-challenge/") else ""
        if self.path != "/scep-challenge" and group not in GROUPS:
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
        serve(("127.0.0.1", WEBHOOK_PORT), WebhookHandler, "SCEP challenge webhook",
              tls=(WEBHOOK_CERT, WEBHOOK_KEY)),
    ]
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
