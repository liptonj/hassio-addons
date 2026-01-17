"""Unlang Policy Management API endpoints.

Unlang policies define authorization conditions and link to profiles.
This is the "WHEN" layer - determining when to apply which profile.
"""

import logging
import math
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import (
    RadiusUnlangPolicy,
    RadiusPolicy,
    RadiusMacBypassConfig,
    RadiusEapMethod,
)
from radius_app.schemas.unlang_policy import (
    UnlangPolicyCreate,
    UnlangPolicyUpdate,
    UnlangPolicyResponse,
    UnlangPolicyListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unlang-policies", tags=["unlang-policies"])


def _get_profile_name(db, profile_id: Optional[int]) -> Optional[str]:
    """Get profile name by ID."""
    if profile_id is None:
        return None
    profile = db.query(RadiusPolicy).filter(RadiusPolicy.id == profile_id).first()
    return profile.name if profile else None


def _validate_profile_id(db, profile_id: Optional[int], field_name: str) -> None:
    """Validate that a profile ID exists if provided."""
    if profile_id is not None:
        profile = db.query(RadiusPolicy).filter(RadiusPolicy.id == profile_id).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name}: profile with ID {profile_id} not found"
            )


def _get_policy_usage(db, policy_id: int) -> tuple[List[str], List[str]]:
    """Get which auth methods use this policy."""
    # Check MAC bypass configs
    mac_bypass_configs = db.query(RadiusMacBypassConfig).filter(
        (RadiusMacBypassConfig.registered_policy_id == policy_id) |
        (RadiusMacBypassConfig.unregistered_policy_id == policy_id)
    ).all()
    mac_bypass_names = [config.name for config in mac_bypass_configs]
    
    # Check EAP methods
    eap_methods = db.query(RadiusEapMethod).filter(
        (RadiusEapMethod.success_policy_id == policy_id) |
        (RadiusEapMethod.failure_policy_id == policy_id)
    ).all()
    eap_method_names = [method.method_name for method in eap_methods]
    
    return mac_bypass_names, eap_method_names


def _build_policy_response(db, policy: RadiusUnlangPolicy) -> UnlangPolicyResponse:
    """Build unlang policy response with profile name and usage info."""
    mac_bypass_names, eap_method_names = _get_policy_usage(db, policy.id)
    
    return UnlangPolicyResponse(
        id=policy.id,
        name=policy.name,
        description=policy.description,
        priority=policy.priority,
        policy_type=policy.policy_type,
        section=policy.section,
        condition_type=policy.condition_type,
        condition_attribute=policy.condition_attribute,
        condition_operator=policy.condition_operator,
        condition_value=policy.condition_value,
        sql_condition=policy.sql_condition,
        additional_conditions=policy.additional_conditions,
        condition_logic=policy.condition_logic,
        action_type=policy.action_type,
        authorization_profile_id=policy.authorization_profile_id,
        module_name=policy.module_name,
        custom_unlang=policy.custom_unlang,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        created_by=policy.created_by,
        authorization_profile_name=_get_profile_name(db, policy.authorization_profile_id),
        used_by_mac_bypass=mac_bypass_names,
        used_by_eap_methods=eap_method_names,
    )


