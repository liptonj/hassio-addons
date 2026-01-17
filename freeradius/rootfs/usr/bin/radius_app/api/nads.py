"""Network Access Device (NAD) Management API endpoints."""

import logging
import math
import socket
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import RadiusClient, RadiusNadExtended, RadiusNadHealth
from radius_app.schemas.nad import (
    NadCreate,
    NadUpdate,
    NadResponse,
    NadListResponse,
    NadHealthStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_nad_response(
    client: RadiusClient,
    extended: Optional[RadiusNadExtended],
    health: Optional[RadiusNadHealth]
) -> NadResponse:
    """Build NAD response from database models."""
    # Build base data from client
    nad_data = {
        "id": client.id,
        "name": client.name,
        "description": extended.description if extended else None,
        "ipaddr": client.ipaddr,
        "secret": client.secret,
        "nas_type": client.nas_type,
        "vendor": extended.vendor if extended else None,
        "model": extended.model if extended else None,
        "location": extended.location if extended else None,
        "radsec_enabled": extended.radsec_enabled if extended else False,
        "radsec_port": extended.radsec_port if extended else None,
        "require_tls_cert": extended.require_tls_cert if extended else False,
        "coa_enabled": extended.coa_enabled if extended else False,
        "coa_port": extended.coa_port if extended else None,
        "require_message_authenticator": client.require_message_authenticator,
        "virtual_server": extended.virtual_server if extended else None,
        "is_active": client.is_active,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
        "created_by": client.created_by,
    }
    
    # Add health status if available
    if health:
        nad_data["health_status"] = NadHealthStatus(
            is_reachable=health.is_reachable,
            last_seen=health.last_seen,
            request_count=health.request_count,
            success_count=health.success_count,
            failure_count=health.failure_count,
            avg_response_time_ms=health.avg_response_time_ms,
        )
    
    return NadResponse(**nad_data)


@router.get("/api/nads", response_model=NadListResponse)
async def list_nads(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name, vendor, or location"),
) -> NadListResponse:
    """
    List all Network Access Devices with health status.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        is_active: Filter by active status
        search: Search term
        
    Returns:
        Paginated list of NADs with health information
    """
    logger.info(f"Listing NADs requested by {admin['sub']} from {admin['ip']}")
    
    # Build query with joins
    query = select(RadiusClient).outerjoin(
        RadiusNadExtended,
        RadiusClient.id == RadiusNadExtended.radius_client_id
    )
    
    # Apply filters
    if is_active is not None:
        query = query.where(RadiusClient.is_active == is_active)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (RadiusClient.name.ilike(search_pattern)) |
            (RadiusNadExtended.vendor.ilike(search_pattern)) |
            (RadiusNadExtended.location.ilike(search_pattern))
        )
    
    # Get total count
    total_query = select(func.count(RadiusClient.id)).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(RadiusClient.created_at.desc())
    
    # Execute query
    clients = db.execute(query).scalars().all()
    
    # Build response with extended info and health
    nad_responses = []
    for client in clients:
        # Get extended info
        extended = db.execute(
            select(RadiusNadExtended).where(
                RadiusNadExtended.radius_client_id == client.id
            )
        ).scalar_one_or_none()
        
        # Get health info
        health = None
        if extended:
            health = db.execute(
                select(RadiusNadHealth).where(
                    RadiusNadHealth.nad_id == extended.id
                )
            ).scalar_one_or_none()
        
        nad_responses.append(_build_nad_response(client, extended, health))
    
    # Calculate pages
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return NadListResponse(
        items=nad_responses,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/api/nads/{nad_id}", response_model=NadResponse)
async def get_nad(
    nad_id: int,
    admin: AdminUser,
    db: DbSession,
) -> NadResponse:
    """
    Get a single NAD by ID with extended information.
    
    Args:
        nad_id: NAD ID (RADIUS client ID)
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        NAD details with health status
        
    Raises:
        HTTPException: 404 if NAD not found
    """
    logger.info(f"Getting NAD {nad_id} requested by {admin['sub']}")
    
    # Get client
    client = db.execute(
        select(RadiusClient).where(RadiusClient.id == nad_id)
    ).scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAD with ID {nad_id} not found",
        )
    
    # Get extended info
    extended = db.execute(
        select(RadiusNadExtended).where(
            RadiusNadExtended.radius_client_id == client.id
        )
    ).scalar_one_or_none()
    
    # Get health info
    health = None
    if extended:
        health = db.execute(
            select(RadiusNadHealth).where(
                RadiusNadHealth.nad_id == extended.id
            )
        ).scalar_one_or_none()
    
    return _build_nad_response(client, extended, health)


