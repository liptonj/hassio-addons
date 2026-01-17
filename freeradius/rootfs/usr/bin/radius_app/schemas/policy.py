"""Pydantic schemas for RADIUS policy management."""

from datetime import datetime, time
from typing import Optional, List

from pydantic import BaseModel, Field


class ReplyAttribute(BaseModel):
    """RADIUS reply attribute."""
    
    attribute: str = Field(..., max_length=100, description="Attribute name")
    operator: str = Field(default=":=", description="Operator (:=, +=, ==, etc.)")
    value: str = Field(..., max_length=255, description="Attribute value")


class CheckAttribute(BaseModel):
    """RADIUS check attribute."""
    
    attribute: str = Field(..., max_length=100, description="Attribute name")
    operator: str = Field(default="==", description="Operator (==, !=, >, <, etc.)")
    value: str = Field(..., max_length=255, description="Attribute value")


class TimeRestriction(BaseModel):
    """Time-based access restrictions."""
    
    days_of_week: Optional[List[int]] = Field(
        None,
        description="Days of week (0=Monday, 6=Sunday)",
        min_length=1,
        max_length=7
    )
    time_start: Optional[time] = Field(None, description="Start time (HH:MM)")
    time_end: Optional[time] = Field(None, description="End time (HH:MM)")
    timezone: str = Field(default="UTC", description="Timezone for time restrictions")


