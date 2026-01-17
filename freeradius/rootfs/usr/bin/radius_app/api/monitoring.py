"""Monitoring and statistics API endpoints."""

import logging
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from radius_app.api.deps import AdminUser, DbSession
from radius_app.config import get_settings
from radius_app.db.models import RadiusClient, UdnAssignment

logger = logging.getLogger(__name__)

router = APIRouter()


class StatsResponse(BaseModel):
    """Overall statistics response."""
    
    total_clients: int = Field(..., description="Total RADIUS clients")
    active_clients: int = Field(..., description="Active RADIUS clients")
    total_assignments: int = Field(..., description="Total UDN assignments")
    active_assignments: int = Field(..., description="Active UDN assignments")
    udn_utilization_percent: float = Field(..., description="Percentage of UDN IDs in use")
    recent_authentications: int = Field(..., description="Authentications in last 24 hours")


class ClientStatsResponse(BaseModel):
    """Client usage statistics."""
    
    client_id: int
    client_name: str
    ipaddr: str
    network_name: Optional[str]
    is_active: bool
    assignments_count: int = Field(..., description="Number of UDN assignments for this client's network")


class LogEntry(BaseModel):
    """Single log entry."""
    
    timestamp: Optional[str] = Field(None, description="Log timestamp")
    level: Optional[str] = Field(None, description="Log level")
    message: str = Field(..., description="Log message")


class LogsResponse(BaseModel):
    """Recent logs response."""
    
    entries: list[LogEntry] = Field(..., description="List of log entries")
    total_lines: int = Field(..., description="Total lines read")


class ConfigFileResponse(BaseModel):
    """Configuration file contents."""
    
    filename: str = Field(..., description="Filename")
    path: str = Field(..., description="Full file path")
    content: str = Field(..., description="File content")
    last_modified: Optional[str] = Field(None, description="Last modification time")


@router.get("/api/stats", response_model=StatsResponse)
async def get_stats(
    admin: AdminUser,
    db: DbSession,
) -> StatsResponse:
    """
    Get overall statistics for RADIUS server.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Overall statistics
    """
    logger.info(f"Getting stats requested by {admin['sub']}")
    
    # Count clients
    total_clients = db.execute(select(func.count(RadiusClient.id))).scalar()
    active_clients = db.execute(
        select(func.count(RadiusClient.id)).where(RadiusClient.is_active == True)  # noqa: E712
    ).scalar()
    
    # Count assignments
    total_assignments = db.execute(select(func.count(UdnAssignment.id))).scalar()
    active_assignments = db.execute(
        select(func.count(UdnAssignment.id)).where(UdnAssignment.is_active == True)  # noqa: E712
    ).scalar()
    
    # Calculate UDN utilization (max UDN is 16777200)
    udn_max = 16777200
    udn_utilization = (total_assignments / udn_max) * 100 if udn_max > 0 else 0
    
    # Count recent authentications (last 24 hours)
    cutoff_time = datetime.now(UTC) - timedelta(hours=24)
    recent_auth = db.execute(
        select(func.count(UdnAssignment.id)).where(
            UdnAssignment.last_auth_at >= cutoff_time
        )
    ).scalar() or 0
    
    return StatsResponse(
        total_clients=total_clients,
        active_clients=active_clients,
        total_assignments=total_assignments,
        active_assignments=active_assignments,
        udn_utilization_percent=round(udn_utilization, 4),
        recent_authentications=recent_auth,
    )


@router.get("/api/stats/clients", response_model=list[ClientStatsResponse])
async def get_client_stats(
    admin: AdminUser,
    db: DbSession,
) -> list[ClientStatsResponse]:
    """
    Get usage statistics for each client.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        List of client statistics
    """
    logger.info(f"Getting client stats requested by {admin['sub']}")
    
    # Get all clients
    clients = db.execute(select(RadiusClient)).scalars().all()
    
    stats = []
    for client in clients:
        # Count assignments for this client's network
        if client.network_id:
            assignments_count = db.execute(
                select(func.count(UdnAssignment.id)).where(
                    UdnAssignment.network_id == client.network_id
                )
            ).scalar() or 0
        else:
            assignments_count = 0
        
        stats.append(ClientStatsResponse(
            client_id=client.id,
            client_name=client.name,
            ipaddr=client.ipaddr,
            network_name=client.network_name,
            is_active=client.is_active,
            assignments_count=assignments_count,
        ))
    
    return stats


