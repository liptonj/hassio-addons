"""Certificate Management Service.

This module provides high-level certificate management operations, coordinating
between the Certificate Authority, database, and external CA providers.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.certificate_authority import InternalCertificateAuthority, CertificateAuthorityError
from app.db.models import (
    CertificateAuthority,
    UserCertificate,
    CertificateRevocation,
    User,
    DeviceRegistration,
)

logger = logging.getLogger(__name__)


class CertificateManagerError(Exception):
    """Base exception for Certificate Manager operations."""


class CertificateManager:
    """High-level certificate management service.
    
    This service coordinates certificate operations across the CA, database,
    and external providers. It handles certificate issuance, renewal, revocation,
    and lifecycle management.
    """

    def __init__(self, db: Session):
        """Initialize the Certificate Manager.
        
        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        
        # Initialize internal CA with encryption key from settings
        # In production, this should come from a secure key management system
        encryption_key = self._get_encryption_key()
        self.ca = InternalCertificateAuthority(encryption_key)
        
        logger.info("Certificate Manager initialized")

    def initialize_internal_ca(
        self,
        common_name: str,
        organization: str,
        created_by: str
    ) -> CertificateAuthority:
        """Initialize a new internal Certificate Authority.
        
        Args:
            common_name: CA common name (e.g., "Property WiFi Root CA")
            organization: Organization name
            created_by: Username of admin who initialized the CA
        
        Returns:
            CertificateAuthority database model
        
        Raises:
            CertificateManagerError: If CA initialization fails
        """
        logger.info(f"Initializing internal CA: {common_name}")
        
        try:
            # Check if a primary CA already exists
            existing_ca = self.db.query(CertificateAuthority).filter_by(
                is_primary=True,
                is_active=True
            ).first()
            
            if existing_ca:
                raise CertificateManagerError("A primary CA already exists. Revoke it first.")
            
            # Generate root CA
            cert_pem, encrypted_key, fingerprint = self.ca.generate_root_ca(
                common_name=common_name,
                organization=organization,
                validity_days=3650,  # 10 years
                key_size=4096
            )
            
            # Parse certificate for validity dates
            cert_info = InternalCertificateAuthority.get_certificate_info(cert_pem)
            valid_from = datetime.fromisoformat(cert_info["not_before"])
            valid_until = datetime.fromisoformat(cert_info["not_after"])
            
            # Create CA record
            ca_record = CertificateAuthority(
                name=common_name,
                description=f"Internal CA for {organization}",
                ca_type="internal",
                root_certificate=cert_pem,
                root_certificate_fingerprint=fingerprint,
                private_key_encrypted=encrypted_key,
                valid_from=valid_from,
                valid_until=valid_until,
                key_algorithm="RSA",
                key_size=4096,
                signature_algorithm="sha256WithRSAEncryption",
                default_validity_days=365,
                auto_renewal_enabled=True,
                renewal_threshold_days=30,
                is_active=True,
                is_primary=True,
                created_by=created_by
            )
            
            self.db.add(ca_record)
            self.db.commit()
            self.db.refresh(ca_record)
            
            logger.info(f"✅ Internal CA initialized. ID: {ca_record.id}, Fingerprint: {fingerprint[:16]}...")
            
            return ca_record
            
        except CertificateAuthorityError as e:
            self.db.rollback()
            logger.error(f"Failed to initialize CA: {e}")
            raise CertificateManagerError(f"CA initialization failed: {e}") from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error initializing CA: {e}", exc_info=True)
            raise CertificateManagerError(f"Unexpected error: {e}") from e

    def issue_user_certificate(
        self,
        user_id: int,
        device_registration_id: int | None = None,
        validity_days: int | None = None
    ) -> UserCertificate:
        """Issue a certificate for a user.
        
        Args:
            user_id: User ID
            device_registration_id: Optional device registration ID
            validity_days: Certificate validity (uses CA default if not specified)
        
        Returns:
            UserCertificate database model
        
        Raises:
            CertificateManagerError: If certificate issuance fails
        """
        logger.info(f"Issuing certificate for user_id={user_id}")
        
        try:
            # Get user
            user = self.db.query(User).filter_by(id=user_id).first()
            if not user:
                raise CertificateManagerError(f"User {user_id} not found")
            
            # Get primary CA
            ca = self.db.query(CertificateAuthority).filter_by(
                is_primary=True,
                is_active=True
            ).first()
            
            if not ca:
                raise CertificateManagerError("No active CA found. Initialize CA first.")
            
            # Use CA default validity if not specified
            if validity_days is None:
                validity_days = ca.default_validity_days
            
            # Generate common name from user email
            common_name = user.email
            
            # Issue certificate
            cert_pem, encrypted_key, serial_hex, fingerprint = self.ca.issue_user_certificate(
                common_name=common_name,
                email=user.email,
                ca_cert_pem=ca.root_certificate,
                ca_key_encrypted=ca.private_key_encrypted,
                validity_days=validity_days,
                key_size=2048
            )
            
            # Parse certificate for validity dates
            cert_info = InternalCertificateAuthority.get_certificate_info(cert_pem)
            valid_from = datetime.fromisoformat(cert_info["not_before"])
            valid_until = datetime.fromisoformat(cert_info["not_after"])
            
            # Generate PKCS#12 for iOS/macOS
            pkcs12_bytes, pkcs12_password = self.ca.generate_pkcs12(
                cert_pem=cert_pem,
                key_encrypted=encrypted_key,
                ca_cert_pem=ca.root_certificate,
                friendly_name=f"{user.name} - WiFi Certificate"
            )
            
            # Encrypt PKCS#12 data and password
            pkcs12_encrypted = self.ca._encrypt_data(pkcs12_bytes)
            pkcs12_password_encrypted = self.ca._encrypt_data(pkcs12_password.encode('utf-8'))
            
            # Create certificate record
            cert_record = UserCertificate(
                user_id=user_id,
                ca_id=ca.id,
                device_registration_id=device_registration_id,
                certificate=cert_pem,
                certificate_fingerprint=fingerprint,
                private_key_encrypted=encrypted_key,
                pkcs12_encrypted=pkcs12_encrypted,
                pkcs12_password_encrypted=pkcs12_password_encrypted,
                subject_common_name=common_name,
                subject_email=user.email,
                subject_distinguished_name=cert_info["subject"],
                valid_from=valid_from,
                valid_until=valid_until,
                key_algorithm="RSA",
                key_size=2048,
                serial_number=serial_hex,
                status="active",
                auto_renew=user.cert_auto_renew if user.cert_auto_renew is not None else True
            )
            
            self.db.add(cert_record)
            
            # Update CA statistics
            ca.certificates_issued += 1
            
            # Mark user as EAP-enabled
            user.eap_enabled = True
            
            self.db.commit()
            self.db.refresh(cert_record)
            
            logger.info(f"✅ Certificate issued. ID: {cert_record.id}, Serial: {serial_hex}")
            
            return cert_record
            
        except CertificateAuthorityError as e:
            self.db.rollback()
            logger.error(f"Failed to issue certificate: {e}")
            raise CertificateManagerError(f"Certificate issuance failed: {e}") from e
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error issuing certificate: {e}", exc_info=True)
            raise CertificateManagerError(f"Unexpected error: {e}") from e

    def renew_certificate(
        self,
        certificate_id: int,
        validity_days: int | None = None
    ) -> UserCertificate:
        """Renew an existing certificate.
        
        Args:
            certificate_id: Certificate ID to renew
            validity_days: New certificate validity (uses CA default if not specified)
        
        Returns:
            New UserCertificate database model
        
        Raises:
            CertificateManagerError: If renewal fails
        """
        logger.info(f"Renewing certificate ID: {certificate_id}")
        
        try:
            # Get old certificate
            old_cert = self.db.query(UserCertificate).filter_by(id=certificate_id).first()
            if not old_cert:
                raise CertificateManagerError(f"Certificate {certificate_id} not found")
            
            # Issue new certificate
            new_cert = self.issue_user_certificate(
                user_id=old_cert.user_id,
                device_registration_id=old_cert.device_registration_id,
                validity_days=validity_days
            )
            
            # Link old and new certificates
            old_cert.renewed_by_certificate_id = new_cert.id
            old_cert.status = "renewed"
            
            self.db.commit()
            
            logger.info(f"✅ Certificate renewed. Old ID: {certificate_id}, New ID: {new_cert.id}")
            
            return new_cert
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to renew certificate: {e}", exc_info=True)
            raise CertificateManagerError(f"Certificate renewal failed: {e}") from e

    def revoke_certificate(
        self,
        certificate_id: int,
        reason: Literal[
            "unspecified",
            "keyCompromise",
            "caCompromise",
            "affiliationChanged",
            "superseded",
            "cessationOfOperation"
        ],
        revoked_by: str,
        notes: str | None = None
    ) -> CertificateRevocation:
        """Revoke a certificate.
        
        Args:
            certificate_id: Certificate ID to revoke
            reason: Revocation reason
            revoked_by: Username of person revoking the certificate
            notes: Optional notes about revocation
        
        Returns:
            CertificateRevocation database model
        
        Raises:
            CertificateManagerError: If revocation fails
        """
        logger.info(f"Revoking certificate ID: {certificate_id}, reason: {reason}")
        
        try:
            # Get certificate
            cert = self.db.query(UserCertificate).filter_by(id=certificate_id).first()
            if not cert:
                raise CertificateManagerError(f"Certificate {certificate_id} not found")
            
            if cert.status == "revoked":
                raise CertificateManagerError("Certificate is already revoked")
            
            # Update certificate status
            cert.status = "revoked"
            cert.revoked_at = datetime.now(timezone.utc)
            cert.revocation_reason = reason
            
            # Create revocation record
            revocation = CertificateRevocation(
                certificate_id=certificate_id,
                ca_id=cert.ca_id,
                serial_number=cert.serial_number,
                revocation_reason=reason,
                revoked_by=revoked_by,
                notes=notes
            )
            
            self.db.add(revocation)
            
            # Update CA statistics
            ca = self.db.query(CertificateAuthority).filter_by(id=cert.ca_id).first()
            if ca:
                ca.certificates_revoked += 1
            
            self.db.commit()
            self.db.refresh(revocation)
            
            logger.info(f"✅ Certificate revoked. Serial: {cert.serial_number}")
            
            return revocation
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to revoke certificate: {e}", exc_info=True)
            raise CertificateManagerError(f"Certificate revocation failed: {e}") from e

    def generate_crl(self, ca_id: int | None = None) -> str:
        """Generate Certificate Revocation List for a CA.
        
        Args:
            ca_id: CA ID (uses primary CA if not specified)
        
        Returns:
            CRL in PEM format
        
        Raises:
            CertificateManagerError: If CRL generation fails
        """
        logger.info(f"Generating CRL for CA ID: {ca_id or 'primary'}")
        
        try:
            # Get CA
            if ca_id:
                ca = self.db.query(CertificateAuthority).filter_by(id=ca_id).first()
            else:
                ca = self.db.query(CertificateAuthority).filter_by(
                    is_primary=True,
                    is_active=True
                ).first()
            
            if not ca:
                raise CertificateManagerError("CA not found")
            
            # Get revoked certificates
            revocations = self.db.query(CertificateRevocation).filter_by(
                ca_id=ca.id
            ).all()
            
            # Build revoked serials list
            revoked_serials = [
                (rev.serial_number, rev.revoked_at, rev.revocation_reason)
                for rev in revocations
            ]
            
            # Generate CRL
            crl_pem = self.ca.generate_crl(
                ca_cert_pem=ca.root_certificate,
                ca_key_encrypted=ca.private_key_encrypted,
                revoked_serials=revoked_serials
            )
            
            # Mark revocations as published
            for revocation in revocations:
                if not revocation.published_to_crl:
                    revocation.published_to_crl = True
                    revocation.crl_published_at = datetime.now(timezone.utc)
            
            self.db.commit()
            
            logger.info(f"✅ CRL generated with {len(revoked_serials)} revoked certificates")
            
            return crl_pem
            
        except Exception as e:
            logger.error(f"Failed to generate CRL: {e}", exc_info=True)
            raise CertificateManagerError(f"CRL generation failed: {e}") from e

    def get_certificate_with_chain(self, certificate_id: int) -> dict:
        """Get certificate with full chain for download.
        
        Args:
            certificate_id: Certificate ID
        
        Returns:
            Dictionary with certificate, private key, CA cert, and PKCS#12
        
        Raises:
            CertificateManagerError: If certificate not found
        """
        try:
            cert = self.db.query(UserCertificate).filter_by(id=certificate_id).first()
            if not cert:
                raise CertificateManagerError(f"Certificate {certificate_id} not found")
            
            ca = self.db.query(CertificateAuthority).filter_by(id=cert.ca_id).first()
            if not ca:
                raise CertificateManagerError(f"CA {cert.ca_id} not found")
            
            # Decrypt private key
            private_key_pem = self.ca._decrypt_data(cert.private_key_encrypted).decode('utf-8')
            
            # Decrypt PKCS#12
            pkcs12_bytes = self.ca._decrypt_data(cert.pkcs12_encrypted) if cert.pkcs12_encrypted else None
            pkcs12_password = self.ca._decrypt_data(cert.pkcs12_password_encrypted).decode('utf-8') if cert.pkcs12_password_encrypted else None
            
            # Update download timestamp
            if cert.downloaded_at is None:
                cert.downloaded_at = datetime.now(timezone.utc)
                self.db.commit()
            
            return {
                "certificate": cert.certificate,
                "private_key": private_key_pem,
                "ca_certificate": ca.root_certificate,
                "pkcs12": pkcs12_bytes,
                "pkcs12_password": pkcs12_password,
                "fingerprint": cert.certificate_fingerprint,
                "serial_number": cert.serial_number,
                "valid_until": cert.valid_until.isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to get certificate chain: {e}", exc_info=True)
            raise CertificateManagerError(f"Failed to get certificate: {e}") from e

    def check_expiring_certificates(self, days_threshold: int = 30) -> list[UserCertificate]:
        """Find certificates expiring within threshold.
        
        Args:
            days_threshold: Number of days to look ahead
        
        Returns:
            List of expiring UserCertificate models
        """
        threshold_date = datetime.now(timezone.utc) + timedelta(days=days_threshold)
        
        expiring = self.db.query(UserCertificate).filter(
            UserCertificate.status == "active",
            UserCertificate.valid_until <= threshold_date,
            UserCertificate.valid_until > datetime.now(timezone.utc),
            UserCertificate.auto_renew == True
        ).all()
        
        logger.info(f"Found {len(expiring)} certificates expiring within {days_threshold} days")
        
        return expiring

    def _get_encryption_key(self) -> bytes:
        """Get encryption key for certificate private keys.
        
        Returns:
            32-byte encryption key
        
        Note:
            In production, this should come from a secure key management system
            like AWS KMS, Azure Key Vault, or HashiCorp Vault.
        """
        # For now, derive from settings SECRET_KEY
        # In production, use a dedicated encryption key from KMS
        secret_key = self.settings.secret_key.encode('utf-8')
        
        # Simple key derivation (in production, use proper KDF like PBKDF2 or Argon2)
        from hashlib import sha256
        return sha256(secret_key + b"cert-encryption").digest()
