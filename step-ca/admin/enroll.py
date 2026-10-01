"""Device enrollment: one-time links, signed Apple profiles, and PKCS#12 bundles.

An administrator creates a one-time link (shown as a QR code). The device opens
it through Home Assistant and either:

* downloads a signed configuration profile (iPhone, iPad, Mac) holding the CA
  certificates, a SCEP payload with a one-time challenge so the device creates
  its own key, and optionally a Wi-Fi (EAP-TLS) payload using that identity; or
* receives a password-protected .p12 with a key, certificate, and the CA chain
  (Windows, Android, Linux, browsers).

Link tokens and SCEP challenges are stored only as SHA-256 hashes.
"""

import base64
import binascii
import datetime
import functools
import hashlib
import ipaddress
import json
import math
import os
import plistlib
import re
import secrets
import struct
import subprocess
import tempfile
import threading
import time
import uuid
import zlib

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from cryptography.x509.oid import NameOID

STEP_PATH = os.environ.get("STEPPATH", "/data/step")
STATE_FILE = f"{STEP_PATH}/enroll/links.json"
# Other CAs devices must trust, e.g. the RADIUS server's CA for EAP-TLS.
EXTRA_CA_FILE = f"{STEP_PATH}/enroll/extra_cas.pem"
ENROLL_PROVISIONER = "enrollment"
ENROLL_PASSWORD = f"{STEP_PATH}/secrets/enrollment_password"
# Public URLs, relative to the Home Assistant origin (see the integration).
PUBLIC_BASE = "/api/step_ca_scep"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")
DOWNLOAD_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
LINK_ID_RE = re.compile(r"^[0-9a-f]{64}$")

# Hosted RADIUS services whose server certificate chains to a public root.
# Wi-Fi profiles trust that root and the service's server names, so devices
# join without an upload under Other trusted CAs.
IDENTRUST_COMMERCIAL_ROOT_CA_1 = x509.load_pem_x509_certificate(b"""\
-----BEGIN CERTIFICATE-----
MIIFYDCCA0igAwIBAgIQCgFCgAAAAUUjyES1AAAAAjANBgkqhkiG9w0BAQsFADBK
MQswCQYDVQQGEwJVUzESMBAGA1UEChMJSWRlblRydXN0MScwJQYDVQQDEx5JZGVu
VHJ1c3QgQ29tbWVyY2lhbCBSb290IENBIDEwHhcNMTQwMTE2MTgxMjIzWhcNMzQw
MTE2MTgxMjIzWjBKMQswCQYDVQQGEwJVUzESMBAGA1UEChMJSWRlblRydXN0MScw
JQYDVQQDEx5JZGVuVHJ1c3QgQ29tbWVyY2lhbCBSb290IENBIDEwggIiMA0GCSqG
SIb3DQEBAQUAA4ICDwAwggIKAoICAQCnUBneP5k91DNG8W9RYYKyqU+PZ4ldhNlT
3Qwo2dfw/66VQ3KZ+bVdfIrBQuExUHTRgQ18zZshq0PirK1ehm7zCYofWjK9ouuU
+ehcCuz/mNKvcbO0U59Oh++SvL3sTzIwiEsXXlfEU8L2ApeN2WIrvyQfYo3fw7gp
S0l4PJNgiCL8mdo2yMKi1CxUAGc1bnO/AljwpN3lsKImesrgNqUZFvX9t++uP0D1
bVoE/c40yiTcdCMbXTMTEl3EASX2MN0CXZ/g1Ue9tOsbobtJSdifWwLziuQkkORi
T0/Br4sOdBeo0XKIanoBScy0RnnGF7HamB4HWfp1IYVl3ZBWzvurpWCdxJ35UrCL
vYf5jysjCiN2O/cz4ckA82n5S6LgTrx+kzmEB/dEcH7+B1rlsazRGMzyNeVJSQjK
Vsk9+w8YfYs7wRPCTY/JTw436R+hDmrfYi7LNQZReSzIJTj0+kuniVyc0uMNOYZK
dHzVWYfCP04MXFL0PfdSgvHqo6z9STQaKPNBiDoT7uje/5kdX7rL6B7yuVBgwDHT
c+XvvqDtMwt0viAgxGds8AgDelWAf0ZOlqf0Hj7h9tgJ4TNkK2PXMl6f+cB7D3hv
l7yTmvmcEpB4eoCHFddydJxVdHixuuFucAS6T6C6aMN7/zHwcz09lCqxC0EOoP5N
iGVreTO01wIDAQABo0IwQDAOBgNVHQ8BAf8EBAMCAQYwDwYDVR0TAQH/BAUwAwEB
/zAdBgNVHQ4EFgQU7UQZwNPwBovupHu+QucmVMiONnYwDQYJKoZIhvcNAQELBQAD
ggIBAA2ukDL2pkt8RHYZYR4nKM1eVO8lvOMIkPkp165oCOGUAFjvLi5+U1KMtlwH
6oi6mYtQlNeCgN9hCQCTrQ0U5s7B8jeUeLBfnLOic7iPBZM4zY0+sLj7wM+x8uwt
LRvM7Kqas6pgghstO8OEPVeKlh6cdbjTMM1gCIOQ045U8U1mwF10A0Cj7oV+wh93
nAbowacYXVKV7cndJZ5t+qntozo00Fl72u1Q8zW/7esUTTHHYPTa8Yec4kjixsU3
+wYQ+nVZZjFHKdp2mhzpgq7vmrlR94gjmmmVYjzlVYA211QC//G5Xc7UI2/YRYRK
W2XviQzdFKcgyxilJbQN+QHwotL0AMh0jqEqSI5l2xPE4iUXfeu+h1sXIFRRk0pT
AwvsXcoz7WL9RccvW9xYoIA55vrX/hMUpu09lEpCdNTDd1lzzY9GvlU47/rokTLq
l1gEIt44w8y8bckzOmoKaT+gyOpyj4xjhiO9bTyWnpXgSUyqorkqG5w2gXjtw+hG
4iZZRHUe2XWJUc0QhJ1hYMtd+ZciTY6Y5uN/9lu7rs3KSoFrXgvzUeF0K+l+J6fZ
mUlO+KWA2yUPHGNiiskzZ2s8EIPGrd6ozRaOjfAHN3Gf8qv8QfXBi+wAN10J5U6A
7/qxXDgGpRtK4dw4LTzcqx+QGtVKnO7RcGzM7vRX+Bi6hG6H
-----END CERTIFICATE-----
""")
RADIUS_SERVICES = {
    "meraki_access_manager": {
        "label": "Cisco Meraki Access Manager",
        "server_names": ["eap.meraki.com"],
        "roots": [IDENTRUST_COMMERCIAL_ROOT_CA_1],
    },
}
CN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$")
BASE_URL_RE = re.compile(r"^https?://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?$")
CHALLENGE_SECONDS = 3600
# An update link lasts this long after its profile was last installed.
UPDATE_SECONDS = 400 * 86400
DOWNLOAD_SECONDS = 600
KEEP_SECONDS = 30 * 86400
P12_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _now():
    return time.time()


