"""Pydantic schemas for UDN assignments."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def normalize_mac_address(mac: str) -> str:
    """
    Normalize MAC address to lowercase with colons.
    
    Accepts formats:
    - AA:BB:CC:DD:EE:FF
    - AA-BB-CC-DD-EE-FF
    - AABBCCDDEEFF
    
    Returns:
        Normalized MAC address (lowercase, colon-separated)
    """
    # Remove all separators
    mac_clean = mac.replace(":", "").replace("-", "").replace(".", "").lower()
    
    # Validate length
    if len(mac_clean) != 12:
        raise ValueError("MAC address must be 12 hex characters")
    
    # Validate hex
    try:
        int(mac_clean, 16)
    except ValueError:
        raise ValueError("MAC address must contain only hex characters")
    
    # Format with colons
    return ":".join(mac_clean[i:i+2] for i in range(0, 12, 2))


class UdnAssignmentBase(BaseModel):
    """Base schema for UDN assignment.
    
    UDN is assigned to USER (not MAC address). Relationship: USER → PSK → UDN
    MAC address is optional (for tracking, not required for UDN lookup).
    """
    
    user_id: int = Field(
        ...,
        description="User ID from portal database (required - UDN assigned to user)",
        examples=[1, 42]
    )
    mac_address: Optional[str] = Field(
        None,
        max_length=50,
        description="MAC address (optional - for tracking only, will be normalized to lowercase with colons)",
        examples=["aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "AABBCCDDEEFF"]
    )
    registration_id: Optional[int] = Field(
        None,
        description="Registration ID from portal",
        examples=[1, 100]
    )
    ipsk_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Meraki IPSK ID",
        examples=["1234567890"]
    )
    user_name: Optional[str] = Field(
        None,
        max_length=255,
        description="User's full name",
        examples=["John Doe", "Jane Smith"]
    )
    user_email: Optional[str] = Field(
        None,
        max_length=255,
        description="User's email address",
        examples=["john@example.com"]
    )
    unit: Optional[str] = Field(
        None,
        max_length=100,
        description="Unit/apartment number",
        examples=["101", "A-205", "Building 3 Unit 12"]
    )
    network_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Meraki network ID",
        examples=["L_123456789"]
    )
    ssid_number: Optional[int] = Field(
        None,
        ge=0,
        le=15,
        description="SSID number (0-15)",
        examples=[0, 1, 2]
    )
    is_active: bool = Field(
        default=True,
        description="Whether this assignment is active"
    )
    note: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes",
        examples=["Created via API", "Temporary assignment"]
    )
    
    @field_validator("mac_address")
    @classmethod
    def normalize_mac(cls, v: Optional[str]) -> Optional[str]:
        """Normalize MAC address format."""
        if v is None:
            return None
        return normalize_mac_address(v)


class UdnAssignmentCreate(UdnAssignmentBase):
    """Schema for creating a UDN assignment."""
    
    udn_id: Optional[int] = Field(
        None,
        ge=2,
        le=16777200,
        description="UDN ID (2-16777200). If not provided, will auto-assign next available.",
        examples=[100, 1000, 12345]
    )
    
    @field_validator("udn_id")
    @classmethod
    def validate_udn_range(cls, v: Optional[int]) -> Optional[int]:
        """Validate UDN ID is in valid range."""
        if v is not None and (v < 2 or v > 16777200):
            raise ValueError("UDN ID must be between 2 and 16777200")
        return v


class UdnAssignmentUpdate(BaseModel):
    """Schema for updating a UDN assignment (all fields optional)."""
    
    udn_id: Optional[int] = Field(
        None,
        ge=2,
        le=16777200,
        description="UDN ID (2-16777200)"
    )
    mac_address: Optional[str] = Field(
        None,
        max_length=50,
        description="MAC address"
    )
    user_id: Optional[int] = Field(
        None,
        description="User ID from portal database"
    )
    registration_id: Optional[int] = Field(
        None,
        description="Registration ID from portal"
    )
    ipsk_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Meraki IPSK ID"
    )
    user_name: Optional[str] = Field(
        None,
        max_length=255,
        description="User's full name"
    )
    user_email: Optional[str] = Field(
        None,
        max_length=255,
        description="User's email address"
    )
    unit: Optional[str] = Field(
        None,
        max_length=100,
        description="Unit/apartment number"
    )
    network_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Meraki network ID"
    )
    ssid_number: Optional[int] = Field(
        None,
        ge=0,
        le=15,
        description="SSID number (0-15)"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Whether this assignment is active"
    )
    note: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes"
    )
    
    @field_validator("udn_id")
    @classmethod
    def validate_udn_range(cls, v: Optional[int]) -> Optional[int]:
        """Validate UDN ID is in valid range."""
        if v is not None and (v < 2 or v > 16777200):
            raise ValueError("UDN ID must be between 2 and 16777200")
        return v
    
    @field_validator("mac_address")
    @classmethod
    def normalize_mac(cls, v: Optional[str]) -> Optional[str]:
        """Normalize MAC address format."""
        if v is None:
            return v
        return normalize_mac_address(v)


class UdnAssignmentResponse(UdnAssignmentBase):
    """Schema for UDN assignment response."""
    
    id: int = Field(..., description="Unique identifier")
    udn_id: int = Field(..., description="UDN ID (2-16777200)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_auth_at: Optional[datetime] = Field(None, description="Last authentication timestamp")
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "udn_id": 1000,
                "mac_address": "aa:bb:cc:dd:ee:ff",
                "user_id": 42,
                "registration_id": 100,
                "ipsk_id": "1234567890",
                "user_name": "John Doe",
                "user_email": "john@example.com",
                "unit": "101",
                "network_id": "L_123456789",
                "ssid_number": 1,
                "is_active": True,
                "note": "Created via portal",
                "created_at": "2026-01-14T12:00:00Z",
                "updated_at": "2026-01-14T12:00:00Z",
                "last_auth_at": "2026-01-14T15:30:00Z"
            }
        }
    }


class UdnAssignmentListResponse(BaseModel):
    """Schema for paginated list of UDN assignments."""
    
    items: list[UdnAssignmentResponse] = Field(..., description="List of assignments")
    total: int = Field(..., description="Total number of assignments")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class AvailableUdnResponse(BaseModel):
    """Schema for next available UDN ID."""
    
    udn_id: int = Field(..., description="Next available UDN ID")
    total_assigned: int = Field(..., description="Total UDN IDs currently assigned")
    total_available: int = Field(..., description="Total UDN IDs still available")
