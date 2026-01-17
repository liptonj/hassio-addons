"""UDN Assignment CRUD API endpoints."""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import UdnAssignment
from radius_app.schemas.udn_assignments import (
    UdnAssignmentCreate,
    UdnAssignmentUpdate,
    UdnAssignmentResponse,
    UdnAssignmentListResponse,
    AvailableUdnResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# UDN ID constants
UDN_MIN = 2
UDN_MAX = 16777200


def get_next_available_udn(db) -> int:
    """
    Get the next available UDN ID.
    
    Finds the smallest unused UDN ID in the range 2-16777200.
    
    Args:
        db: Database session
        
    Returns:
        Next available UDN ID
        
    Raises:
        ValueError: If no UDN IDs are available
    """
    # Get all assigned UDN IDs
    assigned_udns = db.execute(
        select(UdnAssignment.udn_id).order_by(UdnAssignment.udn_id)
    ).scalars().all()
    
    assigned_set = set(assigned_udns)
    
    # Find first available ID
    for udn_id in range(UDN_MIN, UDN_MAX + 1):
        if udn_id not in assigned_set:
            return udn_id
    
    # No available IDs (shouldn't happen with 16M+ range)
    raise ValueError("No available UDN IDs - all allocated")


@router.get("/api/udn-assignments", response_model=UdnAssignmentListResponse)
async def list_udn_assignments(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by MAC, user name, email, or unit"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    network_id: Optional[str] = Query(None, description="Filter by network ID"),
) -> UdnAssignmentListResponse:
    """
    List all UDN assignments with pagination and filtering.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        is_active: Filter by active status
        search: Search term for MAC, user name, email, or unit
        user_id: Filter by user ID
        network_id: Filter by Meraki network ID
        
    Returns:
        Paginated list of UDN assignments
    """
    logger.info(f"Listing UDN assignments requested by {admin['sub']} from {admin['ip']}")
    
    # Build query
    query = select(UdnAssignment)
    
    # Apply filters
    if is_active is not None:
        query = query.where(UdnAssignment.is_active == is_active)
    
    if user_id is not None:
        query = query.where(UdnAssignment.user_id == user_id)
    
    if network_id:
        query = query.where(UdnAssignment.network_id == network_id)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (UdnAssignment.mac_address.ilike(search_pattern)) |
            (UdnAssignment.user_name.ilike(search_pattern)) |
            (UdnAssignment.user_email.ilike(search_pattern)) |
            (UdnAssignment.unit.ilike(search_pattern))
        )
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(UdnAssignment.created_at.desc())
    
    # Execute query
    assignments = db.execute(query).scalars().all()
    
    # Calculate pages
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return UdnAssignmentListResponse(
        items=[UdnAssignmentResponse.model_validate(assignment) for assignment in assignments],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/api/udn-assignments/{assignment_id}", response_model=UdnAssignmentResponse)
async def get_udn_assignment(
    assignment_id: int,
    admin: AdminUser,
    db: DbSession,
) -> UdnAssignmentResponse:
    """
    Get a single UDN assignment by ID.
    
    Args:
        assignment_id: Assignment ID
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        UDN assignment details
        
    Raises:
        HTTPException: 404 if assignment not found
    """
    logger.info(f"Getting UDN assignment {assignment_id} requested by {admin['sub']}")
    
    assignment = db.get(UdnAssignment, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UDN assignment with ID {assignment_id} not found",
        )
    
    return UdnAssignmentResponse.model_validate(assignment)


@router.get("/api/udn-assignments/by-mac/{mac_address}", response_model=UdnAssignmentResponse)
async def get_udn_assignment_by_mac(
    mac_address: str,
    admin: AdminUser,
    db: DbSession,
) -> UdnAssignmentResponse:
    """
    Get a UDN assignment by MAC address.
    
    Args:
        mac_address: MAC address (any format)
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        UDN assignment details
        
    Raises:
        HTTPException: 404 if assignment not found
    """
    from radius_app.schemas.udn_assignments import normalize_mac_address
    
    try:
        normalized_mac = normalize_mac_address(mac_address)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    logger.info(f"Getting UDN assignment for MAC {normalized_mac} by {admin['sub']}")
    
    assignment = db.execute(
        select(UdnAssignment).where(UdnAssignment.mac_address == normalized_mac)
    ).scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No UDN assignment found for MAC address {normalized_mac}",
        )
    
    return UdnAssignmentResponse.model_validate(assignment)


@router.get("/api/udn-assignments/available-udn", response_model=AvailableUdnResponse)
async def get_available_udn(
    admin: AdminUser,
    db: DbSession,
) -> AvailableUdnResponse:
    """
    Get the next available UDN ID.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Next available UDN ID and statistics
    """
    logger.info(f"Getting next available UDN requested by {admin['sub']}")
    
    try:
        next_udn = get_next_available_udn(db)
        total_assigned = db.execute(select(func.count(UdnAssignment.id))).scalar()
        total_available = (UDN_MAX - UDN_MIN + 1) - total_assigned
        
        return AvailableUdnResponse(
            udn_id=next_udn,
            total_assigned=total_assigned,
            total_available=total_available,
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=str(e),
        )