def normalize_base_url(value):
    value = (value or "").strip().rstrip("/")
    return value if BASE_URL_RE.match(value) else ""


DNS_RE = re.compile(r"^(\*\.)?([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+$")
MAX_SANS = 20


def parse_sans(text):
    """Split optional subject alternative names (comma, space, or newline separated).

    Each entry is an IP address, an email address, or a DNS name. Returns the
    normalized list; raises ValueError naming the first invalid entry.
    """
    sans = []
    for entry in re.split(r"[\s,]+", text or ""):
        if not entry:
            continue
        try:
            entry = str(ipaddress.ip_address(entry))
        except ValueError:
            if not (EMAIL_RE.match(entry) or (DNS_RE.match(entry) and len(entry) <= 253)):
                raise ValueError(f"{entry[:64]} is not an email address, DNS name, or IP address.") from None
        if entry not in sans:
            sans.append(entry)
    if len(sans) > MAX_SANS:
        raise ValueError(f"Enter at most {MAX_SANS} alternative names.")
    return sans


def split_sans(sans):
    """Group SANs into (emails, dns_names, ip_addresses)."""
    emails, dns, ips = [], [], []
    for entry in sans or ():
        try:
            ips.append(ipaddress.ip_address(entry))
        except ValueError:
            (emails if "@" in entry else dns).append(entry)
    return emails, dns, ips


def valid_cn(value):
    return bool(CN_RE.match(value or "")) and value == value.strip()


