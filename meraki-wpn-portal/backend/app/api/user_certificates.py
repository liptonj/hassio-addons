"""User certificate management API endpoints."""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.core.certificate_manager import CertificateManager, CertificateManagerError
from app.db.models import UserCertificate, AuthMethodPreference, CertificateAuthority

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas

class CertificateResponse(BaseModel):
    """User certificate information response."""
    id: int
    subject_common_name: str
    subject_email: str
    serial_number: str
    fingerprint: str
    valid_from: str
    valid_until: str
    status: str
    auto_renew: bool
    days_until_expiry: int | None
    last_authenticated_at: str | None
    authentication_count: int
    issued_at: str
    downloaded_at: str | None


class CertificateListResponse(BaseModel):
    """List of user certificates."""
    certificates: list[CertificateResponse]
    total: int
    active_count: int
    expiring_count: int


class CertificateRequestRequest(BaseModel):
    """Request for new certificate."""
    device_registration_id: int | None = None
    validity_days: int | None = Field(None, ge=30, le=3650)


class CertificateRequestResponse(BaseModel):
    """New certificate response."""
    certificate_id: int
    serial_number: str
    fingerprint: str
    valid_until: str
    download_urls: dict
    message: str


class AvailableAuthMethodsResponse(BaseModel):
    """Available authentication methods."""
    ipsk_enabled: bool
    eap_tls_enabled: bool
    allow_user_choice: bool
    has_ipsk: bool
    has_certificate: bool
    recommended_method: str | None


class AuthMethodPreferenceRequest(BaseModel):
    """Set authentication method preference."""
    auth_method: Literal["ipsk", "eap-tls"]
    device_registration_id: int | None = None
    reason: str | None = None


# Endpoints

@router.get("/certificates", response_model=CertificateListResponse)
async def list_user_certificates(
    user: CurrentUser,
    db: DbSession
) -> CertificateListResponse:
    """List all certificates for the current user.
    
    Returns both active and expired certificates with status information.
    """
    logger.info(f"User {user.id} ({user.email}) listing certificates")
    
    try:
        # Get all certificates for user
        certificates = db.query(UserCertificate).filter_by(
            user_id=user.id
        ).order_by(UserCertificate.issued_at.desc()).all()
        
        # Count active and expiring
        active_count = sum(1 for cert in certificates if cert.status == "active")
        expiring_count = sum(1 for cert in certificates if cert.is_expiring_soon)
        
        # Build response
        cert_responses = []
        for cert in certificates:
            # Calculate days until expiry
            days_until_expiry = None
            if cert.status == "active":
                days_until_expiry = (cert.valid_until - datetime.now(timezone.utc)).days
            
            cert_responses.append(CertificateResponse(
                id=cert.id,
                subject_common_name=cert.subject_common_name,
                subject_email=cert.subject_email,
                serial_number=cert.serial_number,
                fingerprint=cert.certificate_fingerprint[:32] + "...",  # Truncate for display
                valid_from=cert.valid_from.isoformat(),
                valid_until=cert.valid_until.isoformat(),
                status=cert.status,
                auto_renew=cert.auto_renew,
                days_until_expiry=days_until_expiry,
                last_authenticated_at=cert.last_authenticated_at.isoformat() if cert.last_authenticated_at else None,
                authentication_count=cert.authentication_count,
                issued_at=cert.issued_at.isoformat(),
                downloaded_at=cert.downloaded_at.isoformat() if cert.downloaded_at else None
            ))
        
        return CertificateListResponse(
            certificates=cert_responses,
            total=len(certificates),
            active_count=active_count,
            expiring_count=expiring_count
        )
        
    except Exception as e:
        logger.error(f"Failed to list certificates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list certificates: {e}")


@router.post("/certificates/request", response_model=CertificateRequestResponse)
async def request_certificate(
    request: CertificateRequestRequest,
    user: CurrentUser,
    db: DbSession
) -> CertificateRequestResponse:
    """Request a new certificate for the current user.
    
    Issues a new certificate and returns download information.
    """
    logger.info(f"User {user.id} ({user.email}) requesting certificate")
    
    try:
        # Check if EAP-TLS is enabled
        from app.db.models import PortalSetting
        eap_enabled = db.query(PortalSetting).filter_by(key="eap_tls_enabled").first()
        if not eap_enabled or eap_enabled.value != "true":
            raise HTTPException(status_code=403, detail="EAP-TLS authentication is not enabled")
        
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Issue certificate
        cert = cert_manager.issue_user_certificate(
            user_id=user.id,
            device_registration_id=request.device_registration_id,
            validity_days=request.validity_days
        )
        
        # Build download URLs
        download_urls = {
            "pem": f"/api/user/certificates/{cert.id}/download?format=pem",
            "pkcs12": f"/api/user/certificates/{cert.id}/download?format=pkcs12",
            "ca_certificate": f"/api/user/certificates/{cert.id}/ca-certificate"
        }
        
        logger.info(f"✅ Certificate issued: ID={cert.id}, Serial={cert.serial_number}")
        
        return CertificateRequestResponse(
            certificate_id=cert.id,
            serial_number=cert.serial_number,
            fingerprint=cert.certificate_fingerprint,
            valid_until=cert.valid_until.isoformat(),
            download_urls=download_urls,
            message="Certificate issued successfully"
        )
        
    except CertificateManagerError as e:
        logger.error(f"Failed to issue certificate: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error issuing certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to issue certificate: {e}")


