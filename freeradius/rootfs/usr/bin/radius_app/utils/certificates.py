"""Certificate management utilities for RadSec and EAP.

Supports:
- Self-signed CA certificates (recommended for EAP-TLS/PEAP/TTLS)
- Let's Encrypt certificates (recommended for RadSec)
- Certificate import from external sources

Per FreeRADIUS documentation:
- EAP: Use self-signed CA. Clients must trust the CA certificate.
- RadSec: Can use Let's Encrypt. Standard TLS trust chain works.

References:
- https://www.freeradius.org/documentation/freeradius-server/4.0.0/howto/os/letsencrypt.html
- https://www.freeradius.org/documentation/freeradius-server/4.0.0/trouble-shooting/eap_certificates.html
"""

import logging
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.x509.oid import NameOID, ExtensionOID

logger = logging.getLogger(__name__)


class CertificateType(Enum):
    """Types of certificate usage."""
    EAP = "eap"           # For EAP-TLS, PEAP, TTLS (self-signed CA recommended)
    RADSEC = "radsec"     # For RadSec (Let's Encrypt compatible)
    CLIENT = "client"     # Client certificates for EAP-TLS


class CertificateSource(Enum):
    """Source of certificates."""
    SELF_SIGNED = "self_signed"
    LETS_ENCRYPT = "lets_encrypt"
    IMPORTED = "imported"


class CertificateError(Exception):
    """Certificate-related error."""
    pass