class LinkStore:
    """One-time enrollment links persisted in /data."""

    def __init__(self, path=STATE_FILE):
        self._path = path
        self._lock = threading.Lock()

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as handle:
                links = json.load(handle)
            return links if isinstance(links, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, links):
        now = _now()
        # Update links whose profile was never installed are dropped as soon as they expire.
        links = {k: v for k, v in links.items()
                 if v["expires"] + (0 if v.get("renewable") and not v.get("active") else KEEP_SECONDS) > now}
        tmp = f"{self._path}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(links, handle)
        os.replace(tmp, self._path)

    @staticmethod
    def status(link):
        if link["status"] == "pending" and link["expires"] < _now():
            return "expired"
        if link["status"] == "pending" and link.get("renewable"):
            return "update"
        return link["status"]

    @classmethod
    def active(cls, link):
        return cls.status(link) in ("pending", "update")

    def create(self, *, label, cn, base_url, wifi, hours, created_by, sans=(), group="", parent=None):
        """New link; returns its token.

        parent: the link whose profile carries this one as its update link. The
        update link is renewable (it can install the profile again and again)
        and lasts only an hour until that profile is installed.
        """
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._lock:
            links = self._load()
            if parent in links:
                links[parent]["update_link"] = _hash(token)
            links[_hash(token)] = {
                "label": label,
                "cn": cn,
                "sans": list(sans),
                "group": group,
                "base_url": base_url,
                "wifi": wifi,
                "created": now,
                "expires": now + hours * 3600,
                "created_by": created_by,
                "status": "pending",
                "challenge": "",
                "challenge_cn": "",
                "challenge_expires": 0,
                "issued_cn": "",
                "issued_at": 0,
                "method": "",
                **({"renewable": True} if parent is not None else {}),
            }
            self._save(links)
        return token

    def all(self):
        with self._lock:
            links = self._load()
        # An update link is listed once the profile that carries it is installed.
        rows = [dict(v, id=k, state=self.status(v)) for k, v in links.items()
                if not v.get("renewable") or v.get("active")]
        rows.sort(key=lambda r: r["created"], reverse=True)
        return rows

    def cancel(self, link_id):
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if link and self.active(link):
                link["status"] = "cancelled"
                link["challenge"] = ""
                self._save(links)

    def delete(self, link_ids):
        """Delete links that are no longer pending (used, expired, or cancelled). Returns the count."""
        with self._lock:
            links = self._load()
            gone = [i for i in link_ids if i in links and not self.active(links[i])]
            for link_id in gone:
                del links[link_id]
            if gone:
                self._save(links)
        return len(gone)

    def get(self, token, device=False):
        """Return (link_id, link) for a usable token, or (None, None).

        device: a device posting to the profile service, whose profile was
        downloaded while the link was valid; its challenge's own hour counts,
        so the link may expire between the download and the install.
        """
        if not TOKEN_RE.match(token or ""):
            return None, None
        link_id = _hash(token)
        with self._lock:
            link = self._load().get(link_id)
        if link is None or not self.active(link) and not (
                device and link["status"] == "pending" and link["challenge_expires"] >= _now()):
            return None, None
        return link_id, link

    def new_challenge(self, link_id, cn, device=False):
        """Issue a SCEP challenge for this link; earlier profiles stop working.

        device: the profile service's reply, which may come after the link
        expired (see get).
        """
        challenge = secrets.token_urlsafe(24)
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if link is None or not (link["status"] == "pending" if device else self.active(link)):
                return None
            link["challenge"] = _hash(challenge)
            link["challenge_cn"] = cn
            link["challenge_expires"] = _now() + CHALLENGE_SECONDS
            self._save(links)
        return challenge

    def take_device_challenge(self, link_id, challenge):
        """Use up a profile service challenge. Returns the link's name template, or None.

        Profile service challenges are stored like SCEP challenges but with the
        $SERIALNUMBER template as their name, which no certificate request can match.
        """
        if not challenge:
            return None
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if (link is None or link["status"] != "pending" or not link["challenge"]
                    or not uses_serial(link["challenge_cn"]) or link["challenge_expires"] < _now()
                    or not secrets.compare_digest(link["challenge"], _hash(challenge))):
                return None
            template = link["challenge_cn"]
            link["challenge"] = ""
            self._save(links)
        return template

    def consume_challenge(self, challenge, cn, group=""):
        """Mark the link used if the challenge, CN, and group match. Returns the link id.

        group is the SCEP provisioner's group ("" for the default one), so a
        profile for one group cannot be replayed against another group's URL.
        """
        if not challenge:
            return None
        digest = _hash(challenge)
        now = _now()
        with self._lock:
            links = self._load()
            for link_id, link in links.items():
                if link["status"] != "pending" or not link["challenge"]:
                    continue
                if not secrets.compare_digest(link["challenge"], digest):
                    continue
                # A profile service challenge (name still has $SERIALNUMBER) is not for SCEP.
                if (link["challenge_expires"] < now or link["challenge_cn"] != cn
                        or uses_serial(cn) or link.get("group", "") != group):
                    return None
                if link.get("renewable"):
                    # An update link stays usable, for a while after each install.
                    link.update(challenge="", issued_cn=cn, issued_at=now, method="Profile update",
                                expires=now + UPDATE_SECONDS, active=True)
                else:
                    link.update(status="issued", challenge="", issued_cn=cn,
                                issued_at=now, method="SCEP profile")
                    update = links.get(link.get("update_link", ""))
                    if update and update["status"] == "pending":
                        update.update(expires=now + UPDATE_SECONDS, active=True)
                self._save(links)
                return link_id
        return None

    def claim(self, link_id, cn, method):
        """Atomically reserve a pending link for a server-side issuance."""
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if link is None or self.status(link) != "pending":
                return False
            link.update(status="issued", challenge="", issued_cn=cn,
                        issued_at=_now(), method=method)
            self._save(links)
            return True

    def release(self, link_id):
        """Undo claim() after a failed issuance."""
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if link and link["status"] == "issued":
                link.update(status="pending", issued_cn="", issued_at=0, method="")
                self._save(links)


class Downloads:
    """Short-lived, in-memory files (e.g. a .p12) handed out once issued."""

    def __init__(self):
        self._lock = threading.Lock()
        self._files = {}

    def add(self, scope, data, filename, content_type):
        download_id = secrets.token_urlsafe(24)
        with self._lock:
            now = _now()
            self._files = {k: v for k, v in self._files.items() if v[0] > now}
            self._files[download_id] = (now + DOWNLOAD_SECONDS, scope, data, filename, content_type)
        return download_id

    def get(self, scope, download_id):
        with self._lock:
            entry = self._files.get(download_id)
        if entry is None or entry[0] < _now() or entry[1] != scope:
            return None
        return entry[2:]


def _load_chain(path):
    with open(path, "rb") as handle:
        return x509.load_pem_x509_certificates(handle.read())


def parse_ca_certs(data):
    """Parse uploaded CA certificates (PEM, possibly several, or one DER)."""
    try:
        if b"-----BEGIN" in data:
            certs = x509.load_pem_x509_certificates(data)
        else:
            certs = [x509.load_der_x509_certificate(data)]
    except ValueError as err:
        raise ValueError("The file is not a PEM or DER certificate.") from err
    for cert in certs:
        try:
            is_ca = cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        except x509.ExtensionNotFound:
            is_ca = cert.issuer == cert.subject
        if not is_ca:
            raise ValueError(f"{cert.subject.rfc4514_string()} is not a CA certificate.")
    return certs


def load_extra_cas(path=EXTRA_CA_FILE):
    try:
        return _load_chain(path)
    except (FileNotFoundError, ValueError):
        return []


def save_extra_cas(certs, path=EXTRA_CA_FILE):
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as handle:
        for cert in certs:
            handle.write(cert.public_bytes(serialization.Encoding.PEM))
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def radius_service(wifi):
    """The hosted RADIUS service selected in the Wi-Fi options, or None."""
    return RADIUS_SERVICES.get((wifi or {}).get("radius_server") or "")


