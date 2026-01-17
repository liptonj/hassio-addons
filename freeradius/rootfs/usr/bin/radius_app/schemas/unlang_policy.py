"""Pydantic schemas for Unlang authorization policies."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class AdditionalCondition(BaseModel):
    """Additional condition for unlang policy."""
    
    attribute: str = Field(..., description="Attribute to check")
    operator: str = Field(default="==", description="Comparison operator")
    value: str = Field(..., description="Value to compare")


class UnlangPolicyBase(BaseModel):
    """Base schema for unlang authorization policy.
    
    Unlang policies define the decision logic (WHEN/HOW to authorize):
    - Conditions to check (attribute values, SQL lookups)
    - Actions to take (accept, reject, apply profile)
    - Which authorization profile to apply
    """
    
    name: str = Field(..., min_length=1, max_length=255, description="Policy name")
    description: Optional[str] = Field(None, max_length=500, description="Policy description")
    
    # Execution order (lower = higher priority)
    priority: int = Field(default=100, ge=0, le=1000, description="Policy priority (0=highest)")
    
    # Policy type / category
    policy_type: str = Field(
        default="authorization",
        description="Policy type: authorization, authentication, accounting, post-auth"
    )
    
    # Processing section
    section: str = Field(
        default="authorize",
        description="FreeRADIUS section: authorize, authenticate, accounting, post-auth"
    )
    
    # Condition type
    condition_type: str = Field(
        default="attribute",
        description="Condition type: attribute, sql_lookup, module_call, custom"
    )
    
    # For attribute conditions
    condition_attribute: Optional[str] = Field(
        None,
        max_length=100,
        description="Attribute to check (e.g., User-Name, Calling-Station-Id)"
    )
    condition_operator: str = Field(
        default="exists",
        description="Operator: ==, !=, =~ (regex), exists, notexists"
    )
    condition_value: Optional[str] = Field(
        None,
        max_length=255,
        description="Value to compare against"
    )
    
    # For SQL lookup conditions
    sql_condition: Optional[str] = Field(
        None,
        max_length=2000,
        description="SQL query for condition check"
    )
    
    # Additional conditions
    additional_conditions: Optional[List[AdditionalCondition]] = Field(
        None,
        description="Additional conditions (AND/OR with primary)"
    )
    condition_logic: str = Field(
        default="AND",
        description="Logic between conditions: AND, OR"
    )
    
    # Action type
    action_type: str = Field(
        default="accept",
        description="Action: accept, reject, apply_profile, continue, call_module"
    )
    
    # Profile to apply (FK to radius_policies/RadiusAuthorizationProfile)
    authorization_profile_id: Optional[int] = Field(
        None,
        description="Authorization profile ID to apply (if action_type=apply_profile)"
    )
    
    # Module to call
    module_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Module to call (if action_type=call_module)"
    )
    
    # Custom unlang code
    custom_unlang: Optional[str] = Field(
        None,
        max_length=5000,
        description="Custom unlang code for advanced policies"
    )
    
    is_active: bool = Field(default=True, description="Policy is active")


class UnlangPolicyCreate(UnlangPolicyBase):
    """Schema for creating an unlang policy."""
    pass


class UnlangPolicyUpdate(BaseModel):
    """Schema for updating an unlang policy."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    priority: Optional[int] = Field(None, ge=0, le=1000)
    policy_type: Optional[str] = None
    section: Optional[str] = None
    condition_type: Optional[str] = None
    condition_attribute: Optional[str] = Field(None, max_length=100)
    condition_operator: Optional[str] = None
    condition_value: Optional[str] = Field(None, max_length=255)
    sql_condition: Optional[str] = Field(None, max_length=2000)
    additional_conditions: Optional[List[AdditionalCondition]] = None
    condition_logic: Optional[str] = None
    action_type: Optional[str] = None
    authorization_profile_id: Optional[int] = None
    module_name: Optional[str] = Field(None, max_length=100)
    custom_unlang: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = None


class UnlangPolicyResponse(UnlangPolicyBase):
    """Schema for unlang policy response."""
    
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    # Profile name for display (resolved from authorization_profile_id)
    authorization_profile_name: Optional[str] = Field(
        None,
        description="Name of the linked authorization profile"
    )
    
    # Usage info - which auth methods use this policy
    used_by_mac_bypass: List[str] = Field(
        default_factory=list,
        description="MAC bypass configs using this policy"
    )
    used_by_eap_methods: List[str] = Field(
        default_factory=list,
        description="EAP methods using this policy"
    )
    
    model_config = ConfigDict(from_attributes=True)


class UnlangPolicyListResponse(BaseModel):
    """Paginated list of unlang policies."""
    
    items: List[UnlangPolicyResponse]
    total: int
    page: int
    page_size: int
    pages: int
