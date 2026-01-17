"""MAC bypass configuration API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import RadiusMacBypassConfig, RadiusUnlangPolicy
from radius_app.schemas.mac_bypass import (
    MacBypassConfigCreate,
    MacBypassConfigResponse,
    MacBypassConfigUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mac-bypass", tags=["mac-bypass"])


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


def _build_mac_bypass_response(db: DbSession, config: RadiusMacBypassConfig) -> MacBypassConfigResponse:
    """Build MAC bypass config response with policy names."""
    return MacBypassConfigResponse(
        id=config.id,
        name=config.name,
        description=config.description,
        mac_addresses=config.mac_addresses or [],
        bypass_mode=config.bypass_mode,
        require_registration=config.require_registration,
        registered_policy_id=config.registered_policy_id,
        unregistered_policy_id=config.unregistered_policy_id,
        is_active=config.is_active,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
        created_by=config.created_by,
        registered_policy_name=_get_policy_name(db, config.registered_policy_id),
        unregistered_policy_name=_get_policy_name(db, config.unregistered_policy_id),
    )


@router.get("/config", response_model=List[MacBypassConfigResponse])
async def list_mac_bypass_configs(
    admin: AdminUser,
    db: DbSession,
    active_only: bool = False,
) -> List[MacBypassConfigResponse]:
    """List all MAC bypass configurations.
    
    Args:
        db: Database session
        admin: Admin user
        active_only: Only return active configurations (default: False to show all)
        
    Returns:
        List of MAC bypass configurations with policy names
    """
    logger.info(f"Admin {admin["sub"]} listing MAC bypass configurations")
    
    query = db.query(RadiusMacBypassConfig)
    if active_only:
        query = query.filter(RadiusMacBypassConfig.is_active == True)
    
    configs = query.order_by(RadiusMacBypassConfig.name).all()
    
    return [_build_mac_bypass_response(db, config) for config in configs]


@router.post("/config", response_model=MacBypassConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_mac_bypass_config(
    config_data: MacBypassConfigCreate,
    admin: AdminUser,
    db: DbSession,
) -> MacBypassConfigResponse:
    """Create a new MAC bypass configuration.
    
    Args:
        config_data: MAC bypass configuration data
        db: Database session
        admin: Admin user
        
    Returns:
        Created MAC bypass configuration
        
    Raises:
        HTTPException: If configuration name already exists or policy IDs invalid
    """
    logger.info(f"Admin {admin["sub"]} creating MAC bypass config: {config_data.name}")
    
    # Check if name already exists
    existing = db.query(RadiusMacBypassConfig).filter(
        RadiusMacBypassConfig.name == config_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MAC bypass configuration '{config_data.name}' already exists"
        )
    
    # Validate policy IDs if provided
    _validate_policy_id(db, config_data.registered_policy_id, "registered_policy_id")
    _validate_policy_id(db, config_data.unregistered_policy_id, "unregistered_policy_id")
    
    # Create new configuration
    config = RadiusMacBypassConfig(
        name=config_data.name,
        description=config_data.description,
        mac_addresses=config_data.mac_addresses or [],
        bypass_mode=config_data.bypass_mode,
        require_registration=config_data.require_registration,
        registered_policy_id=config_data.registered_policy_id,
        unregistered_policy_id=config_data.unregistered_policy_id,
        is_active=config_data.is_active,
        created_by=admin["sub"],
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    logger.info(f"✅ Created MAC bypass config: {config.name}")
    
    return _build_mac_bypass_response(db, config)


@router.get("/config/{config_id}", response_model=MacBypassConfigResponse)
async def get_mac_bypass_config(
    config_id: int,
    admin: AdminUser,
    db: DbSession,
) -> MacBypassConfigResponse:
    """Get a specific MAC bypass configuration.
    
    Args:
        config_id: Configuration ID
        db: Database session
        admin: Admin user
        
    Returns:
        MAC bypass configuration with policy names
        
    Raises:
        HTTPException: If configuration not found
    """
    config = db.query(RadiusMacBypassConfig).filter(
        RadiusMacBypassConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MAC bypass configuration {config_id} not found"
        )
    
    return _build_mac_bypass_response(db, config)


@router.put("/config/{config_id}", response_model=MacBypassConfigResponse)
async def update_mac_bypass_config(
    config_id: int,
    config_data: MacBypassConfigUpdate,
    admin: AdminUser,
    db: DbSession,
) -> MacBypassConfigResponse:
    """Update a MAC bypass configuration.
    
    Args:
        config_id: Configuration ID
        config_data: Updated configuration data
        db: Database session
        admin: Admin user
        
    Returns:
        Updated MAC bypass configuration with policy names
        
    Raises:
        HTTPException: If configuration not found, name conflict, or invalid policy IDs
    """
    logger.info(f"Admin {admin["sub"]} updating MAC bypass config {config_id}")
    
    config = db.query(RadiusMacBypassConfig).filter(
        RadiusMacBypassConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MAC bypass configuration {config_id} not found"
        )
    
    # Check name conflict if name is being changed
    if config_data.name and config_data.name != config.name:
        existing = db.query(RadiusMacBypassConfig).filter(
            RadiusMacBypassConfig.name == config_data.name,
            RadiusMacBypassConfig.id != config_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MAC bypass configuration '{config_data.name}' already exists"
            )
    
    # Validate policy IDs if being updated
    update_data = config_data.model_dump(exclude_unset=True)
    if "registered_policy_id" in update_data:
        _validate_policy_id(db, update_data["registered_policy_id"], "registered_policy_id")
    if "unregistered_policy_id" in update_data:
        _validate_policy_id(db, update_data["unregistered_policy_id"], "unregistered_policy_id")
    
    # Update fields
    for field, value in update_data.items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    logger.info(f"✅ Updated MAC bypass config: {config.name}")
    
    return _build_mac_bypass_response(db, config)


@router.delete("/config/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mac_bypass_config(
    config_id: int,
    admin: AdminUser,
    db: DbSession,
):
    """Delete a MAC bypass configuration.
    
    Args:
        config_id: Configuration ID
        db: Database session
        admin: Admin user
        
    Raises:
        HTTPException: If configuration not found
    """
    logger.info(f"Admin {admin["sub"]} deleting MAC bypass config {config_id}")
    
    config = db.query(RadiusMacBypassConfig).filter(
        RadiusMacBypassConfig.id == config_id
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MAC bypass configuration {config_id} not found"
        )
    
    db.delete(config)
    db.commit()
    
    logger.info(f"✅ Deleted MAC bypass config: {config.name}")