def fingerprint(cert):
    return cert.fingerprint(hashes.SHA256()).hex()


def ca_bundle(certs):
    """PEM bundle of the given certificates without duplicates."""
    seen, out = set(), b""
    for cert in certs:
        if fingerprint(cert) not in seen:
            seen.add(fingerprint(cert))
            out += cert.public_bytes(serialization.Encoding.PEM)
    return out


def chain_pem(cert, pool):
    """PEM of cert followed by its issuers from pool, up to a self-signed root."""
    chain, seen = [cert], {fingerprint(cert)}
    while chain[-1].issuer != chain[-1].subject:
        issuer = next((c for c in pool if c.subject == chain[-1].issuer
                       and fingerprint(c) not in seen), None)
        if issuer is None:
            break
        chain.append(issuer)
        seen.add(fingerprint(issuer))
    return b"".join(c.public_bytes(serialization.Encoding.PEM) for c in chain)


SUBORDINATE_DAYS = 3650


PEM_BLOCK_RE = re.compile(rb"-----BEGIN [A-Z0-9 ]+-----(.+?)-----END [A-Z0-9 ]+-----", re.DOTALL)


def _to_der(data):
    """DER bytes of the first PEM block in data, or data itself if it is not PEM."""
    if b"-----BEGIN" not in data:
        return data
    match = PEM_BLOCK_RE.search(data)
    try:
        return base64.b64decode(b"".join(match.group(1).split()), validate=True) if match else b""
    except binascii.Error:
        return b""


def _der_item(der, pos):
    """(content start, content end) of the DER item at pos."""
    length, pos = der[pos + 1], pos + 2
    if length & 0x80:
        count = length & 0x7F
        length, pos = int.from_bytes(der[pos:pos + count], "big"), pos + count
    return pos, pos + length


def _verify_csr_signature(csr, tbs):
    """Check csr's signature over tbs, its original to-be-signed bytes."""
    key, params, hash_algorithm = csr.public_key(), csr.signature_algorithm_parameters, csr.signature_hash_algorithm
    try:
        if isinstance(key, rsa.RSAPublicKey):
            key.verify(csr.signature, tbs, params, hash_algorithm)
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(csr.signature, tbs, params)
        elif isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
            key.verify(csr.signature, tbs)
        else:
            return False
    except InvalidSignature:
        return False
    return True


def load_csr(data):
    """Load a PEM or DER certificate request and check its signature.

    Returns (csr, der). Some systems (Meraki's SCEP CA) write a version other
    than the only defined one, v1 (0), which cryptography and OpenSSL refuse.
    Such a request is read as v1, and its signature is checked over the
    original bytes, which stay unchanged in der.
    """
    der = _to_der(data)
    try:
        csr = x509.load_der_x509_csr(der)
        valid = csr.is_signature_valid
    except x509.InvalidVersion:
        try:
            # CertificationRequest { CertificationRequestInfo { version, ... }, ... }
            info_start, _ = _der_item(der, 0)
            fields_start, info_end = _der_item(der, info_start)
            version_start, version_end = _der_item(der, fields_start)
            if der[fields_start] != 0x02 or version_end - version_start != 1:
                raise ValueError
            patched = bytearray(der)
            patched[version_start] = 0
            csr = x509.load_der_x509_csr(bytes(patched))
        except (ValueError, IndexError) as err:
            raise ValueError("The file is not a PEM or DER certificate request (CSR).") from err
        valid = _verify_csr_signature(csr, der[info_start:info_end])
    except ValueError as err:
        raise ValueError("The file is not a PEM or DER certificate request (CSR).") from err
    if not valid:
        raise ValueError("The certificate request's signature is not valid.")
    return csr, der


def parse_csr(data):
    """An uploaded certificate request for an end-entity certificate: (csr, der)."""
    csr, der = load_csr(data)
    try:
        sans = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        sans = []
    if not csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME) and not sans:
        raise ValueError("The certificate request has no Common Name or subject alternative names.")
    return csr, der


def sign_csr(der, *, ca_url, root_cert, not_after=""):
    """Have step-ca sign a DER CSR with the intermediate CA (server and client auth).

    The CN and SANs come from the request; not_after is a duration such as
    "720h" (default: the CA's). Returns [leaf, issuers..., root].
    """
    with tempfile.TemporaryDirectory() as tmp:
        csr_path = os.path.join(tmp, "req.csr")
        crt_path = os.path.join(tmp, "cert.crt")
        with open(csr_path, "wb") as handle:
            handle.write(b"-----BEGIN CERTIFICATE REQUEST-----\n"
                         + base64.encodebytes(der) + b"-----END CERTIFICATE REQUEST-----\n")
        result = subprocess.run(
            ["step", "ca", "sign", csr_path, crt_path,
             "--provisioner", ENROLL_PROVISIONER,
             "--provisioner-password-file", ENROLL_PASSWORD,
             "--ca-url", ca_url, "--root", root_cert, "--force"]
            + (["--not-after", not_after] if not_after else []),
            capture_output=True, text=True, timeout=60, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "The CA did not issue the certificate.")
        chain = _load_chain(crt_path)
    root = _load_chain(root_cert)[0]
    if all(fingerprint(c) != fingerprint(root) for c in chain):
        chain.append(root)
    return chain


def parse_subordinate_request(data):
    """Subject and public key from an uploaded CSR or certificate (PEM or DER)."""
    der = _to_der(data)
    try:
        cert = x509.load_der_x509_certificate(der)
    except ValueError:
        csr, _ = load_csr(der)
        return csr.subject, csr.public_key()
    return cert.subject, cert.public_key()