@router.post("/api/nads", response_model=NadResponse, status_code=status.HTTP_201_CREATED)
async def create_nad(
    nad_data: NadCreate,
    admin: AdminUser,
    db: DbSession,
) -> NadResponse:
    """
    Create a new Network Access Device.
    
    Creates both the RADIUS client and extended NAD information.
    
    Args:
        nad_data: NAD data to create
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Created NAD details
        
    Raises:
        HTTPException: 409 if NAD with same name already exists
    """
    logger.info(f"Creating NAD '{nad_data.name}' by {admin['sub']}")
    
    # Check for duplicate name
    existing = db.execute(
        select(RadiusClient).where(RadiusClient.name == nad_data.name)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"NAD with name '{nad_data.name}' already exists",
        )
    
    try:
        # Create RADIUS client
        client = RadiusClient(
            name=nad_data.name,
            ipaddr=nad_data.ipaddr,
            secret=nad_data.secret,
            nas_type=nad_data.nas_type,
            require_message_authenticator=nad_data.require_message_authenticator,
            is_active=nad_data.is_active,
            created_by=admin["sub"],
        )
        db.add(client)
        db.flush()  # Get client.id
        
        # Create extended NAD info
        extended = RadiusNadExtended(
            radius_client_id=client.id,
            description=nad_data.description,
            vendor=nad_data.vendor,
            model=nad_data.model,
            location=nad_data.location,
            radsec_enabled=nad_data.radsec_enabled,
            radsec_port=nad_data.radsec_port,
            require_tls_cert=nad_data.require_tls_cert,
            coa_enabled=nad_data.coa_enabled,
            coa_port=nad_data.coa_port,
            virtual_server=nad_data.virtual_server,
            capabilities=nad_data.capabilities.model_dump() if nad_data.capabilities else None,
        )
        db.add(extended)
        db.flush()  # Get extended.id
        
        # Create initial health record
        health = RadiusNadHealth(
            nad_id=extended.id,
            is_reachable=False,
            request_count=0,
            success_count=0,
            failure_count=0,
        )
        db.add(health)
        
        db.commit()
        db.refresh(client)
        db.refresh(extended)
        db.refresh(health)
        
        logger.info(f"✅ NAD '{client.name}' created successfully (ID: {client.id})")
        
        return _build_nad_response(client, extended, health)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating NAD: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="NAD creation failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating NAD: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create NAD",
        )


@router.put("/api/nads/{nad_id}", response_model=NadResponse)
async def update_nad(
    nad_id: int,
    nad_data: NadUpdate,
    admin: AdminUser,
    db: DbSession,
) -> NadResponse:
    """
    Update an existing Network Access Device.
    
    Args:
        nad_id: NAD ID to update
        nad_data: Updated NAD data (only provided fields are updated)
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Updated NAD details
        
    Raises:
        HTTPException: 404 if NAD not found, 409 if name conflict
    """
    logger.info(f"Updating NAD {nad_id} by {admin['sub']}")
    
    # Get client
    client = db.execute(
        select(RadiusClient).where(RadiusClient.id == nad_id)
    ).scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAD with ID {nad_id} not found",
        )
    
    # Get or create extended info
    extended = db.execute(
        select(RadiusNadExtended).where(
            RadiusNadExtended.radius_client_id == client.id
        )
    ).scalar_one_or_none()
    
    if not extended:
        # Create extended record if it doesn't exist
        extended = RadiusNadExtended(
            radius_client_id=client.id,
        )
        db.add(extended)
        db.flush()
    
    try:
        # Update client fields
        update_data = nad_data.model_dump(exclude_unset=True)
        
        # Fields that go to RadiusClient
        client_fields = ["name", "ipaddr", "secret", "nas_type", "require_message_authenticator", "is_active"]
        for field in client_fields:
            if field in update_data:
                setattr(client, field, update_data[field])
        
        # Fields that go to RadiusNadExtended
        extended_fields = [
            "description", "vendor", "model", "location",
            "radsec_enabled", "radsec_port", "require_tls_cert",
            "coa_enabled", "coa_port", "virtual_server"
        ]
        for field in extended_fields:
            if field in update_data:
                setattr(extended, field, update_data[field])
        
        db.commit()
        db.refresh(client)
        db.refresh(extended)
        
        # Get health info
        health = db.execute(
            select(RadiusNadHealth).where(
                RadiusNadHealth.nad_id == extended.id
            )
        ).scalar_one_or_none()
        
        logger.info(f"✅ NAD {nad_id} updated successfully")
        
        return _build_nad_response(client, extended, health)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error updating NAD: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="NAD update failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating NAD: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update NAD",
        )


@router.delete("/api/nads/{nad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_nad(
    nad_id: int,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """
    Delete a Network Access Device (soft delete - marks as inactive).
    
    Args:
        nad_id: NAD ID to delete
        admin: Authenticated admin user
        db: Database session
        
    Raises:
        HTTPException: 404 if NAD not found
    """
    logger.info(f"Deleting NAD {nad_id} by {admin['sub']}")
    
    # Get client
    client = db.execute(
        select(RadiusClient).where(RadiusClient.id == nad_id)
    ).scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAD with ID {nad_id} not found",
        )
    
    try:
        # Soft delete - mark as inactive
        client.is_active = False
        db.commit()
        
        logger.info(f"✅ NAD {nad_id} marked as inactive")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting NAD: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete NAD",
        )


