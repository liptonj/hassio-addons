"""Policy Management API endpoints."""

import logging
import math
import re
from datetime import datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import RadiusPolicy
from radius_app.schemas.policy import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyListResponse,
    PolicyTestRequest,
    PolicyTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/policies", response_model=PolicyListResponse)
async def list_policies(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    group_name: Optional[str] = Query(None, description="Filter by group name"),
    policy_type: Optional[str] = Query(None, description="Filter by policy type"),
) -> PolicyListResponse:
    """
    List all authorization policies sorted by priority.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        is_active: Filter by active status
        group_name: Filter by group name
        policy_type: Filter by policy type
        
    Returns:
        Paginated list of policies
    """
    logger.info(f"Listing policies requested by {admin['sub']} from {admin['ip']}")
    
    # Build query
    query = select(RadiusPolicy)
    
    # Apply filters
    if is_active is not None:
        query = query.where(RadiusPolicy.is_active == is_active)
    
    if group_name:
        query = query.where(RadiusPolicy.group_name == group_name)
    
    if policy_type:
        query = query.where(RadiusPolicy.policy_type == policy_type)
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination and ordering (by priority)
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(RadiusPolicy.priority.asc())
    
    # Execute query
    policies = db.execute(query).scalars().all()
    
    # Calculate pages
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return PolicyListResponse(
        items=[PolicyResponse.model_validate(policy) for policy in policies],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/api/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: int,
    admin: AdminUser,
    db: DbSession,
) -> PolicyResponse:
    """
    Get a single policy by ID.
    
    Args:
        policy_id: Policy ID
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Policy details
        
    Raises:
        HTTPException: 404 if policy not found
    """
    logger.info(f"Getting policy {policy_id} requested by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusPolicy).where(RadiusPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found",
        )
    
    return PolicyResponse.model_validate(policy)


@router.post("/api/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    policy_data: PolicyCreate,
    admin: AdminUser,
    db: DbSession,
) -> PolicyResponse:
    """
    Create a new authorization policy.
    
    Args:
        policy_data: Policy data to create
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Created policy details
        
    Raises:
        HTTPException: 409 if policy with same name already exists
    """
    logger.info(f"Creating policy '{policy_data.name}' by {admin['sub']}")
    
    # Check for duplicate name
    existing = db.execute(
        select(RadiusPolicy).where(RadiusPolicy.name == policy_data.name)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy with name '{policy_data.name}' already exists",
        )
    
    try:
        # Convert Pydantic models to dict for JSON storage
        reply_attrs = [attr.model_dump() for attr in policy_data.reply_attributes]
        check_attrs = [attr.model_dump() for attr in policy_data.check_attributes]
        time_restrictions = policy_data.time_restrictions.model_dump() if policy_data.time_restrictions else None
        
        # Create policy
        policy = RadiusPolicy(
            name=policy_data.name,
            description=policy_data.description,
            priority=policy_data.priority,
            group_name=policy_data.group_name,
            policy_type=policy_data.policy_type,
            match_username=policy_data.match_username,
            match_mac_address=policy_data.match_mac_address,
            match_calling_station=policy_data.match_calling_station,
            match_nas_identifier=policy_data.match_nas_identifier,
            match_nas_ip=policy_data.match_nas_ip,
            reply_attributes=reply_attrs,
            check_attributes=check_attrs,
            time_restrictions=time_restrictions,
            vlan_id=policy_data.vlan_id,
            vlan_name=policy_data.vlan_name,
            bandwidth_limit_up=policy_data.bandwidth_limit_up,
            bandwidth_limit_down=policy_data.bandwidth_limit_down,
            session_timeout=policy_data.session_timeout,
            idle_timeout=policy_data.idle_timeout,
            max_concurrent_sessions=policy_data.max_concurrent_sessions,
            is_active=policy_data.is_active,
            created_by=admin["sub"],
        )
        
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        logger.info(f"✅ Policy '{policy.name}' created successfully (ID: {policy.id})")
        
        return PolicyResponse.model_validate(policy)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy creation failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create policy",
        )


@router.put("/api/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    policy_data: PolicyUpdate,
    admin: AdminUser,
    db: DbSession,
) -> PolicyResponse:
    """
    Update an existing policy.
    
    Args:
        policy_id: Policy ID to update
        policy_data: Updated policy data (only provided fields are updated)
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Updated policy details
        
    Raises:
        HTTPException: 404 if policy not found, 409 if name conflict
    """
    logger.info(f"Updating policy {policy_id} by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusPolicy).where(RadiusPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found",
        )
    
    try:
        update_data = policy_data.model_dump(exclude_unset=True)
        
        # Convert Pydantic models to dict for JSON storage
        if "reply_attributes" in update_data and update_data["reply_attributes"]:
            update_data["reply_attributes"] = [attr.model_dump() for attr in policy_data.reply_attributes]
        
        if "check_attributes" in update_data and update_data["check_attributes"]:
            update_data["check_attributes"] = [attr.model_dump() for attr in policy_data.check_attributes]
        
        if "time_restrictions" in update_data and update_data["time_restrictions"]:
            update_data["time_restrictions"] = policy_data.time_restrictions.model_dump()
        
        # Update fields
        for field, value in update_data.items():
            setattr(policy, field, value)
        
        db.commit()
        db.refresh(policy)
        
        logger.info(f"✅ Policy {policy_id} updated successfully")
        
        return PolicyResponse.model_validate(policy)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error updating policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy update failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update policy",
        )


