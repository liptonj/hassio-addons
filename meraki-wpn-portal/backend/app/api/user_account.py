"""User account self-service endpoints."""
import io
import logging

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import DbSession, HAClient, require_user
from app.config import get_settings
from app.core.security import (
    decrypt_passphrase,
    encrypt_passphrase,
    generate_passphrase,
    hash_password,
    verify_password,
)
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    """Request to change user password."""

    current_password: str
    new_password: str


class ChangePSKRequest(BaseModel):
    """Request to change WiFi PSK."""

    custom_passphrase: str | None = None


class ChangePSKResponse(BaseModel):
    """Response after PSK change."""

    success: bool
    new_passphrase: str
    qr_code: str
    wifi_config_string: str


def generate_wifi_qr_code(ssid: str, password: str) -> str:
    """Generate WiFi QR code as base64 data URL.
    
    Args:
        ssid: WiFi network name
        password: WiFi password
        
    Returns:
        Base64 data URL string
    """
    wifi_string = f"WIFI:T:WPA;S:{ssid};P:{password};;"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(wifi_string)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 data URL
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    import base64
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


@router.post("/user/change-password")
async def change_password(
    data: ChangePasswordRequest,
    db: DbSession,
    current_user: User = Depends(require_user),
) -> dict:
    """Allow users to change their password.
    
    Args:
        data: Password change request
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Success response
        
    Raises:
        HTTPException: If current password is incorrect or new password invalid
    """
    # Verify current password
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no password set (OAuth user)"
        )
    
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Update password
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    
    logger.info(f"Password changed for user {current_user.email}")
    
    return {"success": True, "message": "Password updated successfully"}


@router.post("/user/change-psk", response_model=ChangePSKResponse)
async def change_psk(
    data: ChangePSKRequest,
    db: DbSession,
    ha_client: HAClient,
    current_user: User = Depends(require_user),
) -> ChangePSKResponse:
    """Allow users to change their WiFi PSK.
    
    Args:
        data: PSK change request
        db: Database session
        ha_client: Home Assistant client
        current_user: Current authenticated user
        
    Returns:
        PSK change response with new credentials and QR code
        
    Raises:
        HTTPException: If user has no iPSK or PSK validation fails
    """
    if not current_user.ipsk_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no iPSK assigned"
        )
    
    settings = get_settings()
    
    # Generate or use custom passphrase
    if data.custom_passphrase:
        if len(data.custom_passphrase) < settings.psk_min_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PSK must be at least {settings.psk_min_length} characters"
            )
        if len(data.custom_passphrase) > settings.psk_max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PSK must be no more than {settings.psk_max_length} characters"
            )
        passphrase = data.custom_passphrase
    else:
        passphrase = generate_passphrase(settings.passphrase_length)
    
    # Update in Meraki/HA
    try:
        await ha_client.update_ipsk_passphrase(current_user.ipsk_id, passphrase)
    except Exception as e:
        logger.error(f"Failed to update iPSK in Meraki: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update WiFi password in system"
        ) from e
    
    # Update in database
    current_user.ipsk_passphrase_encrypted = encrypt_passphrase(passphrase)
    db.commit()
    
    # Generate new QR code
    qr_code = generate_wifi_qr_code(current_user.ssid_name or "WiFi", passphrase)
    
    logger.info(f"PSK changed for user {current_user.email}")
    
    return ChangePSKResponse(
        success=True,
        new_passphrase=passphrase,
        qr_code=qr_code,
        wifi_config_string=f"WIFI:T:WPA;S:{current_user.ssid_name};P:{passphrase};;",
    )
