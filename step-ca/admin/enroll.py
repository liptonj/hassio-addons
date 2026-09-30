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

import datetime
import hashlib
import ipaddress
import json
import os
import plistlib
import re
import secrets
import subprocess
import tempfile
import threading
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
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
CN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,63}$")
BASE_URL_RE = re.compile(r"^https?://(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+)(:[0-9]{1,5})?$")
CHALLENGE_SECONDS = 3600
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
        links = {k: v for k, v in links.items() if v["expires"] + KEEP_SECONDS > now}
        tmp = f"{self._path}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(links, handle)
        os.replace(tmp, self._path)

    @staticmethod
    def status(link):
        if link["status"] == "pending" and link["expires"] < _now():
            return "expired"
        return link["status"]

    def create(self, *, label, cn, base_url, wifi, hours, created_by, sans=()):
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._lock:
            links = self._load()
            links[_hash(token)] = {
                "label": label,
                "cn": cn,
                "sans": list(sans),
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
            }
            self._save(links)
        return token

    def all(self):
        with self._lock:
            links = self._load()
        rows = [dict(v, id=k, state=self.status(v)) for k, v in links.items()]
        rows.sort(key=lambda r: r["created"], reverse=True)
        return rows

    def cancel(self, link_id):
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if link and self.status(link) == "pending":
                link["status"] = "cancelled"
                link["challenge"] = ""
                self._save(links)

    def get(self, token):
        """Return (link_id, link) for a usable token, or (None, None)."""
        if not TOKEN_RE.match(token or ""):
            return None, None
        link_id = _hash(token)
        with self._lock:
            link = self._load().get(link_id)
        if link is None or self.status(link) != "pending":
            return None, None
        return link_id, link

    def new_challenge(self, link_id, cn):
        """Issue a SCEP challenge for this link; earlier profiles stop working."""
        challenge = secrets.token_urlsafe(24)
        with self._lock:
            links = self._load()
            link = links.get(link_id)
            if link is None or self.status(link) != "pending":
                return None
            link["challenge"] = _hash(challenge)
            link["challenge_cn"] = cn
            link["challenge_expires"] = _now() + CHALLENGE_SECONDS
            self._save(links)
        return challenge

    def consume_challenge(self, challenge, cn):
        """Mark the link used if the challenge and CN match. Returns the link id."""
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
                if link["challenge_expires"] < now or link["challenge_cn"] != cn:
                    return None
                link.update(status="issued", challenge="", issued_cn=cn,
                            issued_at=now, method="SCEP profile")
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


def parse_csr(data):
    """An uploaded certificate request (PEM or DER) for an end-entity certificate."""
    try:
        csr = (x509.load_pem_x509_csr(data) if b"-----BEGIN" in data
               else x509.load_der_x509_csr(data))
    except ValueError as err:
        raise ValueError("The file is not a PEM or DER certificate request (CSR).") from err
    if not csr.is_signature_valid:
        raise ValueError("The certificate request's signature is not valid.")
    try:
        sans = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        sans = []
    if not csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME) and not sans:
        raise ValueError("The certificate request has no Common Name or subject alternative names.")
    return csr


def sign_csr(csr, *, ca_url, root_cert):
    """Have step-ca sign a CSR with the intermediate CA (server and client auth).

    The CN and SANs come from the request. Returns [leaf, issuers..., root].
    """
    with tempfile.TemporaryDirectory() as tmp:
        csr_path = os.path.join(tmp, "req.csr")
        crt_path = os.path.join(tmp, "cert.crt")
        with open(csr_path, "wb") as handle:
            handle.write(csr.public_bytes(serialization.Encoding.PEM))
        result = subprocess.run(
            ["step", "ca", "sign", csr_path, crt_path,
             "--provisioner", ENROLL_PROVISIONER,
             "--provisioner-password-file", ENROLL_PASSWORD,
             "--ca-url", ca_url, "--root", root_cert, "--force"],
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
    loaders = ((x509.load_pem_x509_csr, x509.load_pem_x509_certificate) if b"-----BEGIN" in data
               else (x509.load_der_x509_csr, x509.load_der_x509_certificate))
    for loader in loaders:
        try:
            request = loader(data)
        except ValueError:
            continue
        if isinstance(request, x509.CertificateSigningRequest) and not request.is_signature_valid:
            raise ValueError("The certificate request's signature is not valid.")
        return request.subject, request.public_key()
    raise ValueError("The file is not a PEM or DER certificate request (CSR) or certificate.")


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


def build_profile(*, cn, challenge, scep_url, ca_name, organization, root, intermediate, wifi,
                  extra_cas=(), sans=()):
    """Return an unsigned .mobileconfig (XML plist) for SCEP enrollment."""
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
    alt_names = {k: v for k, v in (("rfc822Name", emails), ("dNSName", dns)) if v}
    if alt_names:
        payloads[2]["PayloadContent"]["SubjectAltName"] = alt_names
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
    has_wifi = bool(wifi and wifi.get("ssid"))
    if has_wifi:
        eap = {"AcceptEAPTypes": [13], "UserName": cn, "TLSMinimumVersion": "1.2"}
        server_names = [n for n in wifi.get("radius_server_names") or [] if n]
        if server_names:
            eap["TLSTrustedServerNames"] = server_names
        payloads.append({
            "PayloadType": "com.apple.wifi.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": f"{prefix}.wifi.{_identifier_part(wifi['ssid'])}",
            "PayloadUUID": str(uuid.uuid4()).upper(),
            "PayloadDisplayName": f"Wi-Fi {wifi['ssid']}",
            "SSID_STR": wifi["ssid"],
            "HIDDEN_NETWORK": bool(wifi.get("hidden")),
            "AutoJoin": bool(wifi.get("auto_join", True)),
            "EncryptionType": wifi.get("security") or "WPA2",
            "IsHotspot": False,
            "EAPClientConfiguration": eap,
            # The identity comes from the SCEP payload; the RADIUS server's
            # certificate must chain to this CA or an uploaded extra CA.
            "PayloadCertificateUUID": scep_uuid,
            "PayloadCertificateAnchorUUID": anchors,
        })
    profile = {
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"{prefix}.enroll.{_identifier_part(cn)}",
        "PayloadUUID": str(uuid.uuid4()).upper(),
        "PayloadDisplayName": f"{ca_name}: {cn}",
        "PayloadDescription": "Installs the certificate authority, requests a device "
                              "certificate" + (" and configures Wi-Fi." if has_wifi else "."),
        "PayloadRemovalDisallowed": False,
        "PayloadContent": payloads,
    }
    if organization:
        profile["PayloadOrganization"] = organization
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


def p12_password():
    groups = ("".join(secrets.choice(P12_ALPHABET) for _ in range(4)) for _ in range(4))
    return "-".join(groups)


def issue_p12(cn, *, ca_url, root_cert, extra_cas=(), sans=()):
    """Issue a certificate for a server-generated key and bundle it as .p12.

    Returns (p12_bytes, password, certificate). The key never touches disk.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    builder = x509.CertificateSigningRequestBuilder().subject_name(
        x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
    emails, dns, ips = split_sans(sans)
    names = ([x509.RFC822Name(e) for e in emails] + [x509.DNSName(d) for d in dns]
             + [x509.IPAddress(i) for i in ips])
    if names:
        builder = builder.add_extension(x509.SubjectAlternativeName(names), critical=False)
    csr = builder.sign(key, hashes.SHA256())
    leaf, *extra = sign_csr(csr, ca_url=ca_url, root_cert=root_cert)
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
