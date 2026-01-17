"""CoA (Change of Authorization) and Disconnect API endpoints.

Provides functionality to:
- Send Disconnect-Request to NADs to terminate user sessions
- Send CoA-Request to NADs to modify session parameters
- Check CoA configuration status
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from radius_app.api.deps import AdminUser, DbSession
from radius_app.core.coa_config_generator import CoAClient, CoAConfigGenerator
from radius_app.db.models import RadiusClient, RadiusClientExtended

logger = logging.getLogger(__name__)

router = APIRouter()


class DisconnectRequest(BaseModel):
    """Request to disconnect a user session."""
    
    nad_id: Optional[int] = Field(None, description="NAD ID to send disconnect to")
    nad_ip: Optional[str] = Field(None, description="NAD IP address (alternative to nad_id)")
    user_name: Optional[str] = Field(None, description="User to disconnect")
    session_id: Optional[str] = Field(None, description="Acct-Session-Id to disconnect")
    calling_station_id: Optional[str] = Field(None, description="MAC address of client")
    nas_port: Optional[int] = Field(None, description="NAS port of the session")


class CoARequest(BaseModel):
    """Request to change session authorization."""
    
    nad_id: Optional[int] = Field(None, description="NAD ID to send CoA to")
    nad_ip: Optional[str] = Field(None, description="NAD IP address (alternative to nad_id)")
    user_name: Optional[str] = Field(None, description="User to modify")
    session_id: Optional[str] = Field(None, description="Acct-Session-Id to modify")
    attributes: dict = Field(default_factory=dict, description="Attributes to change")


@router.get("/api/coa/status")
async def get_coa_status(
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Get CoA configuration status.
    
    Returns:
    - Number of NADs with CoA enabled
    - CoA server configuration status
    - List of CoA-enabled NADs
    
    Args:
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        CoA status information
    """
    logger.info(f"Getting CoA status requested by {admin['sub']}")
    
    try:
        # Get NADs with CoA enabled
        coa_gen = CoAConfigGenerator()
        nads_with_coa = coa_gen.get_coa_enabled_nads(db)
        
        return {
            "enabled": True,
            "coa_port": 3799,
            "nads_with_coa": len(nads_with_coa),
            "nads": [
                {
                    "id": nad["id"],
                    "name": nad["name"],
                    "ipaddr": nad["ipaddr"],
                    "coa_port": nad["coa_port"],
                    "vendor": nad["vendor"],
                }
                for nad in nads_with_coa
            ],
        }
        
    except Exception as e:
        logger.error(f"Error getting CoA status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get CoA status",
        )