class LetsEncryptManager:
    """Manages Let's Encrypt certificates for RadSec.
    
    Note: Let's Encrypt certificates are NOT recommended for EAP because:
    1. Clients must install and trust the CA certificate
    2. Certificates expire every 90 days, requiring re-configuration
    3. Users would need to re-install the CA on every renewal
    
    For EAP, use self-signed certificates with your own CA.
    For RadSec, Let's Encrypt works well with standard TLS trust.
    """
    
    # Common Let's Encrypt certificate locations
    LE_PATHS = [
        "/ssl",                           # Home Assistant SSL directory
        "/etc/letsencrypt/live",          # Standard certbot location
        "/config/letsencrypt",            # Alternative HA location
    ]
    
    def __init__(self, cert_dir: Optional[Path] = None):
        """Initialize Let's Encrypt manager.
        
        Args:
            cert_dir: Directory to store/link certificates
        """
        if cert_dir is None:
            from radius_app.config import get_settings
            settings = get_settings()
            cert_dir = Path(settings.radius_config_path) / "certs" / "radsec"
        self.cert_dir = cert_dir
        self.cert_dir.mkdir(parents=True, exist_ok=True)
    
    def find_letsencrypt_certs(self, domain: Optional[str] = None) -> Optional[dict]:
        """Find Let's Encrypt certificates on the system.
        
        Args:
            domain: Specific domain to look for (optional)
            
        Returns:
            Dictionary with cert_file, key_file, chain_file paths or None
        """
        for base_path in self.LE_PATHS:
            base = Path(base_path)
            if not base.exists():
                continue
            
            # Check for standard HA SSL location (/ssl)
            if base_path == "/ssl":
                cert_file = base / "fullchain.pem"
                key_file = base / "privkey.pem"
                
                if cert_file.exists() and key_file.exists():
                    logger.info(f"Found Let's Encrypt certificates in {base_path}")
                    return {
                        "cert_file": cert_file,
                        "key_file": key_file,
                        "chain_file": cert_file,  # fullchain includes chain
                        "source": "home_assistant_ssl",
                    }
            
            # Check for certbot-style directories
            if domain:
                domain_dir = base / domain
                if domain_dir.exists():
                    cert_file = domain_dir / "fullchain.pem"
                    key_file = domain_dir / "privkey.pem"
                    chain_file = domain_dir / "chain.pem"
                    
                    if cert_file.exists() and key_file.exists():
                        return {
                            "cert_file": cert_file,
                            "key_file": key_file,
                            "chain_file": chain_file if chain_file.exists() else cert_file,
                            "source": "certbot",
                        }
            else:
                # Search for any domain directory
                for domain_dir in base.iterdir():
                    if domain_dir.is_dir():
                        cert_file = domain_dir / "fullchain.pem"
                        key_file = domain_dir / "privkey.pem"
                        
                        if cert_file.exists() and key_file.exists():
                            return {
                                "cert_file": cert_file,
                                "key_file": key_file,
                                "chain_file": cert_file,
                                "source": "certbot",
                                "domain": domain_dir.name,
                            }
        
        return None
    
    def import_letsencrypt_certs(
        self,
        domain: Optional[str] = None,
        copy: bool = True,
    ) -> Tuple[Path, Path]:
        """Import Let's Encrypt certificates for RadSec use.
        
        Args:
            domain: Specific domain to import (optional)
            copy: If True, copy files. If False, create symlinks.
            
        Returns:
            Tuple of (certificate_path, key_path)
            
        Raises:
            CertificateError: If certificates not found or import fails
        """
        certs = self.find_letsencrypt_certs(domain)
        
        if not certs:
            raise CertificateError(
                "Let's Encrypt certificates not found. Check that:\n"
                "1. You have certificates in /ssl or /etc/letsencrypt/live\n"
                "2. The 'ssl' directory is mapped in your addon config\n"
                "3. Your domain's certificates are properly installed"
            )
        
        try:
            dest_cert = self.cert_dir / "radsec-server.pem"
            dest_key = self.cert_dir / "radsec-server-key.pem"
            dest_chain = self.cert_dir / "radsec-ca.pem"
            
            if copy:
                # Copy files (recommended for stability)
                shutil.copy2(certs["cert_file"], dest_cert)
                shutil.copy2(certs["key_file"], dest_key)
                if certs.get("chain_file"):
                    shutil.copy2(certs["chain_file"], dest_chain)
                
                logger.info(f"Copied Let's Encrypt certificates to {self.cert_dir}")
            else:
                # Create symlinks (auto-updates but may cause issues)
                for dest, src in [
                    (dest_cert, certs["cert_file"]),
                    (dest_key, certs["key_file"]),
                ]:
                    if dest.exists() or dest.is_symlink():
                        dest.unlink()
                    dest.symlink_to(src)
                
                if certs.get("chain_file"):
                    if dest_chain.exists() or dest_chain.is_symlink():
                        dest_chain.unlink()
                    dest_chain.symlink_to(certs["chain_file"])
                
                logger.info(f"Created symlinks to Let's Encrypt certificates")
            
            # Set proper permissions
            dest_cert.chmod(0o644)
            dest_key.chmod(0o600)
            if dest_chain.exists():
                dest_chain.chmod(0o644)
            
            return dest_cert, dest_key
            
        except (OSError, PermissionError) as e:
            raise CertificateError(f"Failed to import Let's Encrypt certificates: {e}")
    
    def check_letsencrypt_status(self, domain: Optional[str] = None) -> dict:
        """Check Let's Encrypt certificate status.
        
        Args:
            domain: Specific domain to check
            
        Returns:
            Dictionary with certificate status information
        """
        certs = self.find_letsencrypt_certs(domain)
        
        if not certs:
            return {
                "available": False,
                "error": "Let's Encrypt certificates not found",
            }
        
        try:
            with open(certs["cert_file"], "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            
            now = datetime.now(timezone.utc)
            days_until_expiry = (cert.not_valid_after_utc - now).days
            
            # Extract CN/domain from certificate
            cn = None
            for attr in cert.subject:
                if attr.oid == NameOID.COMMON_NAME:
                    cn = attr.value
                    break
            
            # Check for SANs
            sans = []
            try:
                san_ext = cert.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                for name in san_ext.value:
                    sans.append(str(name.value))
            except x509.ExtensionNotFound:
                pass
            
            return {
                "available": True,
                "source": certs.get("source", "unknown"),
                "cert_file": str(certs["cert_file"]),
                "key_file": str(certs["key_file"]),
                "common_name": cn,
                "subject_alternative_names": sans,
                "valid_from": cert.not_valid_before_utc.isoformat(),
                "valid_until": cert.not_valid_after_utc.isoformat(),
                "days_until_expiry": days_until_expiry,
                "is_expired": days_until_expiry < 0,
                "needs_renewal": days_until_expiry < 30,
            }
            
        except Exception as e:
            return {
                "available": True,
                "error": f"Failed to parse certificate: {e}",
                "cert_file": str(certs["cert_file"]),
            }


class CertificateManager:
    """Manages TLS certificates for RadSec and EAP.
    
    Certificate Strategy:
    - EAP (eap/): Self-signed CA + server cert. Clients trust your CA.
    - RadSec (radsec/): Can use Let's Encrypt or self-signed.
    - Clients (clients/): User certificates for EAP-TLS.
    """
    
    def __init__(self, cert_dir: Optional[Path] = None):
        """Initialize certificate manager.
        
        Args:
            cert_dir: Base directory for certificates (defaults to settings)
        """
        if cert_dir is None:
            from radius_app.config import get_settings
            settings = get_settings()
            cert_dir = Path(settings.radius_config_path) / "certs"
        
        self.cert_dir = cert_dir
        self.eap_dir = cert_dir / "eap"
        self.radsec_dir = cert_dir / "radsec"
        self.clients_dir = cert_dir / "clients"
        
        # Initialize Let's Encrypt manager for RadSec
        self.letsencrypt = LetsEncryptManager(self.radsec_dir)
        
        # Create directories
        try:
            for d in [self.cert_dir, self.eap_dir, self.radsec_dir, self.clients_dir]:
                d.mkdir(parents=True, exist_ok=True)
            logger.info(f"Certificate manager initialized: {self.cert_dir}")
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not create cert directories (may be test environment): {e}")
    
    def generate_ca_certificate(
        self,
        common_name: str,
        organization: str = "FreeRADIUS",
        country: str = "US",
        validity_days: int = 3650,
        key_size: int = 4096,
    ) -> Tuple[Path, Path]:
        """Generate CA certificate and private key.
        
        Args:
            common_name: Certificate common name
            organization: Organization name
            country: Country code (2 letters)
            validity_days: Certificate validity in days
            key_size: RSA key size (2048 or 4096)
            
        Returns:
            Tuple of (certificate_path, key_path)
            
        Raises:
            CertificateError: If generation fails
        """
        if key_size < 2048:
            raise CertificateError("Key size must be at least 2048 bits")
        
        try:
            # Generate private key
            logger.info(f"Generating CA certificate for {common_name}")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            # Create certificate
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now(timezone.utc)
            ).not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=validity_days)
            ).add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            ).add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_cert_sign=True,
                    crl_sign=True,
                    key_encipherment=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            ).sign(private_key, hashes.SHA256(), backend=default_backend())
            
            # Save certificate
            cert_path = self.cert_dir / "ca.pem"
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            cert_path.chmod(0o644)
            
            # Save private key
            key_path = self.cert_dir / "ca-key.pem"
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            key_path.chmod(0o600)
            
            logger.info(f"✅ CA certificate generated: {cert_path}")
            return cert_path, key_path
            
        except Exception as e:
            logger.error(f"Failed to generate CA certificate: {e}", exc_info=True)
            raise CertificateError(f"CA certificate generation failed: {e}")
    
    def generate_server_certificate(
        self,
        common_name: str,
        organization: str = "FreeRADIUS",
        country: str = "US",
        validity_days: int = 397,
        key_size: int = 4096,
        ca_cert_path: Optional[Path] = None,
        ca_key_path: Optional[Path] = None,
    ) -> Tuple[Path, Path]:
        """Generate server certificate signed by CA.
        
        Args:
            common_name: Server common name (hostname/FQDN)
            organization: Organization name
            country: Country code
            validity_days: Certificate validity (max 397 for Apple/Chrome, 825 for others)
            key_size: RSA key size
            ca_cert_path: CA certificate path
            ca_key_path: CA private key path
            
        Returns:
            Tuple of (certificate_path, key_path)
            
        Raises:
            CertificateError: If generation fails
        """
        if validity_days > 825:
            raise CertificateError("Certificate validity must not exceed 825 days")
        
        if key_size < 2048:
            raise CertificateError("Key size must be at least 2048 bits")
        
        try:
            # Load CA certificate and key
            ca_cert_path = ca_cert_path or self.cert_dir / "ca.pem"
            ca_key_path = ca_key_path or self.cert_dir / "ca-key.pem"
            
            if not ca_cert_path.exists():
                raise CertificateError(f"CA certificate not found: {ca_cert_path}")
            
            with open(ca_cert_path, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            
            with open(ca_key_path, "rb") as f:
                ca_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Generate server private key
            logger.info(f"Generating server certificate for {common_name}")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            # Create server certificate
            subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                ca_cert.subject
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now(timezone.utc)
            ).not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=validity_days)
            ).add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            ).add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    key_cert_sign=False,
                    crl_sign=False,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            ).add_extension(
                x509.ExtendedKeyUsage([
                    x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                ]),
                critical=True,
            ).sign(ca_key, hashes.SHA256(), backend=default_backend())
            
            # Save certificate
            cert_path = self.cert_dir / "server.pem"
            with open(cert_path, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            cert_path.chmod(0o644)
            
            # Save private key
            key_path = self.cert_dir / "server-key.pem"
            with open(key_path, "wb") as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            key_path.chmod(0o600)
            
            logger.info(f"✅ Server certificate generated: {cert_path}")
            return cert_path, key_path
            
        except Exception as e:
            logger.error(f"Failed to generate server certificate: {e}", exc_info=True)
            raise CertificateError(f"Server certificate generation failed: {e}")
    
    def parse_certificate(self, cert_path: Path) -> dict:
        """Parse certificate and extract information.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Dictionary with certificate information
            
        Raises:
            CertificateError: If parsing fails
        """
        try:
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            
            # Extract subject and issuer
            subject_parts = []
            for attr in cert.subject:
                subject_parts.append(f"{attr.oid._name}={attr.value}")
            subject = ", ".join(subject_parts)
            
            issuer_parts = []
            for attr in cert.issuer:
                issuer_parts.append(f"{attr.oid._name}={attr.value}")
            issuer = ", ".join(issuer_parts)
            
            # Check if expired
            now = datetime.now(timezone.utc)
            is_expired = now > cert.not_valid_after_utc
            days_until_expiry = (cert.not_valid_after_utc - now).days
            
            # Get fingerprint
            fingerprint = cert.fingerprint(hashes.SHA256()).hex(":")
            
            # Check key strength
            public_key = cert.public_key()
            key_size = public_key.key_size if hasattr(public_key, 'key_size') else None
            
            # Warn about weak keys
            warnings = []
            if key_size and key_size < 2048:
                warnings.append(f"WEAK KEY: RSA key size {key_size} bits is insufficient (minimum 2048)")
            
            # Check signature algorithm
            sig_algo = cert.signature_algorithm_oid._name
            if "md5" in sig_algo.lower() or "sha1" in sig_algo.lower():
                warnings.append(f"INSECURE SIGNATURE: {sig_algo} is cryptographically weak")
            
            # Check expiry
            if is_expired:
                warnings.append(f"EXPIRED: Certificate expired on {cert.not_valid_after_utc.isoformat()}")
            elif days_until_expiry < 30:
                warnings.append(f"EXPIRING SOON: Certificate expires in {days_until_expiry} days")
            
            return {
                "subject": subject,
                "issuer": issuer,
                "valid_from": cert.not_valid_before_utc.isoformat(),
                "valid_until": cert.not_valid_after_utc.isoformat(),
                "is_expired": is_expired,
                "days_until_expiry": days_until_expiry,
                "serial_number": str(cert.serial_number),
                "fingerprint_sha256": fingerprint,
                "signature_algorithm": sig_algo,
                "key_size": key_size,
                "warnings": warnings,
            }
            
        except Exception as e:
            logger.error(f"Failed to parse certificate: {e}", exc_info=True)
            raise CertificateError(f"Certificate parsing failed: {e}")
    
    def verify_certificate_chain(
        self,
        cert_path: Path,
        ca_cert_path: Path,
    ) -> Tuple[bool, Optional[str]]:
        """Verify certificate is signed by CA.
        
        Args:
            cert_path: Certificate to verify
            ca_cert_path: CA certificate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Load certificates
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            
            with open(ca_cert_path, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            
            # Verify issuer matches
            if cert.issuer != ca_cert.subject:
                return False, "Certificate issuer does not match CA subject"
            
            # Verify signature
            try:
                ca_public_key = ca_cert.public_key()
                ca_public_key.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    cert.signature_algorithm_parameters,
                    cert.signature_hash_algorithm,
                )
            except Exception as e:
                return False, f"Signature verification failed: {e}"
            
            # Check validity dates
            now = datetime.now(timezone.utc)
            if now < cert.not_valid_before_utc:
                return False, "Certificate is not yet valid"
            if now > cert.not_valid_after_utc:
                return False, "Certificate has expired"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Certificate verification failed: {e}", exc_info=True)
            return False, str(e)
    
    def list_certificates(self) -> list[dict]:
        """List all certificates in certificate directory.
        
        Returns:
            List of certificate information dictionaries
        """
        certificates = []
        
        # Search in all certificate directories
        for search_dir in [self.cert_dir, self.eap_dir, self.radsec_dir, self.clients_dir]:
            if not search_dir.exists():
                continue
            
            for cert_file in search_dir.glob("*.pem"):
                # Skip key files
                if "key" in cert_file.name:
                    continue
                
                try:
                    cert_info = self.parse_certificate(cert_file)
                    cert_info["file_name"] = cert_file.name
                    cert_info["file_path"] = str(cert_file)
                    cert_info["cert_type"] = self._get_cert_type(cert_file)
                    certificates.append(cert_info)
                except CertificateError as e:
                    logger.warning(f"Failed to parse {cert_file}: {e}")
                    continue
        
        return certificates
    
    def _get_cert_type(self, cert_path: Path) -> str:
        """Determine certificate type from path.
        
        Args:
            cert_path: Path to certificate file
            
        Returns:
            Certificate type string
        """
        path_str = str(cert_path)
        if "/eap/" in path_str:
            return CertificateType.EAP.value
        elif "/radsec/" in path_str:
            return CertificateType.RADSEC.value
        elif "/clients/" in path_str:
            return CertificateType.CLIENT.value
        return "unknown"
    
    def generate_eap_certificates(
        self,
        common_name: str,
        organization: str = "FreeRADIUS",
        country: str = "US",
        ca_validity_days: int = 3650,
        server_validity_days: int = 397,
        key_size: int = 4096,
    ) -> dict:
        """Generate complete EAP certificate chain (CA + server).
        
        For EAP-TLS, PEAP, TTLS - uses self-signed CA.
        Clients must install and trust the CA certificate.
        
        Args:
            common_name: Server hostname/FQDN
            organization: Organization name
            country: Country code
            ca_validity_days: CA certificate validity (default 10 years)
            server_validity_days: Server cert validity (default 397 days)
            key_size: RSA key size (minimum 2048)
            
        Returns:
            Dictionary with CA and server certificate paths
        """
        logger.info(f"Generating EAP certificate chain for {common_name}")
        
        # Generate CA certificate
        ca_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{organization} RADIUS CA"),
        ])
        
        ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        ca_cert = x509.CertificateBuilder().subject_name(
            ca_subject
        ).issuer_name(
            ca_subject
        ).public_key(
            ca_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=ca_validity_days)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).sign(ca_key, hashes.SHA256(), backend=default_backend())
        
        # Save CA files
        ca_cert_path = self.eap_dir / "ca.pem"
        ca_key_path = self.eap_dir / "ca-key.pem"
        
        ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        ca_cert_path.chmod(0o644)
        
        ca_key_path.write_bytes(ca_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        ca_key_path.chmod(0o600)
        
        # Generate server certificate
        server_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        server_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        # Add XP Extensions for Windows compatibility
        server_cert = x509.CertificateBuilder().subject_name(
            server_subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            server_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=server_validity_days)
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256(), backend=default_backend())
        
        # Save server files
        server_cert_path = self.eap_dir / "server.pem"
        server_key_path = self.eap_dir / "server-key.pem"
        
        server_cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
        server_cert_path.chmod(0o644)
        
        server_key_path.write_bytes(server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        server_key_path.chmod(0o600)
        
        # Generate DH parameters (can be slow)
        dh_path = self.eap_dir / "dh"
        if not dh_path.exists():
            logger.info("Generating DH parameters (this may take a moment)...")
            try:
                subprocess.run(
                    ["openssl", "dhparam", "-out", str(dh_path), "2048"],
                    check=True,
                    capture_output=True,
                    timeout=300,
                )
                dh_path.chmod(0o644)
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                logger.warning(f"Could not generate DH params: {e}")
        
        logger.info(f"✅ EAP certificates generated in {self.eap_dir}")
        
        return {
            "ca_cert": str(ca_cert_path),
            "ca_key": str(ca_key_path),
            "server_cert": str(server_cert_path),
            "server_key": str(server_key_path),
            "dh_params": str(dh_path) if dh_path.exists() else None,
            "type": CertificateType.EAP.value,
            "source": CertificateSource.SELF_SIGNED.value,
        }
    
    def setup_radsec_letsencrypt(
        self,
        domain: Optional[str] = None,
        copy: bool = True,
    ) -> dict:
        """Setup RadSec using Let's Encrypt certificates.
        
        Args:
            domain: Specific domain to use (optional)
            copy: Copy files vs symlink
            
        Returns:
            Dictionary with certificate paths and info
        """
        logger.info("Setting up RadSec with Let's Encrypt certificates")
        
        # Import Let's Encrypt certs
        cert_path, key_path = self.letsencrypt.import_letsencrypt_certs(
            domain=domain,
            copy=copy,
        )
        
        # Get certificate info
        status = self.letsencrypt.check_letsencrypt_status(domain)
        
        # Create CA file (Let's Encrypt intermediate + root)
        ca_path = self.radsec_dir / "radsec-ca.pem"
        
        return {
            "server_cert": str(cert_path),
            "server_key": str(key_path),
            "ca_cert": str(ca_path) if ca_path.exists() else None,
            "type": CertificateType.RADSEC.value,
            "source": CertificateSource.LETS_ENCRYPT.value,
            "letsencrypt_status": status,
        }
    
    def setup_radsec_selfsigned(
        self,
        common_name: str,
        organization: str = "FreeRADIUS",
        country: str = "US",
        validity_days: int = 397,
        key_size: int = 4096,
    ) -> dict:
        """Setup RadSec using self-signed certificates.
        
        Alternative to Let's Encrypt for RadSec.
        Note: Clients will need to trust your CA certificate.
        
        Args:
            common_name: Server hostname/FQDN
            organization: Organization name
            country: Country code
            validity_days: Certificate validity
            key_size: RSA key size
            
        Returns:
            Dictionary with certificate paths
        """
        logger.info(f"Setting up RadSec with self-signed certificates for {common_name}")
        
        # Generate CA if needed
        ca_cert_path = self.radsec_dir / "radsec-ca.pem"
        ca_key_path = self.radsec_dir / "radsec-ca-key.pem"
        
        if not ca_cert_path.exists():
            ca_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            
            ca_subject = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
                x509.NameAttribute(NameOID.COMMON_NAME, f"{organization} RadSec CA"),
            ])
            
            ca_cert = x509.CertificateBuilder().subject_name(
                ca_subject
            ).issuer_name(
                ca_subject
            ).public_key(
                ca_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.now(timezone.utc)
            ).not_valid_after(
                datetime.now(timezone.utc) + timedelta(days=3650)
            ).add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            ).sign(ca_key, hashes.SHA256(), backend=default_backend())
            
            ca_cert_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
            ca_cert_path.chmod(0o644)
            
            ca_key_path.write_bytes(ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            ca_key_path.chmod(0o600)
        else:
            # Load existing CA
            with open(ca_cert_path, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            with open(ca_key_path, "rb") as f:
                ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())
        
        # Generate server certificate
        server_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        
        server_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        server_cert = x509.CertificateBuilder().subject_name(
            server_subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            server_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc) + timedelta(days=validity_days)
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256(), backend=default_backend())
        
        server_cert_path = self.radsec_dir / "radsec-server.pem"
        server_key_path = self.radsec_dir / "radsec-server-key.pem"
        
        server_cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
        server_cert_path.chmod(0o644)
        
        server_key_path.write_bytes(server_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        server_key_path.chmod(0o600)
        
        logger.info(f"✅ RadSec self-signed certificates generated in {self.radsec_dir}")
        
        return {
            "ca_cert": str(ca_cert_path),
            "ca_key": str(ca_key_path),
            "server_cert": str(server_cert_path),
            "server_key": str(server_key_path),
            "type": CertificateType.RADSEC.value,
            "source": CertificateSource.SELF_SIGNED.value,
        }
    
    def import_certificates(
        self,
        cert_type: CertificateType,
        cert_file: Path,
        key_file: Path,
        ca_file: Optional[Path] = None,
    ) -> dict:
        """Import external certificates.
        
        Args:
            cert_type: Type of certificate (EAP or RADSEC)
            cert_file: Path to certificate file
            key_file: Path to private key file
            ca_file: Optional CA certificate file
            
        Returns:
            Dictionary with imported certificate paths
        """
        # Validate input files exist
        if not cert_file.exists():
            raise CertificateError(f"Certificate file not found: {cert_file}")
        if not key_file.exists():
            raise CertificateError(f"Key file not found: {key_file}")
        
        # Validate certificate
        try:
            self.parse_certificate(cert_file)
        except CertificateError as e:
            raise CertificateError(f"Invalid certificate file: {e}")
        
        # Determine destination directory
        if cert_type == CertificateType.EAP:
            dest_dir = self.eap_dir
            prefix = ""
        elif cert_type == CertificateType.RADSEC:
            dest_dir = self.radsec_dir
            prefix = "radsec-"
        else:
            dest_dir = self.cert_dir
            prefix = ""
        
        # Copy files
        dest_cert = dest_dir / f"{prefix}server.pem"
        dest_key = dest_dir / f"{prefix}server-key.pem"
        
        shutil.copy2(cert_file, dest_cert)
        dest_cert.chmod(0o644)
        
        shutil.copy2(key_file, dest_key)
        dest_key.chmod(0o600)
        
        result = {
            "server_cert": str(dest_cert),
            "server_key": str(dest_key),
            "type": cert_type.value,
            "source": CertificateSource.IMPORTED.value,
        }
        
        if ca_file and ca_file.exists():
            dest_ca = dest_dir / f"{prefix}ca.pem"
            shutil.copy2(ca_file, dest_ca)
            dest_ca.chmod(0o644)
            result["ca_cert"] = str(dest_ca)
        
        logger.info(f"✅ Imported {cert_type.value} certificates to {dest_dir}")
        
        return result
    
    def get_certificate_status(self) -> dict:
        """Get overall certificate status for all types.
        
        Returns:
            Dictionary with status for EAP, RadSec, and Let's Encrypt
        """
        status = {
            "eap": {
                "configured": False,
                "source": None,
            },
            "radsec": {
                "configured": False,
                "source": None,
            },
            "letsencrypt": self.letsencrypt.check_letsencrypt_status(),
        }
        
        # Check EAP certificates
        eap_cert = self.eap_dir / "server.pem"
        if eap_cert.exists():
            try:
                cert_info = self.parse_certificate(eap_cert)
                status["eap"] = {
                    "configured": True,
                    "source": CertificateSource.SELF_SIGNED.value,
                    "common_name": cert_info.get("subject", ""),
                    "valid_until": cert_info.get("valid_until"),
                    "days_until_expiry": cert_info.get("days_until_expiry"),
                    "warnings": cert_info.get("warnings", []),
                }
            except CertificateError:
                pass
        
        # Check RadSec certificates
        for radsec_cert_name in ["radsec-server.pem", "server.pem"]:
            radsec_cert = self.radsec_dir / radsec_cert_name
            if radsec_cert.exists():
                try:
                    cert_info = self.parse_certificate(radsec_cert)
                    
                    # Determine source
                    source = CertificateSource.SELF_SIGNED.value
                    issuer = cert_info.get("issuer", "")
                    if "Let's Encrypt" in issuer or "ISRG" in issuer:
                        source = CertificateSource.LETS_ENCRYPT.value
                    
                    status["radsec"] = {
                        "configured": True,
                        "source": source,
                        "common_name": cert_info.get("subject", ""),
                        "valid_until": cert_info.get("valid_until"),
                        "days_until_expiry": cert_info.get("days_until_expiry"),
                        "warnings": cert_info.get("warnings", []),
                    }
                    break
                except CertificateError:
                    pass
        
        return status
