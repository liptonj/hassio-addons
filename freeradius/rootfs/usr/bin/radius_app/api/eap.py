"""FreeRADIUS EAP management API endpoints."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from radius_app.api.deps import AdminUser, DbSession
from radius_app.core.eap_config_generator import EapConfigGenerator
from radius_app.core.cert_sync import cert_sync_service
from radius_app.db.models import RadiusEapConfig, RadiusEapMethod, RadiusUnlangPolicy

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_policy_name(db, policy_id: Optional[int]) -> Optional[str]:
    """Get policy name by ID."""
    if policy_id is None:
        return None
    policy = db.query(RadiusUnlangPolicy).filter(RadiusUnlangPolicy.id == policy_id).first()
    return policy.name if policy else None


def _validate_policy_id(db, policy_id: Optional[int], field_name: str) -> None:
    """Validate that a policy ID exists if provided."""
    if policy_id is not None:
        policy = db.query(RadiusUnlangPolicy).filter(RadiusUnlangPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {field_name}: policy with ID {policy_id} not found"
            )


# Schemas

class EapConfigResponse(BaseModel):
    """EAP configuration response."""
    id: int
    name: str
    description: str | None
    default_eap_type: str
    enabled_methods: list[str]
    tls_min_version: str
    tls_max_version: str
    is_active: bool


class EapConfigCreate(BaseModel):
    """Create EAP configuration request."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    default_eap_type: Literal["tls", "ttls", "peap"] = "tls"
    enabled_methods: list[Literal["tls", "ttls", "peap", "fast"]] = ["tls"]
    tls_min_version: Literal["1.0", "1.1", "1.2", "1.3"] = "1.2"
    tls_max_version: Literal["1.0", "1.1", "1.2", "1.3"] = "1.3"


class EapConfigUpdate(BaseModel):
    """Update EAP configuration request."""
    description: str | None = None
    default_eap_type: Literal["tls", "ttls", "peap"] | None = None
    enabled_methods: list[Literal["tls", "ttls", "peap", "fast"]] | None = None
    tls_min_version: Literal["1.0", "1.1", "1.2", "1.3"] | None = None
    tls_max_version: Literal["1.0", "1.1", "1.2", "1.3"] | None = None
    is_active: bool | None = None


class EapMethodResponse(BaseModel):
    """EAP method information."""
    id: int
    method_name: str
    is_enabled: bool
    settings: dict | None
    auth_attempts: int
    auth_successes: int
    auth_failures: int
    success_rate: float
    # Authorization policy IDs
    success_policy_id: int | None = None
    failure_policy_id: int | None = None
    # Policy names for display
    success_policy_name: str | None = None
    failure_policy_name: str | None = None


class EapMethodUpdate(BaseModel):
    """Update EAP method request."""
    is_enabled: bool | None = None
    settings: dict | None = None
    success_policy_id: int | None = None
    failure_policy_id: int | None = None


class ConfigRegenerateResponse(BaseModel):
    """Configuration regeneration response."""
    success: bool
    files_updated: dict[str, bool]
    message: str


class SyncStatusResponse(BaseModel):
    """Certificate sync status response."""
    running: bool
    last_sync: str | None
    poll_interval: int
    certificates: dict


# Endpoints

