"""Pydantic schemas for PSK (Pre-Shared Key) configuration."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PskConfigBase(BaseModel):
    """Base schema for PSK authentication configuration."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Configuration name")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    
    # PSK type
    psk_type: str = Field(
        default="user",
        description="PSK type: 'generic' (shared passphrase) or 'user' (per-user IPSK)"
    )
    
    # Generic PSK passphrase (only for psk_type='generic')
    generic_passphrase: Optional[str] = Field(
        None,
        min_length=8,
        max_length=63,
        description="Shared passphrase for generic PSK (WPA2 requires 8-63 chars)"
    )
    
    # Authorization policy for PSK-authenticated devices
    auth_policy_id: Optional[int] = Field(
        None,
        description="Authorization policy ID to apply on PSK authentication"
    )
    
    # Default settings if no policy/profile specified
    default_group_policy: Optional[str] = Field(
        None,
        max_length=255,
        description="Default Meraki group policy (Filter-Id)"
    )
    default_vlan_id: Optional[int] = Field(
        None,
        ge=1,
        le=4094,
        description="Default VLAN ID"
    )
    
    is_active: bool = Field(default=True, description="Whether this configuration is active")
    
    @field_validator("psk_type")
    @classmethod
    def validate_psk_type(cls, v: str) -> str:
        """Validate PSK type."""
        if v not in ["generic", "user"]:
            raise ValueError("psk_type must be 'generic' or 'user'")
        return v


class PskConfigCreate(PskConfigBase):
    """Schema for creating a PSK configuration."""
    pass


class PskConfigUpdate(BaseModel):
    """Schema for updating a PSK configuration."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    psk_type: Optional[str] = None
    generic_passphrase: Optional[str] = Field(None, min_length=8, max_length=63)
    auth_policy_id: Optional[int] = None
    default_group_policy: Optional[str] = Field(None, max_length=255)
    default_vlan_id: Optional[int] = Field(None, ge=1, le=4094)
    is_active: Optional[bool] = None
    
    @field_validator("psk_type")
    @classmethod
    def validate_psk_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate PSK type."""
        if v is not None and v not in ["generic", "user"]:
            raise ValueError("psk_type must be 'generic' or 'user'")
        return v


class PskConfigResponse(PskConfigBase):
    """Schema for PSK configuration response."""
    
    id: int
    created_at: str
    updated_at: str
    created_by: Optional[str] = None
    
    # Policy name for display (resolved from auth_policy_id)
    auth_policy_name: Optional[str] = Field(
        None,
        description="Name of the authorization policy"
    )
    
    model_config = ConfigDict(from_attributes=True)
