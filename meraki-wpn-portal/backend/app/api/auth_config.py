"""Admin API for authentication configuration and CA management."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, DbSession
from app.core.certificate_manager import CertificateManager, CertificateManagerError
from app.db.models import CertificateAuthority, PortalSetting

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas

class AuthConfigResponse(BaseModel):
    """Authentication configuration response."""
    eap_tls_enabled: bool
    ipsk_enabled: bool
    allow_user_auth_choice: bool
    ca_provider: str
    cert_validity_days: int
    cert_auto_renewal_enabled: bool
    cert_renewal_threshold_days: int
    cert_key_size: int
    cert_signature_algorithm: str
    ca_initialized: bool
    ca_info: dict | None = None


class AuthConfigUpdate(BaseModel):
    """Authentication configuration update request."""
    eap_tls_enabled: bool | None = None
    ipsk_enabled: bool | None = None
    allow_user_auth_choice: bool | None = None
    ca_provider: Literal["internal", "letsencrypt", "external", "meraki"] | None = None
    cert_validity_days: int | None = Field(None, ge=30, le=3650)
    cert_auto_renewal_enabled: bool | None = None
    cert_renewal_threshold_days: int | None = Field(None, ge=1, le=90)
    cert_key_size: int | None = Field(None, ge=2048, le=4096)
    cert_signature_algorithm: Literal["sha256", "sha384", "sha512"] | None = None


class CAInitializeRequest(BaseModel):
    """CA initialization request."""
    common_name: str = Field(..., min_length=1, max_length=255)
    organization: str = Field(..., min_length=1, max_length=255)


class CAInitializeResponse(BaseModel):
    """CA initialization response."""
    ca_id: int
    common_name: str
    fingerprint: str
    valid_from: str
    valid_until: str
    message: str


class CARootCertificateResponse(BaseModel):
    """CA root certificate response."""
    certificate: str
    fingerprint: str
    format: Literal["pem"]


class CAStatsResponse(BaseModel):
    """CA statistics response."""
    certificates_issued: int
    certificates_revoked: int
    certificates_active: int
    certificates_expired: int
    certificates_expiring_soon: int


# Endpoints

@router.get("/auth-config", response_model=AuthConfigResponse)
async def get_auth_config(
    db: DbSession,
    admin: AdminUser
) -> AuthConfigResponse:
    """Get current authentication configuration.
    
    Returns the current settings for IPSK and EAP-TLS authentication,
    along with CA information if initialized.
    """
    logger.info(f"Admin {admin.get('sub', 'admin')} fetching auth config")
    
    # Get settings from database
    def get_setting(key: str, default: str) -> str:
        setting = db.query(PortalSetting).filter_by(key=key).first()
        return setting.value if setting else default
    
    eap_tls_enabled = get_setting("eap_tls_enabled", "false") == "true"
    ipsk_enabled = get_setting("ipsk_enabled", "true") == "true"
    allow_user_auth_choice = get_setting("allow_user_auth_choice", "true") == "true"
    ca_provider = get_setting("ca_provider", "internal")
    cert_validity_days = int(get_setting("cert_validity_days", "365"))
    cert_auto_renewal_enabled = get_setting("cert_auto_renewal_enabled", "true") == "true"
    cert_renewal_threshold_days = int(get_setting("cert_renewal_threshold_days", "30"))
    cert_key_size = int(get_setting("cert_key_size", "2048"))
    cert_signature_algorithm = get_setting("cert_signature_algorithm", "sha256")
    
    # Check if CA is initialized
    ca = db.query(CertificateAuthority).filter_by(
        is_primary=True,
        is_active=True
    ).first()
    
    ca_info = None
    if ca:
        ca_info = {
            "id": ca.id,
            "name": ca.name,
            "fingerprint": ca.root_certificate_fingerprint,
            "valid_from": ca.valid_from.isoformat(),
            "valid_until": ca.valid_until.isoformat(),
            "certificates_issued": ca.certificates_issued,
            "certificates_revoked": ca.certificates_revoked,
        }
    
    return AuthConfigResponse(
        eap_tls_enabled=eap_tls_enabled,
        ipsk_enabled=ipsk_enabled,
        allow_user_auth_choice=allow_user_auth_choice,
        ca_provider=ca_provider,
        cert_validity_days=cert_validity_days,
        cert_auto_renewal_enabled=cert_auto_renewal_enabled,
        cert_renewal_threshold_days=cert_renewal_threshold_days,
        cert_key_size=cert_key_size,
        cert_signature_algorithm=cert_signature_algorithm,
        ca_initialized=ca is not None,
        ca_info=ca_info
    )


@router.patch("/auth-config")
async def update_auth_config(
    update: AuthConfigUpdate,
    db: DbSession,
    admin: AdminUser
) -> dict:
    """Update authentication configuration.
    
    Allows admins to enable/disable IPSK and EAP-TLS authentication,
    and configure certificate settings.
    """
    logger.info(f"Admin {admin.get('sub', 'admin')} updating auth config: {update.model_dump(exclude_none=True)}")
    
    try:
        # Update settings
        updates = update.model_dump(exclude_none=True)
        
        for key, value in updates.items():
            # Convert boolean to string
            if isinstance(value, bool):
                value_str = "true" if value else "false"
            else:
                value_str = str(value)
            
            # Check if setting exists
            setting = db.query(PortalSetting).filter_by(key=key).first()
            
            if setting:
                setting.value = value_str
                setting.updated_by = admin.get("sub", "admin")
            else:
                # Create new setting
                new_setting = PortalSetting(
                    key=key,
                    value=value_str,
                    value_type="bool" if isinstance(value, bool) else "string",
                    updated_by=admin.get("sub", "admin")
                )
                db.add(new_setting)
        
        db.commit()
        
        logger.info(f"✅ Auth config updated by {admin.get('sub', 'admin')}")
        
        return {
            "success": True,
            "message": "Authentication configuration updated successfully",
            "updated_fields": list(updates.keys())
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update auth config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {e}")


@router.post("/ca/initialize", response_model=CAInitializeResponse)
async def initialize_ca(
    request: CAInitializeRequest,
    db: DbSession,
    admin: AdminUser
) -> CAInitializeResponse:
    """Initialize a new internal Certificate Authority.
    
    This creates a self-signed root CA for issuing user certificates.
    Can only be done once unless the existing CA is revoked.
    """
    logger.info(f"Admin {admin.get('sub', 'admin')} initializing CA: {request.common_name}")
    
    try:
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Initialize CA
        ca = cert_manager.initialize_internal_ca(
            common_name=request.common_name,
            organization=request.organization,
            created_by=admin.get("sub", "admin")
        )
        
        logger.info(f"✅ CA initialized by {admin.get('sub', 'admin')}: {ca.id}")
        
        return CAInitializeResponse(
            ca_id=ca.id,
            common_name=ca.name,
            fingerprint=ca.root_certificate_fingerprint,
            valid_from=ca.valid_from.isoformat(),
            valid_until=ca.valid_until.isoformat(),
            message="Certificate Authority initialized successfully"
        )
        
    except CertificateManagerError as e:
        logger.error(f"Failed to initialize CA: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error initializing CA: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize CA: {e}")


@router.get("/ca/root-certificate")
async def get_root_certificate(
    db: DbSession,
    admin: AdminUser
) -> Response:
    """Download the root CA certificate.
    
    Returns the root certificate in PEM format for uploading to
    Meraki Dashboard and client devices.
    """
    logger.info(f"Admin {admin.get('sub', 'admin')} downloading root CA certificate")
    
    try:
        # Get primary CA
        ca = db.query(CertificateAuthority).filter_by(
            is_primary=True,
            is_active=True
        ).first()
        
        if not ca:
            raise HTTPException(status_code=404, detail="No active CA found")
        
        # Return certificate as PEM file
        return Response(
            content=ca.root_certificate,
            media_type="application/x-pem-file",
            headers={
                "Content-Disposition": f'attachment; filename="root-ca-{ca.name.replace(" ", "-")}.pem"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get root certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get root certificate: {e}")


@router.get("/ca/stats", response_model=CAStatsResponse)
async def get_ca_stats(
    db: DbSession,
    admin: AdminUser
) -> CAStatsResponse:
    """Get Certificate Authority statistics.
    
    Returns counts of issued, revoked, active, and expiring certificates.
    """
    logger.info(f"Admin {admin.get('sub', 'admin')} fetching CA stats")
    
    try:
        # Get primary CA
        ca = db.query(CertificateAuthority).filter_by(
            is_primary=True,
            is_active=True
        ).first()
        
        if not ca:
            raise HTTPException(status_code=404, detail="No active CA found")
        
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Get expiring certificates (within 30 days)
        expiring_certs = cert_manager.check_expiring_certificates(days_threshold=30)
        
        # Count certificates by status
        from app.db.models import UserCertificate
        active_count = db.query(UserCertificate).filter_by(
            ca_id=ca.id,
            status="active"
        ).count()
        
        expired_count = db.query(UserCertificate).filter_by(
            ca_id=ca.id,
            status="expired"
        ).count()
        
        return CAStatsResponse(
            certificates_issued=ca.certificates_issued,
            certificates_revoked=ca.certificates_revoked,
            certificates_active=active_count,
            certificates_expired=expired_count,
            certificates_expiring_soon=len(expiring_certs)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get CA stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get CA stats: {e}")


@router.post("/ca/regenerate")
async def regenerate_ca(
    request: CAInitializeRequest,
    db: DbSession,
    admin: AdminUser
) -> dict:
    """Regenerate Certificate Authority (DANGER!).
    
    This revokes the existing CA and creates a new one.
    All existing user certificates will be invalidated.
    """
    logger.warning(f"Admin {admin.get('sub', 'admin')} regenerating CA: {request.common_name}")
    
    try:
        # Get existing CA
        existing_ca = db.query(CertificateAuthority).filter_by(
            is_primary=True,
            is_active=True
        ).first()
        
        if existing_ca:
            # Deactivate existing CA
            existing_ca.is_active = False
            existing_ca.is_primary = False
            logger.info(f"Deactivated existing CA: {existing_ca.id}")
        
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Initialize new CA
        new_ca = cert_manager.initialize_internal_ca(
            common_name=request.common_name,
            organization=request.organization,
            created_by=admin.get("sub", "admin")
        )
        
        logger.info(f"✅ CA regenerated by {admin.get('sub', 'admin')}: Old={existing_ca.id if existing_ca else None}, New={new_ca.id}")
        
        return {
            "success": True,
            "message": "Certificate Authority regenerated successfully",
            "warning": "All existing certificates are now invalid and must be reissued",
            "old_ca_id": existing_ca.id if existing_ca else None,
            "new_ca_id": new_ca.id
        }
        
    except CertificateManagerError as e:
        db.rollback()
        logger.error(f"Failed to regenerate CA: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error regenerating CA: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to regenerate CA: {e}")
