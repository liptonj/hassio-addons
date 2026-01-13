"""Registration schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegistrationRequest(BaseModel):
    """Public registration request schema."""

    name: str = Field(..., min_length=2, max_length=255, description="Full name")
    email: EmailStr = Field(..., description="Email address")
    unit: str | None = Field(None, max_length=100, description="Unit or room number")
    area_id: str | None = Field(None, description="Home Assistant area ID")
    invite_code: str | None = Field(None, max_length=20, description="Invite code if required")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Smith",
                "email": "john@example.com",
                "unit": "201",
                "invite_code": "WELCOME2026",
            }
        }


class RegistrationResponse(BaseModel):
    """Successful registration response schema."""

    success: bool = True
    ipsk_id: str | None = Field(None, description="ID of the created IPSK")
    ipsk_name: str = Field(..., description="Name of the created IPSK")
    ssid_name: str = Field(..., description="WiFi network name")
    passphrase: str = Field(..., description="WiFi password")
    qr_code: str = Field(..., description="Base64 encoded QR code image")
    wifi_config_string: str = Field(..., description="WiFi config string for QR")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "ipsk_id": "abc123",
                "ipsk_name": "Unit-201-John",
                "ssid_name": "Resident-WiFi",
                "passphrase": "SecurePass123",
                "qr_code": "data:image/png;base64,...",
                "wifi_config_string": "WIFI:T:WPA;S:Resident-WiFi;P:SecurePass123;;",
            }
        }


class MyNetworkRequest(BaseModel):
    """Request to retrieve existing network credentials."""

    email: EmailStr = Field(..., description="Registered email address")
    verification_code: str | None = Field(None, description="Email verification code")


class MyNetworkResponse(BaseModel):
    """Response with existing network credentials."""

    ipsk_name: str = Field(..., description="Name of the IPSK")
    ssid_name: str = Field(..., description="WiFi network name")
    passphrase: str = Field(..., description="WiFi password")
    status: str = Field(..., description="IPSK status")
    connected_devices: int = Field(0, description="Number of connected devices")
    qr_code: str | None = Field(None, description="Base64 encoded QR code image")

    class Config:
        json_schema_extra = {
            "example": {
                "ipsk_name": "Unit-201-John",
                "ssid_name": "Resident-WiFi",
                "passphrase": "SecurePass123",
                "status": "active",
                "connected_devices": 2,
            }
        }


class RegistrationStatusResponse(BaseModel):
    """Registration status for admin view."""

    id: int
    name: str
    email: str
    unit: str | None
    status: str
    ipsk_id: str | None
    created_at: str
    completed_at: str | None