@router.post("/api/udn-assignments", response_model=UdnAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_udn_assignment(
    assignment_data: UdnAssignmentCreate,
    admin: AdminUser,
    db: DbSession,
) -> UdnAssignmentResponse:
    """
    Create a new UDN assignment.
    
    If udn_id is not provided, automatically assigns the next available ID.
    
    Args:
        assignment_data: Assignment data to create
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Created assignment details
        
    Raises:
        HTTPException: 409 if MAC address or UDN ID already exists
    """
    # UDN is assigned to USER (not MAC). MAC is optional.
    if not assignment_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required for UDN assignment"
        )
    
    logger.info(f"Creating UDN assignment for User {assignment_data.user_id} by {admin.get('sub', 'unknown')}")
    
    # Check if user already has UDN assignment
    existing_user = db.execute(
        select(UdnAssignment).where(
            UdnAssignment.user_id == assignment_data.user_id,
            UdnAssignment.is_active == True
        )
    ).scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {assignment_data.user_id} already has UDN assignment (UDN ID: {existing_user.udn_id})",
        )
    
    # Check for duplicate MAC address if provided (optional)
    if assignment_data.mac_address:
        existing_mac = db.execute(
            select(UdnAssignment).where(UdnAssignment.mac_address == assignment_data.mac_address)
        ).scalar_one_or_none()
        
        if existing_mac:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"MAC address '{assignment_data.mac_address}' is already assigned to User {existing_mac.user_id}",
            )
    
    # Auto-assign UDN ID if not provided
    udn_id = assignment_data.udn_id
    if udn_id is None:
        try:
            udn_id = get_next_available_udn(db)
            logger.info(f"Auto-assigned UDN ID: {udn_id}")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail=str(e),
            )
    else:
        # Check if UDN ID is already assigned
        existing_udn = db.execute(
            select(UdnAssignment).where(UdnAssignment.udn_id == udn_id)
        ).scalar_one_or_none()
        
        if existing_udn:
            mac_str = f"MAC {existing_udn.mac_address}" if existing_udn.mac_address else "no MAC"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"UDN ID {udn_id} is already assigned to User {existing_udn.user_id} ({mac_str})",
            )
    
    # Create assignment
    assignment = UdnAssignment(
        **assignment_data.model_dump(exclude={"udn_id"}),
        udn_id=udn_id,
    )
    
    try:
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        
        mac_str = f"MAC {assignment.mac_address}" if assignment.mac_address else "no MAC"
        logger.info(f"✅ UDN assignment created: User {assignment.user_id} ({mac_str}) -> UDN {assignment.udn_id} (ID: {assignment.id})")
        
        return UdnAssignmentResponse.model_validate(assignment)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating UDN assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="UDN assignment creation failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating UDN assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create UDN assignment",
        )


@router.put("/api/udn-assignments/{assignment_id}", response_model=UdnAssignmentResponse)
async def update_udn_assignment(
    assignment_id: int,
    assignment_data: UdnAssignmentUpdate,
    admin: AdminUser,
    db: DbSession,
) -> UdnAssignmentResponse:
    """
    Update an existing UDN assignment.
    
    Args:
        assignment_id: Assignment ID to update
        assignment_data: Updated assignment data
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Updated assignment details
        
    Raises:
        HTTPException: 404 if assignment not found, 409 if conflict
    """
    logger.info(f"Updating UDN assignment {assignment_id} by {admin['sub']}")
    
    # Get existing assignment
    assignment = db.get(UdnAssignment, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UDN assignment with ID {assignment_id} not found",
        )
    
    # Check for MAC address conflict if MAC is being changed
    if assignment_data.mac_address and assignment_data.mac_address != assignment.mac_address:
        existing_mac = db.execute(
            select(UdnAssignment).where(UdnAssignment.mac_address == assignment_data.mac_address)
        ).scalar_one_or_none()
        
        if existing_mac:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"MAC address '{assignment_data.mac_address}' is already assigned",
            )
    
    # Check for UDN ID conflict if UDN is being changed
    if assignment_data.udn_id and assignment_data.udn_id != assignment.udn_id:
        existing_udn = db.execute(
            select(UdnAssignment).where(UdnAssignment.udn_id == assignment_data.udn_id)
        ).scalar_one_or_none()
        
        if existing_udn:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"UDN ID {assignment_data.udn_id} is already assigned",
            )
    
    # Update fields
    update_data = assignment_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assignment, field, value)
    
    try:
        db.commit()
        db.refresh(assignment)
        
        logger.info(f"✅ UDN assignment {assignment_id} updated successfully")
        
        return UdnAssignmentResponse.model_validate(assignment)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error updating UDN assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="UDN assignment update failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating UDN assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update UDN assignment",
        )


@router.delete("/api/udn-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_udn_assignment(
    assignment_id: int,
    admin: AdminUser,
    db: DbSession,
    hard_delete: bool = Query(False, description="Permanently delete (default: soft delete)"),
) -> None:
    """
    Delete a UDN assignment (soft delete by default).
    
    Args:
        assignment_id: Assignment ID to delete
        admin: Authenticated admin user
        db: Database session
        hard_delete: If True, permanently delete; if False, set is_active=False
        
    Raises:
        HTTPException: 404 if assignment not found
    """
    logger.info(f"Deleting UDN assignment {assignment_id} ({'hard' if hard_delete else 'soft'}) by {admin['sub']}")
    
    # Get existing assignment
    assignment = db.get(UdnAssignment, assignment_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UDN assignment with ID {assignment_id} not found",
        )
    
    try:
        if hard_delete:
            db.delete(assignment)
            logger.info(f"✅ UDN assignment {assignment_id} permanently deleted")
        else:
            assignment.is_active = False
            logger.info(f"✅ UDN assignment {assignment_id} deactivated (soft delete)")
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting UDN assignment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete UDN assignment",
        )
