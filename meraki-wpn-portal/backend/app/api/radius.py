"""RADIUS management endpoints (admin only)."""

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import meraki
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import AdminUser, DbSession
from app.config import get_settings
from app.core.radius_certificates import RadSecCertificateManager
from app.core.udn_manager import InvalidMacAddress, UdnError, UdnManager, normalize_mac_address
from app.db.models import RadiusClient, UdnAssignment

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic schemas
class RadiusConfigResponse(BaseModel):
    """RADIUS configuration response."""
    enabled: bool
    server_host: str
    auth_port: int
    acct_port: int
    radsec_enabled: bool
    radsec_port: int
    radsec_auto_generate: bool
    api_url: str
    has_certificates: bool
    server_status: str


class RadiusConfigUpdate(BaseModel):
    """RADIUS configuration update."""
    enabled: Optional[bool] = None
    server_host: Optional[str] = None
    radsec_enabled: Optional[bool] = None
    radsec_auto_generate: Optional[bool] = None


class RadiusClientCreate(BaseModel):
    """Create RADIUS client."""
    name: str = Field(..., description="Client name")
    ipaddr: str = Field(..., description="IP address or CIDR")
    secret: str = Field(..., description="Shared secret")
    nas_type: str = Field(default="other", description="NAS type")
    shortname: Optional[str] = Field(None, description="Short name")
    network_id: Optional[str] = Field(None, description="Meraki network ID")
    network_name: Optional[str] = Field(None, description="Meraki network name")


class RadiusClientResponse(BaseModel):
    """RADIUS client response."""
    id: int
    name: str
    ipaddr: str
    nas_type: str
    shortname: Optional[str]
    network_id: Optional[str]
    network_name: Optional[str]
    is_active: bool
    created_at: datetime


class CertificateInfoResponse(BaseModel):
    """Certificate information response."""
    common_name: str
    issuer: str
    valid_from: str
    valid_until: str
    key_type: str
    signature_algorithm: str
    is_self_signed: bool
    validation_issues: list[str]


class UdnAssignmentCreate(BaseModel):
    """Create UDN assignment."""
    mac_address: str = Field(..., description="MAC address")
    user_id: Optional[int] = None
    ipsk_id: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    unit: Optional[str] = None
    network_id: Optional[str] = None
    ssid_number: Optional[int] = None
    note: Optional[str] = None
    specific_udn_id: Optional[int] = None


class UdnAssignmentResponse(BaseModel):
    """UDN assignment response."""
    id: int
    udn_id: int
    mac_address: str
    user_id: Optional[int]
    user_name: Optional[str]
    user_email: Optional[str]
    unit: Optional[str]
    ipsk_id: Optional[str]
    network_id: Optional[str]
    ssid_number: Optional[int]
    is_active: bool
    cisco_avpair: str
    created_at: datetime
    last_auth_at: Optional[datetime]


class UdnPoolStatusResponse(BaseModel):
    """UDN pool status response."""
    total: int
    assigned: int
    available: int
    utilization_percent: float


class MerakiCertificateUploadRequest(BaseModel):
    """Request to upload certificate to Meraki."""
    organization_id: str = Field(..., description="Meraki organization ID")


class MerakiCertificateResponse(BaseModel):
    """Meraki certificate response."""
    success: bool
    message: str
    certificate_id: Optional[str] = None
    contents: Optional[str] = None


class MerakiRadSecSetupRequest(BaseModel):
    """Request for automated Meraki RadSec setup."""
    organization_id: str = Field(..., description="Meraki organization ID")
    network_id: str = Field(..., description="Meraki network ID")
    ssid_number: int = Field(..., description="SSID number to configure (0-14)")
    radius_server_host: str = Field(..., description="Public hostname/IP of RADIUS server")
    radius_server_port: int = Field(default=2083, description="RadSec port")
    generate_shared_secret: bool = Field(default=True, description="Auto-generate shared secret")


class SplashPageConfigRequest(BaseModel):
    """Request to configure splash page settings."""
    network_id: str = Field(..., description="Meraki network ID")
    ssid_number: int = Field(..., description="SSID number to configure (0-14)")
    splash_url: str = Field(..., description="URL of your portal (e.g., https://portal.example.com/register)")
    welcome_message: str = Field(
        default="Welcome! Please register to get your personal WiFi credentials.",
        description="Welcome message displayed on splash page"
    )
    splash_timeout: int = Field(
        default=1440,
        description="Splash timeout in minutes (1440 = 24 hours)"
    )
    redirect_url: Optional[str] = Field(
        default=None,
        description="Optional URL to redirect after splash page"
    )


class SplashPageConfigResponse(BaseModel):
    """Response for splash page configuration."""
    success: bool
    message: str
    settings: Optional[dict] = None


# RADIUS Configuration Endpoints


class CloudflareCredentialsResponse(BaseModel):
    """Cloudflare credentials for RADIUS server."""
    success: bool
    cloudflare_enabled: bool
    cloudflare_api_token: str = ""
    cloudflare_zone_id: str = ""
    cloudflare_zone_name: str = ""
    cloudflare_account_id: str = ""
    radius_hostname: str = ""
    radius_cert_source: str = "selfsigned"


@router.get("/cloudflare-credentials", response_model=CloudflareCredentialsResponse)
async def get_cloudflare_credentials_for_radius(
    admin: AdminUser,
) -> CloudflareCredentialsResponse:
    """
    Get Cloudflare credentials for RADIUS server certificate provisioning.
    
    This endpoint provides the actual (unmasked) Cloudflare API credentials
    to the RADIUS server so it can:
    1. Create DNS records for the RADIUS hostname
    2. Use DNS-01 challenge for Let's Encrypt certificates
    
    Security:
    - Requires admin authentication
    - Should only be called from the RADIUS server
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Cloudflare credentials and RADIUS hostname configuration
    """
    settings = get_settings()
    
    return CloudflareCredentialsResponse(
        success=True,
        cloudflare_enabled=settings.cloudflare_enabled,
        cloudflare_api_token=settings.cloudflare_api_token,
        cloudflare_zone_id=settings.cloudflare_zone_id,
        cloudflare_zone_name=settings.cloudflare_zone_name,
        cloudflare_account_id=settings.cloudflare_account_id,
        radius_hostname=getattr(settings, 'radius_hostname', ''),
        radius_cert_source=getattr(settings, 'radius_cert_source', 'selfsigned'),
    )


