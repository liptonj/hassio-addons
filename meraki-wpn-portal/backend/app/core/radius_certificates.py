"""
RadSec certificate management for FreeRADIUS.

This module handles the generation, validation, and management of RadSec
certificates for secure RADIUS over TLS communication with Meraki.

Security Compliance:
- RSA 4096-bit keys (meets codeguard-1-crypto-algorithms requirements)
- SHA-256 signature algorithm (no MD5, SHA-1)
- TLS 1.2+ support
- Proper certificate validation
- No weak cryptographic algorithms
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtensionOID, NameOID

logger = logging.getLogger(__name__)

# Security compliance constants
RSA_KEY_SIZE = 4096  # Strong key size per security requirements
CERTIFICATE_VALIDITY_DAYS = 3650  # 10 years
HASH_ALGORITHM = hashes.SHA256()  # Strong hash algorithm


class CertificateValidationError(Exception):
    """Raised when certificate validation fails."""


class RadSecCertificateManager:
    """Manages RadSec certificates for FreeRADIUS."""

    def __init__(self, certs_path: Optional[str] = "/data/certs"):
        """
        Initialize certificate manager.

        Args:
            certs_path: Path to store certificates (default: /data/certs).
                       If None, certificates are kept in memory only.
        """
        if certs_path:
            self.certs_path = Path(certs_path)
            self.certs_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"RadSec certificate manager initialized: {self.certs_path}")
        else:
            self.certs_path = None
            logger.info("RadSec certificate manager initialized (memory-only mode)")

    def generate_ca_certificate(
        self,
        common_name: str = "RADIUS CA",
        organization: str = "Home Assistant",
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """
        Generate a self-signed CA certificate.

        Args:
            common_name: CN for the certificate
            organization: Organization name

        Returns:
            Tuple of (certificate, private_key)

        Security: Uses RSA 4096-bit key and SHA-256 signature
        """
        logger.info(f"Generating CA certificate: {common_name}")

        # Generate RSA private key (4096-bit for security)
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=RSA_KEY_SIZE,
        )

        # Build certificate subject
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "FreeRADIUS"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Build certificate
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=CERTIFICATE_VALIDITY_DAYS)
            )
            # CA extensions
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            # Sign with SHA-256 (no weak algorithms)
            .sign(private_key, HASH_ALGORITHM)
        )

        logger.info(f"CA certificate generated successfully (valid until {cert.not_valid_after_utc})")
        return cert, private_key

    def generate_server_certificate(
        self,
        ca_cert: x509.Certificate,
        ca_key: rsa.RSAPrivateKey,
        common_name: str = "radius.local",
        organization: str = "Home Assistant",
        san_dns: Optional[list[str]] = None,
        san_ips: Optional[list[str]] = None,
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        """
        Generate a server certificate signed by CA.

        Args:
            ca_cert: CA certificate for signing
            ca_key: CA private key for signing
            common_name: CN for the server certificate
            organization: Organization name
            san_dns: List of DNS names for Subject Alternative Name
            san_ips: List of IP addresses for Subject Alternative Name

        Returns:
            Tuple of (certificate, private_key)

        Security: Uses RSA 4096-bit key and SHA-256 signature
        """
        logger.info(f"Generating server certificate: {common_name}")

        # Generate RSA private key (4096-bit for security)
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=RSA_KEY_SIZE,
        )

        # Build certificate subject
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "FreeRADIUS"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Build Subject Alternative Name extension
        san_names = []
        if san_dns:
            san_names.extend([x509.DNSName(dns) for dns in san_dns])
        if san_ips:
            from ipaddress import ip_address
            san_names.extend([x509.IPAddress(ip_address(ip)) for ip in san_ips])
        
        # Add CN as DNS name if not already in SAN
        if common_name not in (san_dns or []):
            san_names.append(x509.DNSName(common_name))

        # Build certificate
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=CERTIFICATE_VALIDITY_DAYS)
            )
            # Server certificate extensions
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                ]),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
        )

        # Add SAN if we have any names
        if san_names:
            builder = builder.add_extension(
                x509.SubjectAlternativeName(san_names),
                critical=False,
            )

        # Sign with CA key using SHA-256
        cert = builder.sign(ca_key, HASH_ALGORITHM)

        logger.info(f"Server certificate generated successfully (valid until {cert.not_valid_after_utc})")
        return cert, private_key

    def save_certificate(
        self,
        cert: x509.Certificate,
        filename: str,
    ) -> Path:
        """
        Save certificate to PEM file.

        Args:
            cert: Certificate to save
            filename: Filename (without path)

        Returns:
            Path to saved certificate
            
        Raises:
            ValueError: If certs_path is None (memory-only mode)
        """
        if self.certs_path is None:
            raise ValueError("Cannot save certificate in memory-only mode")
            
        cert_path = self.certs_path / filename
        
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Set secure permissions (readable by all, writable by owner)
        cert_path.chmod(0o644)
        
        logger.info(f"Certificate saved: {cert_path}")
        return cert_path

    def save_private_key(
        self,
        key: rsa.RSAPrivateKey,
        filename: str,
        password: Optional[bytes] = None,
    ) -> Path:
        """
        Save private key to PEM file.

        Args:
            key: Private key to save
            filename: Filename (without path)
            password: Optional password for encryption

        Returns:
            Path to saved key
            
        Raises:
            ValueError: If certs_path is None (memory-only mode)
        """
        if self.certs_path is None:
            raise ValueError("Cannot save private key in memory-only mode")
            
        key_path = self.certs_path / filename
        
        # Determine encryption
        encryption: serialization.KeySerializationEncryption
        if password:
            encryption = serialization.BestAvailableEncryption(password)
        else:
            encryption = serialization.NoEncryption()
        
        with open(key_path, "wb") as f:
            f.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=encryption,
                )
            )
        
        # Set secure permissions (readable/writable by owner only)
        key_path.chmod(0o600)
        
        logger.info(f"Private key saved: {key_path}")
        return key_path

    def load_certificate(self, filename: str) -> x509.Certificate:
        """
        Load certificate from PEM file.

        Args:
            filename: Filename (without path)

        Returns:
            Certificate object
        """
        cert_path = self.certs_path / filename
        
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        
        logger.info(f"Certificate loaded: {cert_path}")
        return cert

    def load_private_key(
        self,
        filename: str,
        password: Optional[bytes] = None,
    ) -> rsa.RSAPrivateKey:
        """
        Load private key from PEM file.

        Args:
            filename: Filename (without path)
            password: Optional password for decryption

        Returns:
            Private key object
        """
        key_path = self.certs_path / filename
        
        with open(key_path, "rb") as f:
            key = serialization.load_pem_private_key(
                f.read(),
                password=password,
            )
        
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError("Key is not an RSA private key")
        
        logger.info(f"Private key loaded: {key_path}")
        return key

    def validate_certificate(self, cert: x509.Certificate) -> list[str]:
        """
        Validate certificate against security requirements.

        Args:
            cert: Certificate to validate

        Returns:
            List of validation warnings/errors

        Security: Checks for weak keys, expired certs, weak signatures
        """
        issues = []
        
        # Check expiration (CRITICAL per codeguard-1-digital-certificates)
        now = datetime.now(timezone.utc)
        if cert.not_valid_after_utc < now:
            issues.append(
                f"CRITICAL VULNERABILITY: Certificate expired on "
                f"{cert.not_valid_after_utc.date()}. It must be renewed immediately."
            )
        elif cert.not_valid_before_utc > now:
            issues.append(
                f"WARNING: Certificate not yet valid. "
                f"Valid from {cert.not_valid_before_utc.date()}."
            )
        
        # Check public key strength
        public_key = cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            key_size = public_key.key_size
            if key_size < 2048:
                issues.append(
                    f"High-Priority WARNING: RSA key size ({key_size} bits) is weak. "
                    f"Minimum 2048 bits required, 4096 bits recommended."
                )
        
        # Check signature algorithm
        sig_alg = cert.signature_algorithm_oid._name
        if "md5" in sig_alg.lower() or "sha1" in sig_alg.lower():
            issues.append(
                f"High-Priority WARNING: Signature algorithm '{sig_alg}' is insecure. "
                f"Use SHA-256 or stronger."
            )
        
        # Check if self-signed
        if cert.issuer == cert.subject:
            issues.append(
                "INFO: Self-signed certificate. Ensure this is intentional "
                "and only used for internal services."
            )
        
        return issues

    def generate_radsec_certificates(
        self,
        server_hostname: str = "radius.local",
        organization: str = "Home Assistant",
    ) -> dict[str, Path]:
        """
        Generate complete RadSec certificate set (CA + server).

        Args:
            server_hostname: Hostname for server certificate
            organization: Organization name

        Returns:
            Dictionary with paths to generated files

        Security: Generates RSA 4096-bit keys with SHA-256 signatures
        """
        logger.info("Generating RadSec certificate set...")
        
        # Generate CA
        ca_cert, ca_key = self.generate_ca_certificate(
            common_name=f"{organization} RADIUS CA",
            organization=organization,
        )
        
        # Generate server certificate
        server_cert, server_key = self.generate_server_certificate(
            ca_cert=ca_cert,
            ca_key=ca_key,
            common_name=server_hostname,
            organization=organization,
            san_dns=[server_hostname, "localhost", "freeradius"],
            san_ips=["127.0.0.1"],
        )
        
        # Save all certificates and keys
        paths = {
            "ca_cert": self.save_certificate(ca_cert, "ca.pem"),
            "ca_key": self.save_private_key(ca_key, "ca-key.pem"),
            "server_cert": self.save_certificate(server_cert, "server.pem"),
            "server_key": self.save_private_key(server_key, "server-key.pem"),
        }
        
        # Validate generated certificates
        ca_issues = self.validate_certificate(ca_cert)
        server_issues = self.validate_certificate(server_cert)
        
        if ca_issues:
            logger.warning(f"CA certificate validation: {'; '.join(ca_issues)}")
        if server_issues:
            logger.warning(f"Server certificate validation: {'; '.join(server_issues)}")
        
        logger.info("RadSec certificates generated successfully")
        logger.info(f"  CA Certificate: {paths['ca_cert']}")
        logger.info(f"  Server Certificate: {paths['server_cert']}")
        logger.info(f"  Certificates valid until: {server_cert.not_valid_after_utc.date()}")
        
        return paths

    def get_certificate_info(self, cert: x509.Certificate) -> dict[str, str]:
        """
        Extract certificate information for display.

        Args:
            cert: Certificate to analyze

        Returns:
            Dictionary with certificate details
        """
        subject = cert.subject
        issuer = cert.issuer
        
        # Extract common name
        cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        issuer_cn = issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        
        # Get public key info
        public_key = cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            key_info = f"RSA {public_key.key_size} bits"
        else:
            key_info = "Unknown"
        
        return {
            "common_name": cn,
            "issuer": issuer_cn,
            "serial_number": str(cert.serial_number),
            "valid_from": cert.not_valid_before_utc.isoformat(),
            "valid_until": cert.not_valid_after_utc.isoformat(),
            "key_type": key_info,
            "signature_algorithm": cert.signature_algorithm_oid._name,
            "is_self_signed": cert.issuer == cert.subject,
        }
