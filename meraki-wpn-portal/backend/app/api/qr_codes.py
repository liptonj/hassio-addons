"""QR code generation and sharing endpoints."""
import base64
import io
import logging
import secrets
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import DbSession, require_user
from app.config import get_settings
from app.core.security import decrypt_passphrase
from app.db.models import User, WifiQRToken

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateQRTokenRequest(BaseModel):
    """Request to create a shareable QR code token."""

    ipsk_id: str


class CreateQRTokenResponse(BaseModel):
    """Response with QR code token details."""

    token: str
    public_url: str
    expires_at: str


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
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


@router.post("/wifi-qr/create", response_model=CreateQRTokenResponse)
async def create_qr_token(
    data: CreateQRTokenRequest,
    db: DbSession,
    current_user: User = Depends(require_user),
) -> CreateQRTokenResponse:
    """Generate a shareable QR code token.
    
    Args:
        data: Token creation request
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Token details with public URL
        
    Raises:
        HTTPException: If user doesn't own the iPSK
    """
    # Verify user owns this IPSK
    if current_user.ipsk_id != data.ipsk_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your IPSK"
        )
    
    # Generate secure token
    token = secrets.token_urlsafe(32)
    
    # Create token record
    qr_token = WifiQRToken(
        token=token,
        user_id=current_user.id,
        ipsk_id=data.ipsk_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        access_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(qr_token)
    db.commit()
    
    settings = get_settings()
    base_url = getattr(settings, 'base_url', 'http://localhost:8080')
    
    logger.info(f"Created QR token for user {current_user.email}")
    
    return CreateQRTokenResponse(
        token=token,
        public_url=f"{base_url}/api/wifi-qr/{token}",
        expires_at=qr_token.expires_at.isoformat()
    )


@router.get("/wifi-qr/{token}", response_class=HTMLResponse)
async def get_qr_page(token: str, db: DbSession) -> HTMLResponse:
    """Display public QR code page.
    
    Args:
        token: QR code token
        db: Database session
        
    Returns:
        HTML page with QR code
        
    Raises:
        HTTPException: If token not found or expired
    """
    # Find token
    qr_token = db.query(WifiQRToken).filter(WifiQRToken.token == token).first()
    
    if not qr_token or qr_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR code not found or expired"
        )
    
    # Get user and credentials
    user = db.query(User).filter(User.id == qr_token.user_id).first()
    
    if not user or not user.ipsk_passphrase_encrypted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WiFi credentials not found"
        )
    
    passphrase = decrypt_passphrase(user.ipsk_passphrase_encrypted)
    qr_code = generate_wifi_qr_code(user.ssid_name or "WiFi", passphrase)
    
    # Increment access count
    qr_token.access_count += 1
    db.commit()
    
    settings = get_settings()
    property_name = settings.property_name
    
    # Return HTML page
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
        <title>WiFi Access - {user.ssid_name}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                text-align: center;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .container {{
                background: white;
                border-radius: 16px;
                padding: 40px 30px;
                max-width: 500px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                color: #333;
            }}
            .subtitle {{
                color: #666;
                margin-bottom: 30px;
                font-size: 16px;
            }}
            .qr-code {{
                margin: 30px 0;
                padding: 20px;
                background: #f9f9f9;
                border-radius: 12px;
            }}
            .qr-code img {{
                width: 280px;
                height: 280px;
                max-width: 100%;
            }}
            .credentials {{
                background: #f5f5f5;
                padding: 24px;
                border-radius: 12px;
                margin: 30px 0;
                text-align: left;
            }}
            .credentials p {{
                margin: 16px 0;
                font-size: 16px;
                word-break: break-all;
            }}
            .credentials strong {{
                display: block;
                color: #666;
                margin-bottom: 6px;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .credentials .value {{
                color: #333;
                font-size: 18px;
                font-weight: 600;
            }}
            .instructions {{
                text-align: left;
                margin-top: 30px;
                padding: 20px;
                background: #e3f2fd;
                border-radius: 12px;
            }}
            .instructions h3 {{
                font-size: 18px;
                margin-bottom: 15px;
                color: #1976d2;
            }}
            .instructions ol {{
                margin-left: 20px;
                line-height: 1.8;
            }}
            .instructions li {{
                margin: 8px 0;
                color: #555;
            }}
            @media (max-width: 640px) {{
                .container {{ padding: 30px 20px; }}
                h1 {{ font-size: 24px; }}
                .qr-code img {{ width: 240px; height: 240px; }}
            }}
            @media print {{
                body {{
                    background: white;
                }}
                .container {{
                    box-shadow: none;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌐 {property_name}</h1>
            <p class="subtitle">WiFi Network Access</p>
            
            <div class="qr-code">
                <img src="{qr_code}" alt="WiFi QR Code" />
            </div>
            
            <div class="credentials">
                <p>
                    <strong>Network Name (SSID)</strong>
                    <span class="value">{user.ssid_name}</span>
                </p>
                <p>
                    <strong>Password</strong>
                    <span class="value">{passphrase}</span>
                </p>
            </div>
            
            <div class="instructions">
                <h3>📱 How to Connect:</h3>
                <ol>
                    <li>Open your phone's camera app</li>
                    <li>Point it at the QR code above</li>
                    <li>Tap the WiFi notification to join</li>
                </ol>
                <p style="margin-top: 15px; font-size: 14px; color: #666;">
                    Or manually enter the network name and password above in your WiFi settings.
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/wifi-qr/{token}/image.png")
async def download_qr_image(token: str, db: DbSession) -> Response:
    """Download QR code as PNG image.
    
    Args:
        token: QR code token
        db: Database session
        
    Returns:
        PNG image file
        
    Raises:
        HTTPException: If token not found or expired
    """
    # Find token
    qr_token = db.query(WifiQRToken).filter(WifiQRToken.token == token).first()
    
    if not qr_token or qr_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR code not found or expired"
        )
    
    # Get user and credentials
    user = db.query(User).filter(User.id == qr_token.user_id).first()
    
    if not user or not user.ipsk_passphrase_encrypted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WiFi credentials not found"
        )
    
    passphrase = decrypt_passphrase(user.ipsk_passphrase_encrypted)
    
    # Generate QR code
    wifi_string = f"WIFI:T:WPA;S:{user.ssid_name};P:{passphrase};;"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(wifi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    filename = f"wifi-qr-{user.ssid_name}.png".replace(" ", "_")
    
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