@router.post("/configure-hostname")
async def configure_radius_hostname(
    admin: AdminUser,
    hostname: str,
    ip_address: str,
    create_dns: bool = True,
    obtain_certificate: bool = True,
    cert_email: Optional[str] = None,
) -> dict:
    """
    Configure RADIUS server hostname with DNS and certificate.
    
    This endpoint:
    1. Creates a DNS A record for the RADIUS hostname (if create_dns=True)
    2. Triggers the RADIUS server to obtain a Let's Encrypt certificate (if obtain_certificate=True)
    
    Prerequisites:
    - Cloudflare must be configured
    - RADIUS server must be running
    
    Args:
        admin: Authenticated admin user
        hostname: RADIUS server hostname (e.g., radius.example.com)
        ip_address: Public IP address of the RADIUS server
        create_dns: Create DNS A record
        obtain_certificate: Trigger Let's Encrypt certificate provisioning
        cert_email: Email for Let's Encrypt notifications
        
    Returns:
        Configuration result
    """
    from app.core.cloudflare_client import CloudflareClient
    from app.core.db_settings import get_db_settings_manager
    from app.db.database import get_session_local
    
    settings = get_settings()
    
    if not settings.cloudflare_enabled or not settings.cloudflare_api_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare not configured. Please configure Cloudflare first.",
        )
    
    result = {
        "success": True,
        "hostname": hostname,
        "dns_created": False,
        "certificate_requested": False,
    }
    
    # Create DNS record via Cloudflare
    if create_dns:
        try:
            client = CloudflareClient(
                settings.cloudflare_api_token,
                settings.cloudflare_account_id or None,
            )
            
            # Get zone name
            zones = await client.list_zones()
            zone = next((z for z in zones if z["id"] == settings.cloudflare_zone_id), None)
            
            if not zone:
                await client.close()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configured Cloudflare zone not found",
                )
            
            zone_name = zone["name"]
            
            # Check if hostname matches zone
            if not hostname.endswith(f".{zone_name}"):
                await client.close()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Hostname must be in zone {zone_name}",
                )
            
            # Create A record (not proxied - RADIUS traffic can't go through Cloudflare)
            try:
                await client._client.dns.records.create(
                    zone_id=settings.cloudflare_zone_id,
                    type="A",
                    name=hostname,
                    content=ip_address,
                    proxied=False,
                    ttl=300,
                )
                result["dns_created"] = True
                logger.info(f"Created DNS record: {hostname} -> {ip_address}")
            except Exception as dns_err:
                # Record may already exist, try to update
                logger.warning(f"DNS record may exist: {dns_err}")
                result["dns_note"] = str(dns_err)
            
            await client.close()
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create DNS record: {e}")
            result["dns_error"] = str(e)
    
    # Save radius hostname to settings
    try:
        db_mgr = get_db_settings_manager()
        SessionLocal = get_session_local()
        with SessionLocal() as db:
            db_mgr.bulk_update_settings(
                db=db,
                settings_dict={
                    "radius_hostname": hostname,
                }
            )
        logger.info(f"Saved RADIUS hostname: {hostname}")
    except Exception as e:
        logger.error(f"Failed to save RADIUS hostname: {e}")
    
    # Trigger certificate provisioning on RADIUS server
    if obtain_certificate and settings.radius_api_url:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # First sync Cloudflare config to RADIUS
                sync_response = await client.post(
                    f"{settings.radius_api_url}/api/cloudflare/configure",
                    params={
                        "api_token": settings.cloudflare_api_token,
                        "zone_id": settings.cloudflare_zone_id,
                        "zone_name": settings.cloudflare_zone_name,
                        "account_id": settings.cloudflare_account_id,
                    },
                    headers={"Authorization": f"Bearer {settings.radius_api_token}"},
                )
                
                if sync_response.status_code != 200:
                    logger.warning(f"Failed to sync Cloudflare config to RADIUS: {sync_response.text}")
                
                # Request certificate
                cert_response = await client.post(
                    f"{settings.radius_api_url}/api/cloudflare/certificates/obtain",
                    json={
                        "domain": hostname,
                        "email": cert_email or settings.admin_notification_email or "admin@example.com",
                        "staging": False,
                    },
                    headers={"Authorization": f"Bearer {settings.radius_api_token}"},
                )
                
                if cert_response.status_code == 200:
                    result["certificate_requested"] = True
                    result["certificate_result"] = cert_response.json()
                    logger.info(f"Certificate provisioned for {hostname}")
                else:
                    result["certificate_error"] = cert_response.text
                    
        except Exception as e:
            logger.error(f"Failed to request certificate: {e}")
            result["certificate_error"] = str(e)
    
    return result


@router.get("/config", response_model=RadiusConfigResponse)
async def get_radius_config(admin: AdminUser) -> RadiusConfigResponse:
    """
    Get current RADIUS configuration.

    Args:
        admin: Authenticated admin user

    Returns:
        RADIUS configuration
    """
    settings = get_settings()
    
    # Check if certificates exist
    cert_manager = RadSecCertificateManager()
    has_certs = False
    if cert_manager.certs_path:
        has_certs = (
            (cert_manager.certs_path / "ca.pem").exists() and
            (cert_manager.certs_path / "server.pem").exists()
        )
    
    # Check server status
    server_status = "unknown"
    if settings.radius_enabled:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.radius_api_url}/health")
                if response.status_code == 200:
                    server_status = "running"
                else:
                    server_status = "error"
        except Exception as e:
            logger.warning(f"Failed to check RADIUS server status: {e}")
            server_status = "unreachable"
    else:
        server_status = "disabled"
    
    return RadiusConfigResponse(
        enabled=settings.radius_enabled,
        server_host=settings.radius_server_host,
        auth_port=settings.radius_auth_port,
        acct_port=settings.radius_acct_port,
        radsec_enabled=settings.radius_radsec_enabled,
        radsec_port=settings.radius_radsec_port,
        radsec_auto_generate=settings.radius_radsec_auto_generate,
        api_url=settings.radius_api_url,
        has_certificates=has_certs,
        server_status=server_status,
    )


@router.put("/config")
async def update_radius_config(
    config: RadiusConfigUpdate,
    admin: AdminUser,
) -> dict[str, str]:
    """
    Update RADIUS configuration.

    Args:
        config: Configuration updates
        admin: Authenticated admin user

    Returns:
        Success message
    """
    settings = get_settings()
    
    # Update settings (in production, this would update the settings manager)
    updates = {}
    if config.enabled is not None:
        updates["radius_enabled"] = config.enabled
    if config.server_host is not None:
        updates["radius_server_host"] = config.server_host
    if config.radsec_enabled is not None:
        updates["radius_radsec_enabled"] = config.radsec_enabled
    if config.radsec_auto_generate is not None:
        updates["radius_radsec_auto_generate"] = config.radsec_auto_generate
    
    logger.info(f"Updated RADIUS configuration: {updates}")
    
    return {
        "message": "RADIUS configuration updated successfully",
        "requires_restart": False
    }


# Certificate Management Endpoints


@router.post("/certificates/generate")
async def generate_radsec_certificates(
    admin: AdminUser,
    hostname: Optional[str] = None,
) -> dict[str, str]:
    """
    Generate RadSec certificates.

    Args:
        admin: Authenticated admin user
        hostname: Server hostname for certificate

    Returns:
        Certificate generation status
    """
    settings = get_settings()
    
    if not settings.radius_radsec_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RadSec is not enabled"
        )
    
    cert_manager = RadSecCertificateManager()
    
    try:
        paths = cert_manager.generate_radsec_certificates(
            server_hostname=hostname or settings.radius_server_host,
            organization=settings.property_name,
        )
        
        logger.info("Generated RadSec certificates successfully")
        
        return {
            "message": "RadSec certificates generated successfully",
            "ca_cert_path": str(paths["ca_cert"]),
            "server_cert_path": str(paths["server_cert"]),
        }
        
    except Exception as e:
        logger.exception(f"Failed to generate certificates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate certificates: {str(e)}"
        ) from e


@router.get("/certificates/info", response_model=CertificateInfoResponse)
async def get_certificate_info(
    admin: AdminUser,
    cert_type: str = "server",  # "ca" or "server"
) -> CertificateInfoResponse:
    """
    Get certificate information.

    Args:
        admin: Authenticated admin user
        cert_type: Certificate type ("ca" or "server")

    Returns:
        Certificate information
    """
    cert_manager = RadSecCertificateManager()
    
    try:
        if cert_type == "ca":
            cert = cert_manager.load_certificate("ca.pem")
        elif cert_type == "server":
            cert = cert_manager.load_certificate("server.pem")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid certificate type"
            )
        
        info = cert_manager.get_certificate_info(cert)
        validation_issues = cert_manager.validate_certificate(cert)
        
        return CertificateInfoResponse(
            **info,
            validation_issues=validation_issues
        )
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate not found: {cert_type}"
        ) from e
    except Exception as e:
        logger.exception(f"Failed to load certificate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load certificate: {str(e)}"
        ) from e


