"""Pydantic schemas for RADIUS clients."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ClientBase(BaseModel):
    """Base schema for RADIUS client."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique name for the RADIUS client",
        examples=["meraki-network-1", "office-access-point"]
    )
    ipaddr: str = Field(
        ...,
        max_length=100,
        description="IP address or CIDR range (e.g., 192.168.1.1 or 10.0.0.0/24)",
        examples=["192.168.1.1", "10.0.0.0/24", "2001:db8::1"]
    )
    secret: str = Field(
        ...,
        min_length=16,
        max_length=255,
        description="Shared secret for RADIUS authentication (minimum 16 characters)",
        examples=["SecureRandomString123!"]
    )
    nas_type: str = Field(
        default="other",
        max_length=50,
        description="Network Access Server type",
        examples=["other", "cisco", "meraki", "aruba"]
    )
    shortname: Optional[str] = Field(
        None,
        max_length=100,
        description="Short name for the client",
        examples=["office-ap", "branch-1"]
    )
    network_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Meraki network ID",
        examples=["L_123456789"]
    )
    network_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Meraki network name",
        examples=["Office Network", "Branch Office"]
    )
    require_message_authenticator: bool = Field(
        default=True,
        description="Require Message-Authenticator attribute for additional security"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this client is active"
    )
    
    @field_validator("secret")
    @classmethod
    def validate_secret_strength(cls, v: str) -> str:
        """Validate secret is strong enough."""
        if len(v) < 16:
            raise ValueError("Secret must be at least 16 characters long")
        
        # Check for common weak passwords
        weak_patterns = ["password", "123456", "qwerty", "test", "admin"]
        v_lower = v.lower()
        for pattern in weak_patterns:
            if pattern in v_lower:
                raise ValueError(f"Secret contains weak pattern: {pattern}")
        
        return v
    
    @field_validator("ipaddr")
    @classmethod
    def validate_ip_or_cidr(cls, v: str) -> str:
        """Validate IP address or CIDR notation."""
        # Simple validation - FreeRADIUS will do the real validation
        # Check for basic IPv4, IPv6, or CIDR patterns
        ipv4_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$"
        ipv6_pattern = r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(/\d{1,3})?$"
        
        if not (re.match(ipv4_pattern, v) or re.match(ipv6_pattern, v)):
            raise ValueError("Invalid IP address or CIDR notation")
        
        return v


class ClientCreate(ClientBase):
    """Schema for creating a RADIUS client."""
    
    created_by: Optional[str] = Field(
        None,
        max_length=255,
        description="Username of creator (filled automatically)",
        examples=["admin"]
    )


class ClientUpdate(BaseModel):
    """Schema for updating a RADIUS client (all fields optional)."""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Unique name for the RADIUS client"
    )
    ipaddr: Optional[str] = Field(
        None,
        max_length=100,
        description="IP address or CIDR range"
    )
    secret: Optional[str] = Field(
        None,
        min_length=16,
        max_length=255,
        description="Shared secret for RADIUS authentication"
    )
    nas_type: Optional[str] = Field(
        None,
        max_length=50,
        description="Network Access Server type"
    )
    shortname: Optional[str] = Field(
        None,
        max_length=100,
        description="Short name for the client"
    )
    network_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Meraki network ID"
    )
    network_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Meraki network name"
    )
    require_message_authenticator: Optional[bool] = Field(
        None,
        description="Require Message-Authenticator attribute"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether this client is active"
    )
    
    @field_validator("secret")
    @classmethod
    def validate_secret_strength(cls, v: Optional[str]) -> Optional[str]:
        """Validate secret is strong enough."""
        if v is None:
            return v
        
        if len(v) < 16:
            raise ValueError("Secret must be at least 16 characters long")
        
        # Check for common weak passwords
        weak_patterns = ["password", "123456", "qwerty", "test", "admin"]
        v_lower = v.lower()
        for pattern in weak_patterns:
            if pattern in v_lower:
                raise ValueError(f"Secret contains weak pattern: {pattern}")
        
        return v
    
    @field_validator("ipaddr")
    @classmethod
    def validate_ip_or_cidr(cls, v: Optional[str]) -> Optional[str]:
        """Validate IP address or CIDR notation."""
        if v is None:
            return v
        
        ipv4_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$"
        ipv6_pattern = r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(/\d{1,3})?$"
        
        if not (re.match(ipv4_pattern, v) or re.match(ipv6_pattern, v)):
            raise ValueError("Invalid IP address or CIDR notation")
        
        return v


class ClientResponse(ClientBase):
    """Schema for RADIUS client response."""
    
    id: int = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Username of creator")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "name": "meraki-office-network",
                "ipaddr": "192.168.1.0/24",
                "secret": "SecureRandomString123!",
                "nas_type": "meraki",
                "shortname": "office",
                "network_id": "L_123456789",
                "network_name": "Office Network",
                "require_message_authenticator": True,
                "is_active": True,
                "created_at": "2026-01-14T12:00:00Z",
                "updated_at": "2026-01-14T12:00:00Z",
                "created_by": "admin"
            }
        }
    }


class ClientListResponse(BaseModel):
    """Schema for paginated list of RADIUS clients."""
    
    items: list[ClientResponse] = Field(..., description="List of clients")
    total: int = Field(..., description="Total number of clients")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class ClientTestRequest(BaseModel):
    """Schema for testing a RADIUS client."""
    
    username: str = Field(
        default="test",
        description="Username for test authentication",
        examples=["test", "admin"]
    )
    password: str = Field(
        default="test",
        description="Password for test authentication",
        examples=["testpass"]
    )


class ClientTestResponse(BaseModel):
    """Schema for RADIUS client test result."""
    
    success: bool = Field(..., description="Whether the test succeeded")
    message: str = Field(..., description="Test result message")
    output: Optional[str] = Field(None, description="Raw radtest output")