def sign_subordinate(data, issuer, issuer_key, days=SUBORDINATE_DAYS):
    """Sign a subordinate CA (e.g. Meraki's SCEP CA) that may not issue further CAs.

    The subject is copied unchanged from the request, because some CAs (Meraki)
    only accept their certificate back with the exact subject they asked for.
    """
    subject, public_key = parse_subordinate_request(data)
    now = datetime.datetime.now(datetime.timezone.utc)
    not_after = min(now + datetime.timedelta(days=days), issuer.not_valid_after_utc)
    try:
        aki = x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
            issuer.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value)
    except x509.ExtensionNotFound:
        aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer.public_key())
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.subject)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=False,
            encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
        .add_extension(aki, critical=False)
        .sign(issuer_key, hashes.SHA256())
    )


def common_name(cert):
    names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    return str(names[0].value) if names else cert.subject.rfc4514_string()


def _spki(public_key):
    return public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


class ProfileSigner:
    """Signs configuration profiles with the first usable certificate.

    Candidates are (label, cert_path, key_path). A publicly trusted certificate
    (e.g. Home Assistant's Let's Encrypt certificate in /ssl) makes iOS show the
    profile as "Verified"; the CA-issued signer is always available as fallback.
    """

    def __init__(self, candidates):
        self._candidates = [c for c in candidates if c[1] and c[2]]

    def _load(self, label, cert_path, key_path):
        chain = _load_chain(cert_path)
        with open(key_path, "rb") as handle:
            key = serialization.load_pem_private_key(handle.read(), password=None)
        cert = chain[0]
        now = datetime.datetime.now(datetime.timezone.utc)
        if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise ValueError("certificate is not currently valid")
        if _spki(cert.public_key()) != _spki(key.public_key()):
            raise ValueError("key does not match certificate")
        return label, cert, key, chain[1:]

    def signer(self):
        errors = []
        for label, cert_path, key_path in self._candidates:
            try:
                return self._load(label, cert_path, key_path)
            except (OSError, ValueError, TypeError) as err:
                errors.append(f"{label}: {err}")
        raise RuntimeError("No usable profile signing certificate (" + "; ".join(errors) + ")")

    def describe(self):
        try:
            label, cert, _, _ = self.signer()
        except RuntimeError as err:
            return None, str(err)
        return label, cert.subject.rfc4514_string()

    def sign(self, data):
        _, cert, key, extra = self.signer()
        builder = pkcs7.PKCS7SignatureBuilder().set_data(data).add_signer(cert, key, hashes.SHA256())
        for extra_cert in extra:
            builder = builder.add_certificate(extra_cert)
        # Attached (non-detached) SignedData, as Apple expects for profiles.
        return builder.sign(serialization.Encoding.DER, [])


def _identifier_part(value):
    return re.sub(r"[^A-Za-z0-9-]+", "-", value).strip("-").lower() or "device"


def wifi_name(wifi):
    """The network's own name, else its SSID, else its Passpoint domain."""
    wifi = wifi or {}
    return wifi.get("name") or wifi_ssid(wifi)


def wifi_ssid(wifi):
    """The SSID devices see, or the Passpoint domain for a Passpoint network without one."""
    wifi = wifi or {}
    return wifi.get("ssid") or (wifi.get("passpoint_domain") if wifi.get("passpoint") else "") or ""


# Keys Apple supports on one platform only, left out of the other's profiles.
IOS_ONLY_WIFI_KEYS = ("CaptiveBypass", "MCCAndMNCs", "HESSID")
MACOS_ONLY_WIFI_KEYS = ("SetupModes",)


def wifi_payload(wifi, prefix, identifiers, platform=None):
    """A com.apple.wifi.managed payload without its credentials (Password or EAP).

    platform "ios" or "macos" leaves out the keys the other platform alone uses;
    None (a profile for any Apple device) keeps them all.
    """
    name = wifi_name(wifi)
    identifier = f"{prefix}.wifi.{_identifier_part(name)}"
    while identifier in identifiers:
        identifier += "-2"
    identifiers.add(identifier)
    payload = {
        "PayloadType": "com.apple.wifi.managed",
        "PayloadVersion": 1,
        "PayloadIdentifier": identifier,
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": f"Wi-Fi {wifi_ssid(wifi)}",
        "HIDDEN_NETWORK": bool(wifi.get("hidden")),
        "AutoJoin": bool(wifi.get("auto_join", True)),
        "EncryptionType": wifi.get("security") or "WPA2",
        "IsHotspot": bool(wifi.get("passpoint")),
        "DisableAssociationMACRandomization": bool(wifi.get("disable_mac_randomization")),
    }
    if wifi.get("ssid"):
        payload["SSID_STR"] = wifi["ssid"]
    proxy = wifi.get("proxy") or "none"
    if proxy == "manual":
        payload.update(ProxyType="Manual", ProxyServer=wifi.get("proxy_server") or "",
                       ProxyServerPort=int(wifi.get("proxy_port") or 0))
        if wifi.get("proxy_username"):
            payload["ProxyUsername"] = wifi["proxy_username"]
            payload["ProxyPassword"] = wifi.get("proxy_password") or ""
    elif proxy == "auto":
        payload["ProxyType"] = "Auto"
        if wifi.get("proxy_pac_url"):
            payload["ProxyPACURL"] = wifi["proxy_pac_url"]
        payload["ProxyPACFallbackAllowed"] = bool(wifi.get("proxy_pac_fallback"))
    if wifi.get("captive_bypass"):
        payload["CaptiveBypass"] = True
    if wifi.get("mac_login_window"):
        payload["SetupModes"] = ["System", "Loginwindow"]
    qos = wifi.get("qos_marking") or "default"
    if qos == "off":
        payload["QoSMarkingPolicy"] = {"QoSMarkingEnabled": False}
    elif qos == "allowlist":
        payload["QoSMarkingPolicy"] = {
            "QoSMarkingEnabled": True,
            "QoSMarkingAppleAudioVideoCalls": bool(wifi.get("qos_apple_calls", True)),
            "QoSMarkingAllowListAppIdentifiers": [a for a in wifi.get("qos_apps") or [] if a],
        }
    if wifi.get("passpoint"):
        for key, option in (("DomainName", "passpoint_domain"), ("DisplayedOperatorName", "passpoint_operator_name"),
                            ("HESSID", "passpoint_hessid")):
            if wifi.get(option):
                payload[key] = wifi[option]
        for key, option in (("RoamingConsortiumOIs", "passpoint_roaming_consortium_ois"),
                            ("NAIRealmNames", "passpoint_nai_realms"), ("MCCAndMNCs", "passpoint_mcc_mncs")):
            values = [v for v in wifi.get(option) or [] if v]
            if values:
                payload[key] = values
        payload["ServiceProviderRoamingEnabled"] = bool(wifi.get("passpoint_roaming"))
    for key in {"ios": MACOS_ONLY_WIFI_KEYS, "macos": IOS_ONLY_WIFI_KEYS}.get(platform, ()):
        payload.pop(key, None)
    return payload


