"""Cloudflare DNS and Let's Encrypt API endpoints.

Provides:
- Sync Cloudflare configuration from portal
- Create DNS records for RADIUS hostname
- Obtain certificates via DNS-01 challenge (no port 80 needed)
- Certificate renewal management
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from radius_app.api.deps import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter()


class CloudflareConfigSync(BaseModel):
    """Request to sync Cloudflare config from portal."""
    
    portal_api_url: str = Field(..., description="Portal API URL")
    portal_token: str = Field(..., description="Portal API token")


class DNSRecordRequest(BaseModel):
    """Request to create/update a DNS record."""
    
    hostname: str = Field(..., description="Full hostname (e.g., radius.example.com)")
    ip_address: str = Field(..., description="IP address for the record")
    proxied: bool = Field(False, description="Proxy through Cloudflare (usually False for RADIUS)")


class CertificateRequest(BaseModel):
    """Request to obtain Let's Encrypt certificate."""
    
    domain: str = Field(..., description="Domain for certificate")
    email: str = Field(..., description="Email for Let's Encrypt notifications")
    staging: bool = Field(False, description="Use staging environment for testing")


# Store synced Cloudflare config
_cloudflare_config: dict = {}


@router.get("/api/cloudflare/status")
async def get_cloudflare_status(
    admin: AdminUser,
) -> dict:
    """
    Get Cloudflare integration status.
    
    Returns:
    - Whether Cloudflare is configured
    - Zone information
    - DNS record status
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Cloudflare status information
    """
    logger.info(f"Getting Cloudflare status requested by {admin['sub']}")
    
    if not _cloudflare_config.get("cloudflare_enabled"):
        return {
            "configured": False,
            "message": "Cloudflare not configured. Sync from portal first.",
        }
    
    return {
        "configured": True,
        "zone_id": _cloudflare_config.get("cloudflare_zone_id", ""),
        "zone_name": _cloudflare_config.get("cloudflare_zone_name", ""),
        "radius_hostname": _cloudflare_config.get("radius_hostname", ""),
        "has_token": bool(_cloudflare_config.get("cloudflare_api_token")),
    }


@router.post("/api/cloudflare/sync")
async def sync_cloudflare_config(
    request: CloudflareConfigSync,
    admin: AdminUser,
) -> dict:
    """
    Sync Cloudflare configuration from the portal server.
    
    Retrieves Cloudflare API credentials and zone information from
    the portal to enable DNS management and certificate automation.
    
    Args:
        request: Portal API connection details
        admin: Authenticated admin user
        
    Returns:
        Sync result
    """
    global _cloudflare_config
    
    logger.info(f"Syncing Cloudflare config from portal by {admin['sub']}")
    
    try:
        from radius_app.core.cloudflare_dns import sync_cloudflare_config_from_portal
        
        config = await sync_cloudflare_config_from_portal(
            portal_api_url=request.portal_api_url,
            portal_token=request.portal_token,
        )
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve Cloudflare config from portal",
            )
        
        _cloudflare_config = config
        
        return {
            "success": True,
            "message": "Cloudflare configuration synced from portal",
            "configured": config.get("cloudflare_enabled", False),
            "zone_name": config.get("cloudflare_zone_name", ""),
        }
        
    except Exception as e:
        logger.error(f"Failed to sync Cloudflare config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync Cloudflare config: {e}",
        )


@router.post("/api/cloudflare/configure")
async def configure_cloudflare(
    admin: AdminUser,
    api_token: str = Query(..., description="Cloudflare API token"),
    zone_id: str = Query(..., description="Cloudflare zone ID"),
    zone_name: str = Query("", description="Zone name (domain)"),
    account_id: Optional[str] = Query(None, description="Optional account ID"),
) -> dict:
    """
    Manually configure Cloudflare credentials.
    
    Use this if you want to configure Cloudflare directly without
    syncing from the portal.
    
    Args:
        admin: Authenticated admin user
        api_token: Cloudflare API token with DNS edit permissions
        zone_id: Zone ID for your domain
        zone_name: Domain name
        account_id: Optional account ID
        
    Returns:
        Configuration result
    """
    global _cloudflare_config
    
    logger.info(f"Configuring Cloudflare credentials by {admin['sub']}")
    
    try:
        from radius_app.core.cloudflare_dns import CloudflareDNSManager
        
        # Verify token
        manager = CloudflareDNSManager(api_token, zone_id, account_id)
        
        if not await manager.verify_token():
            await manager.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Cloudflare API token",
            )
        
        # Get zone name if not provided
        if not zone_name:
            zone_name = await manager.get_zone_name()
        
        await manager.close()
        
        _cloudflare_config = {
            "cloudflare_enabled": True,
            "cloudflare_api_token": api_token,
            "cloudflare_zone_id": zone_id,
            "cloudflare_zone_name": zone_name,
            "cloudflare_account_id": account_id or "",
        }
        
        return {
            "success": True,
            "message": "Cloudflare configured successfully",
            "zone_name": zone_name,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure Cloudflare: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure Cloudflare: {e}",
        )