@router.get("/certificates/{certificate_id}/download")
async def download_certificate(
    certificate_id: int,
    user: CurrentUser,
    db: DbSession,
    format: Literal["pem", "pkcs12"] = "pem",
) -> Response:
    """Download certificate in specified format.
    
    Supports PEM (for Android/Linux) and PKCS#12 (for iOS/macOS).
    """
    logger.info(f"User {user.id} downloading certificate {certificate_id} in {format} format")
    
    try:
        # Get certificate
        cert = db.query(UserCertificate).filter_by(
            id=certificate_id,
            user_id=user.id
        ).first()
        
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Get certificate with chain
        cert_data = cert_manager.get_certificate_with_chain(certificate_id)
        
        if format == "pem":
            # Return certificate bundle (cert + key + CA) in PEM format
            pem_bundle = (
                "# User Certificate\n" +
                cert_data["certificate"] + "\n" +
                "# Private Key\n" +
                cert_data["private_key"] + "\n" +
                "# CA Certificate\n" +
                cert_data["ca_certificate"]
            )
            
            return Response(
                content=pem_bundle,
                media_type="application/x-pem-file",
                headers={
                    "Content-Disposition": f'attachment; filename="wifi-certificate-{user.email}.pem"'
                }
            )
        
        elif format == "pkcs12":
            # Return PKCS#12 bundle for iOS/macOS
            if not cert_data["pkcs12"]:
                raise HTTPException(status_code=500, detail="PKCS#12 bundle not available")
            
            # Include password in response header (user needs it to install)
            return Response(
                content=cert_data["pkcs12"],
                media_type="application/x-pkcs12",
                headers={
                    "Content-Disposition": f'attachment; filename="wifi-certificate-{user.email}.p12"',
                    "X-Certificate-Password": cert_data["pkcs12_password"]  # iOS needs this
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to download certificate: {e}")


@router.get("/certificates/{certificate_id}/ca-certificate")
async def download_ca_certificate(
    certificate_id: int,
    user: CurrentUser,
    db: DbSession
) -> Response:
    """Download the CA certificate for a user certificate.
    
    Users need this to trust the certificate chain.
    """
    logger.info(f"User {user.id} downloading CA certificate for cert {certificate_id}")
    
    try:
        # Get certificate
        cert = db.query(UserCertificate).filter_by(
            id=certificate_id,
            user_id=user.id
        ).first()
        
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        # Get CA
        ca = db.query(CertificateAuthority).filter_by(id=cert.ca_id).first()
        if not ca:
            raise HTTPException(status_code=404, detail="CA not found")
        
        return Response(
            content=ca.root_certificate,
            media_type="application/x-pem-file",
            headers={
                "Content-Disposition": f'attachment; filename="ca-certificate.pem"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download CA certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to download CA certificate: {e}")


@router.delete("/certificates/{certificate_id}")
async def revoke_certificate(
    certificate_id: int,
    user: CurrentUser,
    db: DbSession
) -> dict:
    """Revoke a certificate.
    
    Once revoked, the certificate cannot be used for authentication.
    """
    logger.info(f"User {user.id} revoking certificate {certificate_id}")
    
    try:
        # Get certificate
        cert = db.query(UserCertificate).filter_by(
            id=certificate_id,
            user_id=user.id
        ).first()
        
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        if cert.status == "revoked":
            raise HTTPException(status_code=400, detail="Certificate is already revoked")
        
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Revoke certificate
        revocation = cert_manager.revoke_certificate(
            certificate_id=certificate_id,
            reason="cessationOfOperation",
            revoked_by=user.email,
            notes="User-initiated revocation"
        )
        
        logger.info(f"✅ Certificate revoked: ID={certificate_id}, Serial={cert.serial_number}")
        
        return {
            "success": True,
            "message": "Certificate revoked successfully",
            "certificate_id": certificate_id,
            "revoked_at": revocation.revoked_at.isoformat()
        }
        
    except CertificateManagerError as e:
        logger.error(f"Failed to revoke certificate: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error revoking certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to revoke certificate: {e}")


@router.post("/certificates/{certificate_id}/renew", response_model=CertificateRequestResponse)
async def renew_certificate(
    certificate_id: int,
    user: CurrentUser,
    db: DbSession
) -> CertificateRequestResponse:
    """Manually renew a certificate.
    
    Creates a new certificate to replace the expiring one.
    """
    logger.info(f"User {user.id} renewing certificate {certificate_id}")
    
    try:
        # Get certificate
        cert = db.query(UserCertificate).filter_by(
            id=certificate_id,
            user_id=user.id
        ).first()
        
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        if cert.status not in ["active", "expired"]:
            raise HTTPException(status_code=400, detail="Certificate cannot be renewed")
        
        # Initialize certificate manager
        cert_manager = CertificateManager(db)
        
        # Renew certificate
        new_cert = cert_manager.renew_certificate(
            certificate_id=certificate_id,
            validity_days=None  # Use CA default
        )
        
        # Build download URLs
        download_urls = {
            "pem": f"/api/user/certificates/{new_cert.id}/download?format=pem",
            "pkcs12": f"/api/user/certificates/{new_cert.id}/download?format=pkcs12",
            "ca_certificate": f"/api/user/certificates/{new_cert.id}/ca-certificate"
        }
        
        logger.info(f"✅ Certificate renewed: Old={certificate_id}, New={new_cert.id}")
        
        return CertificateRequestResponse(
            certificate_id=new_cert.id,
            serial_number=new_cert.serial_number,
            fingerprint=new_cert.certificate_fingerprint,
            valid_until=new_cert.valid_until.isoformat(),
            download_urls=download_urls,
            message="Certificate renewed successfully"
        )
        
    except CertificateManagerError as e:
        logger.error(f"Failed to renew certificate: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error renewing certificate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to renew certificate: {e}")


@router.get("/auth-methods", response_model=AvailableAuthMethodsResponse)
async def get_available_auth_methods(
    user: CurrentUser,
    db: DbSession
) -> AvailableAuthMethodsResponse:
    """Get available authentication methods for the current user.
    
    Returns which methods are enabled and which the user has configured.
    """
    logger.info(f"User {user.id} checking available auth methods")
    
    try:
        # Get settings
        from app.db.models import PortalSetting
        
        def get_setting(key: str, default: str) -> bool:
            setting = db.query(PortalSetting).filter_by(key=key).first()
            return (setting.value if setting else default) == "true"
        
        ipsk_enabled = get_setting("ipsk_enabled", "true")
        eap_tls_enabled = get_setting("eap_tls_enabled", "false")
        allow_user_choice = get_setting("allow_user_auth_choice", "true")
        
        # Check what user has
        has_ipsk = user.ipsk_id is not None
        has_certificate = db.query(UserCertificate).filter_by(
            user_id=user.id,
            status="active"
        ).count() > 0
        
        # Recommend method
        recommended = None
        if eap_tls_enabled and not has_certificate:
            recommended = "eap-tls"
        elif ipsk_enabled and not has_ipsk:
            recommended = "ipsk"
        elif has_certificate:
            recommended = "eap-tls"
        elif has_ipsk:
            recommended = "ipsk"
        
        return AvailableAuthMethodsResponse(
            ipsk_enabled=ipsk_enabled,
            eap_tls_enabled=eap_tls_enabled,
            allow_user_choice=allow_user_choice,
            has_ipsk=has_ipsk,
            has_certificate=has_certificate,
            recommended_method=recommended
        )
        
    except Exception as e:
        logger.error(f"Failed to get auth methods: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get auth methods: {e}")


@router.post("/auth-method/preference")
async def set_auth_method_preference(
    request: AuthMethodPreferenceRequest,
    user: CurrentUser,
    db: DbSession
) -> dict:
    """Set authentication method preference.
    
    Records the user's preferred authentication method for a device.
    """
    logger.info(f"User {user.id} setting auth preference: {request.auth_method}")
    
    try:
        # Check if preference already exists
        existing = db.query(AuthMethodPreference).filter_by(
            user_id=user.id,
            device_registration_id=request.device_registration_id
        ).first()
        
        if existing:
            # Update existing
            existing.auth_method = request.auth_method
            existing.preference_reason = request.reason
            existing.updated_at = datetime.now(timezone.utc)
        else:
            # Create new
            preference = AuthMethodPreference(
                user_id=user.id,
                device_registration_id=request.device_registration_id,
                auth_method=request.auth_method,
                preference_reason=request.reason
            )
            db.add(preference)
        
        # Update user's preferred method
        user.preferred_auth_method = request.auth_method
        
        db.commit()
        
        logger.info(f"✅ Auth preference set: User={user.id}, Method={request.auth_method}")
        
        return {
            "success": True,
            "message": "Authentication method preference saved",
            "auth_method": request.auth_method
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to set auth preference: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to set preference: {e}")