@router.get("/config", response_model=list[EapConfigResponse])
async def list_eap_configs(
    db: DbSession,
    admin: AdminUser
) -> list[EapConfigResponse]:
    """List all EAP configurations.
    
    Returns all configured EAP settings, including active and inactive.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} listing EAP configurations")
    
    configs = db.query(RadiusEapConfig).all()
    
    return [
        EapConfigResponse(
            id=config.id,
            name=config.name,
            description=config.description,
            default_eap_type=config.default_eap_type,
            enabled_methods=config.enabled_methods or [],
            tls_min_version=config.tls_min_version,
            tls_max_version=config.tls_max_version,
            is_active=config.is_active
        )
        for config in configs
    ]


@router.post("/config", response_model=EapConfigResponse)
async def create_eap_config(
    config: EapConfigCreate,
    db: DbSession,
    admin: AdminUser
) -> EapConfigResponse:
    """Create a new EAP configuration.
    
    Creates a new EAP configuration with the specified settings.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} creating EAP config: {config.name}")
    
    try:
        # Check for duplicate name
        existing = db.query(RadiusEapConfig).filter_by(name=config.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Configuration '{config.name}' already exists")
        
        # Create new configuration
        new_config = RadiusEapConfig(
            name=config.name,
            description=config.description,
            default_eap_type=config.default_eap_type,
            enabled_methods=config.enabled_methods,
            tls_min_version=config.tls_min_version,
            tls_max_version=config.tls_max_version,
            is_active=True,
            created_by=admin["username"]
        )
        
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        
        logger.info(f"✅ EAP configuration created: {new_config.id}")
        
        return EapConfigResponse(
            id=new_config.id,
            name=new_config.name,
            description=new_config.description,
            default_eap_type=new_config.default_eap_type,
            enabled_methods=new_config.enabled_methods or [],
            tls_min_version=new_config.tls_min_version,
            tls_max_version=new_config.tls_max_version,
            is_active=new_config.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create EAP config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create configuration: {e}")


@router.patch("/config/{config_id}", response_model=EapConfigResponse)
async def update_eap_config(
    config_id: int,
    update: EapConfigUpdate,
    db: DbSession,
    admin: AdminUser
) -> EapConfigResponse:
    """Update an existing EAP configuration.
    
    Updates the specified EAP configuration with new settings.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} updating EAP config: {config_id}")
    
    try:
        config = db.query(RadiusEapConfig).filter_by(id=config_id).first()
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # Update fields
        if update.description is not None:
            config.description = update.description
        if update.default_eap_type is not None:
            config.default_eap_type = update.default_eap_type
        if update.enabled_methods is not None:
            config.enabled_methods = update.enabled_methods
        if update.tls_min_version is not None:
            config.tls_min_version = update.tls_min_version
        if update.tls_max_version is not None:
            config.tls_max_version = update.tls_max_version
        if update.is_active is not None:
            config.is_active = update.is_active
        
        db.commit()
        db.refresh(config)
        
        logger.info(f"✅ EAP configuration updated: {config_id}")
        
        return EapConfigResponse(
            id=config.id,
            name=config.name,
            description=config.description,
            default_eap_type=config.default_eap_type,
            enabled_methods=config.enabled_methods or [],
            tls_min_version=config.tls_min_version,
            tls_max_version=config.tls_max_version,
            is_active=config.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update EAP config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {e}")


@router.get("/methods", response_model=list[EapMethodResponse])
async def list_eap_methods(
    db: DbSession,
    admin: AdminUser
) -> list[EapMethodResponse]:
    """List all EAP methods with statistics and policy information.
    
    Returns all configured EAP methods with authentication statistics
    and authorization policy assignments.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} listing EAP methods")
    
    methods = db.query(RadiusEapMethod).all()
    
    return [
        EapMethodResponse(
            id=method.id,
            method_name=method.method_name,
            is_enabled=method.is_enabled,
            settings=method.settings,
            auth_attempts=method.auth_attempts,
            auth_successes=method.auth_successes,
            auth_failures=method.auth_failures,
            success_rate=(
                method.auth_successes / method.auth_attempts * 100
                if method.auth_attempts > 0 else 0.0
            ),
            success_policy_id=method.success_policy_id,
            failure_policy_id=method.failure_policy_id,
            success_policy_name=_get_policy_name(db, method.success_policy_id),
            failure_policy_name=_get_policy_name(db, method.failure_policy_id),
        )
        for method in methods
    ]


@router.patch("/methods/{method_id}", response_model=EapMethodResponse)
async def update_eap_method(
    method_id: int,
    update: EapMethodUpdate,
    db: DbSession,
    admin: AdminUser
) -> EapMethodResponse:
    """Update an EAP method's settings and policy assignments.
    
    Updates the specified EAP method with new settings and/or policy IDs.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} updating EAP method: {method_id}")
    
    try:
        method = db.query(RadiusEapMethod).filter_by(id=method_id).first()
        if not method:
            raise HTTPException(status_code=404, detail="EAP method not found")
        
        # Validate policy IDs if provided
        if update.success_policy_id is not None:
            _validate_policy_id(db, update.success_policy_id, "success_policy_id")
        if update.failure_policy_id is not None:
            _validate_policy_id(db, update.failure_policy_id, "failure_policy_id")
        
        # Update fields
        if update.is_enabled is not None:
            method.is_enabled = update.is_enabled
        if update.settings is not None:
            method.settings = update.settings
        if update.success_policy_id is not None:
            method.success_policy_id = update.success_policy_id
        if update.failure_policy_id is not None:
            method.failure_policy_id = update.failure_policy_id
        
        db.commit()
        db.refresh(method)
        
        logger.info(f"✅ EAP method updated: {method_id}")
        
        return EapMethodResponse(
            id=method.id,
            method_name=method.method_name,
            is_enabled=method.is_enabled,
            settings=method.settings,
            auth_attempts=method.auth_attempts,
            auth_successes=method.auth_successes,
            auth_failures=method.auth_failures,
            success_rate=(
                method.auth_successes / method.auth_attempts * 100
                if method.auth_attempts > 0 else 0.0
            ),
            success_policy_id=method.success_policy_id,
            failure_policy_id=method.failure_policy_id,
            success_policy_name=_get_policy_name(db, method.success_policy_id),
            failure_policy_name=_get_policy_name(db, method.failure_policy_id),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update EAP method: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update method: {e}")


@router.post("/methods/{method_name}/enable")
async def enable_eap_method(
    method_name: Literal["tls", "ttls", "peap", "fast"],
    db: DbSession,
    admin: AdminUser
) -> dict:
    """Enable an EAP method.
    
    Enables the specified EAP method in the active configuration.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} enabling EAP method: {method_name}")
    
    try:
        # Get active configuration
        config = db.query(RadiusEapConfig).filter_by(is_active=True).first()
        if not config:
            raise HTTPException(status_code=404, detail="No active EAP configuration found")
        
        # Add method to enabled list if not already there
        enabled_methods = config.enabled_methods or []
        if method_name not in enabled_methods:
            enabled_methods.append(method_name)
            config.enabled_methods = enabled_methods
        
        # Get or create method record
        method = db.query(RadiusEapMethod).filter_by(
            eap_config_id=config.id,
            method_name=method_name
        ).first()
        
        if method:
            method.is_enabled = True
        else:
            method = RadiusEapMethod(
                eap_config_id=config.id,
                method_name=method_name,
                is_enabled=True
            )
            db.add(method)
        
        db.commit()
        
        logger.info(f"✅ EAP method enabled: {method_name}")
        
        return {
            "success": True,
            "message": f"EAP method '{method_name}' enabled successfully",
            "method": method_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to enable EAP method: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to enable method: {e}")


@router.post("/methods/{method_name}/disable")
async def disable_eap_method(
    method_name: Literal["tls", "ttls", "peap", "fast"],
    db: DbSession,
    admin: AdminUser
) -> dict:
    """Disable an EAP method.
    
    Disables the specified EAP method in the active configuration.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} disabling EAP method: {method_name}")
    
    try:
        # Get active configuration
        config = db.query(RadiusEapConfig).filter_by(is_active=True).first()
        if not config:
            raise HTTPException(status_code=404, detail="No active EAP configuration found")
        
        # Remove method from enabled list
        enabled_methods = config.enabled_methods or []
        if method_name in enabled_methods:
            enabled_methods.remove(method_name)
            config.enabled_methods = enabled_methods
        
        # Update method record
        method = db.query(RadiusEapMethod).filter_by(
            eap_config_id=config.id,
            method_name=method_name
        ).first()
        
        if method:
            method.is_enabled = False
        
        db.commit()
        
        logger.info(f"✅ EAP method disabled: {method_name}")
        
        return {
            "success": True,
            "message": f"EAP method '{method_name}' disabled successfully",
            "method": method_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to disable EAP method: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to disable method: {e}")


@router.post("/regenerate", response_model=ConfigRegenerateResponse)
async def regenerate_eap_config(
    db: DbSession,
    admin: AdminUser
) -> ConfigRegenerateResponse:
    """Regenerate EAP configuration files.
    
    Generates fresh EAP configuration files from database and reloads FreeRADIUS.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} regenerating EAP configuration")
    
    try:
        config_gen = EapConfigGenerator()
        results = config_gen.write_config_files(db)
        
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])
        
        logger.info("✅ EAP configuration regenerated successfully")
        
        return ConfigRegenerateResponse(
            success=True,
            files_updated=results,
            message="EAP configuration regenerated and FreeRADIUS reloaded"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to regenerate: {e}")


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    admin: AdminUser
) -> SyncStatusResponse:
    """Get certificate synchronization status.
    
    Returns the current status of the certificate sync service.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} checking certificate sync status")
    
    try:
        status = await cert_sync_service.get_sync_status()
        
        return SyncStatusResponse(
            running=status["running"],
            last_sync=status["last_sync"],
            poll_interval=status["poll_interval"],
            certificates=status["certificates"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e}")


@router.post("/sync/force")
async def force_certificate_sync(
    admin: AdminUser
) -> dict:
    """Force an immediate certificate synchronization.
    
    Triggers a manual certificate sync from portal to FreeRADIUS.
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} forcing certificate sync")
    
    try:
        result = await cert_sync_service.force_sync()
        
        return {
            "success": result.get("success", False),
            "certificates_added": result.get("certificates_added", 0),
            "certificates_updated": result.get("certificates_updated", 0),
            "certificates_revoked": result.get("certificates_revoked", 0),
            "total_synced": result.get("total_synced", 0),
            "message": "Certificate synchronization completed"
        }
        
    except Exception as e:
        logger.error(f"Failed to force sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync: {e}")
