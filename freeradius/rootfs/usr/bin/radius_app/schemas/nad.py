"""Pydantic schemas for Network Access Device (NAD) management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class NadCapabilities(BaseModel):
    """NAD capabilities and features."""
    
    supports_radsec: bool = Field(default=False, description="Supports RadSec (RADIUS over TLS)")
    supports_coa: bool = Field(default=False, description="Supports Change of Authorization")
    supports_disconnect: bool = Field(default=False, description="Supports Disconnect Messages")
    supports_accounting: bool = Field(default=True, description="Supports RADIUS Accounting")
    supports_ipv6: bool = Field(default=False, description="Supports IPv6")
    max_sessions: Optional[int] = Field(None, ge=0, description="Maximum concurrent sessions")


class NadHealthStatus(BaseModel):
    """NAD health and connectivity status."""
    
    is_reachable: bool = Field(..., description="NAD is reachable via network")
    last_seen: Optional[datetime] = Field(None, description="Last time NAD was seen")
    request_count: int = Field(default=0, description="Total authentication requests")
    success_count: int = Field(default=0, description="Successful authentications")
    failure_count: int = Field(default=0, description="Failed authentications")
    avg_response_time_ms: Optional[float] = Field(None, description="Average response time in milliseconds")


class NadBase(BaseModel):
    """Base schema for Network Access Device."""
    
    name: str = Field(..., min_length=1, max_length=255, description="NAD name/identifier")
    description: Optional[str] = Field(None, max_length=500, description="NAD description")
    
    # Network configuration
    ipaddr: str = Field(..., max_length=100, description="IP address or CIDR")
    # Note: min_length=1 for responses (existing data), validation done on create
    secret: str = Field(..., min_length=1, max_length=255, description="Shared secret")
    
    # Device information
    nas_type: str = Field(default="other", max_length=50, description="NAS device type")
    vendor: Optional[str] = Field(None, max_length=100, description="Vendor name")
    model: Optional[str] = Field(None, max_length=100, description="Device model")
    location: Optional[str] = Field(None, max_length=255, description="Physical location")
    
    # RadSec configuration
    radsec_enabled: bool = Field(default=False, description="Enable RadSec for this NAD")
    radsec_port: Optional[int] = Field(None, ge=1024, le=65535, description="RadSec port")
    require_tls_cert: bool = Field(default=False, description="Require TLS client certificate")
    
    # CoA/DM configuration
    coa_enabled: bool = Field(default=False, description="Enable Change of Authorization")
    coa_port: Optional[int] = Field(None, ge=1024, le=65535, description="CoA port (default: 3799)")
    
    # Advanced settings
    require_message_authenticator: bool = Field(default=True, description="Require Message-Authenticator")
    virtual_server: Optional[str] = Field(None, max_length=100, description="FreeRADIUS virtual server")
    
    # Status
    is_active: bool = Field(default=True, description="NAD is active")


class NadCreate(NadBase):
    """Schema for creating a NAD."""
    
    capabilities: Optional[NadCapabilities] = Field(None, description="NAD capabilities")
    created_by: Optional[str] = Field(None, description="Creator username")
    
    @field_validator("secret")
    @classmethod
    def validate_secret_strength(cls, v: str) -> str:
        """Validate secret is strong enough for new NADs."""
        if len(v) < 16:
            raise ValueError("Secret must be at least 16 characters long")
        return v


class NadUpdate(BaseModel):
    """Schema for updating a NAD (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    ipaddr: Optional[str] = Field(None, max_length=100)
    secret: Optional[str] = Field(None, min_length=16, max_length=255)
    nas_type: Optional[str] = Field(None, max_length=50)
    vendor: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)
    radsec_enabled: Optional[bool] = None
    radsec_port: Optional[int] = Field(None, ge=1024, le=65535)
    require_tls_cert: Optional[bool] = None
    coa_enabled: Optional[bool] = None
    coa_port: Optional[int] = Field(None, ge=1024, le=65535)
    require_message_authenticator: Optional[bool] = None
    virtual_server: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class NadResponse(NadBase):
    """Schema for NAD response."""
    
    id: int = Field(..., description="NAD ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator username")
    
    # Health status (computed)
    health_status: Optional[NadHealthStatus] = Field(None, description="Current health status")
    
    model_config = {"from_attributes": True}


class NadListResponse(BaseModel):
    """Paginated list of NADs."""
    
    items: list[NadResponse]
    total: int
    page: int
    page_size: int
    pages: int