@router.get("/api/nads/{nad_id}/health", response_model=NadHealthStatus)
async def get_nad_health(
    nad_id: int,
    admin: AdminUser,
    db: DbSession,
) -> NadHealthStatus:
    """
    Get detailed health metrics for a NAD.
    
    Args:
        nad_id: NAD ID
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Health status with metrics
        
    Raises:
        HTTPException: 404 if NAD not found or no health data
    """
    logger.info(f"Getting NAD {nad_id} health by {admin['sub']}")
    
    # Get extended info
    extended = db.execute(
        select(RadiusNadExtended).where(
            RadiusNadExtended.radius_client_id == nad_id
        )
    ).scalar_one_or_none()
    
    if not extended:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAD with ID {nad_id} not found",
        )
    
    # Get health info
    health = db.execute(
        select(RadiusNadHealth).where(
            RadiusNadHealth.nad_id == extended.id
        )
    ).scalar_one_or_none()
    
    if not health:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No health data found for NAD {nad_id}",
        )
    
    return NadHealthStatus(
        is_reachable=health.is_reachable,
        last_seen=health.last_seen,
        request_count=health.request_count,
        success_count=health.success_count,
        failure_count=health.failure_count,
        avg_response_time_ms=health.avg_response_time_ms,
    )


@router.post("/api/nads/{nad_id}/test-connection")
async def test_nad_connection(
    nad_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Test connectivity to a NAD.
    
    Performs a simple TCP connection test to the NAD's IP address.
    
    Args:
        nad_id: NAD ID to test
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Test results with latency information
        
    Raises:
        HTTPException: 404 if NAD not found
    """
    logger.info(f"Testing NAD {nad_id} connection by {admin['sub']}")
    
    # Get client
    client = db.execute(
        select(RadiusClient).where(RadiusClient.id == nad_id)
    ).scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAD with ID {nad_id} not found",
        )
    
    # Extract IP address (handle CIDR)
    ip_addr = client.ipaddr.split('/')[0]
    
    # Test connection on RADIUS ports (1812 for auth, 1813 for accounting)
    test_results = []
    
    for port, service in [(1812, "authentication"), (1813, "accounting")]:
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip_addr, port))
            sock.close()
            
            latency_ms = (time.time() - start_time) * 1000
            
            if result == 0:
                test_results.append({
                    "service": service,
                    "port": port,
                    "status": "open",
                    "latency_ms": round(latency_ms, 2),
                })
            else:
                test_results.append({
                    "service": service,
                    "port": port,
                    "status": "closed",
                    "latency_ms": round(latency_ms, 2),
                })
        except socket.timeout:
            test_results.append({
                "service": service,
                "port": port,
                "status": "timeout",
                "latency_ms": 3000,
            })
        except Exception as e:
            test_results.append({
                "service": service,
                "port": port,
                "status": "error",
                "error": str(e),
            })
    
    # Determine overall reachability
    is_reachable = any(r["status"] == "open" for r in test_results)
    
    # Update health record
    extended = db.execute(
        select(RadiusNadExtended).where(
            RadiusNadExtended.radius_client_id == client.id
        )
    ).scalar_one_or_none()
    
    if extended:
        health = db.execute(
            select(RadiusNadHealth).where(
                RadiusNadHealth.nad_id == extended.id
            )
        ).scalar_one_or_none()
        
        if health:
            health.is_reachable = is_reachable
            health.checked_at = datetime.now(timezone.utc)
            if is_reachable:
                health.last_seen = datetime.now(timezone.utc)
            db.commit()
    
    return {
        "nad_id": nad_id,
        "ip_address": ip_addr,
        "is_reachable": is_reachable,
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "tests": test_results,
    }


@router.get("/api/nads/{nad_id}/statistics")
async def get_nad_statistics(
    nad_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Get usage statistics for a NAD.
    
    Args:
        nad_id: NAD ID
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Statistics including request counts and success rates
        
    Raises:
        HTTPException: 404 if NAD not found
    """
    logger.info(f"Getting NAD {nad_id} statistics by {admin['sub']}")
    
    # Get extended info
    extended = db.execute(
        select(RadiusNadExtended).where(
            RadiusNadExtended.radius_client_id == nad_id
        )
    ).scalar_one_or_none()
    
    if not extended:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"NAD with ID {nad_id} not found",
        )
    
    # Get health info
    health = db.execute(
        select(RadiusNadHealth).where(
            RadiusNadHealth.nad_id == extended.id
        )
    ).scalar_one_or_none()
    
    if not health:
        return {
            "nad_id": nad_id,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "success_rate": 0.0,
            "avg_response_time_ms": None,
            "is_reachable": False,
            "last_seen": None,
        }
    
    # Calculate success rate
    success_rate = 0.0
    if health.request_count > 0:
        success_rate = (health.success_count / health.request_count) * 100
    
    return {
        "nad_id": nad_id,
        "total_requests": health.request_count,
        "successful_requests": health.success_count,
        "failed_requests": health.failure_count,
        "success_rate": round(success_rate, 2),
        "avg_response_time_ms": health.avg_response_time_ms,
        "is_reachable": health.is_reachable,
        "last_seen": health.last_seen.isoformat() if health.last_seen else None,
        "last_checked": health.checked_at.isoformat(),
    }
