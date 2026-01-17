"""IPSK (Identity PSK) schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class IPSKCreate(BaseModel):
    """Schema for creating a new IPSK."""

    name: str = Field(..., min_length=1, max_length=255, description="IPSK name")
    network_id: str | None = Field(None, description="Meraki network ID (uses default if not provided)")
    ssid_number: int | None = Field(None, ge=0, le=14, description="SSID number (uses default if not provided)")
    passphrase: str | None = Field(None, min_length=8, max_length=32, description="Custom passphrase (auto-generated if not provided)")
    duration_hours: int | None = Field(None, ge=0, le=8760, description="Duration in hours (0 = permanent)")
    group_policy_id: str | None = Field(None, description="Group policy ID")
    associated_device_id: str | None = Field(None, description="HA device ID to associate")
    associated_area_id: str | None = Field(None, description="HA area ID to associate")
    associated_user: str | None = Field(None, description="User name to associate")
    associated_unit: str | None = Field(None, description="Unit/room identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Unit-201-John",
                "passphrase": "SecurePass123",
                "duration_hours": 0,
                "associated_unit": "201",
            }
        }


class IPSKUpdate(BaseModel):
    """Schema for updating an existing IPSK."""

    name: str | None = Field(None, min_length=1, max_length=255, description="New IPSK name")
    group_policy_id: str | None = Field(None, description="New group policy ID")
    associated_device_id: str | None = Field(None, description="HA device ID to associate")
    associated_area_id: str | None = Field(None, description="HA area ID to associate")


class IPSKResponse(BaseModel):
    """Schema for IPSK response."""

    id: str = Field(..., description="IPSK identifier")
    name: str = Field(..., description="IPSK name")
    network_id: str = Field(..., description="Meraki network ID")
    ssid_number: int = Field(..., description="SSID number")
    ssid_name: str | None = Field(None, description="SSID name")
    status: str = Field(..., description="IPSK status (active, expired, revoked)")
    group_policy_id: str | None = Field(None, description="Group policy ID")
    group_policy_name: str | None = Field(None, description="Group policy name")
    psk_group_id: str | None = Field(None, description="WPN/UPN Group ID - unique per iPSK")
    expires_at: datetime | None = Field(None, description="Expiration timestamp")
    created_at: datetime | None = Field(None, description="Creation timestamp")

    # Associations
    associated_device_id: str | None = Field(None, description="Associated HA device ID")
    associated_device_name: str | None = Field(None, description="Associated HA device name")
    associated_area_id: str | None = Field(None, description="Associated HA area ID")
    associated_area_name: str | None = Field(None, description="Associated HA area name")
    associated_user: str | None = Field(None, description="Associated user name")
    associated_unit: str | None = Field(None, description="Associated unit/room")

    # Stats (if available)
    connected_clients: int | None = Field(None, description="Number of connected clients")
    last_seen: datetime | None = Field(None, description="Last activity timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "ipsk_123abc",
                "name": "Unit-201-John",
                "network_id": "L_123456789",
                "ssid_number": 1,
                "ssid_name": "Resident-WiFi",
                "status": "active",
                "associated_unit": "201",
                "connected_clients": 2,
            }
        }


class IPSKRevealResponse(BaseModel):
    """Schema for revealed IPSK passphrase."""

    id: str = Field(..., description="IPSK identifier")
    name: str = Field(..., description="IPSK name")
    passphrase: str = Field(..., description="IPSK passphrase")
    ssid_name: str | None = Field(None, description="SSID name")
    qr_code: str | None = Field(None, description="Base64 encoded QR code image")
    wifi_config_string: str | None = Field(None, description="WiFi config string")


class IPSKStatsResponse(BaseModel):
    """Schema for IPSK statistics."""

    total_ipsks: int = Field(..., description="Total number of IPSKs")
    active_ipsks: int = Field(..., description="Number of active IPSKs")
    expired_ipsks: int = Field(..., description="Number of expired IPSKs")
    revoked_ipsks: int = Field(..., description="Number of revoked IPSKs")
    online_devices: int = Field(..., description="Number of devices currently online")
    registrations_today: int = Field(0, description="Number of registrations today")