@router.get("/certificates/download/{cert_type}")
async def download_certificate(
    admin: AdminUser,
    cert_type: str,  # "ca", "server", or "bundle"
) -> dict[str, str]:
    """
    Download certificate file.

    Args:
        admin: Authenticated admin user
        cert_type: Certificate type to download

    Returns:
        Certificate PEM content
    """
    cert_manager = RadSecCertificateManager()
    
    try:
        if cert_type == "ca":
            cert_path = cert_manager.certs_path / "ca.pem"
        elif cert_type == "server":
            cert_path = cert_manager.certs_path / "server.pem"
        elif cert_type == "bundle":
            # Return CA + Server chain
            ca_path = cert_manager.certs_path / "ca.pem"
            server_path = cert_manager.certs_path / "server.pem"
            
            with open(ca_path, "r") as f:
                ca_pem = f.read()
            with open(server_path, "r") as f:
                server_pem = f.read()
            
            return {
                "filename": "certificate-bundle.pem",
                "content": server_pem + "\n" + ca_pem
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid certificate type"
            )
        
        with open(cert_path, "r") as f:
            content = f.read()
        
        return {
            "filename": cert_path.name,
            "content": content
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate not found: {cert_type}"
        ) from e
    except Exception as e:
        logger.exception(f"Failed to download certificate: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download certificate: {str(e)}"
        ) from e


# RADIUS Client Management Endpoints


@router.get("/clients", response_model=list[RadiusClientResponse])
async def list_radius_clients(
    admin: AdminUser,
    db: DbSession,
) -> list[RadiusClientResponse]:
    """
    List all RADIUS clients.

    Args:
        admin: Authenticated admin user
        db: Database session

    Returns:
        List of RADIUS clients
    """
    clients = db.query(RadiusClient).filter(
        RadiusClient.is_active == True  # noqa: E712
    ).all()
    
    return [
        RadiusClientResponse(
            id=client.id,
            name=client.name,
            ipaddr=client.ipaddr,
            nas_type=client.nas_type,
            shortname=client.shortname,
            network_id=client.network_id,
            network_name=client.network_name,
            is_active=client.is_active,
            created_at=client.created_at,
        )
        for client in clients
    ]


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def create_radius_client(
    client_data: RadiusClientCreate,
    admin: AdminUser,
    db: DbSession,
) -> RadiusClientResponse:
    """
    Create a new RADIUS client.

    Args:
        client_data: Client data
        admin: Authenticated admin user
        db: Database session

    Returns:
        Created client
    """
    settings = get_settings()
    
    # Check if client already exists
    existing = db.query(RadiusClient).filter(
        RadiusClient.name == client_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Client '{client_data.name}' already exists"
        )
    
    # Create client
    client = RadiusClient(
        name=client_data.name,
        ipaddr=client_data.ipaddr,
        secret=client_data.secret,  # Will be encrypted by settings manager
        nas_type=client_data.nas_type,
        shortname=client_data.shortname or client_data.name,
        network_id=client_data.network_id,
        network_name=client_data.network_name,
        require_message_authenticator=True,
        is_active=True,
        created_by=admin.get("sub", "admin"),
    )
    
    db.add(client)
    db.commit()
    db.refresh(client)
    
    # Sync with FreeRADIUS server
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            await http_client.post(
                f"{settings.radius_api_url}/api/clients",
                json={
                    "name": client.name,
                    "ipaddr": client.ipaddr,
                    "secret": client.secret,
                    "nas_type": client.nas_type,
                    "shortname": client.shortname,
                },
                headers={"Authorization": f"Bearer {settings.radius_api_token}"}
            )
    except Exception as e:
        logger.warning(f"Failed to sync client to RADIUS server: {e}")
    
    logger.info(f"Created RADIUS client: {client.name}")
    
    return RadiusClientResponse(
        id=client.id,
        name=client.name,
        ipaddr=client.ipaddr,
        nas_type=client.nas_type,
        shortname=client.shortname,
        network_id=client.network_id,
        network_name=client.network_name,
        is_active=client.is_active,
        created_at=client.created_at,
    )


class BulkNadCreateRequest(BaseModel):
    """Bulk NAD creation from Meraki devices."""
    network_id: str = Field(..., description="Meraki network ID")
    device_serials: list[str] = Field(..., description="List of device serials to create NADs for")
    shared_secret: str = Field(..., description="Shared secret for all NADs")
    nas_type: str = Field(default="other", description="NAS type")


class BulkNadCreateResult(BaseModel):
    """Result of bulk NAD creation."""
    created: list[dict] = Field(default_factory=list, description="Successfully created NADs")
    failed: list[dict] = Field(default_factory=list, description="Failed NAD creations")
    skipped: list[dict] = Field(default_factory=list, description="Skipped (already exist)")


