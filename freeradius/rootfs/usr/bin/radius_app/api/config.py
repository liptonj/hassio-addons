"""Configuration management endpoints."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from radius_app.api.deps import AdminUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()


class ReloadRequest(BaseModel):
    """Request to reload configuration."""
    force: bool = Field(default=False, description="Force immediate reload")


class ReloadResponse(BaseModel):
    """Response from configuration reload."""
    success: bool
    message: str
    reloaded: bool
    validation_failed: bool = Field(default=False, description="Whether validation failed")


@router.post("/api/reload", response_model=ReloadResponse)
async def reload_configuration(request: ReloadRequest, admin: AdminUser) -> ReloadResponse:
    """
    Trigger immediate configuration reload from database.
    
    With shared database architecture, configuration is automatically
    regenerated when changes are detected. This endpoint allows manual
    triggering if immediate reload is needed.
    
    Args:
        request: Reload options
        admin: Authenticated admin user
        
    Returns:
        Reload result
    """
    from radius_app.core.db_watcher import DatabaseWatcher
    
    logger.info(f"Manual reload requested by {admin['sub']} from {admin['ip']} (force={request.force})")
    
    try:
        watcher = DatabaseWatcher(poll_interval=5)
        result = await watcher.check_and_regenerate(force=request.force)
        
        # Check for validation failures
        if result.get("validation_failed", False):
            message = "Configuration validation failed - NOT reloaded"
            if result.get("clients_regenerated"):
                message += " (clients.conf generated but invalid)"
            if result.get("users_regenerated"):
                message += " (users file generated but invalid)"
            if result.get("policies_regenerated"):
                message += " (policies file generated but invalid)"
            
            return ReloadResponse(
                success=False,
                message=message,
                reloaded=False,
                validation_failed=True,
            )
        
        if result.get("clients_regenerated") or result.get("users_regenerated") or result.get("policies_regenerated"):
            message = "Configuration regenerated"
            if result.get("clients_regenerated"):
                message += " (clients.conf updated)"
            if result.get("users_regenerated"):
                message += " (users file updated)"
            if result.get("policies_regenerated"):
                message += " (policies file updated)"
            
            if result.get("reloaded"):
                message += " and reloaded"
            else:
                message += " but reload failed"
        else:
            message = "No changes detected, config up to date"
        
        return ReloadResponse(
            success=True,
            message=message,
            reloaded=result.get("reloaded", False),
            validation_failed=False,
        )
        
    except Exception as e:
        logger.error(f"Reload failed: {e}", exc_info=True)
        return ReloadResponse(
            success=False,
            message=f"Reload failed: {str(e)}",
            reloaded=False,
        )


@router.get("/api/config/status")
async def get_config_status(admin: AdminUser, db: DbSession) -> dict:
    """
    Get configuration status from database.
    
    Args:
        admin: Authenticated admin user
        db: Database session
    
    Returns:
        Configuration statistics
    """
    from radius_app.db.models import RadiusClient, UdnAssignment
    
    logger.info(f"Config status requested by {admin['sub']} from {admin['ip']}")
    
    clients_count = db.query(RadiusClient).filter(RadiusClient.is_active == True).count()  # noqa: E712
    assignments_count = db.query(UdnAssignment).filter(UdnAssignment.is_active == True).count()  # noqa: E712
    
    return {
        "clients_count": clients_count,
        "assignments_count": assignments_count,
        "status": "active" if clients_count > 0 else "no_clients",
    }
