"""
Certificate test helpers.

Utilities for generating, validating, and testing certificates in tests.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def generate_test_rsa_key(key_size: int = 2048) -> rsa.RSAPrivateKey:
    """
    Generate RSA private key for testing.

    Args:
        key_size: Key size in bits

    Returns:
        RSA private key
    """
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )


def generate_test_certificate(
    common_name: str = "test.example.com",
    key: Optional[rsa.RSAPrivateKey] = None,
    issuer_cert: Optional[x509.Certificate] = None,
    issuer_key: Optional[rsa.RSAPrivateKey] = None,
    valid_days: int = 365,
    key_size: int = 2048,
    hash_algorithm: hashes.HashAlgorithm = hashes.SHA256(),
    is_ca: bool = False,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """
    Generate a test certificate.

    Args:
        common_name: Common name for certificate
        key: Private key (generates new one if None)
        issuer_cert: Issuer certificate (self-signed if None)
        issuer_key: Issuer private key
        valid_days: Certificate validity in days
        key_size: Key size in bits if generating new key
        hash_algorithm: Hash algorithm for signature
        is_ca: Whether this is a CA certificate

    Returns:
        Tuple of (certificate, private_key)
    """
    # Generate key if not provided
    if key is None:
        key = generate_test_rsa_key(key_size)

    # Build subject
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Test State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Test City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test Org"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # Determine issuer
    if issuer_cert and issuer_key:
        issuer = issuer_cert.subject
        signing_key = issuer_key
    else:
        # Self-signed
        issuer = subject
        signing_key = key

    # Build certificate
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=valid_days))
        .add_extension(
            x509.BasicConstraints(ca=is_ca, path_length=None if not is_ca else 0),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
            critical=False,
        )
    )

    # Sign certificate
    cert = builder.sign(signing_key, hash_algorithm)

    logger.debug(f"Generated test certificate: {common_name}")
    return cert, key


def generate_expired_certificate(
    common_name: str = "expired.example.com",
    expired_days_ago: int = 30,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """
    Generate an expired certificate for testing.

    Args:
        common_name: Common name
        expired_days_ago: How many days ago it expired

    Returns:
        Tuple of (expired_certificate, private_key)
    """
    key = generate_test_rsa_key()

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # Certificate expired expired_days_ago days ago
    not_valid_before = datetime.now(timezone.utc) - timedelta(days=expired_days_ago + 365)
    not_valid_after = datetime.now(timezone.utc) - timedelta(days=expired_days_ago)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )

    logger.debug(f"Generated expired certificate: {common_name} (expired {expired_days_ago} days ago)")
    return cert, key


def generate_weak_key_certificate(
    common_name: str = "weak.example.com",
    key_size: int = 1024,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """
    Generate certificate with weak key for testing.

    Args:
        common_name: Common name
        key_size: Weak key size (< 2048)

    Returns:
        Tuple of (certificate, weak_private_key)
    """
    return generate_test_certificate(
        common_name=common_name,
        key_size=key_size,
    )


def generate_weak_hash_certificate(
    common_name: str = "weakhash.example.com",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """
    Generate certificate with weak hash algorithm for testing.

    Args:
        common_name: Common name

    Returns:
        Tuple of (certificate, private_key)
    """
    return generate_test_certificate(
        common_name=common_name,
        hash_algorithm=hashes.SHA1(),  # Weak hash
    )


def save_certificate_to_file(cert: x509.Certificate, path: Path) -> None:
    """
    Save certificate to PEM file.

    Args:
        cert: Certificate to save
        path: File path
    """
    with open(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    path.chmod(0o644)
    logger.debug(f"Saved certificate to {path}")


def save_private_key_to_file(key: rsa.RSAPrivateKey, path: Path) -> None:
    """
    Save private key to PEM file.

    Args:
        key: Private key to save
        path: File path
    """
    with open(path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    path.chmod(0o600)
    logger.debug(f"Saved private key to {path}")


def load_certificate_from_file(path: Path) -> x509.Certificate:
    """
    Load certificate from PEM file.

    Args:
        path: File path

    Returns:
        Certificate
    """
    with open(path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    logger.debug(f"Loaded certificate from {path}")
    return cert


def validate_certificate_properties(
    cert: x509.Certificate,
    expected_cn: Optional[str] = None,
    expected_key_size: Optional[int] = None,
    check_not_expired: bool = True,
) -> list[str]:
    """
    Validate certificate properties.

    Args:
        cert: Certificate to validate
        expected_cn: Expected common name
        expected_key_size: Expected RSA key size
        check_not_expired: Whether to check expiration

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check common name
    if expected_cn:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not cn_attrs:
            errors.append("Certificate has no Common Name")
        elif cn_attrs[0].value != expected_cn:
            errors.append(f"Common Name mismatch: expected {expected_cn}, got {cn_attrs[0].value}")

    # Check key size
    if expected_key_size:
        public_key = cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            if public_key.key_size != expected_key_size:
                errors.append(
                    f"Key size mismatch: expected {expected_key_size}, got {public_key.key_size}"
                )

    # Check expiration
    if check_not_expired:
        now = datetime.now(timezone.utc)
        if cert.not_valid_after_utc < now:
            errors.append(f"Certificate expired on {cert.not_valid_after_utc}")
        if cert.not_valid_before_utc > now:
            errors.append(f"Certificate not yet valid until {cert.not_valid_before_utc}")

    return errors


def get_certificate_fingerprint(cert: x509.Certificate) -> str:
    """
    Get SHA-256 fingerprint of certificate.

    Args:
        cert: Certificate

    Returns:
        Hex-encoded fingerprint
    """
    fingerprint = cert.fingerprint(hashes.SHA256())
    return fingerprint.hex()
