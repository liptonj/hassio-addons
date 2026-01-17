"""RadSec (RADIUS over TLS) Configuration API endpoints."""

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import RadiusRadSecConfig, RadiusRadSecClient, RadiusClient
from radius_app.schemas.radsec import (
    RadSecConfigCreate,
    RadSecConfigUpdate,
    RadSecConfigResponse,
    RadSecConfigListResponse,
    RadSecClientCreate,
    RadSecClientUpdate,
    RadSecClientResponse,
    RadSecClientListResponse,
    CertificateGenerateRequest,
    CertificateGenerateResponse,
    CertificateInfo,
)
from radius_app.utils.certificates import CertificateManager, CertificateError

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy certificate manager initialization (avoids errors in test environments)
_cert_manager: Optional[CertificateManager] = None

def get_cert_manager() -> CertificateManager:
    """Get certificate manager instance (lazy initialization).
    
    Returns:
        CertificateManager instance
    """
    global _cert_manager
    if _cert_manager is None:
        try:
            _cert_manager = CertificateManager()
        except (OSError, PermissionError) as e:
            # In test environments, create with temp directory
            import tempfile
            temp_cert_dir = Path(tempfile.mkdtemp()) / "certs"
            _cert_manager = CertificateManager(cert_dir=temp_cert_dir)
    return _cert_manager


@router.get("/api/radsec/configs", response_model=RadSecConfigListResponse)
async def list_radsec_configs(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> RadSecConfigListResponse:
    """
    List all RadSec configurations.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        page: Page number
        page_size: Items per page
        is_active: Filter by active status
        
    Returns:
        Paginated list of RadSec configurations
    """
    logger.info(f"Listing RadSec configs requested by {admin['sub']}")
    
    # Build query
    query = select(RadiusRadSecConfig)
    
    if is_active is not None:
        query = query.where(RadiusRadSecConfig.is_active == is_active)
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(RadiusRadSecConfig.created_at.desc())
    
    configs = db.execute(query).scalars().all()
    
    # Calculate pages
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Build responses with certificate info
    responses = []
    for config in configs:
        response_data = RadSecConfigResponse.model_validate(config).model_dump()
        
        # Add certificate information if files exist
        try:
            cert_path = Path(config.certificate_file)
            if cert_path.exists():
                cert_info = get_cert_manager().parse_certificate(cert_path)
                response_data["server_cert_info"] = CertificateInfo(**cert_info)
        except Exception as e:
            logger.warning(f"Failed to parse server certificate: {e}")
        
        responses.append(RadSecConfigResponse(**response_data))
    
    return RadSecConfigListResponse(
        items=responses,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/api/radsec/configs/{config_id}", response_model=RadSecConfigResponse)
async def get_radsec_config(
    config_id: int,
    admin: AdminUser,
    db: DbSession,
) -> RadSecConfigResponse:
    """
    Get RadSec configuration by ID.
    
    Args:
        config_id: Configuration ID
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        RadSec configuration details
        
    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Getting RadSec config {config_id} by {admin['sub']}")
    
    config = db.execute(
        select(RadiusRadSecConfig).where(RadiusRadSecConfig.id == config_id)
    ).scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RadSec configuration with ID {config_id} not found",
        )
    
    response_data = RadSecConfigResponse.model_validate(config).model_dump()
    
    # Add certificate information
    try:
        cert_path = Path(config.certificate_file)
        if cert_path.exists():
            cert_info = get_cert_manager().parse_certificate(cert_path)
            response_data["server_cert_info"] = CertificateInfo(**cert_info)
    except Exception as e:
        logger.warning(f"Failed to parse server certificate: {e}")
    
    return RadSecConfigResponse(**response_data)


@router.post("/api/radsec/configs", response_model=RadSecConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_radsec_config(
    config_data: RadSecConfigCreate,
    admin: AdminUser,
    db: DbSession,
) -> RadSecConfigResponse:
    """
    Create new RadSec configuration.
    
    Args:
        config_data: RadSec configuration data
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Created configuration
        
    Raises:
        HTTPException: 409 if name already exists
    """
    logger.info(f"Creating RadSec config '{config_data.name}' by {admin['sub']}")
    
    # Check for duplicate name
    existing = db.execute(
        select(RadiusRadSecConfig).where(RadiusRadSecConfig.name == config_data.name)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"RadSec configuration with name '{config_data.name}' already exists",
        )
    
    try:
        config = RadiusRadSecConfig(
            **config_data.model_dump(exclude={"created_by"}),
            created_by=admin["sub"],
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        logger.info(f"✅ RadSec config '{config.name}' created (ID: {config.id})")
        
        return RadSecConfigResponse.model_validate(config)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RadSec configuration creation failed",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating RadSec config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create RadSec configuration",
        )


@router.put("/api/radsec/configs/{config_id}", response_model=RadSecConfigResponse)
async def update_radsec_config(
    config_id: int,
    config_data: RadSecConfigUpdate,
    admin: AdminUser,
    db: DbSession,
) -> RadSecConfigResponse:
    """
    Update RadSec configuration.
    
    Args:
        config_id: Configuration ID
        config_data: Updated configuration data
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Updated configuration
        
    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Updating RadSec config {config_id} by {admin['sub']}")
    
    config = db.execute(
        select(RadiusRadSecConfig).where(RadiusRadSecConfig.id == config_id)
    ).scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RadSec configuration with ID {config_id} not found",
        )
    
    try:
        update_data = config_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(config, field, value)
        
        db.commit()
        db.refresh(config)
        
        logger.info(f"✅ RadSec config {config_id} updated")
        
        return RadSecConfigResponse.model_validate(config)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RadSec configuration update failed",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating RadSec config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update RadSec configuration",
        )