@functools.lru_cache(maxsize=1)
def update_icon(size=180, background=(0x03, 0xA9, 0xF4)):
    """PNG for the Update Home Screen icon: a white circular arrow on Home Assistant blue."""
    centre, radius, width = size / 2, size * 0.29, size * 0.09
    gap_start, gap_end = math.radians(-10), math.radians(60)  # the arc's opening, at the upper right
    # Arrowhead at the upper end of the arc, pointing clockwise into the gap.
    tip_angle = gap_end
    ax, ay = centre + radius * math.cos(tip_angle), centre - radius * math.sin(tip_angle)
    head = size * 0.13
    tangent = (math.sin(tip_angle), math.cos(tip_angle))  # clockwise direction in screen coordinates
    normal = (math.cos(tip_angle), -math.sin(tip_angle))
    triangle = [
        (ax + tangent[0] * head, ay + tangent[1] * head),
        (ax + normal[0] * head, ay + normal[1] * head),
        (ax - normal[0] * head, ay - normal[1] * head),
    ]

    def inside_triangle(x, y):
        (x1, y1), (x2, y2), (x3, y3) = triangle
        d1 = (x - x2) * (y1 - y2) - (x1 - x2) * (y - y2)
        d2 = (x - x3) * (y2 - y3) - (x2 - x3) * (y - y3)
        d3 = (x - x1) * (y3 - y1) - (x3 - x1) * (y - y1)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    def white(x, y):
        dx, dy = x - centre, centre - y
        if abs(math.hypot(dx, dy) - radius) <= width / 2:
            angle = math.atan2(dy, dx)
            if not gap_start < angle < gap_end:
                return True
        return inside_triangle(x, y)

    samples = (0.25, 0.75)
    rows = []
    for y in range(size):
        row = bytearray(b"\0")
        for x in range(size):
            cover = sum(white(x + sx, y + sy) for sx in samples for sy in samples) / 4
            row += bytes(round(c + (255 - c) * cover) for c in background)
        rows.append(bytes(row))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + chunk(b"IEND", b""))