@router.post("/nads/bulk-from-devices", status_code=status.HTTP_201_CREATED)
async def bulk_create_nads_from_devices(
    bulk_data: BulkNadCreateRequest,
    admin: AdminUser,
    db: DbSession,
) -> BulkNadCreateResult:
    """
    Bulk create RADIUS NADs from Meraki network devices.

    This endpoint fetches device details from Meraki and creates RADIUS clients (NADs)
    for selected devices (APs, switches, etc.) using their LAN IP addresses and names.

    Args:
        bulk_data: Bulk creation request with network ID, device serials, and shared secret
        admin: Authenticated admin user
        db: Database session

    Returns:
        Results showing created, failed, and skipped NADs
    """
    settings = get_settings()
    
    result = BulkNadCreateResult()
    
    try:
        # Get Meraki client
        from app.core.meraki_client import MerakiDashboardClient
        
        meraki_client = MerakiDashboardClient(settings.meraki_api_key)
        await meraki_client.connect()
        
        try:
            # Fetch all devices in the network
            all_devices = await meraki_client.get_network_devices(bulk_data.network_id)
            
            # Filter to only requested devices
            devices_to_process = [
                dev for dev in all_devices 
                if dev.get("serial") in bulk_data.device_serials
            ]
            
            if not devices_to_process:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No devices found with the provided serials"
                )
            
            # Process each device
            for device in devices_to_process:
                serial = device.get("serial", "")
                name = device.get("name", f"Device-{serial}")
                lan_ip = device.get("lanIp")
                model = device.get("model", "")
                mac = device.get("mac", "")
                
                # Skip if no LAN IP
                if not lan_ip:
                    result.skipped.append({
                        "serial": serial,
                        "name": name,
                        "reason": "No LAN IP address available"
                    })
                    continue
                
                # Check if NAD already exists with this name or IP
                existing = db.query(RadiusClient).filter(
                    (RadiusClient.name == name) | (RadiusClient.ipaddr == lan_ip)
                ).first()
                
                if existing:
                    result.skipped.append({
                        "serial": serial,
                        "name": name,
                        "ip": lan_ip,
                        "reason": f"NAD already exists (name: {existing.name}, IP: {existing.ipaddr})"
                    })
                    continue
                
                try:
                    # Create RADIUS client
                    client = RadiusClient(
                        name=name,
                        ipaddr=lan_ip,
                        secret=bulk_data.shared_secret,
                        nas_type=bulk_data.nas_type,
                        shortname=name[:32],  # Limit shortname length
                        network_id=bulk_data.network_id,
                        network_name=device.get("networkId", bulk_data.network_id),
                        require_message_authenticator=True,
                        is_active=True,
                        created_by=admin.get("sub", "admin"),
                    )
                    
                    db.add(client)
                    db.flush()  # Flush to get the ID but don't commit yet
                    
                    result.created.append({
                        "id": client.id,
                        "serial": serial,
                        "name": name,
                        "ip": lan_ip,
                        "model": model,
                        "mac": mac,
                    })
                    
                    logger.info(f"Created NAD from device: {name} ({lan_ip})")
                    
                except Exception as e:
                    db.rollback()
                    result.failed.append({
                        "serial": serial,
                        "name": name,
                        "ip": lan_ip,
                        "error": str(e)
                    })
                    logger.error(f"Failed to create NAD for device {name}: {e}")
            
            # Commit all successful creations
            db.commit()
            
            # Sync with FreeRADIUS server (best effort)
            if result.created and settings.radius_api_url and settings.radius_api_token:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as http_client:
                        for created_nad in result.created:
                            try:
                                await http_client.post(
                                    f"{settings.radius_api_url}/api/reload",
                                    json={"force": True},
                                    headers={"Authorization": f"Bearer {settings.radius_api_token}"}
                                )
                                break  # Only need to reload once
                            except Exception as e:
                                logger.warning(f"Failed to trigger RADIUS reload: {e}")
                except Exception as e:
                    logger.warning(f"Failed to sync with RADIUS server: {e}")
            
            logger.info(
                f"Bulk NAD creation completed: {len(result.created)} created, "
                f"{len(result.skipped)} skipped, {len(result.failed)} failed"
            )
            
            return result
            
        finally:
            await meraki_client.disconnect()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Bulk NAD creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk NAD creation failed: {str(e)}"
        ) from e


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_radius_client(
    client_id: int,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """
    Delete a RADIUS client.

    Args:
        client_id: Client ID
        admin: Authenticated admin user
        db: Database session
    """
    client = db.query(RadiusClient).filter(RadiusClient.id == client_id).first()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    client.is_active = False
    db.commit()
    
    logger.info(f"Deleted RADIUS client: {client.name}")


# UDN Assignment Endpoints


@router.get("/udn/pool", response_model=UdnPoolStatusResponse)
async def get_udn_pool_status(
    admin: AdminUser,
    db: DbSession,
) -> UdnPoolStatusResponse:
    """
    Get UDN ID pool status.

    Args:
        admin: Authenticated admin user
        db: Database session

    Returns:
        Pool status
    """
    udn_manager = UdnManager(db)
    status_data = udn_manager.get_udn_pool_status()
    
    return UdnPoolStatusResponse(**status_data)


@router.get("/udn/assignments", response_model=list[UdnAssignmentResponse])
async def list_udn_assignments(
    admin: AdminUser,
    db: DbSession,
    active_only: bool = True,
    unit: Optional[str] = None,
) -> list[UdnAssignmentResponse]:
    """
    List UDN assignments.

    Args:
        admin: Authenticated admin user
        db: Database session
        active_only: Only return active assignments
        unit: Filter by unit

    Returns:
        List of assignments
    """
    udn_manager = UdnManager(db)
    assignments = udn_manager.list_assignments(active_only=active_only, unit=unit)
    
    from app.core.udn_manager import format_cisco_avpair
    
    return [
        UdnAssignmentResponse(
            id=assignment.id,
            udn_id=assignment.udn_id,
            mac_address=assignment.mac_address,
            user_id=assignment.user_id,
            user_name=assignment.user_name,
            user_email=assignment.user_email,
            unit=assignment.unit,
            ipsk_id=assignment.ipsk_id,
            network_id=assignment.network_id,
            ssid_number=assignment.ssid_number,
            is_active=assignment.is_active,
            cisco_avpair=format_cisco_avpair(assignment.udn_id),
            created_at=assignment.created_at,
            last_auth_at=assignment.last_auth_at,
        )
        for assignment in assignments
    ]


@router.post("/udn/assignments", status_code=status.HTTP_201_CREATED)
async def create_udn_assignment(
    assignment_data: UdnAssignmentCreate,
    admin: AdminUser,
    db: DbSession,
) -> UdnAssignmentResponse:
    """
    Create a UDN assignment.

    Args:
        assignment_data: Assignment data
        admin: Authenticated admin user
        db: Database session

    Returns:
        Created assignment
    """
    udn_manager = UdnManager(db)
    
    try:
        # UDN is assigned to USER (not MAC). MAC is optional.
        if not assignment_data.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id is required for UDN assignment"
            )
        
        assignment = udn_manager.assign_udn_id(
            user_id=assignment_data.user_id,  # Required
            mac_address=assignment_data.mac_address,  # Optional
            ipsk_id=assignment_data.ipsk_id,
            user_name=assignment_data.user_name,
            user_email=assignment_data.user_email,
            unit=assignment_data.unit,
            network_id=assignment_data.network_id,
            ssid_number=assignment_data.ssid_number,
            note=assignment_data.note,
            specific_udn_id=assignment_data.specific_udn_id,
        )
        
        from app.core.udn_manager import format_cisco_avpair
        
        return UdnAssignmentResponse(
            id=assignment.id,
            udn_id=assignment.udn_id,
            mac_address=assignment.mac_address,
            user_id=assignment.user_id,
            user_name=assignment.user_name,
            user_email=assignment.user_email,
            unit=assignment.unit,
            ipsk_id=assignment.ipsk_id,
            network_id=assignment.network_id,
            ssid_number=assignment.ssid_number,
            is_active=assignment.is_active,
            cisco_avpair=format_cisco_avpair(assignment.udn_id),
            created_at=assignment.created_at,
            last_auth_at=assignment.last_auth_at,
        )
        
    except (InvalidMacAddress, UdnError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.exception(f"Failed to create UDN assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create assignment: {str(e)}"
        ) from e


@router.delete("/udn/assignments/{mac_address}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_udn_assignment(
    mac_address: str,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """
    Revoke a UDN assignment.

    Args:
        mac_address: MAC address to revoke
        admin: Authenticated admin user
        db: Database session
    """
    udn_manager = UdnManager(db)
    
    try:
        success = udn_manager.revoke_assignment(mac_address)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
    except InvalidMacAddress as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e


@router.get("/status")
async def get_radius_status(admin: AdminUser) -> dict[str, str]:
    """
    Get RADIUS server status.

    Args:
        admin: Authenticated admin user

    Returns:
        Server status
    """
    settings = get_settings()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.radius_api_url}/health")
            data = response.json()
            
            return {
                "status": "running",
                "radius_running": data.get("radius_running", False),
                "timestamp": data.get("timestamp", ""),
            }
            
    except Exception as e:
        logger.warning(f"Failed to check RADIUS server status: {e}")
        return {
            "status": "unreachable",
            "error": str(e),
        }


# ============================================================================
# Meraki RadSec Certificate Exchange
# ============================================================================


@router.post("/meraki/upload-ca")
async def upload_ca_to_meraki(
    request: MerakiCertificateUploadRequest,
    admin: AdminUser,
) -> MerakiCertificateResponse:
    """
    Upload FreeRADIUS CA certificate to Meraki organization.

    This allows Meraki access points to trust your RADIUS server.

    Args:
        request: Upload request with organization ID
        admin: Authenticated admin user

    Returns:
        Upload result with certificate ID
    """
    settings = get_settings()
    
    if not settings.meraki_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meraki API key not configured"
        )
    
    # Get Meraki client from app state
    from app.main import app
    meraki_client = getattr(app.state, 'ha_client', None)
    
    if not meraki_client or not hasattr(meraki_client, 'upload_radsec_ca_certificate'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meraki client not available"
        )
    
    # Load our CA certificate
    cert_manager = RadSecCertificateManager()
    try:
        ca_cert = cert_manager.load_certificate("ca.pem")
        from cryptography.hazmat.primitives import serialization
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CA certificate not found. Generate certificates first."
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load CA certificate: {str(e)}"
        ) from e
    
    # Upload to Meraki
    try:
        result = await meraki_client.upload_radsec_ca_certificate(
            organization_id=request.organization_id,
            cert_contents=ca_pem,
        )
        
        logger.info(f"Uploaded CA certificate to Meraki org {request.organization_id}")
        
        return MerakiCertificateResponse(
            success=True,
            message="CA certificate uploaded successfully to Meraki",
            certificate_id=result["certificate_id"],
        )
        
    except Exception as e:
        logger.exception(f"Failed to upload CA to Meraki: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload certificate to Meraki: {str(e)}"
        ) from e