@router.delete("/api/radsec/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_radsec_config(
    config_id: int,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """
    Delete RadSec configuration.
    
    Args:
        config_id: Configuration ID
        admin: Authenticated admin user
        db: Database session
        
    Raises:
        HTTPException: 404 if not found
    """
    logger.info(f"Deleting RadSec config {config_id} by {admin['sub']}")
    
    config = db.execute(
        select(RadiusRadSecConfig).where(RadiusRadSecConfig.id == config_id)
    ).scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RadSec configuration with ID {config_id} not found",
        )
    
    try:
        db.delete(config)
        db.commit()
        
        logger.info(f"✅ RadSec config {config_id} deleted")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting RadSec config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete RadSec configuration",
        )


@router.get("/api/radsec/clients", response_model=RadSecClientListResponse)
async def list_radsec_clients(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
) -> RadSecClientListResponse:
    """List all RadSec clients."""
    logger.info(f"Listing RadSec clients requested by {admin['sub']}")
    
    query = select(RadiusRadSecClient)
    
    if is_active is not None:
        query = query.where(RadiusRadSecClient.is_active == is_active)
    
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(RadiusRadSecClient.created_at.desc())
    
    clients = db.execute(query).scalars().all()
    
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return RadSecClientListResponse(
        items=[RadSecClientResponse.model_validate(client) for client in clients],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/api/radsec/clients", response_model=RadSecClientResponse, status_code=status.HTTP_201_CREATED)
async def create_radsec_client(
    client_data: RadSecClientCreate,
    admin: AdminUser,
    db: DbSession,
) -> RadSecClientResponse:
    """Create new RadSec client."""
    logger.info(f"Creating RadSec client '{client_data.name}' by {admin['sub']}")
    
    existing = db.execute(
        select(RadiusRadSecClient).where(RadiusRadSecClient.name == client_data.name)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"RadSec client with name '{client_data.name}' already exists",
        )
    
    try:
        client = RadiusRadSecClient(
            **client_data.model_dump(exclude={"created_by"}),
            created_by=admin["sub"],
        )
        
        db.add(client)
        db.commit()
        db.refresh(client)
        
        logger.info(f"✅ RadSec client '{client.name}' created (ID: {client.id})")
        
        return RadSecClientResponse.model_validate(client)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating RadSec client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create RadSec client",
        )