def build_profile(*, cn, challenge, scep_url, ca_name, organization, root, intermediate, wifi,
                  extra_cas=(), sans=(), include_scep=True, system_scope=False, identifier=None,
                  display_name=None, email_sans=(), platform=None, update_url=None):
    """Return an unsigned .mobileconfig (XML plist) for SCEP enrollment.

    update_url adds a Home Screen icon (iPhone and iPad only) that opens this
    URL, where the device can install the newest profile again.

    With include_scep=False only the certificate payloads are included (and no
    Wi-Fi, which needs the SCEP identity). system_scope installs the profile
    for the whole Mac (System keychain) rather than the user; iOS ignores it.
    email_sans are added as email SANs as given, so they may be MDM variables.
    platform "ios" or "macos" builds the profile for that platform only (see
    wifi_payload); None makes one profile that suits both.
    """
    root_uuid, inter_uuid, scep_uuid = (str(uuid.uuid4()).upper() for _ in range(3))
    prefix = f"io.home-assistant.step-ca.{_identifier_part(ca_name)}"
    payloads = [
        {
            "PayloadType": "com.apple.security.root",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{prefix}.root",
            "PayloadUUID": root_uuid,
            "PayloadDisplayName": f"{ca_name} Root CA",
            "PayloadCertificateFileName": "root_ca.cer",
            "PayloadContent": root.public_bytes(serialization.Encoding.DER),
        },
        {
            "PayloadType": "com.apple.security.pkcs1",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{prefix}.intermediate",
            "PayloadUUID": inter_uuid,
            "PayloadDisplayName": f"{ca_name} Intermediate CA",
            "PayloadCertificateFileName": "intermediate_ca.cer",
            "PayloadContent": intermediate.public_bytes(serialization.Encoding.DER),
        },
        {
            "PayloadType": "com.apple.security.scep",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{prefix}.scep",
            "PayloadUUID": scep_uuid,
            "PayloadDisplayName": f"{cn} certificate",
            "PayloadContent": {
                "URL": scep_url,
                "Name": ca_name,
                "Subject": [[["CN", cn]]],
                "Challenge": challenge,
                "Keysize": 2048,
                "Key Type": "RSA",
                # 1 = signing, 4 = encryption.
                "Key Usage": 5,
                "Retries": 3,
                "RetryDelay": 10,
                "KeyIsExtractable": False,
                "AllowAllAppsAccess": True,
            },
        },
    ]
    emails, dns, _ = split_sans(sans)  # Apple's SCEP payload has no IP address SANs.
    emails += [e for e in email_sans if e and e not in emails]
    alt_names = {k: v for k, v in (("rfc822Name", emails), ("dNSName", dns)) if v}
    if alt_names:
        payloads[2]["PayloadContent"]["SubjectAltName"] = alt_names
    if not include_scep:
        payloads.pop()
        wifi = None
    anchors = [root_uuid, inter_uuid]
    for index, cert in enumerate(extra_cas, 1):
        extra_uuid = str(uuid.uuid4()).upper()
        anchors.append(extra_uuid)
        self_signed = cert.issuer == cert.subject
        payloads.append({
            "PayloadType": "com.apple.security.root" if self_signed else "com.apple.security.pkcs1",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{prefix}.extra-ca.{fingerprint(cert)[:16]}",
            "PayloadUUID": extra_uuid,
            "PayloadDisplayName": common_name(cert),
            "PayloadCertificateFileName": f"extra_ca_{index}.cer",
            "PayloadContent": cert.public_bytes(serialization.Encoding.DER),
        })
    if isinstance(wifi, dict):
        wifi = [wifi]
    networks = [w for w in wifi or [] if wifi_name(w)]
    has_wifi = bool(networks)
    known = {fingerprint(c) for c in extra_cas}
    identifiers = set()
    for network in networks:
        payload = wifi_payload(network, prefix, identifiers, platform)
        if network.get("authentication") == "psk":
            payload["Password"] = network.get("password") or ""
            payloads.append(payload)
            continue
        eap = {"AcceptEAPTypes": [13], "UserName": cn, "TLSMinimumVersion": "1.2"}
        server_names = [n for n in network.get("radius_server_names") or [] if n]
        service = radius_service(network)
        if service:
            for cert in service["roots"]:
                if fingerprint(cert) in known:
                    continue
                known.add(fingerprint(cert))
                service_uuid = str(uuid.uuid4()).upper()
                anchors.append(service_uuid)
                payloads.append({
                    "PayloadType": "com.apple.security.root",
                    "PayloadVersion": 1,
                    "PayloadIdentifier": f"{prefix}.radius-ca.{fingerprint(cert)[:16]}",
                    "PayloadUUID": service_uuid,
                    "PayloadDisplayName": common_name(cert),
                    "PayloadCertificateFileName": "radius_ca.cer",
                    "PayloadContent": cert.public_bytes(serialization.Encoding.DER),
                })
            server_names += [n for n in service["server_names"] if n not in server_names]
        if server_names:
            eap["TLSTrustedServerNames"] = server_names
        payload.update({
            "EAPClientConfiguration": eap,
            # The identity comes from the SCEP payload; the RADIUS server's
            # certificate must chain to this CA, an uploaded extra CA, or a
            # selected RADIUS service's root.
            "PayloadCertificateUUID": scep_uuid,
            "PayloadCertificateAnchorUUID": anchors,
        })
        payloads.append(payload)
    if update_url:
        payloads.append({
            "PayloadType": "com.apple.webClip.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{prefix}.update.{_identifier_part(cn)}",
            "PayloadUUID": str(uuid.uuid4()).upper(),
            "PayloadDisplayName": "Update icon",
            "URL": update_url,
            "Label": "Update Wi-Fi" if has_wifi else "Update Cert",
            "IsRemovable": True,
            "FullScreen": False,
            "Precomposed": True,
            "Icon": update_icon(),
        })
    if platform != "ios" and any(n.get("mac_login_window") for n in networks):
        # Joining at the Mac login window needs the identity in the System keychain.
        system_scope = True
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"{prefix}.{identifier or 'enroll.' + _identifier_part(cn)}",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": display_name or f"{ca_name}: {cn}",
        "PayloadDescription": "Installs the certificate authority"
                              + ((", requests a device certificate" + (" and configures Wi-Fi."
                                  if has_wifi else ".")) if include_scep else "."),
        "PayloadRemovalDisallowed": False,
        "PayloadContent": payloads,
    }
    if organization:
        profile["PayloadOrganization"] = organization
    if system_scope:
        profile["PayloadScope"] = "System"
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)



# Certificate name variable for one-time links: an Apple device sends its serial
# number through a profile service, the same way an MDM fills $SERIALNUMBER.
SERIAL_VAR = "$SERIALNUMBER"
SERIAL_RE = re.compile(r"^[A-Za-z0-9-]{1,32}$")
MAX_DEVICE_BYTES = 65536


def uses_serial(cn):
    return SERIAL_VAR in (cn or "")


def valid_cn_template(value):
    """A certificate name, or one with $SERIALNUMBER in it (filled in from the device)."""
    return valid_cn(value) or (uses_serial(value) and len(value) <= 64
                               and valid_cn(value.replace(SERIAL_VAR, "X")))


def fill_serial(template, serial):
    """The certificate name with the device's serial number, or "" if it is not valid."""
    if not SERIAL_RE.match(serial or ""):
        return ""
    cn = template.replace(SERIAL_VAR, serial)
    return cn if valid_cn(cn) else ""


