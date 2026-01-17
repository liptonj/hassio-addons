"""RADIUS Client CRUD API endpoints."""

import logging
import math
import subprocess
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from radius_app.api.deps import AdminUser, DbSession
from radius_app.db.models import RadiusClient
from radius_app.schemas.clients import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientListResponse,
    ClientTestRequest,
    ClientTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/clients", response_model=ClientListResponse)
async def list_clients(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or IP"),
) -> ClientListResponse:
    """
    List all RADIUS clients with pagination and filtering.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page
        is_active: Filter by active status
        search: Search term for name or IP address
        
    Returns:
        Paginated list of RADIUS clients
    """
    logger.info(f"Listing clients requested by {admin['sub']} from {admin['ip']}")
    
    # Build query
    query = select(RadiusClient)
    
    # Apply filters
    if is_active is not None:
        query = query.where(RadiusClient.is_active == is_active)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (RadiusClient.name.ilike(search_pattern)) |
            (RadiusClient.ipaddr.ilike(search_pattern)) |
            (RadiusClient.network_name.ilike(search_pattern))
        )
    
    # Get total count
    total_query = select(func.count()).select_from(query.subquery())
    total = db.execute(total_query).scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(RadiusClient.created_at.desc())
    
    # Execute query
    clients = db.execute(query).scalars().all()
    
    # Calculate pages
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return ClientListResponse(
        items=[ClientResponse.model_validate(client) for client in clients],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/api/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    admin: AdminUser,
    db: DbSession,
) -> ClientResponse:
    """
    Get a single RADIUS client by ID.
    
    Args:
        client_id: Client ID
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        RADIUS client details
        
    Raises:
        HTTPException: 404 if client not found
    """
    logger.info(f"Getting client {client_id} requested by {admin['sub']}")
    
    client = db.get(RadiusClient, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with ID {client_id} not found",
        )
    
    return ClientResponse.model_validate(client)


@router.post("/api/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    admin: AdminUser,
    db: DbSession,
) -> ClientResponse:
    """
    Create a new RADIUS client.
    
    Args:
        client_data: Client data to create
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Created client details
        
    Raises:
        HTTPException: 409 if client with same name already exists
    """
    logger.info(f"Creating client '{client_data.name}' by {admin['sub']}")
    
    # Check for duplicate name
    existing = db.execute(
        select(RadiusClient).where(RadiusClient.name == client_data.name)
    ).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Client with name '{client_data.name}' already exists",
        )
    
    # Create client
    client = RadiusClient(
        **client_data.model_dump(exclude={"created_by"}),
        created_by=admin["sub"],
    )
    
    try:
        db.add(client)
        db.commit()
        db.refresh(client)
        
        logger.info(f"✅ Client '{client.name}' created successfully (ID: {client.id})")
        
        return ClientResponse.model_validate(client)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client creation failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create client",
        )


@router.put("/api/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    admin: AdminUser,
    db: DbSession,
) -> ClientResponse:
    """
    Update an existing RADIUS client.
    
    Args:
        client_id: Client ID to update
        client_data: Updated client data
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Updated client details
        
    Raises:
        HTTPException: 404 if client not found, 409 if name conflict
    """
    logger.info(f"Updating client {client_id} by {admin['sub']}")
    
    # Get existing client
    client = db.get(RadiusClient, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with ID {client_id} not found",
        )
    
    # Check for name conflict if name is being changed
    if client_data.name and client_data.name != client.name:
        existing = db.execute(
            select(RadiusClient).where(RadiusClient.name == client_data.name)
        ).scalar_one_or_none()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Client with name '{client_data.name}' already exists",
            )
    
    # Update fields
    update_data = client_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)
    
    try:
        db.commit()
        db.refresh(client)
        
        logger.info(f"✅ Client {client_id} updated successfully")
        
        return ClientResponse.model_validate(client)
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error updating client: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Client update failed due to database constraint violation",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update client",
        )


@router.delete("/api/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    admin: AdminUser,
    db: DbSession,
    hard_delete: bool = Query(False, description="Permanently delete (default: soft delete)"),
) -> None:
    """
    Delete a RADIUS client (soft delete by default).
    
    Args:
        client_id: Client ID to delete
        admin: Authenticated admin user
        db: Database session
        hard_delete: If True, permanently delete; if False, set is_active=False
        
    Raises:
        HTTPException: 404 if client not found
    """
    logger.info(f"Deleting client {client_id} ({'hard' if hard_delete else 'soft'}) by {admin['sub']}")
    
    # Get existing client
    client = db.get(RadiusClient, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with ID {client_id} not found",
        )
    
    try:
        if hard_delete:
            db.delete(client)
            logger.info(f"✅ Client {client_id} permanently deleted")
        else:
            client.is_active = False
            logger.info(f"✅ Client {client_id} deactivated (soft delete)")
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client",
        )


@router.post("/api/clients/{client_id}/test", response_model=ClientTestResponse)
async def test_client(
    client_id: int,
    test_request: ClientTestRequest,
    admin: AdminUser,
    db: DbSession,
) -> ClientTestResponse:
    """
    Test RADIUS client connectivity using radtest.
    
    Args:
        client_id: Client ID to test
        test_request: Test parameters (username, password)
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Test result
        
    Raises:
        HTTPException: 404 if client not found
    """
    logger.info(f"Testing client {client_id} by {admin['sub']}")
    
    # Get client
    client = db.get(RadiusClient, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client with ID {client_id} not found",
        )
    
    # Run radtest
    try:
        # radtest usage: radtest <user> <password> <server> <port> <secret>
        result = subprocess.run(
            [
                "radtest",
                test_request.username,
                test_request.password,
                "localhost",
                "1812",
                client.secret,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        if success:
            message = f"✅ RADIUS test successful for client '{client.name}'"
        else:
            message = f"❌ RADIUS test failed for client '{client.name}'"
        
        logger.info(f"Client {client_id} test result: {'success' if success else 'failed'}")
        
        return ClientTestResponse(
            success=success,
            message=message,
            output=output,
        )
        
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout testing client {client_id}")
        return ClientTestResponse(
            success=False,
            message="Test timeout - RADIUS server may be unresponsive",
            output=None,
        )
    except Exception as e:
        logger.error(f"Error testing client {client_id}: {e}", exc_info=True)
        return ClientTestResponse(
            success=False,
            message=f"Test failed: {str(e)}",
            output=None,
        )
