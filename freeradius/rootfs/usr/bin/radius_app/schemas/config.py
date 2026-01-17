"""Configuration update schemas."""

from pydantic import BaseModel, ConfigDict, Field


class ConfigUpdateRequest(BaseModel):
    """Request to regenerate configuration from database."""
    
    force: bool = Field(
        default=False,
        description="Force regeneration even if no changes detected"
    )
    reload_radius: bool = Field(
        default=True,
        description="Reload RADIUS daemon after regeneration"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "force": False,
                "reload_radius": True
            }
        }
    )


class ConfigUpdateResponse(BaseModel):
    """Response after configuration update."""
    
    success: bool = Field(..., description="Was update successful")
    clients_count: int = Field(..., description="Number of clients configured")
    users_count: int = Field(..., description="Number of users configured")
    reloaded: bool = Field(..., description="Was RADIUS daemon reloaded")
    message: str = Field(..., description="Status message")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "clients_count": 5,
                "users_count": 42,
                "reloaded": True,
                "message": "Configuration updated successfully"
            }
        }
    )