class PolicyBase(BaseModel):
    """Base schema for authorization policy."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Policy name")
    description: Optional[str] = Field(None, max_length=500, description="Policy description")
    
    # Priority and grouping
    priority: int = Field(default=100, ge=0, le=1000, description="Policy priority (0=highest)")
    group_name: Optional[str] = Field(None, max_length=100, description="Policy group")
    
    # Policy type
    policy_type: str = Field(
        default="user",
        description="Policy type: user, group, device, network"
    )
    
    # Match conditions
    match_username: Optional[str] = Field(None, max_length=255, description="Username pattern (regex supported)")
    match_mac_address: Optional[str] = Field(None, max_length=50, description="MAC address pattern")
    match_calling_station: Optional[str] = Field(None, max_length=100, description="Calling station pattern")
    match_nas_identifier: Optional[str] = Field(None, max_length=100, description="NAS identifier pattern")
    match_nas_ip: Optional[str] = Field(None, max_length=100, description="NAS IP pattern")
    
    # Reply attributes
    reply_attributes: List[ReplyAttribute] = Field(
        default_factory=list,
        description="Attributes to return on accept"
    )
    
    # Check attributes (additional conditions)
    check_attributes: List[CheckAttribute] = Field(
        default_factory=list,
        description="Attributes to check before granting access"
    )
    
    # Time restrictions
    time_restrictions: Optional[TimeRestriction] = Field(
        None,
        description="Time-based access restrictions"
    )
    
    # VLAN assignment
    vlan_id: Optional[int] = Field(None, ge=1, le=4094, description="VLAN ID to assign")
    vlan_name: Optional[str] = Field(None, max_length=100, description="VLAN name")
    
    # Bandwidth limits
    bandwidth_limit_up: Optional[int] = Field(None, ge=0, description="Upload bandwidth limit (kbps)")
    bandwidth_limit_down: Optional[int] = Field(None, ge=0, description="Download bandwidth limit (kbps)")
    
    # Session limits
    session_timeout: Optional[int] = Field(None, ge=0, description="Session timeout (seconds)")
    idle_timeout: Optional[int] = Field(None, ge=0, description="Idle timeout (seconds)")
    max_concurrent_sessions: Optional[int] = Field(None, ge=1, description="Max concurrent sessions")
    
    # Captive Portal / URL Redirect
    splash_url: Optional[str] = Field(
        None,
        max_length=500,
        description="Captive portal URL (Cisco-AVPair: url-redirect=<URL>)"
    )
    url_redirect_acl: Optional[str] = Field(
        None,
        max_length=100,
        description="ACL for URL redirect (Cisco-AVPair: url-redirect-acl=<ACL>)"
    )
    
    # Group Policy - Vendor-specific
    group_policy_vendor: str = Field(
        default="meraki",
        description="Vendor for group policy format: meraki, cisco_aireos, cisco_ise, aruba"
    )
    registered_group_policy: Optional[str] = Field(
        None,
        max_length=255,
        description="Group policy for registered/authenticated users"
    )
    unregistered_group_policy: Optional[str] = Field(
        None,
        max_length=255,
        description="Group policy for unregistered/guest users (pre-auth)"
    )
    filter_id: Optional[str] = Field(
        None,
        max_length=255,
        description="Meraki Filter-Id for group policy name"
    )
    downloadable_acl: Optional[str] = Field(
        None,
        max_length=255,
        description="Cisco ISE Downloadable ACL name (ACS:CiscoSecure-Defined-ACL)"
    )
    
    # Cisco TrustSec / Meraki Adaptive Policy - SGT
    sgt_value: Optional[int] = Field(
        None,
        ge=0,
        le=65535,
        description="Security Group Tag (0-65535) for TrustSec/Adaptive Policy"
    )
    sgt_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Human-readable name for the SGT (e.g., 'Sales', 'Engineering')"
    )
    
    # UDN Settings
    include_udn: bool = Field(
        default=True,
        description="Include UDN ID in RADIUS response"
    )
    
    # Status
    is_active: bool = Field(default=True, description="Policy is active")


class PolicyCreate(PolicyBase):
    """Schema for creating a policy."""
    
    created_by: Optional[str] = Field(None, description="Creator username")


class PolicyUpdate(BaseModel):
    """Schema for updating a policy (all fields optional)."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = Field(None, ge=0, le=1000)
    group_name: Optional[str] = Field(None, max_length=100)
    policy_type: Optional[str] = None
    match_username: Optional[str] = Field(None, max_length=255)
    match_mac_address: Optional[str] = Field(None, max_length=50)
    match_calling_station: Optional[str] = Field(None, max_length=100)
    match_nas_identifier: Optional[str] = Field(None, max_length=100)
    match_nas_ip: Optional[str] = Field(None, max_length=100)
    reply_attributes: Optional[List[ReplyAttribute]] = None
    check_attributes: Optional[List[CheckAttribute]] = None
    time_restrictions: Optional[TimeRestriction] = None
    vlan_id: Optional[int] = Field(None, ge=1, le=4094)
    vlan_name: Optional[str] = Field(None, max_length=100)
    bandwidth_limit_up: Optional[int] = Field(None, ge=0)
    bandwidth_limit_down: Optional[int] = Field(None, ge=0)
    session_timeout: Optional[int] = Field(None, ge=0)
    idle_timeout: Optional[int] = Field(None, ge=0)
    max_concurrent_sessions: Optional[int] = Field(None, ge=1)
    # Captive Portal / URL Redirect
    splash_url: Optional[str] = Field(None, max_length=500)
    url_redirect_acl: Optional[str] = Field(None, max_length=100)
    # Group Policy
    group_policy_vendor: Optional[str] = None
    registered_group_policy: Optional[str] = Field(None, max_length=255)
    unregistered_group_policy: Optional[str] = Field(None, max_length=255)
    filter_id: Optional[str] = Field(None, max_length=255)
    downloadable_acl: Optional[str] = Field(None, max_length=255)
    sgt_value: Optional[int] = Field(None, ge=0, le=65535)
    sgt_name: Optional[str] = Field(None, max_length=100)
    include_udn: Optional[bool] = None
    is_active: Optional[bool] = None


class PolicyResponse(PolicyBase):
    """Schema for policy response."""
    
    id: int = Field(..., description="Policy ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator username")
    
    # Usage statistics
    usage_count: int = Field(default=0, description="Number of times policy was applied")
    last_used: Optional[datetime] = Field(None, description="Last time policy was used")
    
    model_config = {"from_attributes": True}


class PolicyListResponse(BaseModel):
    """Paginated list of policies."""
    
    items: list[PolicyResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PolicyTestRequest(BaseModel):
    """Test policy against sample attributes."""
    
    username: str = Field(..., description="Username to test")
    mac_address: Optional[str] = Field(None, description="MAC address")
    nas_identifier: Optional[str] = Field(None, description="NAS identifier")
    nas_ip: Optional[str] = Field(None, description="NAS IP address")
    additional_attributes: Optional[dict] = Field(None, description="Additional attributes")


class PolicyTestResponse(BaseModel):
    """Policy test result."""
    
    matches: bool = Field(..., description="Policy matches the test conditions")
    policy_id: Optional[int] = Field(None, description="Matched policy ID")
    policy_name: Optional[str] = Field(None, description="Matched policy name")
    reply_attributes: List[ReplyAttribute] = Field(default_factory=list)
    reason: Optional[str] = Field(None, description="Match/no-match reason")