@router.post("/api/cloudflare/dns/create")
async def create_dns_record(
    request: DNSRecordRequest,
    admin: AdminUser,
) -> dict:
    """
    Create or update DNS A record for RADIUS server.
    
    This creates an A record pointing to the RADIUS server's IP address.
    Note: RADIUS traffic should NOT be proxied through Cloudflare.
    
    Args:
        request: DNS record details
        admin: Authenticated admin user
        
    Returns:
        Created/updated record info
    """
    logger.info(f"Creating DNS record for {request.hostname} by {admin['sub']}")
    
    if not _cloudflare_config.get("cloudflare_enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare not configured. Configure credentials first.",
        )
    
    try:
        from radius_app.core.cloudflare_dns import CloudflareDNSManager
        
        manager = CloudflareDNSManager(
            _cloudflare_config["cloudflare_api_token"],
            _cloudflare_config["cloudflare_zone_id"],
        )
        
        record = await manager.create_a_record(
            hostname=request.hostname,
            ip_address=request.ip_address,
            proxied=request.proxied,
        )
        
        # Store the hostname
        _cloudflare_config["radius_hostname"] = request.hostname
        
        await manager.close()
        
        return {
            "success": True,
            "message": f"DNS record created for {request.hostname}",
            "record": record,
        }
        
    except Exception as e:
        logger.error(f"Failed to create DNS record: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create DNS record: {e}",
        )


@router.get("/api/cloudflare/dns/records")
async def list_dns_records(
    admin: AdminUser,
    record_type: Optional[str] = Query(None, description="Filter by type (A, AAAA, TXT, etc.)"),
) -> dict:
    """
    List DNS records in the configured zone.
    
    Args:
        admin: Authenticated admin user
        record_type: Optional filter by record type
        
    Returns:
        List of DNS records
    """
    logger.info(f"Listing DNS records by {admin['sub']}")
    
    if not _cloudflare_config.get("cloudflare_enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare not configured",
        )
    
    try:
        from radius_app.core.cloudflare_dns import CloudflareDNSManager
        
        manager = CloudflareDNSManager(
            _cloudflare_config["cloudflare_api_token"],
            _cloudflare_config["cloudflare_zone_id"],
        )
        
        records = await manager.list_records(record_type)
        await manager.close()
        
        return {
            "records": records,
            "count": len(records),
            "zone_name": _cloudflare_config.get("cloudflare_zone_name", ""),
        }
        
    except Exception as e:
        logger.error(f"Failed to list DNS records: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list DNS records: {e}",
        )


@router.post("/api/cloudflare/certificates/obtain")
async def obtain_certificate(
    request: CertificateRequest,
    admin: AdminUser,
) -> dict:
    """
    Obtain Let's Encrypt certificate using DNS-01 challenge.
    
    This uses Cloudflare DNS for domain validation, so no port 80 is needed.
    This is the recommended approach for RADIUS servers.
    
    Prerequisites:
    - Cloudflare must be configured with DNS edit permissions
    - certbot and python3-certbot-dns-cloudflare must be installed
    
    Args:
        request: Certificate request details
        admin: Authenticated admin user
        
    Returns:
        Certificate paths and status
    """
    logger.info(f"Obtaining certificate for {request.domain} by {admin['sub']}")
    
    if not _cloudflare_config.get("cloudflare_enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare not configured. Configure credentials first.",
        )
    
    try:
        from radius_app.core.cloudflare_dns import LetsEncryptDNS01
        
        le_manager = LetsEncryptDNS01(
            cloudflare_token=_cloudflare_config["cloudflare_api_token"],
            zone_id=_cloudflare_config["cloudflare_zone_id"],
        )
        
        result = await le_manager.obtain_certificate(
            domain=request.domain,
            email=request.email,
            staging=request.staging,
        )
        
        await le_manager.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to obtain certificate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to obtain certificate: {e}",
        )


@router.post("/api/cloudflare/certificates/renew")
async def renew_certificates(
    admin: AdminUser,
) -> dict:
    """
    Renew existing Let's Encrypt certificates.
    
    Runs certbot renew to check and renew any certificates
    that are close to expiry.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Renewal result
    """
    logger.info(f"Renewing certificates by {admin['sub']}")
    
    if not _cloudflare_config.get("cloudflare_enabled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare not configured",
        )
    
    try:
        from radius_app.core.cloudflare_dns import LetsEncryptDNS01
        
        le_manager = LetsEncryptDNS01(
            cloudflare_token=_cloudflare_config["cloudflare_api_token"],
            zone_id=_cloudflare_config["cloudflare_zone_id"],
        )
        
        result = await le_manager.renew_certificate()
        await le_manager.close()
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to renew certificates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to renew certificates: {e}",
        )