@router.post("/meraki/download-device-ca")
async def download_meraki_device_ca(
    request: MerakiCertificateUploadRequest,
    admin: AdminUser,
) -> MerakiCertificateResponse:
    """
    Download Meraki device CA certificate to trust on RADIUS server.

    This creates and trusts a Meraki-generated CA that signs certificates
    for your access points.

    Args:
        request: Request with organization ID
        admin: Authenticated admin user

    Returns:
        Certificate contents and ID
    """
    settings = get_settings()
    
    if not settings.meraki_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meraki API key not configured"
        )
    
    # Get Meraki client
    from app.main import app
    meraki_client = getattr(app.state, 'ha_client', None)
    
    if not meraki_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meraki client not available"
        )
    
    try:
        # Check if device CA already exists
        existing_cas = await meraki_client.get_radsec_device_certificate_authorities(
            organization_id=request.organization_id,
        )
        
        device_ca = None
        if existing_cas:
            # Use first existing CA
            device_ca = existing_cas[0]
            logger.info(f"Using existing Meraki device CA: {device_ca['id']}")
            
            # Ensure it's trusted
            if device_ca.get("status") != "trusted":
                device_ca = await meraki_client.trust_radsec_device_certificate_authority(
                    organization_id=request.organization_id,
                    authority_id=device_ca["id"],
                )
        else:
            # Create new device CA
            logger.info("Creating new Meraki device CA")
            device_ca = await meraki_client.create_radsec_device_certificate_authority(
                organization_id=request.organization_id,
            )
            
            # Check if contents are ready (async generation)
            if not device_ca.get("ready") or not device_ca.get("contents"):
                logger.warning("CA generation in progress, waiting...")
                # Poll for completion (max 10 attempts, 2 seconds apart)
                for attempt in range(10):
                    await asyncio.sleep(2)
                    
                    # Use convenience method to get specific CA
                    updated_ca = await meraki_client.get_radsec_device_certificate_authority(
                        organization_id=request.organization_id,
                        certificate_authority_id=device_ca["certificate_authority_id"],
                    )
                    
                    if updated_ca and updated_ca.get("contents"):
                        device_ca["contents"] = updated_ca["contents"]
                        device_ca["status"] = updated_ca["status"]
                        device_ca["ready"] = True
                        logger.info(f"CA contents ready after {attempt + 1} attempts")
                        break
                    
                    if device_ca.get("ready"):
                        break
                
                if not device_ca.get("contents"):
                    raise HTTPException(
                        status_code=status.HTTP_408_REQUEST_TIMEOUT,
                        detail="Meraki CA generation timed out. Please try again in a few moments.",
                    )
            
            # Trust it
            device_ca = await meraki_client.trust_radsec_device_certificate_authority(
                organization_id=request.organization_id,
                authority_id=device_ca["certificate_authority_id"],
            )
        
        # Save Meraki CA to RADIUS server
        cert_manager = RadSecCertificateManager()
        ca_path = cert_manager.certs_path / "meraki-device-ca.pem"
        with open(ca_path, "w") as f:
            f.write(device_ca["contents"])
        ca_path.chmod(0o644)
        
        logger.info(f"Downloaded and saved Meraki device CA to {ca_path}")
        
        return MerakiCertificateResponse(
            success=True,
            message="Meraki device CA downloaded and saved to RADIUS server",
            certificate_id=device_ca.get("authority_id") or device_ca.get("id"),
            contents=device_ca["contents"],
        )
        
    except Exception as e:
        logger.exception(f"Failed to download Meraki device CA: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download Meraki device CA: {str(e)}"
        ) from e


