"""Internal Certificate Authority implementation.

This module provides a self-signed Certificate Authority for issuing user certificates
for EAP-TLS authentication. It implements secure key generation, certificate signing,
and lifecycle management with encryption at rest.

Security Features:
- RSA 4096-bit root CA keys
- RSA 2048-bit minimum user certificate keys
- SHA-256 signature algorithm (no weak crypto)
- AES-256-GCM encryption for private keys at rest
- CRL generation and management
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID, ExtensionOID

logger = logging.getLogger(__name__)


class CertificateAuthorityError(Exception):
    """Base exception for Certificate Authority operations."""


class InternalCertificateAuthority:
    """Internal Certificate Authority for issuing user certificates.
    
    This class handles all cryptographic operations for certificate management,
    including CA initialization, certificate signing, and CRL generation.
    """

    def __init__(self, encryption_key: bytes):
        """Initialize the Certificate Authority.
        
        Args:
            encryption_key: 32-byte key for AES-256-GCM encryption
        
        Raises:
            ValueError: If encryption_key is not 32 bytes
        """
        if len(encryption_key) != 32:
            raise ValueError("Encryption key must be 32 bytes for AES-256")
        
        self.encryption_key = encryption_key
        self._cipher = AESGCM(encryption_key)
        logger.info("Certificate Authority initialized")

    def generate_root_ca(
        self,
        common_name: str,
        organization: str,
        validity_days: int = 3650,
        key_size: int = 4096
    ) -> tuple[str, str, str]:
        """Generate a new self-signed root Certificate Authority.
        
        Args:
            common_name: CA common name (e.g., "Property WiFi Root CA")
            organization: Organization name
            validity_days: Certificate validity in days (default 10 years)
            key_size: RSA key size in bits (default 4096)
        
        Returns:
            Tuple of (certificate_pem, encrypted_private_key, fingerprint)
        
        Raises:
            CertificateAuthorityError: If CA generation fails
        """
        logger.info(f"Generating root CA: {common_name} (RSA {key_size}-bit)")
        
        try:
            # Generate RSA private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # Build CA certificate subject
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
            
            # Generate certificate
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=validity_days))
                .add_extension(
                    x509.BasicConstraints(ca=True, path_length=0),
                    critical=True
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_cert_sign=True,
                        crl_sign=True,
                        key_encipherment=False,
                        content_commitment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        encipher_only=False,
                        decipher_only=False
                    ),
                    critical=True
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                    critical=False
                )
                .sign(private_key, hashes.SHA256())
            )
            
            # Serialize certificate to PEM
            cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            
            # Serialize and encrypt private key
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            encrypted_key = self._encrypt_data(key_pem)
            
            # Calculate fingerprint
            fingerprint = cert.fingerprint(hashes.SHA256()).hex()
            
            logger.info(f"✅ Root CA generated successfully. Fingerprint: {fingerprint[:16]}...")
            
            return cert_pem, encrypted_key, fingerprint
            
        except Exception as e:
            logger.error(f"Failed to generate root CA: {e}", exc_info=True)
            raise CertificateAuthorityError(f"Root CA generation failed: {e}") from e

    def issue_user_certificate(
        self,
        common_name: str,
        email: str,
        ca_cert_pem: str,
        ca_key_encrypted: str,
        validity_days: int = 365,
        key_size: int = 2048
    ) -> tuple[str, str, str, str]:
        """Issue a user certificate signed by the CA.
        
        Args:
            common_name: User's common name (typically email or username)
            email: User's email address
            ca_cert_pem: CA certificate in PEM format
            ca_key_encrypted: Encrypted CA private key
            validity_days: Certificate validity in days (default 365)
            key_size: RSA key size in bits (default 2048)
        
        Returns:
            Tuple of (cert_pem, encrypted_key, serial_number, fingerprint)
        
        Raises:
            CertificateAuthorityError: If certificate issuance fails
        """
        logger.info(f"Issuing user certificate for: {common_name}")
        
        try:
            # Decrypt CA private key
            ca_key_pem = self._decrypt_data(ca_key_encrypted)
            ca_private_key = serialization.load_pem_private_key(
                ca_key_pem,
                password=None
            )
            
            # Load CA certificate
            ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode('utf-8'))
            
            # Generate user private key
            user_private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # Build user certificate subject
            subject = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
                x509.NameAttribute(NameOID.EMAIL_ADDRESS, email),
            ])
            
            # Generate serial number
            serial = x509.random_serial_number()
            
            # Generate certificate
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(ca_cert.subject)
                .public_key(user_private_key.public_key())
                .serial_number(serial)
                .not_valid_before(datetime.now(timezone.utc))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=validity_days))
                .add_extension(
                    x509.BasicConstraints(ca=False, path_length=None),
                    critical=True
                )
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_encipherment=True,
                        key_cert_sign=False,
                        crl_sign=False,
                        content_commitment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        encipher_only=False,
                        decipher_only=False
                    ),
                    critical=True
                )
                .add_extension(
                    x509.ExtendedKeyUsage([
                        x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                    ]),
                    critical=True
                )
                .add_extension(
                    x509.SubjectAlternativeName([
                        x509.RFC822Name(email),
                    ]),
                    critical=False
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(user_private_key.public_key()),
                    critical=False
                )
                .add_extension(
                    x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_private_key.public_key()),
                    critical=False
                )
                .sign(ca_private_key, hashes.SHA256())
            )
            
            # Serialize certificate to PEM
            cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            
            # Serialize and encrypt private key
            key_pem = user_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            encrypted_key = self._encrypt_data(key_pem)
            
            # Calculate fingerprint
            fingerprint = cert.fingerprint(hashes.SHA256()).hex()
            
            # Get serial number as hex string
            serial_hex = format(serial, 'X')
            
            logger.info(f"✅ User certificate issued. Serial: {serial_hex}, Fingerprint: {fingerprint[:16]}...")
            
            return cert_pem, encrypted_key, serial_hex, fingerprint
            
        except Exception as e:
            logger.error(f"Failed to issue user certificate: {e}", exc_info=True)
            raise CertificateAuthorityError(f"Certificate issuance failed: {e}") from e

    def generate_pkcs12(
        self,
        cert_pem: str,
        key_encrypted: str,
        ca_cert_pem: str,
        friendly_name: str
    ) -> tuple[bytes, str]:
        """Generate PKCS#12 bundle for iOS/macOS.
        
        Args:
            cert_pem: User certificate in PEM format
            key_encrypted: Encrypted user private key
            ca_cert_pem: CA certificate in PEM format
            friendly_name: Friendly name for the certificate
        
        Returns:
            Tuple of (pkcs12_bytes, password)
        
        Raises:
            CertificateAuthorityError: If PKCS#12 generation fails
        """
        logger.info(f"Generating PKCS#12 bundle: {friendly_name}")
        
        try:
            # Decrypt private key
            key_pem = self._decrypt_data(key_encrypted)
            private_key = serialization.load_pem_private_key(key_pem, password=None)
            
            # Load certificates
            cert = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'))
            ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode('utf-8'))
            
            # Generate random password for PKCS#12
            password = secrets.token_urlsafe(16)
            
            # Create PKCS#12 bundle
            pkcs12 = serialization.pkcs12.serialize_key_and_certificates(
                name=friendly_name.encode('utf-8'),
                key=private_key,
                cert=cert,
                cas=[ca_cert],
                encryption_algorithm=serialization.BestAvailableEncryption(password.encode('utf-8'))
            )
            
            logger.info("✅ PKCS#12 bundle generated successfully")
            
            return pkcs12, password
            
        except Exception as e:
            logger.error(f"Failed to generate PKCS#12: {e}", exc_info=True)
            raise CertificateAuthorityError(f"PKCS#12 generation failed: {e}") from e

    def generate_crl(
        self,
        ca_cert_pem: str,
        ca_key_encrypted: str,
        revoked_serials: list[tuple[str, datetime, str]]
    ) -> str:
        """Generate Certificate Revocation List (CRL).
        
        Args:
            ca_cert_pem: CA certificate in PEM format
            ca_key_encrypted: Encrypted CA private key
            revoked_serials: List of (serial_hex, revoked_date, reason) tuples
        
        Returns:
            CRL in PEM format
        
        Raises:
            CertificateAuthorityError: If CRL generation fails
        """
        logger.info(f"Generating CRL with {len(revoked_serials)} revoked certificates")
        
        try:
            # Decrypt CA private key
            ca_key_pem = self._decrypt_data(ca_key_encrypted)
            ca_private_key = serialization.load_pem_private_key(ca_key_pem, password=None)
            
            # Load CA certificate
            ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode('utf-8'))
            
            # Build CRL
            crl_builder = x509.CertificateRevocationListBuilder()
            crl_builder = crl_builder.issuer_name(ca_cert.subject)
            crl_builder = crl_builder.last_update(datetime.now(timezone.utc))
            crl_builder = crl_builder.next_update(datetime.now(timezone.utc) + timedelta(days=1))
            
            # Add revoked certificates
            reason_map = {
                "unspecified": x509.ReasonFlags.unspecified,
                "keyCompromise": x509.ReasonFlags.key_compromise,
                "caCompromise": x509.ReasonFlags.ca_compromise,
                "affiliationChanged": x509.ReasonFlags.affiliation_changed,
                "superseded": x509.ReasonFlags.superseded,
                "cessationOfOperation": x509.ReasonFlags.cessation_of_operation,
            }
            
            for serial_hex, revoked_date, reason in revoked_serials:
                serial_int = int(serial_hex, 16)
                revoked_cert = (
                    x509.RevokedCertificateBuilder()
                    .serial_number(serial_int)
                    .revocation_date(revoked_date)
                    .add_extension(
                        x509.CRLReason(reason_map.get(reason, x509.ReasonFlags.unspecified)),
                        critical=False
                    )
                    .build()
                )
                crl_builder = crl_builder.add_revoked_certificate(revoked_cert)
            
            # Sign CRL
            crl = crl_builder.sign(ca_private_key, hashes.SHA256())
            
            # Serialize to PEM
            crl_pem = crl.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            
            logger.info("✅ CRL generated successfully")
            
            return crl_pem
            
        except Exception as e:
            logger.error(f"Failed to generate CRL: {e}", exc_info=True)
            raise CertificateAuthorityError(f"CRL generation failed: {e}") from e

    def verify_certificate(
        self,
        cert_pem: str,
        ca_cert_pem: str
    ) -> tuple[bool, str]:
        """Verify that a certificate was signed by the CA.
        
        Args:
            cert_pem: Certificate to verify in PEM format
            ca_cert_pem: CA certificate in PEM format
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Load certificates
            cert = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'))
            ca_cert = x509.load_pem_x509_certificate(ca_cert_pem.encode('utf-8'))
            
            # Verify signature
            ca_public_key = ca_cert.public_key()
            try:
                ca_public_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    cert.signature_algorithm_parameters
                )
            except Exception as e:
                return False, f"Signature verification failed: {e}"
            
            # Verify validity period
            now = datetime.now(timezone.utc)
            if now < cert.not_valid_before_utc:
                return False, "Certificate not yet valid"
            if now > cert.not_valid_after_utc:
                return False, "Certificate has expired"
            
            # Verify issuer matches CA subject
            if cert.issuer != ca_cert.subject:
                return False, "Issuer does not match CA"
            
            return True, "Certificate is valid"
            
        except Exception as e:
            logger.error(f"Certificate verification failed: {e}", exc_info=True)
            return False, f"Verification error: {e}"

    def _encrypt_data(self, data: bytes) -> str:
        """Encrypt data using AES-256-GCM.
        
        Args:
            data: Data to encrypt
        
        Returns:
            Base64-encoded nonce + ciphertext
        """
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        ciphertext = self._cipher.encrypt(nonce, data, None)
        
        # Return nonce + ciphertext as hex string
        return (nonce + ciphertext).hex()

    def _decrypt_data(self, encrypted_hex: str) -> bytes:
        """Decrypt data using AES-256-GCM.
        
        Args:
            encrypted_hex: Hex-encoded nonce + ciphertext
        
        Returns:
            Decrypted data
        """
        encrypted = bytes.fromhex(encrypted_hex)
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        
        return self._cipher.decrypt(nonce, ciphertext, None)

    @staticmethod
    def get_certificate_info(cert_pem: str) -> dict:
        """Extract information from a certificate.
        
        Args:
            cert_pem: Certificate in PEM format
        
        Returns:
            Dictionary with certificate information
        """
        try:
            cert = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'))
            
            return {
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "serial_number": format(cert.serial_number, 'X'),
                "not_before": cert.not_valid_before_utc.isoformat(),
                "not_after": cert.not_valid_after_utc.isoformat(),
                "fingerprint": cert.fingerprint(hashes.SHA256()).hex(),
                "version": cert.version.name,
                "signature_algorithm": cert.signature_algorithm_oid._name,
            }
        except Exception as e:
            logger.error(f"Failed to parse certificate: {e}")
            return {"error": str(e)}
