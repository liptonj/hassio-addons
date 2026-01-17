"""Comprehensive Authentication Configuration API endpoint.

This endpoint provides a unified view of all authentication-related configurations:
- MAC bypass configurations
- EAP methods
- Authorization policies
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import (
    RadiusMacBypassConfig,
    RadiusEapConfig,
    RadiusEapMethod,
    RadiusPolicy,
)
from radius_app.schemas.mac_bypass import MacBypassConfigResponse
from radius_app.schemas.policy import PolicyResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth-config", tags=["Authentication Config"])


class EapMethodSummary(BaseModel):
    """EAP method summary."""
    
    method_name: str = Field(..., description="EAP method name (tls, ttls, peap, fast)")
    is_enabled: bool = Field(..., description="Whether this method is enabled")
    auth_attempts: int = Field(default=0, description="Total authentication attempts")
    auth_successes: int = Field(default=0, description="Successful authentications")
    auth_failures: int = Field(default=0, description="Failed authentications")
    success_rate: float = Field(default=0.0, description="Success rate percentage")


class EapConfigSummary(BaseModel):
    """EAP configuration summary."""
    
    id: int
    name: str
    description: str | None
    default_eap_type: str
    enabled_methods: List[str]
    tls_min_version: str
    tls_max_version: str
    is_active: bool
    methods: List[EapMethodSummary] = Field(default_factory=list)


class MacBypassSummary(BaseModel):
    """MAC bypass configuration summary."""
    
    id: int
    name: str
    description: str | None
    mac_addresses: List[str]
    bypass_mode: str
    require_registration: bool
    is_active: bool


class PolicySummary(BaseModel):
    """Authorization policy summary."""
    
    id: int
    name: str
    description: str | None
    priority: int
    group_name: str | None
    policy_type: str
    is_active: bool
    psk_validation_required: bool
    mac_matching_enabled: bool
    match_on_psk_only: bool
    include_udn: bool
    splash_url: str | None
    registered_group_policy: str | None
    unregistered_group_policy: str | None


class AuthenticationConfigResponse(BaseModel):
    """Comprehensive authentication configuration response."""
    
    mac_bypass_configs: List[MacBypassSummary] = Field(
        default_factory=list,
        description="MAC bypass configurations"
    )
    eap_config: EapConfigSummary | None = Field(
        None,
        description="Active EAP configuration"
    )
    authorization_policies: List[PolicySummary] = Field(
        default_factory=list,
        description="Authorization policies (sorted by priority)"
    )
    
    summary: dict = Field(
        default_factory=dict,
        description="Summary statistics"
    )


@router.get("", response_model=AuthenticationConfigResponse)
async def get_authentication_config(
    admin: AdminUser,
    db: DbSession,
    active_only: bool = True,
) -> AuthenticationConfigResponse:
    """
    Get comprehensive authentication configuration.
    
    Returns all authentication-related configurations in a single response:
    - MAC bypass configurations
    - EAP methods and configuration
    - Authorization policies
    
    This endpoint provides a complete view of how devices authenticate
    and what authorization policies are applied.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        active_only: Only return active configurations (default: True)
        
    Returns:
        Comprehensive authentication configuration
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} requesting comprehensive auth config")
    
    # Get MAC bypass configurations
    mac_bypass_query = db.query(RadiusMacBypassConfig)
    if active_only:
        mac_bypass_query = mac_bypass_query.filter(RadiusMacBypassConfig.is_active == True)
    
    mac_bypass_configs = mac_bypass_query.order_by(RadiusMacBypassConfig.name).all()
    
    mac_bypass_summaries = [
        MacBypassSummary(
            id=config.id,
            name=config.name,
            description=config.description,
            mac_addresses=config.mac_addresses or [],
            bypass_mode=config.bypass_mode,
            require_registration=config.require_registration,
            is_active=config.is_active,
        )
        for config in mac_bypass_configs
    ]
    
    # Get EAP configuration
    eap_config = None
    eap_methods = []
    
    eap_config_query = db.query(RadiusEapConfig)
    if active_only:
        eap_config_query = eap_config_query.filter(RadiusEapConfig.is_active == True)
    
    eap_config_obj = eap_config_query.first()
    
    if eap_config_obj:
        # Get EAP methods for this config
        methods_query = db.query(RadiusEapMethod).filter(
            RadiusEapMethod.eap_config_id == eap_config_obj.id
        )
        methods = methods_query.all()
        
        eap_methods = [
            EapMethodSummary(
                method_name=method.method_name,
                is_enabled=method.is_enabled,
                auth_attempts=method.auth_attempts,
                auth_successes=method.auth_successes,
                auth_failures=method.auth_failures,
                success_rate=(
                    method.auth_successes / method.auth_attempts * 100
                    if method.auth_attempts > 0 else 0.0
                ),
            )
            for method in methods
        ]
        
        eap_config = EapConfigSummary(
            id=eap_config_obj.id,
            name=eap_config_obj.name,
            description=eap_config_obj.description,
            default_eap_type=eap_config_obj.default_eap_type,
            enabled_methods=eap_config_obj.enabled_methods or [],
            tls_min_version=eap_config_obj.tls_min_version,
            tls_max_version=eap_config_obj.tls_max_version,
            is_active=eap_config_obj.is_active,
            methods=eap_methods,
        )
    
    # Get authorization policies
    policy_query = select(RadiusPolicy)
    if active_only:
        policy_query = policy_query.where(RadiusPolicy.is_active == True)
    
    policy_query = policy_query.order_by(RadiusPolicy.priority.asc())
    policies = db.execute(policy_query).scalars().all()
    
    policy_summaries = [
        PolicySummary(
            id=policy.id,
            name=policy.name,
            description=policy.description,
            priority=policy.priority,
            group_name=policy.group_name,
            policy_type=policy.policy_type,
            is_active=policy.is_active,
            psk_validation_required=policy.psk_validation_required,
            mac_matching_enabled=policy.mac_matching_enabled,
            match_on_psk_only=policy.match_on_psk_only,
            include_udn=policy.include_udn,
            splash_url=policy.splash_url,
            registered_group_policy=policy.registered_group_policy,
            unregistered_group_policy=policy.unregistered_group_policy,
        )
        for policy in policies
    ]
    
    # Build summary statistics
    enabled_eap_methods = [m for m in eap_methods if m.is_enabled] if eap_config else []
    
    summary = {
        "mac_bypass_configs_count": len(mac_bypass_summaries),
        "active_mac_bypass_configs": len([c for c in mac_bypass_summaries if c.is_active]),
        "total_mac_addresses": sum(len(c.mac_addresses) for c in mac_bypass_summaries),
        "eap_config_active": eap_config.is_active if eap_config else False,
        "enabled_eap_methods_count": len(enabled_eap_methods),
        "enabled_eap_methods": [m.method_name for m in enabled_eap_methods],
        "authorization_policies_count": len(policy_summaries),
        "active_policies_count": len([p for p in policy_summaries if p.is_active]),
        "policies_with_udn": len([p for p in policy_summaries if p.include_udn]),
        "policies_with_splash_url": len([p for p in policy_summaries if p.splash_url]),
        "psk_only_policies": len([p for p in policy_summaries if p.match_on_psk_only]),
    }
    
    logger.info(f"✅ Returning auth config: {summary['mac_bypass_configs_count']} MAC bypass, "
                f"{summary['enabled_eap_methods_count']} EAP methods, "
                f"{summary['authorization_policies_count']} policies")
    
    return AuthenticationConfigResponse(
        mac_bypass_configs=mac_bypass_summaries,
        eap_config=eap_config,
        authorization_policies=policy_summaries,
        summary=summary,
    )