@router.get("", response_model=UnlangPolicyListResponse)
async def list_unlang_policies(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    policy_type: Optional[str] = Query(None, description="Filter by policy type"),
    section: Optional[str] = Query(None, description="Filter by section"),
) -> UnlangPolicyListResponse:
    """List all unlang authorization policies.
    
    These are the policies that define conditions and link to profiles.
    """
    logger.info(f"Listing unlang policies requested by {admin['sub']}")
    
    # Build query
    query = select(RadiusUnlangPolicy)
    
    # Apply filters
    if is_active is not None:
        query = query.where(RadiusUnlangPolicy.is_active == is_active)
    
    if policy_type:
        query = query.where(RadiusUnlangPolicy.policy_type == policy_type)
    
    if section:
        query = query.where(RadiusUnlangPolicy.section == section)
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(RadiusUnlangPolicy.priority.asc())
    
    # Execute query
    policies = db.execute(query).scalars().all()
    
    # Calculate pages
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return UnlangPolicyListResponse(
        items=[_build_policy_response(db, policy) for policy in policies],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{policy_id}", response_model=UnlangPolicyResponse)
async def get_unlang_policy(
    policy_id: int,
    admin: AdminUser,
    db: DbSession,
) -> UnlangPolicyResponse:
    """Get a single unlang policy by ID."""
    logger.info(f"Getting unlang policy {policy_id} requested by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusUnlangPolicy).where(RadiusUnlangPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unlang policy with ID {policy_id} not found",
        )
    
    return _build_policy_response(db, policy)


@router.post("", response_model=UnlangPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_unlang_policy(
    policy_data: UnlangPolicyCreate,
    admin: AdminUser,
    db: DbSession,
) -> UnlangPolicyResponse:
    """Create a new unlang authorization policy."""
    logger.info(f"Creating unlang policy '{policy_data.name}' by {admin['sub']}")
    
    # Check for duplicate name
    existing = db.execute(
        select(RadiusUnlangPolicy).where(RadiusUnlangPolicy.name == policy_data.name)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unlang policy with name '{policy_data.name}' already exists",
        )
    
    # Validate profile ID if provided
    _validate_profile_id(db, policy_data.authorization_profile_id, "authorization_profile_id")
    
    try:
        # Convert additional conditions to dict
        additional_conds = None
        if policy_data.additional_conditions:
            additional_conds = [cond.model_dump() for cond in policy_data.additional_conditions]
        
        policy = RadiusUnlangPolicy(
            name=policy_data.name,
            description=policy_data.description,
            priority=policy_data.priority,
            policy_type=policy_data.policy_type,
            section=policy_data.section,
            condition_type=policy_data.condition_type,
            condition_attribute=policy_data.condition_attribute,
            condition_operator=policy_data.condition_operator,
            condition_value=policy_data.condition_value,
            sql_condition=policy_data.sql_condition,
            additional_conditions=additional_conds,
            condition_logic=policy_data.condition_logic,
            action_type=policy_data.action_type,
            authorization_profile_id=policy_data.authorization_profile_id,
            module_name=policy_data.module_name,
            custom_unlang=policy_data.custom_unlang,
            is_active=policy_data.is_active,
            created_by=admin["sub"],
        )
        
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        logger.info(f"✅ Unlang policy '{policy.name}' created successfully (ID: {policy.id})")
        
        return _build_policy_response(db, policy)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating unlang policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy creation failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating unlang policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create policy",
        )


@router.put("/{policy_id}", response_model=UnlangPolicyResponse)
async def update_unlang_policy(
    policy_id: int,
    policy_data: UnlangPolicyUpdate,
    admin: AdminUser,
    db: DbSession,
) -> UnlangPolicyResponse:
    """Update an existing unlang policy."""
    logger.info(f"Updating unlang policy {policy_id} by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusUnlangPolicy).where(RadiusUnlangPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unlang policy with ID {policy_id} not found",
        )
    
    # Check for duplicate name
    if policy_data.name and policy_data.name != policy.name:
        existing = db.execute(
            select(RadiusUnlangPolicy).where(
                RadiusUnlangPolicy.name == policy_data.name,
                RadiusUnlangPolicy.id != policy_id
            )
        ).scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unlang policy with name '{policy_data.name}' already exists",
            )
    
    # Validate profile ID if being updated
    update_data = policy_data.model_dump(exclude_unset=True)
    if "authorization_profile_id" in update_data:
        _validate_profile_id(db, update_data["authorization_profile_id"], "authorization_profile_id")
    
    try:
        # Handle additional conditions
        if "additional_conditions" in update_data and update_data["additional_conditions"]:
            update_data["additional_conditions"] = [
                cond.model_dump() if hasattr(cond, 'model_dump') else cond 
                for cond in update_data["additional_conditions"]
            ]
        
        # Update fields
        for field, value in update_data.items():
            setattr(policy, field, value)
        
        db.commit()
        db.refresh(policy)
        
        logger.info(f"✅ Unlang policy '{policy.name}' updated successfully")
        
        return _build_policy_response(db, policy)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error updating unlang policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy update failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating unlang policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update policy",
        )


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unlang_policy(
    policy_id: int,
    admin: AdminUser,
    db: DbSession,
):
    """Delete an unlang policy.
    
    Will fail if the policy is currently in use by any auth method.
    """
    logger.info(f"Deleting unlang policy {policy_id} by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusUnlangPolicy).where(RadiusUnlangPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unlang policy with ID {policy_id} not found",
        )
    
    # Check if policy is in use
    mac_bypass_names, eap_method_names = _get_policy_usage(db, policy_id)
    if mac_bypass_names or eap_method_names:
        in_use_by = []
        if mac_bypass_names:
            in_use_by.append(f"MAC bypass configs: {', '.join(mac_bypass_names)}")
        if eap_method_names:
            in_use_by.append(f"EAP methods: {', '.join(eap_method_names)}")
        
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete policy in use by: {'; '.join(in_use_by)}",
        )
    
    try:
        db.delete(policy)
        db.commit()
        
        logger.info(f"✅ Unlang policy '{policy.name}' deleted successfully")
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error deleting unlang policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete policy - it may still be referenced",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting unlang policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete policy",
        )