@router.put("/api/radsec/clients/{client_id}", response_model=RadSecClientResponse)
async def update_radsec_client(
    client_id: int,
    client_data: RadSecClientUpdate,
    admin: AdminUser,
    db: DbSession,
) -> RadSecClientResponse:
    """Update RadSec client."""
    logger.info(f"Updating RadSec client {client_id} by {admin['sub']}")
    
    client = db.execute(
        select(RadiusRadSecClient).where(RadiusRadSecClient.id == client_id)
    ).scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RadSec client with ID {client_id} not found",
        )
    
    try:
        update_data = client_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(client, field, value)
        
        db.commit()
        db.refresh(client)
        
        logger.info(f"✅ RadSec client {client_id} updated")
        
        return RadSecClientResponse.model_validate(client)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating RadSec client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update RadSec client",
        )


@router.delete("/api/radsec/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_radsec_client(
    client_id: int,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """Delete RadSec client."""
    logger.info(f"Deleting RadSec client {client_id} by {admin['sub']}")
    
    client = db.execute(
        select(RadiusRadSecClient).where(RadiusRadSecClient.id == client_id)
    ).scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RadSec client with ID {client_id} not found",
        )
    
    try:
        db.delete(client)
        db.commit()
        
        logger.info(f"✅ RadSec client {client_id} deleted")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting RadSec client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete RadSec client",
        )


@router.get("/api/radsec/certificates")
async def list_certificates(
    admin: AdminUser,
) -> dict:
    """
    List all certificates with expiry information.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        List of certificates with metadata
    """
    logger.info(f"Listing certificates requested by {admin['sub']}")
    
    try:
        certificates = get_cert_manager().list_certificates()
        
        return {
            "certificates": certificates,
            "count": len(certificates),
        }
        
    except Exception as e:
        logger.error(f"Error listing certificates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list certificates",
        )


@router.post("/api/radsec/certificates/generate", response_model=CertificateGenerateResponse)
async def generate_certificates(
    request: CertificateGenerateRequest,
    admin: AdminUser,
) -> CertificateGenerateResponse:
    """
    Generate new server certificates.
    
    Args:
        request: Certificate generation request
        admin: Authenticated admin user
        
    Returns:
        Generation result with paths
        
    Raises:
        HTTPException: If generation fails
    """
    logger.info(f"Generating certificates for '{request.common_name}' by {admin['sub']}")
    
    try:
        # Generate CA if it doesn't exist
        cert_mgr = get_cert_manager()
        ca_path = cert_mgr.cert_dir / "ca.pem"
        if not ca_path.exists():
            logger.info("CA certificate not found, generating...")
            cert_mgr.generate_ca_certificate(
                common_name=f"{request.organization} CA",
                organization=request.organization,
                country=request.country,
                key_size=request.key_size,
            )
        
        # Generate server certificate
        cert_path, key_path = cert_mgr.generate_server_certificate(
            common_name=request.common_name,
            organization=request.organization,
            country=request.country,
            validity_days=request.validity_days,
            key_size=request.key_size,
        )
        
        # Parse certificate info
        cert_info = get_cert_manager().parse_certificate(cert_path)
        
        return CertificateGenerateResponse(
            success=True,
            message=f"Certificate generated successfully for {request.common_name}",
            certificate_path=str(cert_path),
            key_path=str(key_path),
            certificate_info=CertificateInfo(**cert_info),
        )
        
    except CertificateError as e:
        logger.error(f"Certificate generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error generating certificates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate certificates",
        )


