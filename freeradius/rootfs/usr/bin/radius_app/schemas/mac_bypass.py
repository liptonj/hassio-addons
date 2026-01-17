"""Pydantic schemas for MAC bypass configuration."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MacBypassConfigBase(BaseModel):
    """Base schema for MAC bypass configuration."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Configuration name")
    description: Optional[str] = Field(None, max_length=500, description="Configuration description")
    
    mac_addresses: Optional[list[str]] = Field(
        default_factory=list,
        description="List of MAC addresses (will be normalized)"
    )
    
    bypass_mode: str = Field(
        default="whitelist",
        description="Bypass mode: 'whitelist' (only these MACs bypass) or 'blacklist' (these MACs don't bypass)"
    )
    
    require_registration: bool = Field(
        default=False,
        description="Require MAC to be registered before bypass"
    )
    
    # Authorization policy for registered MAC addresses
    registered_policy_id: Optional[int] = Field(
        None,
        description="Authorization policy ID for registered MACs (found in device_registrations)"
    )
    
    # Authorization policy for unregistered MAC addresses
    unregistered_policy_id: Optional[int] = Field(
        None,
        description="Authorization policy ID for unregistered MACs"
    )
    
    is_active: bool = Field(default=True, description="Whether this configuration is active")
    
    @field_validator("bypass_mode")
    @classmethod
    def validate_bypass_mode(cls, v: str) -> str:
        """Validate bypass mode."""
        if v not in ["whitelist", "blacklist"]:
            raise ValueError("bypass_mode must be 'whitelist' or 'blacklist'")
        return v
    
    @field_validator("mac_addresses")
    @classmethod
    def normalize_mac_addresses(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Normalize MAC addresses."""
        if not v:
            return []
        
        normalized = []
        for mac in v:
            # Normalize MAC address (remove separators, lowercase, add colons)
            mac_clean = mac.replace(":", "").replace("-", "").replace(".", "").lower()
            if len(mac_clean) != 12:
                raise ValueError(f"Invalid MAC address format: {mac}")
            normalized.append(":".join(mac_clean[i:i+2] for i in range(0, 12, 2)))
        
        return normalized


class MacBypassConfigCreate(MacBypassConfigBase):
    """Schema for creating a MAC bypass configuration."""
    pass


class MacBypassConfigUpdate(BaseModel):
    """Schema for updating a MAC bypass configuration."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    mac_addresses: Optional[list[str]] = Field(None)
    bypass_mode: Optional[str] = Field(None)
    require_registration: Optional[bool] = None
    registered_policy_id: Optional[int] = None
    unregistered_policy_id: Optional[int] = None
    is_active: Optional[bool] = None
    
    @field_validator("bypass_mode")
    @classmethod
    def validate_bypass_mode(cls, v: Optional[str]) -> Optional[str]:
        """Validate bypass mode."""
        if v is not None and v not in ["whitelist", "blacklist"]:
            raise ValueError("bypass_mode must be 'whitelist' or 'blacklist'")
        return v


class MacBypassConfigResponse(MacBypassConfigBase):
    """Schema for MAC bypass configuration response."""
    
    id: int
    created_at: str
    updated_at: str
    created_by: Optional[str] = None
    
    # Policy names for display (resolved from policy IDs)
    registered_policy_name: Optional[str] = Field(
        None,
        description="Name of the registered MAC authorization policy"
    )
    unregistered_policy_name: Optional[str] = Field(
        None,
        description="Name of the unregistered MAC authorization policy"
    )
    
    model_config = ConfigDict(from_attributes=True)