@router.post("/api/coa/disconnect")
async def send_disconnect(
    request: DisconnectRequest,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Send Disconnect-Request to terminate a user session.
    
    Per RFC 5176, a Disconnect-Request can be used to:
    - Terminate an active session immediately
    - Force a user to re-authenticate
    
    You must provide either nad_id or nad_ip, and at least one of:
    - user_name
    - session_id
    - calling_station_id
    
    Args:
        request: Disconnect request parameters
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Disconnect result (success/failure and details)
        
    Raises:
        HTTPException: 400 if invalid request
        HTTPException: 404 if NAD not found
    """
    logger.info(
        f"Disconnect request by {admin['sub']}: "
        f"user={request.user_name}, session={request.session_id}"
    )
    
    # Get NAD information
    nad_ip = request.nad_ip
    nad_port = 3799
    shared_secret = None
    
    if request.nad_id:
        # Look up NAD by ID
        client = db.execute(
            select(RadiusClient).where(RadiusClient.id == request.nad_id)
        ).scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with ID {request.nad_id} not found",
            )
        
        nad_ip = client.ipaddr
        shared_secret = client.secret
        
        # Get extended info for CoA port
        extended = db.execute(
            select(RadiusClientExtended).where(
                RadiusClientExtended.radius_client_id == client.id
            )
        ).scalar_one_or_none()
        
        if extended and extended.coa_port:
            nad_port = extended.coa_port
        
        if extended and not extended.coa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CoA is not enabled for NAD {client.name}",
            )
    elif request.nad_ip:
        # Look up NAD by IP
        client = db.execute(
            select(RadiusClient).where(RadiusClient.ipaddr == request.nad_ip)
        ).scalar_one_or_none()
        
        if client:
            shared_secret = client.secret
            extended = db.execute(
                select(RadiusClientExtended).where(
                    RadiusClientExtended.radius_client_id == client.id
                )
            ).scalar_one_or_none()
            
            if extended and extended.coa_port:
                nad_port = extended.coa_port
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with IP {request.nad_ip} not found",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide nad_id or nad_ip",
        )
    
    if not shared_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine NAD shared secret",
        )
    
    # Validate we have session identification
    if not any([request.user_name, request.session_id, request.calling_station_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide user_name, session_id, or calling_station_id",
        )
    
    # Send disconnect request
    try:
        coa_client = CoAClient()
        result = await coa_client.send_disconnect_request(
            nad_ip=nad_ip,
            nad_port=nad_port,
            shared_secret=shared_secret,
            user_name=request.user_name,
            session_id=request.session_id,
            nas_port=request.nas_port,
            calling_station_id=request.calling_station_id,
        )
        
        if result["success"]:
            logger.info(f"✅ Disconnect successful for {request.user_name or request.session_id}")
        else:
            logger.warning(f"Disconnect failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error sending disconnect: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send disconnect request: {e}",
        )


@router.post("/api/coa/change")
async def send_coa_change(
    request: CoARequest,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Send CoA-Request to change session parameters.
    
    Per RFC 5176, a CoA-Request can be used to modify:
    - Session timeouts
    - Bandwidth limits
    - VLAN assignments
    - QoS policies
    
    The attributes dictionary should contain RADIUS attribute names
    and their new values.
    
    Args:
        request: CoA request parameters
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        CoA result (success/failure and details)
        
    Raises:
        HTTPException: 400 if invalid request
        HTTPException: 404 if NAD not found
    """
    logger.info(
        f"CoA change request by {admin['sub']}: "
        f"user={request.user_name}, attrs={list(request.attributes.keys())}"
    )
    
    # Get NAD information (same logic as disconnect)
    nad_ip = request.nad_ip
    nad_port = 3799
    shared_secret = None
    
    if request.nad_id:
        client = db.execute(
            select(RadiusClient).where(RadiusClient.id == request.nad_id)
        ).scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with ID {request.nad_id} not found",
            )
        
        nad_ip = client.ipaddr
        shared_secret = client.secret
        
        extended = db.execute(
            select(RadiusClientExtended).where(
                RadiusClientExtended.radius_client_id == client.id
            )
        ).scalar_one_or_none()
        
        if extended and extended.coa_port:
            nad_port = extended.coa_port
        
        if extended and not extended.coa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CoA is not enabled for NAD {client.name}",
            )
    elif request.nad_ip:
        client = db.execute(
            select(RadiusClient).where(RadiusClient.ipaddr == request.nad_ip)
        ).scalar_one_or_none()
        
        if client:
            shared_secret = client.secret
            extended = db.execute(
                select(RadiusClientExtended).where(
                    RadiusClientExtended.radius_client_id == client.id
                )
            ).scalar_one_or_none()
            
            if extended and extended.coa_port:
                nad_port = extended.coa_port
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with IP {request.nad_ip} not found",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide nad_id or nad_ip",
        )
    
    if not shared_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine NAD shared secret",
        )
    
    if not any([request.user_name, request.session_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide user_name or session_id",
        )
    
    if not request.attributes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide attributes to change",
        )
    
    # Send CoA request
    try:
        coa_client = CoAClient()
        result = await coa_client.send_coa_request(
            nad_ip=nad_ip,
            nad_port=nad_port,
            shared_secret=shared_secret,
            user_name=request.user_name,
            session_id=request.session_id,
            attributes=request.attributes,
        )
        
        if result["success"]:
            logger.info(f"✅ CoA successful for {request.user_name or request.session_id}")
        else:
            logger.warning(f"CoA failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error sending CoA: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send CoA request: {e}",
        )