@router.get("/api/radsec/certificates/verify")
async def verify_certificate(
    admin: AdminUser,
    certificate_path: str = Query(..., description="Path to certificate to verify"),
    ca_path: Optional[str] = Query(None, description="Path to CA certificate"),
) -> dict:
    """
    Verify certificate validity and chain.
    
    Args:
        admin: Authenticated admin user
        certificate_path: Path to certificate to verify
        ca_path: Optional CA certificate path
        
    Returns:
        Verification result
    """
    logger.info(f"Verifying certificate {certificate_path} by {admin['sub']}")
    
    try:
        cert_path = Path(certificate_path)
        if not cert_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Certificate not found: {certificate_path}",
            )
        # Parse certificate
        cert_mgr = get_cert_manager()
        cert_info = cert_mgr.parse_certificate(cert_path)
        
        # Verify chain if CA provided
        chain_valid = None
        chain_error = None
        
        if ca_path:
            ca_cert_path = Path(ca_path)
            if ca_cert_path.exists():
                chain_valid, chain_error = cert_mgr.verify_certificate_chain(
                    cert_path, ca_cert_path
                )
        
        return {
            "certificate_info": cert_info,
            "chain_valid": chain_valid,
            "chain_error": chain_error,
        }
        
    except CertificateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error verifying certificate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify certificate",
        )


@router.get("/api/radsec/certificates/status")
async def get_certificate_status(
    admin: AdminUser,
) -> dict:
    """
    Get overall certificate status for EAP and RadSec.
    
    Returns status of:
    - EAP certificates (self-signed CA)
    - RadSec certificates (self-signed or Let's Encrypt)
    - Let's Encrypt availability
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Dictionary with certificate status for all types
    """
    logger.info(f"Getting certificate status requested by {admin['sub']}")
    
    try:
        cert_mgr = get_cert_manager()
        return cert_mgr.get_certificate_status()
        
    except Exception as e:
        logger.error(f"Error getting certificate status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get certificate status",
        )


@router.get("/api/radsec/certificates/letsencrypt/status")
async def get_letsencrypt_status(
    admin: AdminUser,
    domain: Optional[str] = Query(None, description="Specific domain to check"),
) -> dict:
    """
    Check Let's Encrypt certificate availability and status.
    
    Let's Encrypt certificates are recommended for RadSec but NOT for EAP.
    
    For RadSec: Let's Encrypt works with standard TLS trust chain.
    For EAP: Use self-signed CA (clients must install CA certificate).
    
    Args:
        admin: Authenticated admin user
        domain: Optional specific domain to check
        
    Returns:
        Let's Encrypt certificate status
    """
    logger.info(f"Checking Let's Encrypt status requested by {admin['sub']}")
    
    try:
        cert_mgr = get_cert_manager()
        return cert_mgr.letsencrypt.check_letsencrypt_status(domain)
        
    except Exception as e:
        logger.error(f"Error checking Let's Encrypt status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check Let's Encrypt status",
        )


@router.post("/api/radsec/certificates/letsencrypt/setup")
async def setup_letsencrypt_radsec(
    admin: AdminUser,
    domain: Optional[str] = Query(None, description="Specific domain to use"),
    copy: bool = Query(True, description="Copy files (True) or create symlinks (False)"),
) -> dict:
    """
    Setup RadSec using Let's Encrypt certificates.
    
    This imports Let's Encrypt certificates from /ssl or /etc/letsencrypt
    for use with RadSec. The certificates are validated and copied/linked
    to the RadSec certificate directory.
    
    Note: Let's Encrypt is NOT recommended for EAP. Use this only for RadSec.
    
    Prerequisites:
    - Let's Encrypt certificates must exist in /ssl or /etc/letsencrypt/live
    - For Home Assistant: Ensure ssl directory is mapped in addon config
    
    Args:
        admin: Authenticated admin user
        domain: Optional specific domain to use
        copy: If True, copy files. If False, create symlinks.
        
    Returns:
        Dictionary with certificate paths and status
        
    Raises:
        HTTPException: 404 if Let's Encrypt certs not found
        HTTPException: 400 if setup fails
    """
    logger.info(f"Setting up Let's Encrypt for RadSec requested by {admin['sub']}")
    
    try:
        cert_mgr = get_cert_manager()
        result = cert_mgr.setup_radsec_letsencrypt(domain=domain, copy=copy)
        
        return {
            "success": True,
            "message": "Let's Encrypt certificates configured for RadSec",
            **result,
        }
        
    except CertificateError as e:
        logger.error(f"Let's Encrypt setup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error setting up Let's Encrypt: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup Let's Encrypt certificates",
        )


