"""Device registration and management endpoints."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from user_agents import parse  # type: ignore[import-untyped]

from app.api.deps import DbSession, require_admin, require_user
from app.db.models import DeviceRegistration, User

logger = logging.getLogger(__name__)

router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    """Request to register a device."""

    mac_address: str
    user_agent: str
    device_name: str | None = None


class DeviceRegisterResponse(BaseModel):
    """Response after device registration."""

    device_id: int
    device_type: str
    device_os: str
    device_os_version: str
    browser_name: str
    device_model: str
    device_vendor: str
    registered: bool


class DeviceInfoResponse(BaseModel):
    """Device information response."""

    id: int
    mac_address: str
    device_type: str
    device_os: str
    device_model: str
    device_name: str | None
    registered_at: str
    last_seen_at: str | None
    is_active: bool


def detect_device_type(ua) -> str:
    """Detect device type from parsed User-Agent.
    
    Args:
        ua: Parsed User-Agent object
        
    Returns:
        Device type string: phone, tablet, laptop, desktop, or other
    """
    if ua.is_mobile:
        return "phone"
    if ua.is_tablet:
        return "tablet"
    if ua.is_pc:
        if "macintosh" in ua.os.family.lower():
            return "laptop"
        return "desktop"
    return "other"


@router.post("/devices/register", response_model=DeviceRegisterResponse)
async def register_device(
    request: Request,
    data: DeviceRegisterRequest,
    db: DbSession,
    current_user: User = Depends(require_user),
) -> DeviceRegisterResponse:
    """Register a device with full User-Agent parsing.
    
    Args:
        request: FastAPI request object
        data: Device registration data
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Device registration response
        
    Raises:
        HTTPException: If device already registered or parsing fails
    """
    logger.info(f"Registering device for user {current_user.email}: {data.mac_address}")
    
    # Check if device already registered
    existing = db.query(DeviceRegistration).filter(
        DeviceRegistration.user_id == current_user.id,
        DeviceRegistration.mac_address == data.mac_address,
    ).first()
    
    if existing and existing.is_active:
        logger.info(f"Device {data.mac_address} already registered")
        return DeviceRegisterResponse(
            device_id=existing.id,
            device_type=existing.device_type,
            device_os=existing.device_os,
            device_os_version=existing.device_os_version or "",
            browser_name=existing.browser_name or "",
            device_model=existing.device_model or "",
            device_vendor=existing.device_vendor or "",
            registered=True,
        )
    
    # Parse User-Agent
    ua = parse(data.user_agent)
    
    # Create device registration
    device = DeviceRegistration(
        user_id=current_user.id,
        mac_address=data.mac_address,
        device_type=detect_device_type(ua),
        device_os=ua.os.family.lower() if ua.os.family else "unknown",
        device_os_version=ua.os.version_string or "",
        browser_name=ua.browser.family or "unknown",
        browser_version=ua.browser.version_string or "",
        device_vendor=ua.device.brand or "",
        device_model=ua.device.model or "",
        user_agent=data.user_agent,
        device_name=data.device_name,
        last_ip_address=request.client.host if request.client else None,
        registered_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        is_active=True,
    )
    
    db.add(device)
    db.commit()
    db.refresh(device)
    
    logger.info(f"Device {data.mac_address} registered successfully")
    
    return DeviceRegisterResponse(
        device_id=device.id,
        device_type=device.device_type,
        device_os=device.device_os,
        device_os_version=device.device_os_version or "",
        browser_name=device.browser_name or "",
        device_model=device.device_model or "",
        device_vendor=device.device_vendor or "",
        registered=True,
    )


@router.get("/detect-device")
async def detect_device_from_ua(request: Request) -> dict:
    """Quick device detection from User-Agent header.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dictionary with device detection results
    """
    ua_string = request.headers.get("user-agent", "")
    ua = parse(ua_string)
    
    return {
        "device_type": detect_device_type(ua),
        "device_os": ua.os.family.lower() if ua.os.family else "unknown",
        "is_mobile": ua.is_mobile,
        "is_tablet": ua.is_tablet,
        "browser": ua.browser.family or "unknown",
    }


@router.get("/user/devices", response_model=list[DeviceInfoResponse])
async def get_user_devices(
    db: DbSession,
    current_user: User = Depends(require_user),
) -> list[DeviceInfoResponse]:
    """Get list of user's registered devices.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List of user's devices
    """
    devices = db.query(DeviceRegistration).filter(
        DeviceRegistration.user_id == current_user.id,
        DeviceRegistration.is_active == True,  # noqa: E712
    ).all()
    
    return [
        DeviceInfoResponse(
            id=d.id,
            mac_address=d.mac_address,
            device_type=d.device_type,
            device_os=d.device_os,
            device_model=d.device_model or "",
            device_name=d.device_name,
            registered_at=d.registered_at.isoformat(),
            last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
            is_active=d.is_active,
        )
        for d in devices
    ]


@router.get("/admin/devices", response_model=dict)
async def list_all_devices(
    db: DbSession,
    admin: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """Get list of all registered devices (admin only).
    
    Args:
        db: Database session
        admin: Admin user
        skip: Pagination offset
        limit: Max results
        
    Returns:
        Dict with total count and list of devices with user info
    """
    from sqlalchemy import select, func, join
    
    # Get total count
    total = db.execute(
        select(func.count(DeviceRegistration.id))
        .where(DeviceRegistration.is_active == True)  # noqa: E712
    ).scalar_one()
    
    # Get devices with user info
    devices_query = (
        select(DeviceRegistration, User)
        .join(User, DeviceRegistration.user_id == User.id)
        .where(DeviceRegistration.is_active == True)  # noqa: E712
        .order_by(DeviceRegistration.registered_at.desc())
        .offset(skip)
        .limit(limit)
    )
    
    results = db.execute(devices_query).all()
    
    return {
        "success": True,
        "total": total,
        "devices": [
            {
                "id": device.id,
                "mac_address": device.mac_address,
                "device_type": device.device_type,
                "device_os": device.device_os,
                "device_model": device.device_model or "",
                "device_name": device.device_name,
                "registered_at": device.registered_at.isoformat(),
                "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
                "is_active": device.is_active,
                "user_email": user.email,
                "user_name": user.name,
                "user_unit": user.unit,
            }
            for device, user in results
        ],
    }


@router.delete("/user/devices/{mac}")
async def remove_user_device(
    mac: str,
    db: DbSession,
    current_user: User = Depends(require_user),
) -> dict:
    """Unregister a device.
    
    Args:
        mac: MAC address of device to remove
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success response
        
    Raises:
        HTTPException: If device not found
    """
    device = db.query(DeviceRegistration).filter(
        DeviceRegistration.user_id == current_user.id,
        DeviceRegistration.mac_address == mac,
    ).first()
    
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )
    
    device.is_active = False
    db.commit()
    
    logger.info(f"Device {mac} removed for user {current_user.email}")
    
    return {"success": True, "message": "Device removed"}