def build_profile_service(*, url, challenge, ca_name, organization, cn):
    """Unsigned profile service payload that asks the device for its serial number.

    The device posts its attributes (signed CMS) to url and installs the
    profile that comes back.
    """
    prefix = f"io.home-assistant.step-ca.{_identifier_part(ca_name)}"
    profile = {
        "PayloadType": "Profile Service",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"{prefix}.profile-service",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": f"{ca_name}: device enrollment",
        "PayloadDescription": "Sends this device's serial number to get a certificate named "
                              f"{cn.replace(SERIAL_VAR, '<serial number>')}.",
        "PayloadContent": {
            "URL": url,
            "DeviceAttributes": ["SERIAL", "UDID", "PRODUCT", "VERSION"],
            "Challenge": challenge,
        },
    }
    if organization:
        profile["PayloadOrganization"] = organization
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


def _ber_items(data, pos, end):
    """Yield (tag, constructed, content start, content end, next) for BER items in data[pos:end].

    Handles indefinite lengths, which some CMS encoders use.
    """
    while pos < end:
        tag = data[pos]
        if tag == 0 and pos + 1 < end and data[pos + 1] == 0:
            return
        if tag & 0x1F == 0x1F:
            raise ValueError("high tag numbers are not used here")
        length, pos = data[pos + 1], pos + 2
        constructed = bool(tag & 0x20)
        if length == 0x80:
            if not constructed:
                raise ValueError("indefinite length on a primitive item")
            stop = pos
            for item in _ber_items(data, pos, end):
                stop = item[4]
            if data[stop:stop + 2] != b"\0\0":
                raise ValueError("missing end of contents")
            yield tag, constructed, pos, stop, stop + 2
            pos = stop + 2
            continue
        if length & 0x80:
            count = length & 0x7F
            if not 1 <= count <= 4:
                raise ValueError("bad length")
            length, pos = int.from_bytes(data[pos:pos + count], "big"), pos + count
        if pos + length > end:
            raise ValueError("truncated")
        yield tag, constructed, pos, pos + length, pos + length
        pos += length


def _ber_children(data, start, end):
    return list(_ber_items(data, start, end))


def _octets(data, item):
    """Content of an OCTET STRING item, joining the pieces of a constructed one."""
    tag, constructed, start, end, _ = item
    if tag & 0x1F != 0x04:
        raise ValueError("not an octet string")
    if not constructed:
        return data[start:end]
    return b"".join(_octets(data, child) for child in _ber_children(data, start, end))


SIGNED_DATA_OID = bytes.fromhex("2a864886f70d010702")


def device_attributes(body):
    """The attributes plist (SERIAL, UDID, CHALLENGE, ...) from a device's signed CMS post.

    The signature is not checked: the one-time challenge in the plist is what
    ties the post to the enrollment link.
    """
    if not body or len(body) > MAX_DEVICE_BYTES:
        raise ValueError("empty or too large")
    data = bytes(body)
    items = _ber_children(data, 0, len(data))
    info = items[0] if items else None
    if info is None or info[0] != 0x30:
        raise ValueError("not a CMS ContentInfo")
    oid, wrapper = _ber_children(data, info[2], info[3])[:2]
    if oid[0] != 0x06 or data[oid[2]:oid[3]] != SIGNED_DATA_OID or wrapper[0] != 0xA0:
        raise ValueError("not CMS SignedData")
    (signed,) = _ber_children(data, wrapper[2], wrapper[3])[:1]
    # SignedData: version, digestAlgorithms, encapContentInfo, ...
    encap = _ber_children(data, signed[2], signed[3])[2]
    parts = _ber_children(data, encap[2], encap[3])
    if len(parts) < 2 or parts[1][0] != 0xA0:
        raise ValueError("no signed content")
    (content,) = _ber_children(data, parts[1][2], parts[1][3])[:1]
    attributes = plistlib.loads(_octets(data, content))
    if not isinstance(attributes, dict):
        raise ValueError("attributes are not a dictionary")
    return attributes

def p12_password():
    groups = ("".join(secrets.choice(P12_ALPHABET) for _ in range(4)) for _ in range(4))
    return "-".join(groups)


def issue_p12(cn, *, ca_url, root_cert, extra_cas=(), sans=(), ou="", not_after=""):
    """Issue a certificate for a server-generated key and bundle it as .p12.

    ou is a group's organizational unit; not_after its certificate lifetime.
    Returns (p12_bytes, password, certificate). The key never touches disk.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    if ou:
        subject.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, ou))
    builder = x509.CertificateSigningRequestBuilder().subject_name(x509.Name(subject))
    emails, dns, ips = split_sans(sans)
    names = ([x509.RFC822Name(e) for e in emails] + [x509.DNSName(d) for d in dns]
             + [x509.IPAddress(i) for i in ips])
    if names:
        builder = builder.add_extension(x509.SubjectAlternativeName(names), critical=False)
    csr = builder.sign(key, hashes.SHA256())
    leaf, *extra = sign_csr(csr.public_bytes(serialization.Encoding.DER), ca_url=ca_url, root_cert=root_cert,
                            not_after=not_after)
    known = {fingerprint(c) for c in extra}
    extra += [c for c in extra_cas if fingerprint(c) not in known]
    password = p12_password()
    # 3DES/SHA-1 keeps the bundle importable on older Windows, Android, and
    # macOS Keychain, which reject AES-based PKCS#12.
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1())
        .build(password.encode())
    )
    data = pkcs12.serialize_key_and_certificates(cn.encode(), key, leaf, extra, encryption)
    return data, password, leaf