@router.get("/api/logs/recent", response_model=LogsResponse)
async def get_recent_logs(
    admin: AdminUser,
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to retrieve"),
) -> LogsResponse:
    """
    Get recent FreeRADIUS log entries.
    
    Args:
        admin: Authenticated admin user
        lines: Number of lines to retrieve (max 1000)
        
    Returns:
        Recent log entries
    """
    logger.info(f"Getting recent logs ({lines} lines) requested by {admin['sub']}")
    
    log_file = Path("/var/log/radius/radius.log")
    
    if not log_file.exists():
        logger.warning(f"Log file not found: {log_file}")
        return LogsResponse(
            entries=[LogEntry(message="Log file not found")],
            total_lines=0,
        )
    
    try:
        # Read last N lines efficiently
        with open(log_file, "r") as f:
            # Seek to end and read backwards
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            
            # If file is small, just read it all
            if file_size < 1024 * 1024:  # 1MB
                f.seek(0)
                all_lines = f.readlines()
                log_lines = all_lines[-lines:]
            else:
                # Read last chunk and split
                chunk_size = min(file_size, lines * 200)  # Estimate 200 bytes per line
                f.seek(max(0, file_size - chunk_size))
                chunk = f.read()
                all_lines = chunk.split("\n")
                log_lines = all_lines[-lines:]
        
        # Parse log entries (simple parsing)
        entries = []
        for line in log_lines:
            if not line.strip():
                continue
            
            # Try to parse timestamp and level (FreeRADIUS format varies)
            parts = line.split(None, 3)
            if len(parts) >= 3:
                # Basic parsing - may need adjustment based on actual log format
                entry = LogEntry(
                    timestamp=parts[0] if len(parts) > 0 else None,
                    level=parts[1] if len(parts) > 1 else None,
                    message=parts[2] if len(parts) > 2 else line,
                )
            else:
                entry = LogEntry(message=line)
            
            entries.append(entry)
        
        return LogsResponse(
            entries=entries,
            total_lines=len(entries),
        )
        
    except Exception as e:
        logger.error(f"Error reading log file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read log file: {str(e)}",
        )


@router.get("/api/config/files", response_model=list[ConfigFileResponse])
async def get_config_files(
    admin: AdminUser,
) -> list[ConfigFileResponse]:
    """
    Get generated configuration files for debugging.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        List of configuration files with contents
    """
    logger.info(f"Getting config files requested by {admin['sub']}")
    
    settings = get_settings()
    
    config_files = [
        {
            "filename": "clients.conf",
            "path": str(Path(settings.radius_clients_path) / "clients.conf"),
        },
        {
            "filename": "users",
            "path": str(Path(settings.radius_config_path) / "users"),
        },
    ]
    
    results = []
    for file_info in config_files:
        file_path = Path(file_info["path"])
        
        if not file_path.exists():
            results.append(ConfigFileResponse(
                filename=file_info["filename"],
                path=file_info["path"],
                content=f"# File not found: {file_info['path']}",
                last_modified=None,
            ))
            continue
        
        try:
            content = file_path.read_text()
            stat = file_path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            results.append(ConfigFileResponse(
                filename=file_info["filename"],
                path=file_info["path"],
                content=content,
                last_modified=last_modified,
            ))
            
        except Exception as e:
            logger.error(f"Error reading config file {file_path}: {e}")
            results.append(ConfigFileResponse(
                filename=file_info["filename"],
                path=file_info["path"],
                content=f"# Error reading file: {str(e)}",
                last_modified=None,
            ))
    
    return results


@router.get("/api/config/status")
async def get_config_status_detailed(
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """
    Get detailed configuration status (extended version of original endpoint).
    
    Args:
        admin: Authenticated admin user
        db: Database session
        
    Returns:
        Detailed configuration status
    """
    from radius_app.db.models import RadiusClient, UdnAssignment
    
    logger.info(f"Config status requested by {admin['sub']} from {admin['ip']}")
    
    clients_count = db.execute(
        select(func.count(RadiusClient.id)).where(RadiusClient.is_active == True)  # noqa: E712
    ).scalar()
    assignments_count = db.execute(
        select(func.count(UdnAssignment.id)).where(UdnAssignment.is_active == True)  # noqa: E712
    ).scalar()
    
    settings = get_settings()
    clients_file = Path(settings.radius_clients_path) / "clients.conf"
    users_file = Path(settings.radius_config_path) / "users"
    
    return {
        "clients_count": clients_count,
        "assignments_count": assignments_count,
        "status": "active" if clients_count > 0 else "no_clients",
        "config_files": {
            "clients_conf_exists": clients_file.exists(),
            "clients_conf_path": str(clients_file),
            "users_file_exists": users_file.exists(),
            "users_file_path": str(users_file),
        },
        "deployment_mode": settings.deployment_mode.value,
        "database_type": "mysql" if "mysql" in settings.database_url else
                        "postgresql" if "postgresql" in settings.database_url else
                        "sqlite",
    }