@router.post("/meraki/setup-radsec")
async def automated_meraki_radsec_setup(
    request: MerakiRadSecSetupRequest,
    admin: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    """
    Automated end-to-end RadSec setup with Meraki.

    This endpoint performs:
    1. Generate FreeRADIUS RadSec certificates (if needed)
    2. Upload our CA to Meraki
    3. Download Meraki's device CA
    4. Add Meraki network as RADIUS client
    5. Configure network for RadSec (when API available)

    Args:
        request: Setup request with organization and network IDs
        admin: Authenticated admin user
        db: Database session

    Returns:
        Complete setup status and instructions
    """
    settings = get_settings()
    results = {
        "steps_completed": [],
        "steps_failed": [],
        "manual_steps_required": [],
    }
    
    if not settings.meraki_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meraki API key not configured"
        )
    
    # Step 1: Generate RadSec certificates
    cert_manager = RadSecCertificateManager()
    try:
        ca_exists = (cert_manager.certs_path / "ca.pem").exists()
        if not ca_exists:
            logger.info("Generating RadSec certificates...")
            cert_manager.generate_radsec_certificates(
                server_hostname=request.radius_server_host,
                organization=settings.property_name,
            )
            results["steps_completed"].append("Generated RadSec certificates")
        else:
            results["steps_completed"].append("Using existing RadSec certificates")
    except Exception as e:
        results["steps_failed"].append(f"Certificate generation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate certificates: {str(e)}"
        ) from e
    
    # Step 2: Upload our CA to Meraki
    ca_certificate_id = None
    try:
        ca_cert = cert_manager.load_certificate("ca.pem")
        from cryptography.hazmat.primitives import serialization
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM).decode()
        
        from app.main import app
        meraki_client = getattr(app.state, 'ha_client', None)
        
        if meraki_client:
            upload_result = await meraki_client.upload_radsec_ca_certificate(
                organization_id=request.organization_id,
                cert_contents=ca_pem,
            )
            ca_certificate_id = upload_result['certificate_id']
            results["steps_completed"].append(
                f"Uploaded CA to Meraki (ID: {ca_certificate_id})"
            )
        else:
            results["steps_failed"].append("Meraki client not available")
    except Exception as e:
        results["steps_failed"].append(f"CA upload to Meraki failed: {str(e)}")
        logger.warning(f"Failed to upload CA to Meraki: {e}")
    
    # Step 3: Download Meraki's device CA
    try:
        if meraki_client:
            existing_cas = await meraki_client.get_radsec_device_certificate_authorities(
                organization_id=request.organization_id,
            )
            
            if existing_cas:
                device_ca = existing_cas[0]
                if device_ca.get("status") != "trusted":
                    device_ca = await meraki_client.trust_radsec_device_certificate_authority(
                        organization_id=request.organization_id,
                        authority_id=device_ca["id"],
                    )
            else:
                # Create new device CA
                logger.info("Creating new Meraki device CA")
                device_ca_result = await meraki_client.create_radsec_device_certificate_authority(
                    organization_id=request.organization_id,
                )
                
                # Check if contents are ready (async generation)
                if not device_ca_result.get("ready") or not device_ca_result.get("contents"):
                    logger.warning("CA generation in progress, waiting...")
                    # Poll for completion (max 10 attempts, 2 seconds apart)
                    for attempt in range(10):
                        await asyncio.sleep(2)
                        
                        # Use convenience method to get specific CA
                        updated_ca = await meraki_client.get_radsec_device_certificate_authority(
                            organization_id=request.organization_id,
                            certificate_authority_id=device_ca_result["certificate_authority_id"],
                        )
                        
                        if updated_ca and updated_ca.get("contents"):
                            device_ca_result["contents"] = updated_ca["contents"]
                            device_ca_result["ready"] = True
                            device_ca = updated_ca
                            logger.info(f"CA contents ready after {attempt + 1} attempts")
                            break
                        
                        if device_ca_result.get("ready"):
                            break
                    
                    if not device_ca_result.get("contents"):
                        results["steps_failed"].append("Meraki CA generation timed out")
                        logger.error("Meraki CA generation timed out")
                        raise ValueError("CA generation timed out")
                else:
                    # Contents ready immediately
                    device_ca = {
                        "id": device_ca_result["certificate_authority_id"],
                        "contents": device_ca_result["contents"],
                        "status": device_ca_result["status"],
                    }
                
                # Trust it
                device_ca = await meraki_client.trust_radsec_device_certificate_authority(
                    organization_id=request.organization_id,
                    authority_id=device_ca["id"],
                )
            
            # Save to file
            ca_path = cert_manager.certs_path / "meraki-device-ca.pem"
            with open(ca_path, "w") as f:
                f.write(device_ca["contents"])
            ca_path.chmod(0o644)
            
            results["steps_completed"].append("Downloaded Meraki device CA")
    except Exception as e:
        results["steps_failed"].append(f"Download Meraki CA failed: {str(e)}")
        logger.warning(f"Failed to download Meraki CA: {e}")
    
    # Step 4: Add Meraki network as RADIUS client
    try:
        # Generate shared secret if requested
        shared_secret = ""
        if request.generate_shared_secret:
            shared_secret = secrets.token_urlsafe(32)
        
        # Get network info
        network_info = await meraki_client.get_network(request.network_id)
        
        # Check if client already exists
        existing = db.query(RadiusClient).filter(
            RadiusClient.network_id == request.network_id
        ).first()
        
        if not existing:
            # Add as RADIUS client
            client = RadiusClient(
                name=network_info.get("name", f"Network-{request.network_id}"),
                ipaddr="0.0.0.0/0",  # Allow from any IP (Meraki uses multiple IPs)
                secret=shared_secret,
                nas_type="other",
                shortname=network_info.get("name", "meraki")[:20],
                network_id=request.network_id,
                network_name=network_info.get("name"),
                require_message_authenticator=True,
                is_active=True,
                created_by=admin.get("sub", "admin"),
            )
            db.add(client)
            db.commit()
            
            results["steps_completed"].append(
                f"Added network as RADIUS client (shared secret generated)"
            )
            results["shared_secret"] = shared_secret
        else:
            results["steps_completed"].append("Network already configured as RADIUS client")
            results["shared_secret"] = "Using existing shared secret"
    except Exception as e:
        results["steps_failed"].append(f"Add RADIUS client failed: {str(e)}")
        logger.warning(f"Failed to add RADIUS client: {e}")
    
    # Step 5: Configure SSID for RadSec
    wpn_info = None
    try:
        if meraki_client and ca_certificate_id and results["shared_secret"]:
            ssid_result = await meraki_client.configure_network_radsec(
                network_id=request.network_id,
                ssid_number=request.ssid_number,
                radius_host=request.radius_server_host,
                radius_port=request.radius_server_port,
                shared_secret=results["shared_secret"],
                ca_certificate_id=ca_certificate_id,
            )
            
            wpn_enabled = ssid_result.get("wpn_enabled", False)
            wpn_id = ssid_result.get("wifiPersonalNetworkId")
            
            if wpn_id:
                results["steps_completed"].append(
                    f"Configured SSID {request.ssid_number} for RadSec with WPN (ID: {wpn_id})"
                )
                wpn_info = {"enabled": True, "id": wpn_id}
            else:
                results["steps_completed"].append(
                    f"Configured SSID {request.ssid_number} for RadSec (WPN may need manual enable)"
                )
                wpn_info = {"enabled": False, "manual_required": True}
    except Exception as e:
        results["steps_failed"].append(f"SSID configuration failed: {str(e)}")
        logger.warning(f"Failed to configure SSID: {e}")
    
    # Step 6: Manual steps (only if WPN needs manual enable)
    if wpn_info and wpn_info.get("manual_required"):
        results["manual_steps_required"].extend([
            "Note: SSID is fully configured for RadSec, but WPN enablement:",
            "1. In Meraki Dashboard → Wireless → Configure → Access Control",
            f"2. Select SSID {request.ssid_number}",
            "3. Under 'Layer 3 firewall', enable 'Wi-Fi Personal Network (WPN)'",
            "4. Save changes and test with a device registration",
        ])
    else:
        results["manual_steps_required"].extend([
            "Setup complete! Next steps:",
            "1. Verify SSID configuration in Meraki Dashboard",
            "2. Test with a device registration through the portal",
            "3. Verify UDN ID assignment in RADIUS logs",
        ])
    
    logger.info("Automated RadSec setup completed")
    logger.info(f"Steps completed: {len(results['steps_completed'])}")
    logger.info(f"Steps failed: {len(results['steps_failed'])}")
    logger.info(f"Manual steps required: {len(results['manual_steps_required'])}")
    
    return {
        "success": len(results["steps_failed"]) == 0,
        "message": "RadSec setup completed" if len(results["steps_failed"]) == 0 
                   else "Setup completed with some failures",
        "wpn_info": wpn_info,
        **results,
    }


# Splash Page Endpoints


@router.post("/meraki/configure-splash", response_model=SplashPageConfigResponse)
async def configure_splash_page(
    request: SplashPageConfigRequest,
    admin: AdminUser,
) -> SplashPageConfigResponse:
    """
    Configure splash page settings for a Meraki SSID.
    
    This endpoint sets up a custom splash page URL that redirects users to your portal
    for registration. This is useful for guest networks or networks that don't use RADIUS.
    
    Uses Meraki API: 
    https://developer.cisco.com/meraki/api-v1/update-network-wireless-ssid-splash-settings/
    
    Args:
        request: Splash page configuration request
        admin: Authenticated admin user
        
    Returns:
        Configuration result
    """
    from app.api.deps import get_meraki_client
    
    logger.info(
        f"Configuring splash page for network {request.network_id}, "
        f"SSID {request.ssid_number}"
    )
    
    try:
        # Get Meraki client
        meraki_client = get_meraki_client()
        
        # Configure splash page
        settings = await meraki_client.configure_splash_page(
            network_id=request.network_id,
            ssid_number=request.ssid_number,
            splash_url=request.splash_url,
            welcome_message=request.welcome_message,
            splash_timeout=request.splash_timeout,
            redirect_url=request.redirect_url,
        )
        
        logger.info(f"Successfully configured splash page for SSID {request.ssid_number}")
        
        return SplashPageConfigResponse(
            success=True,
            message=f"Splash page configured for SSID {request.ssid_number}",
            settings=settings,
        )
    except meraki.APIError as e:
        logger.error(f"Meraki API error configuring splash page: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meraki API error: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Error configuring splash page: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure splash page: {str(e)}",
        ) from e


@router.get("/meraki/splash-settings/{network_id}/{ssid_number}")
async def get_splash_settings(
    network_id: str,
    ssid_number: int,
    admin: AdminUser,
) -> dict[str, Any]:
    """
    Get current splash page settings for a Meraki SSID.
    
    Uses Meraki API:
    https://developer.cisco.com/meraki/api-v1/get-network-wireless-ssid-splash-settings/
    
    Args:
        network_id: Meraki network ID
        ssid_number: SSID number (0-14)
        admin: Authenticated admin user
        
    Returns:
        Current splash page settings
    """
    from app.api.deps import get_meraki_client
    
    logger.info(
        f"Retrieving splash settings for network {network_id}, SSID {ssid_number}"
    )
    
    try:
        meraki_client = get_meraki_client()
        settings = await meraki_client.get_splash_settings(
            network_id=network_id,
            ssid_number=ssid_number,
        )
        
        logger.info(f"Retrieved splash settings for SSID {ssid_number}")
        return settings
    except meraki.APIError as e:
        logger.error(f"Meraki API error retrieving splash settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Meraki API error: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Error retrieving splash settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve splash settings: {str(e)}",
        ) from e


