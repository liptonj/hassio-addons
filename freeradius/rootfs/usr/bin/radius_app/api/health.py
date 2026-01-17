"""Health check endpoints."""

import logging
import subprocess
from datetime import datetime, UTC

from fastapi import APIRouter
from pydantic import BaseModel

from radius_app.db.database import get_engine

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    radius_running: bool
    portal_db_connected: bool
    config_files_exist: bool


def check_radiusd_running() -> bool:
    """Check if radiusd process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "radiusd"],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"Failed to check radiusd status: {e}")
        return False


def check_db_connection() -> bool:
    """Check database connectivity."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            return True
    except Exception as e:
        logger.warning(f"Database connection check failed: {e}")
        return False


def check_config_files() -> bool:
    """Check if required config files exist."""
    from pathlib import Path
    from radius_app.config import get_settings
    
    settings = get_settings()
    clients_conf = Path(settings.radius_clients_path) / "clients.conf"
    users_file = Path(settings.radius_config_path) / "users"
    
    return clients_conf.exists() and users_file.exists()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check FreeRADIUS server health.
    
    Returns:
        Health status including RADIUS daemon, database, and config files
    """
    radius_running = check_radiusd_running()
    db_connected = check_db_connection()
    config_exists = check_config_files()
    
    # Overall status
    if radius_running and db_connected and config_exists:
        status = "healthy"
    elif db_connected:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now(UTC).isoformat(),
        radius_running=radius_running,
        portal_db_connected=db_connected,
        config_files_exist=config_exists,
    )