class GroupPolicyCoARequest(BaseModel):
    """Request to change user's group policy via CoA.
    
    This is the typical workflow for captive portal authentication:
    1. User connects to guest SSID
    2. User is assigned unregistered_group_policy (restricted access)
    3. User completes captive portal authentication
    4. CoA is sent to change to registered_group_policy (full access)
    """
    
    nad_id: Optional[int] = Field(None, description="NAD ID to send CoA to")
    nad_ip: Optional[str] = Field(None, description="NAD IP address (alternative to nad_id)")
    user_name: Optional[str] = Field(None, description="User to modify")
    session_id: Optional[str] = Field(None, description="Acct-Session-Id to modify")
    calling_station_id: Optional[str] = Field(None, description="MAC address of client")
    
    # Group Policy - Vendor-specific
    group_policy: str = Field(..., description="New group policy to apply")
    vendor: str = Field(
        default="meraki",
        description="Vendor type: meraki, cisco_aireos, cisco_ise, aruba"
    )
    
    # Optional: URL redirect removal (for captive portal post-auth)
    remove_url_redirect: bool = Field(
        default=True,
        description="Remove URL redirect after applying new policy"
    )


@router.post("/api/coa/group-policy")
async def send_group_policy_coa(
    request: GroupPolicyCoARequest,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Send CoA to change a user's group policy.
    
    This is the typical workflow for captive portal authentication:
    1. User connects and gets unregistered policy (url-redirect active)
    2. User completes portal registration/login
    3. This endpoint is called to apply registered policy (full access)
    
    Vendor-specific attribute mapping:
    - meraki: Filter-Id=<policy>
    - cisco_aireos: Cisco-AVPair="air-group-policy-name=<policy>"
    - cisco_ise: Cisco-AVPair="ACS:CiscoSecure-Group-Id=<policy>"
    - aruba: Aruba-User-Role=<policy>
    
    Args:
        request: Group policy change request
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        CoA result (success/failure and details)
    """
    logger.info(
        f"Group policy CoA request by {admin['sub']}: "
        f"user={request.user_name}, policy={request.group_policy}, vendor={request.vendor}"
    )
    
    # Build vendor-specific attributes
    attributes = {}
    vendor = request.vendor.lower()
    
    if vendor == "meraki":
        # Meraki uses Filter-Id for group policy
        attributes["Filter-Id"] = request.group_policy
        if request.remove_url_redirect:
            # Remove URL redirect by sending empty value
            attributes["Cisco-AVPair"] = ["url-redirect=", "url-redirect-acl="]
    elif vendor == "cisco_aireos":
        # Cisco AireOS uses air-group-policy-name
        avpairs = [f"air-group-policy-name={request.group_policy}"]
        if request.remove_url_redirect:
            avpairs.extend(["url-redirect=", "url-redirect-acl="])
        attributes["Cisco-AVPair"] = avpairs
    elif vendor == "cisco_ise":
        # Cisco ISE uses ACS attributes
        avpairs = [f"ACS:CiscoSecure-Group-Id={request.group_policy}"]
        if request.remove_url_redirect:
            avpairs.extend(["url-redirect=", "url-redirect-acl="])
        attributes["Cisco-AVPair"] = avpairs
    elif vendor == "aruba":
        # Aruba uses Aruba-User-Role
        attributes["Aruba-User-Role"] = request.group_policy
    else:
        # Default: Generic Cisco-AVPair
        attributes["Cisco-AVPair"] = f"group-policy-name={request.group_policy}"
    
    # Get NAD information
    nad_ip = request.nad_ip
    nad_port = 3799
    shared_secret = None
    
    if request.nad_id:
        client = db.execute(
            select(RadiusClient).where(RadiusClient.id == request.nad_id)
        ).scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with ID {request.nad_id} not found",
            )
        
        nad_ip = client.ipaddr
        shared_secret = client.secret
        
        extended = db.execute(
            select(RadiusClientExtended).where(
                RadiusClientExtended.radius_client_id == client.id
            )
        ).scalar_one_or_none()
        
        if extended and extended.coa_port:
            nad_port = extended.coa_port
        
        if extended and not extended.coa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CoA is not enabled for NAD {client.name}",
            )
    elif request.nad_ip:
        client = db.execute(
            select(RadiusClient).where(RadiusClient.ipaddr == request.nad_ip)
        ).scalar_one_or_none()
        
        if client:
            shared_secret = client.secret
            extended = db.execute(
                select(RadiusClientExtended).where(
                    RadiusClientExtended.radius_client_id == client.id
                )
            ).scalar_one_or_none()
            
            if extended and extended.coa_port:
                nad_port = extended.coa_port
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with IP {request.nad_ip} not found",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide nad_id or nad_ip",
        )
    
    if not shared_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine NAD shared secret",
        )
    
    if not any([request.user_name, request.session_id, request.calling_station_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide user_name, session_id, or calling_station_id",
        )
    
    # Send CoA request
    try:
        coa_client = CoAClient()
        result = await coa_client.send_coa_request(
            nad_ip=nad_ip,
            nad_port=nad_port,
            shared_secret=shared_secret,
            user_name=request.user_name,
            session_id=request.session_id,
            attributes=attributes,
        )
        
        if result["success"]:
            logger.info(
                f"✅ Group policy CoA successful: "
                f"{request.user_name or request.session_id} -> {request.group_policy}"
            )
        else:
            logger.warning(f"Group policy CoA failed: {result.get('error', 'Unknown error')}")
        
        return {
            **result,
            "applied_policy": request.group_policy,
            "vendor": request.vendor,
            "attributes_sent": attributes,
        }
        
    except Exception as e:
        logger.error(f"Error sending group policy CoA: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send CoA request: {e}",
        )


class SgtCoARequest(BaseModel):
    """Request to change user's Security Group Tag (SGT) via CoA.
    
    Used for Cisco TrustSec and Meraki Adaptive Policy network segmentation.
    SGT is dynamically assigned to control what network resources a user can access.
    """
    
    nad_id: Optional[int] = Field(None, description="NAD ID to send CoA to")
    nad_ip: Optional[str] = Field(None, description="NAD IP address (alternative to nad_id)")
    user_name: Optional[str] = Field(None, description="User to modify")
    session_id: Optional[str] = Field(None, description="Acct-Session-Id to modify")
    calling_station_id: Optional[str] = Field(None, description="MAC address of client")
    
    # SGT assignment
    sgt_value: int = Field(
        ...,
        ge=0,
        le=65535,
        description="Security Group Tag value (0-65535)"
    )
    sgt_name: Optional[str] = Field(
        None,
        description="Human-readable SGT name (for logging)"
    )


@router.post("/api/coa/sgt")
async def send_sgt_coa(
    request: SgtCoARequest,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Send CoA to change a user's Security Group Tag (SGT).
    
    Used for Cisco TrustSec and Meraki Adaptive Policy to dynamically
    change network segmentation for a user session.
    
    The SGT is sent as: Cisco-AVPair="cts:security-group-tag=XXXX-00"
    where XXXX is the hex representation of the SGT value.
    
    Example SGT values:
    - 0 = Unknown
    - 2 = TrustSec_Devices (default)
    - Custom values: 100-65535 for your security groups
    
    Args:
        request: SGT change request
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        CoA result (success/failure and details)
    """
    # Convert SGT to hex format
    sgt_hex = f"{request.sgt_value:04x}-00"
    sgt_display = f"{request.sgt_name} ({request.sgt_value})" if request.sgt_name else str(request.sgt_value)
    
    logger.info(
        f"SGT CoA request by {admin['sub']}: "
        f"user={request.user_name}, SGT={sgt_display}"
    )
    
    # Build attributes
    attributes = {
        "Cisco-AVPair": f"cts:security-group-tag={sgt_hex}"
    }
    
    # Get NAD information
    nad_ip = request.nad_ip
    nad_port = 3799
    shared_secret = None
    
    if request.nad_id:
        client = db.execute(
            select(RadiusClient).where(RadiusClient.id == request.nad_id)
        ).scalar_one_or_none()
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with ID {request.nad_id} not found",
            )
        
        nad_ip = client.ipaddr
        shared_secret = client.secret
        
        extended = db.execute(
            select(RadiusClientExtended).where(
                RadiusClientExtended.radius_client_id == client.id
            )
        ).scalar_one_or_none()
        
        if extended and extended.coa_port:
            nad_port = extended.coa_port
        
        if extended and not extended.coa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CoA is not enabled for NAD {client.name}",
            )
    elif request.nad_ip:
        client = db.execute(
            select(RadiusClient).where(RadiusClient.ipaddr == request.nad_ip)
        ).scalar_one_or_none()
        
        if client:
            shared_secret = client.secret
            extended = db.execute(
                select(RadiusClientExtended).where(
                    RadiusClientExtended.radius_client_id == client.id
                )
            ).scalar_one_or_none()
            
            if extended and extended.coa_port:
                nad_port = extended.coa_port
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NAD with IP {request.nad_ip} not found",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide nad_id or nad_ip",
        )
    
    if not shared_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not determine NAD shared secret",
        )
    
    if not any([request.user_name, request.session_id, request.calling_station_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide user_name, session_id, or calling_station_id",
        )
    
    # Send CoA request
    try:
        coa_client = CoAClient()
        result = await coa_client.send_coa_request(
            nad_ip=nad_ip,
            nad_port=nad_port,
            shared_secret=shared_secret,
            user_name=request.user_name,
            session_id=request.session_id,
            attributes=attributes,
        )
        
        if result["success"]:
            logger.info(
                f"✅ SGT CoA successful: "
                f"{request.user_name or request.session_id} -> SGT {sgt_display}"
            )
        else:
            logger.warning(f"SGT CoA failed: {result.get('error', 'Unknown error')}")
        
        return {
            **result,
            "applied_sgt": request.sgt_value,
            "sgt_name": request.sgt_name,
            "sgt_hex": sgt_hex,
            "attributes_sent": attributes,
        }
        
    except Exception as e:
        logger.error(f"Error sending SGT CoA: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send CoA request: {e}",
        )


@router.post("/api/coa/regenerate-config")
async def regenerate_coa_config(
    admin: AdminUser,
    db: DbSession,
    listen_address: str = Query("*", description="Listen address"),
    coa_port: int = Query(3799, description="CoA port"),
) -> dict:
    """
    Regenerate CoA server configuration from database.
    
    Creates/updates the CoA virtual server configuration based on
    the current NAD settings in the database.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        listen_address: IP to listen on (default: all)
        coa_port: Port for CoA (default: 3799)
        
    Returns:
        Regeneration result
    """
    logger.info(f"Regenerating CoA config requested by {admin['sub']}")
    
    try:
        coa_gen = CoAConfigGenerator()
        output_path = coa_gen.generate_coa_conf(
            db=db,
            listen_address=listen_address,
            coa_port=coa_port,
        )
        
        return {
            "success": True,
            "message": "CoA configuration regenerated",
            "config_path": str(output_path),
        }
        
    except Exception as e:
        logger.error(f"Error regenerating CoA config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate CoA configuration",
        )
