"""Health check schemas."""

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Overall health status")
    timestamp: str = Field(..., description="ISO timestamp of check")
    mode: str = Field(..., description="Deployment mode (addon/standalone)")
    radius_running: bool = Field(..., description="Is RADIUS daemon running")
    database_connected: bool = Field(..., description="Is database connected")
    config_files_exist: bool = Field(..., description="Do config files exist")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "timestamp": "2026-01-13T12:00:00Z",
                "mode": "addon",
                "radius_running": True,
                "database_connected": True,
                "config_files_exist": True
            }
        }
    )