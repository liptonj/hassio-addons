"""PSK (Pre-Shared Key) configuration API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import RadiusPskConfig, RadiusUnlangPolicy
from radius_app.schemas.psk_config import (
    PskConfigCreate,
    PskConfigResponse,
    PskConfigUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/psk", tags=["psk"])


def _get_policy_name(db: DbSession, policy_id: Optional[int]) -> Optional[str]:
    """Get policy name by ID."""
    if policy_id is None:
        return None
    policy = db.query(RadiusUnlangPolicy).filter(RadiusUnlangPolicy.id == policy_id).first()
    return policy.name if policy else None


def _validate_policy_id(db: DbSession, policy_id: Optional[int], field_name: str) -> None:
    """Validate that a policy ID exists if provided."""
    if policy_id is not None:
        policy = db.query(RadiusUnlangPolicy).filter(RadiusUnlangPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name}: policy with ID {policy_id} not found"
            )


def _build_psk_config_response(db: DbSession, config: RadiusPskConfig) -> PskConfigResponse:
    """Build PSK config response with policy name."""
    return PskConfigResponse(
        id=config.id,
        name=config.name,
        description=config.description,
        psk_type=config.psk_type,
        generic_passphrase=config.generic_passphrase,
        auth_policy_id=config.auth_policy_id,
        default_group_policy=config.default_group_policy,
        default_vlan_id=config.default_vlan_id,
        is_active=config.is_active,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
        created_by=config.created_by,
        auth_policy_name=_get_policy_name(db, config.auth_policy_id),
    )


@router.get("/config", response_model=List[PskConfigResponse])
async def list_psk_configs(
    admin: AdminUser,
    db: DbSession,
    active_only: bool = False,
) -> List[PskConfigResponse]:
    """List all PSK configurations.
    
    Args:
        db: Database session
        admin: Admin user
        active_only: Only return active configurations
        
    Returns:
        List of PSK configurations with policy names
    """
    logger.info(f"Admin {admin['sub']} listing PSK configurations")
    
    query = db.query(RadiusPskConfig)
    if active_only:
        query = query.filter(RadiusPskConfig.is_active == True)
    
    configs = query.order_by(RadiusPskConfig.name).all()
    
    return [_build_psk_config_response(db, config) for config in configs]


@router.post("/config", response_model=PskConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_psk_config(
    config_data: PskConfigCreate,
    admin: AdminUser,
    db: DbSession,
) -> PskConfigResponse:
    """Create a new PSK configuration.
    
    Args:
        config_data: PSK configuration data
        db: Database session
        admin: Admin user
        
    Returns:
        Created PSK configuration
        
    Raises:
        HTTPException: If configuration name already exists or policy ID invalid
    """
    logger.info(f"Admin {admin['sub']} creating PSK config: {config_data.name}")
    
    # Check if name already exists
    existing = db.query(RadiusPskConfig).filter(
        RadiusPskConfig.name == config_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PSK configuration '{config_data.name}' already exists"
        )
    
    # Validate policy ID if provided
    _validate_policy_id(db, config_data.auth_policy_id, "auth_policy_id")
    
    # Create new configuration
    config = RadiusPskConfig(
        name=config_data.name,
        description=config_data.description,
        psk_type=config_data.psk_type,
        generic_passphrase=config_data.generic_passphrase,
        auth_policy_id=config_data.auth_policy_id,
        default_group_policy=config_data.default_group_policy,
        default_vlan_id=config_data.default_vlan_id,
        is_active=config_data.is_active,
        created_by=admin["sub"],
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    logger.info(f"✅ Created PSK config: {config.name}")
    
    return _build_psk_config_response(db, config)


@router.get("/config/{config_id}", response_model=PskConfigResponse)
async def get_psk_config(
    config_id: int,
    admin: AdminUser,
    db: DbSession,
) -> PskConfigResponse:
    """Get a specific PSK configuration.
    
    Args:
        config_id: Configuration ID
        db: Database session
        admin: Admin user
        
    Returns:
        PSK configuration with policy name
        
    Raises:
        HTTPException: If configuration not found
    """
    config = db.query(RadiusPskConfig).filter(
        RadiusPskConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PSK configuration {config_id} not found"
        )
    
    return _build_psk_config_response(db, config)


@router.put("/config/{config_id}", response_model=PskConfigResponse)
async def update_psk_config(
    config_id: int,
    config_data: PskConfigUpdate,
    admin: AdminUser,
    db: DbSession,
) -> PskConfigResponse:
    """Update a PSK configuration.
    
    Args:
        config_id: Configuration ID
        config_data: Updated configuration data
        db: Database session
        admin: Admin user
        
    Returns:
        Updated PSK configuration with policy name
        
    Raises:
        HTTPException: If configuration not found, name conflict, or invalid policy ID
    """
    logger.info(f"Admin {admin['sub']} updating PSK config {config_id}")
    
    config = db.query(RadiusPskConfig).filter(
        RadiusPskConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PSK configuration {config_id} not found"
        )
    
    # Check name conflict if name is being changed
    if config_data.name and config_data.name != config.name:
        existing = db.query(RadiusPskConfig).filter(
            RadiusPskConfig.name == config_data.name,
            RadiusPskConfig.id != config_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PSK configuration '{config_data.name}' already exists"
            )
    
    # Validate policy ID if being updated
    update_data = config_data.model_dump(exclude_unset=True)
    if "auth_policy_id" in update_data:
        _validate_policy_id(db, update_data["auth_policy_id"], "auth_policy_id")
    
    # Update fields
    for field, value in update_data.items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    logger.info(f"✅ Updated PSK config: {config.name}")
    
    return _build_psk_config_response(db, config)


@router.delete("/config/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_psk_config(
    config_id: int,
    admin: AdminUser,
    db: DbSession,
):
    """Delete a PSK configuration.
    
    Args:
        config_id: Configuration ID
        db: Database session
        admin: Admin user
        
    Raises:
        HTTPException: If configuration not found
    """
    logger.info(f"Admin {admin['sub']} deleting PSK config {config_id}")
    
    config = db.query(RadiusPskConfig).filter(
        RadiusPskConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PSK configuration {config_id} not found"
        )
    
    db.delete(config)
    db.commit()
    
    logger.info(f"✅ Deleted PSK config: {config.name}")