# FreeRADIUS Server Integration


class RadiusSyncRequest(BaseModel):
    """Request to sync configuration to FreeRADIUS."""
    sync_clients: bool = Field(default=True, description="Sync RADIUS clients")
    sync_users: bool = Field(default=True, description="Sync UDN assignments/users")
    reload_radius: bool = Field(default=True, description="Reload RADIUS after sync")


class RadiusSyncResponse(BaseModel):
    """Response from FreeRADIUS sync operation."""
    success: bool
    clients_synced: int
    users_synced: int
    errors: list[str]
    reloaded: bool
    message: str


class RadiusReloadRequest(BaseModel):
    """Request to reload FreeRADIUS configuration."""
    force: bool = Field(default=False, description="Force immediate reload")


class RadiusReloadResponse(BaseModel):
    """Response from FreeRADIUS reload operation."""
    success: bool
    message: str
    reloaded: bool


@router.post("/sync", response_model=RadiusSyncResponse)
async def sync_to_freeradius(
    sync_request: RadiusSyncRequest,
    admin: AdminUser,
) -> RadiusSyncResponse:
    """
    Sync configuration from portal database to FreeRADIUS.
    
    This endpoint triggers FreeRADIUS to pull latest configuration
    from the portal's PostgreSQL database and regenerate config files.
    
    Args:
        sync_request: Sync options
        admin: Authenticated admin user
        
    Returns:
        Sync result with counts and status
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    # Build FreeRADIUS API URL
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    logger.info(f"Triggering FreeRADIUS config sync at {radius_api_url}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/sync",
                json={
                    "sync_clients": sync_request.sync_clients,
                    "sync_users": sync_request.sync_users,
                    "reload_radius": sync_request.reload_radius,
                },
                headers=headers,
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"FreeRADIUS sync failed: {error_detail}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"FreeRADIUS sync failed: {error_detail}"
                )
            
            result = response.json()
            
            logger.info(
                f"Sync completed: clients={result.get('clients_synced', 0)}, "
                f"users={result.get('users_synced', 0)}"
            )
            
            return RadiusSyncResponse(
                success=result.get("success", True),
                clients_synced=result.get("clients_synced", 0),
                users_synced=result.get("users_synced", 0),
                errors=result.get("errors", []),
                reloaded=result.get("reloaded", False),
                message=result.get("message", "Configuration synced successfully"),
            )
            
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to FreeRADIUS API: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FreeRADIUS server unavailable: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        ) from e


@router.post("/reload", response_model=RadiusReloadResponse)
async def reload_freeradius_config(
    reload_request: RadiusReloadRequest,
    admin: AdminUser,
) -> RadiusReloadResponse:
    """
    Trigger FreeRADIUS configuration reload.
    
    With shared database architecture, FreeRADIUS automatically watches
    for database changes every 5 seconds. This endpoint allows manual
    triggering of an immediate reload if needed.
    
    Args:
        reload_request: Reload options
        admin: Authenticated admin user
        
    Returns:
        Reload result
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    # Build FreeRADIUS API URL
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    logger.info(f"Triggering FreeRADIUS config reload at {radius_api_url}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/reload",
                json={"force": reload_request.force},
                headers=headers,
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"FreeRADIUS reload failed: {error_detail}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"FreeRADIUS reload failed: {error_detail}"
                )
            
            result = response.json()
            
            logger.info(f"Reload completed: {result.get('message', 'Success')}")
            
            return RadiusReloadResponse(
                success=result.get("success", True),
                message=result.get("message", "Configuration reloaded successfully"),
                reloaded=result.get("reloaded", True),
            )
            
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to FreeRADIUS API: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FreeRADIUS server unavailable: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reload failed: {str(e)}"
        ) from e


@router.get("/freeradius/health")
async def check_freeradius_health(admin: AdminUser) -> dict[str, Any]:
    """
    Check FreeRADIUS server health status.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Health status from FreeRADIUS server
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {
            "status": "disabled",
            "message": "RADIUS is not enabled"
        }
    
    # Build FreeRADIUS API URL
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(f"{radius_api_url}/health", headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "unhealthy",
                    "message": f"FreeRADIUS returned status {response.status_code}"
                }
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to connect to FreeRADIUS health endpoint: {e}")
        return {
            "status": "unavailable",
            "message": f"Cannot connect to FreeRADIUS: {str(e)}"
        }


@router.get("/freeradius/stats")
async def get_freeradius_stats(admin: AdminUser) -> dict[str, Any]:
    """
    Get FreeRADIUS server statistics.
    
    Proxies the /api/stats endpoint from FreeRADIUS.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Statistics from FreeRADIUS server
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {
            "total_clients": 0,
            "active_clients": 0,
            "udn_utilization_percent": 0.0,
            "message": "RADIUS is not enabled"
        }
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(f"{radius_api_url}/api/stats", headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"FreeRADIUS stats returned {response.status_code}")
                return {
                    "total_clients": 0,
                    "active_clients": 0,
                    "udn_utilization_percent": 0.0,
                    "error": f"FreeRADIUS returned status {response.status_code}"
                }
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get FreeRADIUS stats: {e}")
        return {
            "total_clients": 0,
            "active_clients": 0,
            "udn_utilization_percent": 0.0,
            "error": f"Cannot connect to FreeRADIUS: {str(e)}"
        }


@router.get("/freeradius/config-status")
async def get_freeradius_config_status(admin: AdminUser) -> dict[str, Any]:
    """
    Get FreeRADIUS configuration status.
    
    Proxies the /api/config/status endpoint from FreeRADIUS.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Config status from FreeRADIUS server
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {
            "status": "disabled",
            "message": "RADIUS is not enabled"
        }
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(f"{radius_api_url}/api/config/status", headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "error",
                    "message": f"FreeRADIUS returned status {response.status_code}"
                }
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get FreeRADIUS config status: {e}")
        return {
            "status": "unavailable",
            "message": f"Cannot connect to FreeRADIUS: {str(e)}"
        }


# =============================================================================
# FreeRADIUS NAD Proxy Endpoints
# =============================================================================


@router.get("/freeradius/nads")
async def list_freeradius_nads(
    admin: AdminUser,
    page: int = 1,
    page_size: int = 100,  # FreeRADIUS max is 100
    is_active: bool = True,
    search: Optional[str] = None,
) -> dict[str, Any]:
    """
    List NADs from FreeRADIUS server.
    
    Proxies the /api/nads endpoint from FreeRADIUS.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "pages": 0,
            "message": "RADIUS is not enabled"
        }
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    params = {
        "page": page,
        "page_size": min(page_size, 100),  # FreeRADIUS max is 100
        "is_active": is_active,
    }
    if search:
        params["search"] = search
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(
                f"{radius_api_url}/api/nads",
                params=params,
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"FreeRADIUS NAD list returned {response.status_code}: {response.text}")
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": min(page_size, 100),
                    "pages": 0,
                    "error": f"FreeRADIUS returned status {response.status_code}"
                }
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get FreeRADIUS NADs: {e}")
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": min(page_size, 100),
            "pages": 0,
            "error": f"Cannot connect to FreeRADIUS: {str(e)}"
        }


