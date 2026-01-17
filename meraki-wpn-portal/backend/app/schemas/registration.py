"""Registration schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegistrationRequest(BaseModel):
    """Public registration request schema."""

    name: str = Field(..., min_length=2, max_length=255, description="Full name")
    email: EmailStr = Field(..., description="Email address")
    unit: str | None = Field(None, max_length=100, description="Unit or room number")
    area_id: str | None = Field(None, description="Home Assistant area ID")
    invite_code: str | None = Field(None, max_length=20, description="Invite code if required")
    mac_address: str | None = Field(None, description="Device MAC address for RADIUS/UDN assignment")
    # NEW FIELDS
    custom_passphrase: str | None = Field(None, min_length=8, max_length=63, description="Custom WiFi password (optional)")
    accept_aup: bool | None = Field(None, description="Acceptable Use Policy acceptance")
    custom_fields: dict[str, str] | None = Field(None, description="Custom registration fields")
    user_agent: str | None = Field(None, description="Browser User-Agent for device detection")
    # EAP-TLS FIELDS
    auth_method: str = Field("ipsk", description="Authentication method: 'ipsk', 'eap-tls', or 'both'")
    certificate_password: str | None = Field(None, min_length=8, description="Password for PKCS#12 certificate bundle")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Smith",
                "email": "john@example.com",
                "unit": "201",
                "invite_code": "WELCOME2026",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "custom_passphrase": "MySecurePass123",
                "accept_aup": True,
                "custom_fields": {"parking_spot": "A5"},
                "auth_method": "both",
                "certificate_password": "CertPass123",
            }
        }


class RegistrationResponse(BaseModel):
    """Successful registration response schema."""

    success: bool = True
    ipsk_id: str | None = Field(None, description="ID of the created IPSK")
    ipsk_name: str | None = Field(None, description="Name of the created IPSK")
    ssid_name: str = Field(..., description="WiFi network name")
    passphrase: str | None = Field(None, description="WiFi password (for IPSK)")
    qr_code: str | None = Field(None, description="Base64 encoded QR code image")
    wifi_config_string: str | None = Field(None, description="WiFi config string for QR")
    # NEW FIELDS
    is_returning_user: bool = Field(False, description="True if reusing invite code with existing credentials")
    device_info: dict[str, str] | None = Field(None, description="Detected device information")
    mobileconfig_url: str | None = Field(None, description="URL to download Apple mobileconfig profile")
    # EAP-TLS FIELDS
    auth_method: str = Field("ipsk", description="Authentication method used: 'ipsk', 'eap-tls', or 'both'")
    certificate_id: int | None = Field(None, description="ID of the issued certificate (for EAP-TLS)")
    certificate_download_url: str | None = Field(None, description="URL to download certificate bundle")
    # APPROVAL WORKFLOW FIELDS
    pending_approval: bool = Field(False, description="True if registration is pending admin approval")
    pending_message: str | None = Field(None, description="Message shown when registration is pending")

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
                "is_returning_user": False,
                "device_info": {
                    "device_type": "phone",
                    "device_os": "iOS",
                    "device_model": "iPhone 15 Pro"
                },
                "mobileconfig_url": "/api/wifi-config/abc123/mobileconfig",
                "auth_method": "both",
                "certificate_id": 456,
                "certificate_download_url": "/api/user/certificates/456/download",
                "pending_approval": False,
                "pending_message": None,
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
