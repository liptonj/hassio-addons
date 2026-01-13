"""Device and area schemas for Home Assistant integration."""

from pydantic import BaseModel, Field


class DeviceResponse(BaseModel):
    """Schema for Home Assistant device."""

    id: str = Field(..., description="Device ID")
    name: str = Field(..., description="Device name")
    name_by_user: str | None = Field(None, description="User-assigned name")
    manufacturer: str | None = Field(None, description="Device manufacturer")
    model: str | None = Field(None, description="Device model")
    area_id: str | None = Field(None, description="Associated area ID")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123",
                "name": "Living Room TV",
                "manufacturer": "LG",
                "model": "OLED55C1",
                "area_id": "living_room",
            }
        }


class AreaResponse(BaseModel):
    """Schema for Home Assistant area."""

    area_id: str = Field(..., description="Area ID")
    name: str = Field(..., description="Area name")
    aliases: list[str] = Field(default_factory=list, description="Area aliases")
    picture: str | None = Field(None, description="Area picture URL")

    class Config:
        json_schema_extra = {
            "example": {
                "area_id": "living_room",
                "name": "Living Room",
                "aliases": ["Main Room"],
            }
        }


class DeviceAssociationRequest(BaseModel):
    """Schema for associating a device or area with an IPSK."""

    device_id: str | None = Field(None, description="HA device ID to associate")
    area_id: str | None = Field(None, description="HA area ID to associate")


class InviteCodeCreate(BaseModel):
    """Schema for creating an invite code."""

    max_uses: int = Field(1, ge=1, le=1000, description="Maximum number of uses")
    expires_in_hours: int | None = Field(None, ge=1, le=8760, description="Expires in hours from now")
    note: str | None = Field(None, max_length=500, description="Note about the code")

    class Config:
        json_schema_extra = {
            "example": {
                "max_uses": 10,
                "expires_in_hours": 168,
                "note": "For new tenants in Building A",
            }
        }


class InviteCodeResponse(BaseModel):
    """Schema for invite code response."""

    code: str = Field(..., description="Invite code")
    max_uses: int = Field(..., description="Maximum number of uses")
    uses: int = Field(..., description="Current number of uses")
    is_active: bool = Field(..., description="Whether the code is active")
    expires_at: str | None = Field(None, description="Expiration timestamp")
    note: str | None = Field(None, description="Note about the code")
    created_by: str | None = Field(None, description="Creator identifier")
    created_at: str = Field(..., description="Creation timestamp")
    last_used_at: str | None = Field(None, description="Last use timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "code": "WELCOME2026",
                "max_uses": 10,
                "uses": 3,
                "is_active": True,
                "expires_at": "2026-02-01T00:00:00Z",
                "note": "For new tenants",
            }
        }