@router.delete("/api/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: int,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """
    Delete a policy.
    
    Args:
        policy_id: Policy ID to delete
        admin: Authenticated admin user
        db: Database session
        
    Raises:
        HTTPException: 404 if policy not found
    """
    logger.info(f"Deleting policy {policy_id} by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusPolicy).where(RadiusPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found",
        )
    
    try:
        db.delete(policy)
        db.commit()
        
        logger.info(f"✅ Policy {policy_id} deleted successfully")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete policy",
        )


@router.post("/api/policies/{policy_id}/test", response_model=PolicyTestResponse)
async def test_policy(
    policy_id: int,
    test_data: PolicyTestRequest,
    admin: AdminUser,
    db: DbSession,
) -> PolicyTestResponse:
    """
    Test a policy against sample data.
    
    Simulates policy evaluation without applying it.
    
    Args:
        policy_id: Policy ID to test
        test_data: Test data (username, MAC, NAS info, etc.)
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Test result indicating if policy matches and what attributes would be returned
        
    Raises:
        HTTPException: 404 if policy not found
    """
    logger.info(f"Testing policy {policy_id} by {admin['sub']}")
    
    policy = db.execute(
        select(RadiusPolicy).where(RadiusPolicy.id == policy_id)
    ).scalar_one_or_none()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found",
        )
    
    # Check if policy is active
    if not policy.is_active:
        return PolicyTestResponse(
            matches=False,
            policy_id=policy.id,
            policy_name=policy.name,
            reply_attributes=[],
            reason="Policy is not active",
        )
    
    # Evaluate match conditions
    matches = True
    reasons = []
    
    # Username match
    if policy.match_username:
        pattern = policy.match_username
        if not re.match(pattern, test_data.username):
            matches = False
            reasons.append(f"Username '{test_data.username}' does not match pattern '{pattern}'")
    
    # MAC address match
    if policy.match_mac_address and test_data.mac_address:
        pattern = policy.match_mac_address
        if not re.match(pattern, test_data.mac_address):
            matches = False
            reasons.append(f"MAC address '{test_data.mac_address}' does not match pattern '{pattern}'")
    
    # NAS identifier match
    if policy.match_nas_identifier and test_data.nas_identifier:
        pattern = policy.match_nas_identifier
        if not re.match(pattern, test_data.nas_identifier):
            matches = False
            reasons.append(f"NAS identifier '{test_data.nas_identifier}' does not match pattern '{pattern}'")
    
    # NAS IP match
    if policy.match_nas_ip and test_data.nas_ip:
        pattern = policy.match_nas_ip
        if not re.match(pattern, test_data.nas_ip):
            matches = False
            reasons.append(f"NAS IP '{test_data.nas_ip}' does not match pattern '{pattern}'")
    
    # Time restrictions (basic check - just validate structure)
    if policy.time_restrictions:
        # Could add time-based evaluation here
        pass
    
    # Build response
    if matches:
        # Convert stored reply attributes back to Pydantic models
        from radius_app.schemas.policy import ReplyAttribute
        reply_attrs = [ReplyAttribute(**attr) for attr in (policy.reply_attributes or [])]
        
        return PolicyTestResponse(
            matches=True,
            policy_id=policy.id,
            policy_name=policy.name,
            reply_attributes=reply_attrs,
            reason="All match conditions satisfied",
        )
    else:
        return PolicyTestResponse(
            matches=False,
            policy_id=policy.id,
            policy_name=policy.name,
            reply_attributes=[],
            reason="; ".join(reasons),
        )


@router.get("/api/policies/groups")
async def list_policy_groups(
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    List unique policy groups.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        List of unique group names
    """
    logger.info(f"Listing policy groups requested by {admin['sub']}")
    
    # Get distinct group names
    groups = db.execute(
        select(RadiusPolicy.group_name)
        .where(RadiusPolicy.group_name.isnot(None))
        .distinct()
        .order_by(RadiusPolicy.group_name)
    ).scalars().all()
    
    return {
        "groups": list(groups),
        "count": len(groups),
    }


@router.post("/api/policies/reorder")
async def reorder_policies(
    policy_priorities: dict[int, int],
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Batch reorder policies by updating priorities.
    
    Args:
        policy_priorities: Dictionary mapping policy_id to new priority
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Status of reordering operation
        
    Example:
        POST /api/policies/reorder
        {
            "1": 10,
            "2": 20,
            "3": 5
        }
    """
    logger.info(f"Reordering {len(policy_priorities)} policies by {admin['sub']}")
    
    try:
        updated_count = 0
        
        for policy_id, new_priority in policy_priorities.items():
            policy = db.execute(
                select(RadiusPolicy).where(RadiusPolicy.id == int(policy_id))
            ).scalar_one_or_none()
            
            if policy:
                policy.priority = new_priority
                updated_count += 1
        
        db.commit()
        
        logger.info(f"✅ Reordered {updated_count} policies")
        
        return {
            "updated": updated_count,
            "message": f"Successfully reordered {updated_count} policies",
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error reordering policies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder policies",
        )