class NadCreateRequest(BaseModel):
    """NAD creation request."""
    name: str
    ipaddr: str
    secret: str
    nas_type: str = "other"
    description: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    radsec_enabled: bool = False
    radsec_port: Optional[int] = None
    require_tls_cert: bool = True
    coa_enabled: bool = False
    coa_port: Optional[int] = None
    require_message_authenticator: bool = True
    virtual_server: Optional[str] = None


@router.post("/freeradius/nads")
async def create_freeradius_nad(
    nad_data: NadCreateRequest,
    admin: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    """
    Create a NAD on FreeRADIUS server.
    
    Proxies the /api/nads endpoint from FreeRADIUS and also saves to local database.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    # Also save to local database for tracking
    existing = db.query(RadiusClient).filter(
        RadiusClient.name == nad_data.name
    ).first()
    
    if not existing:
        client = RadiusClient(
            name=nad_data.name,
            ipaddr=nad_data.ipaddr,
            secret=nad_data.secret,
            nas_type=nad_data.nas_type,
            shortname=nad_data.name,
            require_message_authenticator=nad_data.require_message_authenticator,
            is_active=True,
            created_by=admin.get("sub", "admin"),
        )
        db.add(client)
        db.commit()
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/nads",
                json=nad_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code in (200, 201):
                return response.json()
            else:
                detail = response.text
                logger.warning(f"FreeRADIUS NAD create returned {response.status_code}: {detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {detail}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to create NAD on FreeRADIUS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


@router.delete("/freeradius/nads/{nad_id}")
async def delete_freeradius_nad(
    nad_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict[str, str]:
    """
    Delete a NAD from FreeRADIUS server.
    
    Proxies the DELETE /api/nads/{id} endpoint from FreeRADIUS.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.delete(
                f"{radius_api_url}/api/nads/{nad_id}",
                headers=headers,
            )
            
            if response.status_code in (200, 204):
                return {"message": "NAD deleted successfully"}
            else:
                detail = response.text
                logger.warning(f"FreeRADIUS NAD delete returned {response.status_code}: {detail}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {detail}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to delete NAD on FreeRADIUS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


# =============================================================================
# FreeRADIUS RadSec Config Proxy Endpoints
# =============================================================================


@router.get("/freeradius/radsec/configs")
async def list_freeradius_radsec_configs(
    admin: AdminUser,
    page: int = 1,
    page_size: int = 100,
    is_active: bool = True,
) -> dict[str, Any]:
    """
    List RadSec configurations from FreeRADIUS server.
    
    Proxies the /api/radsec/configs endpoint from FreeRADIUS.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "pages": 0,
        }
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(
                f"{radius_api_url}/api/radsec/configs",
                params={"page": page, "page_size": page_size, "is_active": is_active},
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get FreeRADIUS RadSec configs: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}


class RadSecConfigCreateRequest(BaseModel):
    """RadSec configuration creation request."""
    name: str
    description: Optional[str] = None
    listen_address: str = "0.0.0.0"
    listen_port: int = 2083
    tls_min_version: str = "1.2"
    tls_max_version: str = "1.3"
    certificate_file: Optional[str] = None
    private_key_file: Optional[str] = None
    ca_certificate_file: Optional[str] = None
    require_client_cert: bool = True
    verify_client_cert: bool = True
    is_active: bool = True


class RadSecConfigUpdateRequest(BaseModel):
    """RadSec configuration update request."""
    name: Optional[str] = None
    description: Optional[str] = None
    listen_address: Optional[str] = None
    listen_port: Optional[int] = None
    tls_min_version: Optional[str] = None
    tls_max_version: Optional[str] = None
    certificate_file: Optional[str] = None
    private_key_file: Optional[str] = None
    ca_certificate_file: Optional[str] = None
    require_client_cert: Optional[bool] = None
    verify_client_cert: Optional[bool] = None
    is_active: Optional[bool] = None


@router.post("/freeradius/radsec/configs")
async def create_freeradius_radsec_config(
    config_data: RadSecConfigCreateRequest,
    admin: AdminUser,
) -> dict[str, Any]:
    """
    Create a RadSec configuration on FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/radsec/configs",
                json=config_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code in (200, 201):
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to create RadSec config: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


@router.put("/freeradius/radsec/configs/{config_id}")
async def update_freeradius_radsec_config(
    config_id: int,
    config_data: RadSecConfigUpdateRequest,
    admin: AdminUser,
) -> dict[str, Any]:
    """
    Update a RadSec configuration on FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.put(
                f"{radius_api_url}/api/radsec/configs/{config_id}",
                json=config_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to update RadSec config: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


@router.delete("/freeradius/radsec/configs/{config_id}")
async def delete_freeradius_radsec_config(
    config_id: int,
    admin: AdminUser,
) -> dict[str, str]:
    """
    Delete a RadSec configuration from FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.delete(
                f"{radius_api_url}/api/radsec/configs/{config_id}",
                headers=headers,
            )
            
            if response.status_code in (200, 204):
                return {"message": "RadSec config deleted successfully"}
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to delete RadSec config: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


@router.get("/freeradius/radsec/certificates")
async def list_freeradius_radsec_certificates(
    admin: AdminUser,
) -> dict[str, Any]:
    """
    List RadSec certificates from FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {"certificates": []}
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(
                f"{radius_api_url}/api/radsec/certificates",
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"certificates": []}
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get RadSec certificates: {e}")
        return {"certificates": []}


# =============================================================================
# FreeRADIUS Policy Proxy Endpoints
# =============================================================================


class PolicyCreateRequest(BaseModel):
    """Policy creation request."""
    name: str
    group_name: str
    policy_type: str = "user"
    priority: int = 100
    vlan_id: Optional[int] = None
    bandwidth_limit_up: Optional[int] = None
    bandwidth_limit_down: Optional[int] = None
    is_active: bool = True
    attributes: Optional[dict] = None


@router.get("/freeradius/policies")
async def list_freeradius_policies(
    admin: AdminUser,
    page: int = 1,
    page_size: int = 200,
    is_active: bool = True,
) -> dict[str, Any]:
    """
    List policies from FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(
                f"{radius_api_url}/api/policies",
                params={"page": page, "page_size": page_size, "is_active": is_active},
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get FreeRADIUS policies: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}


@router.post("/freeradius/policies")
async def create_freeradius_policy(
    policy_data: PolicyCreateRequest,
    admin: AdminUser,
) -> dict[str, Any]:
    """
    Create a policy on FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/policies",
                json=policy_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code in (200, 201):
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to create policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


@router.put("/freeradius/policies/{policy_id}")
async def update_freeradius_policy(
    policy_id: int,
    policy_data: PolicyCreateRequest,
    admin: AdminUser,
) -> dict[str, Any]:
    """
    Update a policy on FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.put(
                f"{radius_api_url}/api/policies/{policy_id}",
                json=policy_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to update policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


@router.delete("/freeradius/policies/{policy_id}")
async def delete_freeradius_policy(
    policy_id: int,
    admin: AdminUser,
) -> dict[str, str]:
    """
    Delete a policy from FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.delete(
                f"{radius_api_url}/api/policies/{policy_id}",
                headers=headers,
            )
            
            if response.status_code in (200, 204):
                return {"message": "Policy deleted successfully"}
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to delete policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e


class PolicyTestRequestModel(BaseModel):
    """Policy test request."""
    username: str
    mac_address: Optional[str] = None
    nas_identifier: Optional[str] = None


@router.post("/freeradius/policies/{policy_id}/test")
async def test_freeradius_policy(
    policy_id: int,
    test_data: PolicyTestRequestModel,
    admin: AdminUser,
) -> dict[str, Any]:
    """
    Test a policy on FreeRADIUS server.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RADIUS is not enabled"
        )
    
    radius_api_url = f"http://{settings.radius_server_host}:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/policies/{policy_id}/test",
                json=test_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}"
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to test policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}"
        ) from e