@router.post("/api/radsec/certificates/eap/generate")
async def generate_eap_certificates(
    admin: AdminUser,
    common_name: str = Query(..., description="Server hostname/FQDN"),
    organization: str = Query("FreeRADIUS", description="Organization name"),
    country: str = Query("US", description="2-letter country code"),
    key_size: int = Query(4096, ge=2048, le=8192, description="RSA key size"),
) -> dict:
    """
    Generate EAP certificates (self-signed CA + server certificate).
    
    For EAP-TLS, PEAP, and TTLS authentication. Uses a self-signed CA
    that clients must install and trust.
    
    This is the RECOMMENDED approach for EAP. Let's Encrypt is NOT
    suitable for EAP because:
    1. Clients must install the CA certificate
    2. LE certs expire every 90 days, requiring client reconfiguration
    
    Args:
        admin: Authenticated admin user
        common_name: Server hostname/FQDN for the certificate
        organization: Organization name for certificate subject
        country: 2-letter country code
        key_size: RSA key size (2048-8192, default 4096)
        
    Returns:
        Dictionary with generated certificate paths
    """
    logger.info(f"Generating EAP certificates for '{common_name}' by {admin['sub']}")
    
    try:
        cert_mgr = get_cert_manager()
        result = cert_mgr.generate_eap_certificates(
            common_name=common_name,
            organization=organization,
            country=country,
            key_size=key_size,
        )
        
        return {
            "success": True,
            "message": f"EAP certificates generated for {common_name}",
            **result,
        }
        
    except CertificateError as e:
        logger.error(f"EAP certificate generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error generating EAP certificates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate EAP certificates",
        )


@router.post("/api/radsec/certificates/radsec/generate")
async def generate_radsec_certificates(
    admin: AdminUser,
    common_name: str = Query(..., description="Server hostname/FQDN"),
    organization: str = Query("FreeRADIUS", description="Organization name"),
    country: str = Query("US", description="2-letter country code"),
    key_size: int = Query(4096, ge=2048, le=8192, description="RSA key size"),
) -> dict:
    """
    Generate self-signed RadSec certificates.
    
    Alternative to Let's Encrypt for RadSec. Use this if:
    - You don't have Let's Encrypt set up
    - You prefer to use your own CA
    - You're in a closed network environment
    
    Note: Clients connecting via RadSec will need to trust your CA.
    
    Args:
        admin: Authenticated admin user
        common_name: Server hostname/FQDN
        organization: Organization name
        country: 2-letter country code
        key_size: RSA key size
        
    Returns:
        Dictionary with generated certificate paths
    """
    logger.info(f"Generating RadSec certificates for '{common_name}' by {admin['sub']}")
    
    try:
        cert_mgr = get_cert_manager()
        result = cert_mgr.setup_radsec_selfsigned(
            common_name=common_name,
            organization=organization,
            country=country,
            key_size=key_size,
        )
        
        return {
            "success": True,
            "message": f"RadSec certificates generated for {common_name}",
            **result,
        }
        
    except CertificateError as e:
        logger.error(f"RadSec certificate generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error generating RadSec certificates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate RadSec certificates",
        )
