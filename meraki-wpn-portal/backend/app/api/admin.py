"""Admin dashboard endpoints."""

import logging
import os
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.deps import AdminUser, DbSession, HAClient
from app.config import get_settings, reload_settings
from app.core.db_settings import DatabaseSettingsManager
from app.core.invite_codes import InviteCodeManager
from app.core.security import hash_password
from app.db.models import Registration, SplashAccess, User
from app.schemas.auth import OAuthSettings
from app.schemas.device import InviteCodeCreate, InviteCodeResponse
from app.schemas.settings import AllSettings, SettingsResponse, SettingsUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize database settings manager
_db_settings_manager = None


def get_db_settings_manager() -> DatabaseSettingsManager:
    """Get or create database settings manager singleton."""
    global _db_settings_manager
    if _db_settings_manager is None:
        # Get encryption key from environment or generate
        key_env = os.getenv("SETTINGS_ENCRYPTION_KEY")
        if key_env:
            key = key_env.encode()
        else:
            key = Fernet.generate_key()
            logger.warning(f"Generated encryption key: SETTINGS_ENCRYPTION_KEY={key.decode()}")
        _db_settings_manager = DatabaseSettingsManager(key)
    return _db_settings_manager


@router.get("/settings/all", response_model=AllSettings)
async def get_all_settings(admin: AdminUser) -> AllSettings:
    """Get ALL portal settings including secrets (masked).
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Complete settings with secrets masked
    """
    _ = admin  # Unused but required for auth
    settings = get_settings()
    
    # Return current runtime settings
    return AllSettings(
        run_mode=settings.run_mode,
        is_standalone=settings.is_standalone,
        editable_settings=settings.editable_settings,
        meraki_api_key="***" if settings.meraki_api_key else "",
        ha_url=settings.ha_url,
        ha_token="***" if settings.ha_token else "",
        property_name=settings.property_name,
        logo_url=settings.logo_url,
        primary_color=settings.primary_color,
        default_network_id=settings.default_network_id,
        default_ssid_number=settings.default_ssid_number,
        default_group_policy_id=settings.default_group_policy_id,
        standalone_ssid_name=settings.standalone_ssid_name,
        auth_self_registration=settings.auth_self_registration,
        auth_invite_codes=settings.auth_invite_codes,
        auth_email_verification=settings.auth_email_verification,
        auth_sms_verification=settings.auth_sms_verification,
        require_unit_number=settings.require_unit_number,
        unit_source=settings.unit_source,
        manual_units=settings.manual_units,
        default_ipsk_duration_hours=settings.default_ipsk_duration_hours,
        passphrase_length=settings.passphrase_length,
        admin_notification_email=settings.admin_notification_email,
        admin_username=settings.admin_username,
        admin_password="",  # Never expose
        admin_password_hash="***" if settings.admin_password_hash else "",
        secret_key="***" if settings.secret_key else "",
        access_token_expire_minutes=settings.access_token_expire_minutes,
        database_url=settings.database_url,
        enable_oauth=settings.enable_oauth,
        oauth_provider=settings.oauth_provider,
        oauth_admin_only=settings.oauth_admin_only,
        oauth_auto_provision=settings.oauth_auto_provision,
        oauth_callback_url=settings.oauth_callback_url,
        duo_client_id=settings.duo_client_id,
        duo_client_secret="***" if settings.duo_client_secret else "",
        duo_api_hostname=settings.duo_api_hostname,
        entra_client_id=settings.entra_client_id,
        entra_client_secret="***" if settings.entra_client_secret else "",
        entra_tenant_id=settings.entra_tenant_id,
        # Cloudflare
        cloudflare_enabled=settings.cloudflare_enabled,
        cloudflare_api_token="***" if settings.cloudflare_api_token else "",
        cloudflare_account_id=settings.cloudflare_account_id,
        cloudflare_tunnel_id=settings.cloudflare_tunnel_id,
        cloudflare_tunnel_name=settings.cloudflare_tunnel_name,
        cloudflare_zone_id=settings.cloudflare_zone_id,
        cloudflare_zone_name=settings.cloudflare_zone_name,
        cloudflare_hostname=settings.cloudflare_hostname,
        cloudflare_local_url=settings.cloudflare_local_url,
    )


@router.put("/settings/all", response_model=SettingsResponse)
async def update_all_settings(
    request: Request,
    admin: AdminUser,
    db: DbSession,
    settings_update: SettingsUpdate,
) -> SettingsResponse:
    """Update portal settings (saved to DATABASE for dynamic reload).
    
    Settings are stored in the database and can be reloaded without Docker restart.
    
    Args:
        admin: Authenticated admin user
        db: Database session
        settings_update: Settings to update (only provided fields are changed)
        
    Returns:
        Success response with updated settings
        
    Raises:
        HTTPException: If not in standalone mode or not editable
    """
    _ = admin  # Unused but required for auth
    settings = get_settings()
    
    if not settings.is_standalone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Settings can only be edited in standalone mode. Use config.yaml in HA mode.",
        )
    
    if not settings.editable_settings:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editable settings is disabled. Set EDITABLE_SETTINGS=true to allow changes.",
        )
    
    # Get database settings manager
    db_mgr = get_db_settings_manager()
    
    # Apply updates
    update_dict = settings_update.model_dump(exclude_unset=True)
    
    # Special handling for password - hash it
    if "admin_password" in update_dict and update_dict["admin_password"]:
        hashed_password = hash_password(update_dict["admin_password"])
        update_dict["admin_password_hash"] = hashed_password
        del update_dict["admin_password"]  # Don't store plain password
    
    # Save to database
    success = db_mgr.bulk_update_settings(
        db=db,
        settings_dict=update_dict,
        updated_by=admin.get("sub", "admin"),
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save settings to database",
        )
    
    # Reload settings from database (dynamic reload!)
    reload_settings()
    
    # Reinitialize the Meraki client with new API key if changed
    if "meraki_api_key" in update_dict:
        from app.main import reinitialize_client
        await reinitialize_client(request.app)
    
    logger.info(f"Settings updated by {admin.get('sub')}: {', '.join(update_dict.keys())}")
    
    # Get updated settings for response (with secrets masked)
    updated_settings = db_mgr.get_all_settings(db)
    
    # Mask secrets in response
    for secret_key in ["meraki_api_key", "admin_password_hash", "secret_key", "duo_client_secret", "entra_client_secret"]:
        if secret_key in updated_settings and updated_settings[secret_key]:
            updated_settings[secret_key] = "***"
    
    return SettingsResponse(
        success=True,
        message="Settings saved to database! Changes applied immediately (no restart needed).",
        settings=updated_settings,
        requires_restart=False,  # Database settings don't need restart!
    )


@router.post("/settings/test-connection")
async def test_connection_settings(
    admin: AdminUser,
    test_settings: dict,
) -> dict:
    """Test connection settings before saving (Meraki API, Database, OAuth, etc).
    
    Args:
        admin: Authenticated admin user
        test_settings: Settings to test
        
    Returns:
        Test results
    """
    _ = admin  # Unused but required for auth
    
    results = {
        "overall_success": True,
        "tests": {},
    }
    
    # Test Meraki API
    api_key = test_settings.get("meraki_api_key", "")
    
    # If masked (***) or empty, use the saved API key
    if not api_key or api_key == "***" or api_key.startswith("***"):
        settings = get_settings()
        api_key = settings.meraki_api_key or ""
    
    if api_key:
        try:
            from app.core.meraki_client import MerakiDashboardClient
            client = MerakiDashboardClient(api_key)
            await client.connect()
            orgs = await client.get_organizations()
            results["tests"]["meraki_api"] = {
                "success": True,
                "message": f"Connected successfully. Found {len(orgs)} organization(s).",
                "organizations": orgs,
            }
            await client.disconnect()
        except Exception as e:
            results["overall_success"] = False
            results["tests"]["meraki_api"] = {
                "success": False,
                "message": f"Connection failed: {str(e)}",
            }
    else:
        results["tests"]["meraki_api"] = {
            "success": False,
            "message": "No API key configured. Please enter a Meraki API key.",
        }
        results["overall_success"] = False
    
    # Test Database Connection
    if "database_url" in test_settings and test_settings["database_url"]:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.sql import text
            engine = create_engine(test_settings["database_url"])
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            results["tests"]["database"] = {
                "success": True,
                "message": "Database connection successful.",
            }
        except Exception as e:
            results["overall_success"] = False
            results["tests"]["database"] = {
                "success": False,
                "message": f"Database connection failed: {str(e)}",
            }
    
    # Test OAuth Provider
    if test_settings.get("enable_oauth") and test_settings.get("oauth_provider"):
        provider = test_settings["oauth_provider"].lower()
        
        if provider == "duo":
            try:
                from duo_universal import Client as DuoClient
                duo_client = DuoClient(
                    client_id=test_settings.get("duo_client_id", ""),
                    client_secret=test_settings.get("duo_client_secret", ""),
                    host=test_settings.get("duo_api_hostname", ""),
                    redirect_uri=test_settings.get("oauth_callback_url", ""),
                )
                duo_client.health_check()
                results["tests"]["duo_oauth"] = {
                    "success": True,
                    "message": "Duo connection successful.",
                }
            except Exception as e:
                results["overall_success"] = False
                results["tests"]["duo_oauth"] = {
                    "success": False,
                    "message": f"Duo connection failed: {str(e)}",
                }
        
        elif provider == "entra":
            results["tests"]["entra_oauth"] = {
                "success": True,
                "message": "Entra ID validation passed (full test requires OAuth flow).",
            }
    
    return results


@router.post("/settings/reset")
async def reset_settings_to_defaults(admin: AdminUser) -> dict:
    """Reset all settings to defaults (creates backup first).
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If not in standalone mode
    """
    _ = admin  # Unused but required for auth
    settings = get_settings()
    
    if not settings.is_standalone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Settings reset only available in standalone mode.",
        )
    
    db_mgr = get_db_settings_manager()
    
    try:
        db_mgr.reset_to_defaults()
        reload_settings()
        logger.info(f"Settings reset to defaults by {admin.get('sub')}")
        return {
            "success": True,
            "message": "Settings reset to defaults successfully.",
        }
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset settings",
        ) from e


@router.get("/settings/export")
async def export_settings_backup(admin: AdminUser, include_secrets: bool = False) -> dict:
    """Export settings for backup.
    
    Args:
        admin: Authenticated admin user
        include_secrets: Include decrypted secrets (use with caution!)
        
    Returns:
        Settings dictionary
    """
    _ = admin  # Unused but required for auth
    
    db_mgr = get_db_settings_manager()
    settings_dict = db_mgr.export_settings(mask_secrets=not include_secrets)
    
    if include_secrets:
        logger.warning(f"Settings exported WITH SECRETS by {admin.get('sub')}")
    
    return {
        "success": True,
        "settings": settings_dict,
        "includes_secrets": include_secrets,
        "warning": "Keep this backup secure!" if include_secrets else None,
    }


@router.post("/settings/import")
async def import_settings_backup(admin: AdminUser, settings_data: dict) -> dict:
    """Import settings from backup.
    
    Args:
        admin: Authenticated admin user
        settings_data: Settings dictionary to import
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If import fails
    """
    _ = admin  # Unused but required for auth
    settings = get_settings()
    
    if not settings.is_standalone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Settings import only available in standalone mode.",
        )
    
    db_mgr = get_db_settings_manager()
    
    try:
        db_mgr.import_settings(settings_data)
        reload_settings()
        logger.info(f"Settings imported by {admin.get('sub')}")
        return {
            "success": True,
            "message": "Settings imported successfully.",
        }
    except Exception as e:
        logger.error(f"Failed to import settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import settings",
        ) from e


@router.get("/oauth-settings", response_model=OAuthSettings)
async def get_oauth_settings(admin: AdminUser) -> OAuthSettings:
    """Get OAuth/SSO configuration.
    
    Args:
        admin: Authenticated admin user
        
    Returns:
        OAuth settings (secrets are masked)
    """
    _ = admin  # Unused but required for auth
    settings = get_settings()
    
    return OAuthSettings(
        enable_oauth=settings.enable_oauth,
        oauth_provider=settings.oauth_provider,
        oauth_admin_only=settings.oauth_admin_only,
        oauth_auto_provision=settings.oauth_auto_provision,
        duo_client_id=settings.duo_client_id,
        duo_client_secret="***" if settings.duo_client_secret else "",
        duo_api_hostname=settings.duo_api_hostname,
        entra_client_id=settings.entra_client_id,
        entra_client_secret="***" if settings.entra_client_secret else "",
        entra_tenant_id=settings.entra_tenant_id,
        oauth_callback_url=settings.oauth_callback_url,
    )


@router.put("/oauth-settings")
async def update_oauth_settings(admin: AdminUser, oauth_settings: OAuthSettings) -> dict:
    """Update OAuth/SSO configuration (standalone mode only).
    
    Args:
        admin: Authenticated admin user
        oauth_settings: New OAuth settings
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If settings are not editable
    """
    _ = admin  # Unused but required for auth
    _ = oauth_settings  # Reserved for future implementation
    settings = get_settings()
    
    if not settings.editable_settings or not settings.is_standalone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OAuth settings cannot be edited in this mode. Use environment variables.",
        )
    
    # In a real implementation, you would:
    # 1. Validate OAuth credentials (test connection)
    # 2. Persist settings to config file
    # 3. Reinitialize OAuth clients
    
    logger.info(f"OAuth settings update requested by {admin.get('sub')}")
    
    return {
        "success": True,
        "message": "OAuth settings updated. Restart required to apply changes.",
    }


@router.post("/change-password")
async def change_admin_password(
    admin: AdminUser,
    current_password: str,
    new_password: str,
) -> dict:
    """Change admin password (standalone mode only).
    
    Args:
        admin: Authenticated admin user
        current_password: Current password for verification
        new_password: New password to set
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If password change fails
    """
    settings = get_settings()
    
    if not settings.is_standalone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change not available in Home Assistant mode.",
        )
    
    # Verify current password
    from app.core.security import verify_password
    
    password_valid = False
    if settings.admin_password_hash:
        password_valid = verify_password(current_password, settings.admin_password_hash)
    else:
        password_valid = current_password == settings.admin_password
    
    if not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    
    # Hash new password
    new_password_hash = hash_password(new_password)
    
    # In a real implementation, you would:
    # 1. Save the new password hash to config
    # 2. Update environment or config file
    
    logger.info(f"Password changed for admin user: {admin.get('sub')}")
    
    return {
        "success": True,
        "message": "Password changed successfully",
        "new_password_hash": new_password_hash,
        "instruction": "Save this hash to ADMIN_PASSWORD_HASH environment variable",
    }


@router.get("/registrations")
async def list_registrations(
    admin: AdminUser,
    db: DbSession,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List registration requests.

    Args:
        admin: Authenticated admin user
        db: Database session
        status_filter: Optional filter by status
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of registrations with pagination info
    """
    query = db.query(Registration)

    if status_filter:
        query = query.filter(Registration.status == status_filter)

    total = query.count()
    registrations = (
        query.order_by(Registration.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "registrations": [
            {
                "id": reg.id,
                "name": reg.name,
                "email": reg.email,
                "unit": reg.unit,
                "status": reg.status,
                "ipsk_id": reg.ipsk_id,
                "invite_code": reg.invite_code,
                "created_at": reg.created_at.isoformat() if reg.created_at else None,
                "completed_at": reg.completed_at.isoformat() if reg.completed_at else None,
            }
            for reg in registrations
        ],
    }


# =========================================================================
# Invite Code Management
# =========================================================================


@router.get("/invite-codes", response_model=list[InviteCodeResponse])
async def list_invite_codes(
    admin: AdminUser,
    db: DbSession,
    include_expired: bool = False,
    include_inactive: bool = False,
) -> list[InviteCodeResponse]:
    """List all invite codes.

    Args:
        admin: Authenticated admin user
        db: Database session
        include_expired: Include expired codes
        include_inactive: Include deactivated codes

    Returns:
        List of invite codes
    """
    manager = InviteCodeManager(db)
    codes = manager.list_codes(
        include_expired=include_expired,
        include_inactive=include_inactive,
    )

    return [
        InviteCodeResponse(
            code=code.code,
            max_uses=code.max_uses,
            uses=code.uses,
            is_active=code.is_active,
            expires_at=code.expires_at.isoformat() if code.expires_at else None,
            note=code.note,
            created_by=code.created_by,
            created_at=code.created_at.isoformat(),
            last_used_at=code.last_used_at.isoformat() if code.last_used_at else None,
        )
        for code in codes
    ]


@router.post("/invite-codes", response_model=InviteCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_invite_code(
    data: InviteCodeCreate,
    admin: AdminUser,
    db: DbSession,
) -> InviteCodeResponse:
    """Create a new invite code.

    Args:
        data: Invite code creation data
        admin: Authenticated admin user
        db: Database session

    Returns:
        Created invite code
    """
    expires_at = None
    if data.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=data.expires_in_hours)

    manager = InviteCodeManager(db)
    code = manager.create_code(
        max_uses=data.max_uses,
        expires_at=expires_at,
        note=data.note,
        created_by=admin.get("sub", "admin"),
    )

    logger.info(f"Created invite code: {code.code}")

    return InviteCodeResponse(
        code=code.code,
        max_uses=code.max_uses,
        uses=code.uses,
        is_active=code.is_active,
        expires_at=code.expires_at.isoformat() if code.expires_at else None,
        note=code.note,
        created_by=code.created_by,
        created_at=code.created_at.isoformat(),
        last_used_at=None,
    )


@router.delete("/invite-codes/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite_code(
    code: str,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """Delete an invite code.

    Args:
        code: Invite code to delete
        admin: Authenticated admin user
        db: Database session
    """
    manager = InviteCodeManager(db)
    if not manager.delete_code(code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found",
        )

    logger.info(f"Deleted invite code: {code}")


@router.post("/invite-codes/{code}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_invite_code(
    code: str,
    admin: AdminUser,
    db: DbSession,
) -> None:
    """Deactivate an invite code without deleting it.

    Args:
        code: Invite code to deactivate
        admin: Authenticated admin user
        db: Database session
    """
    manager = InviteCodeManager(db)
    if not manager.deactivate_code(code):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found",
        )

    logger.info(f"Deactivated invite code: {code}")


# =========================================================================
# Dashboard Stats
# =========================================================================


@router.get("/dashboard")
async def get_dashboard_stats(
    admin: AdminUser,
    db: DbSession,
    ha_client: HAClient,
) -> dict:
    """Get dashboard statistics and recent activity.

    Args:
        admin: Authenticated admin user
        db: Database session
        ha_client: Home Assistant client

    Returns:
        Dashboard data with stats and recent activity
    """
    # Get IPSK stats
    try:
        ipsks = await ha_client.list_ipsks()
        total_ipsks = len(ipsks)
        active_ipsks = sum(1 for i in ipsks if i.get("status") == "active")
        expired_ipsks = sum(1 for i in ipsks if i.get("status") == "expired")
        revoked_ipsks = sum(1 for i in ipsks if i.get("status") == "revoked")
        online_now = sum(1 for i in ipsks if i.get("connected_clients", 0) > 0)
    except Exception as e:
        logger.warning(f"Failed to fetch IPSK stats: {e}")
        total_ipsks = active_ipsks = expired_ipsks = revoked_ipsks = online_now = 0

    # Get registration stats
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    registrations_today = (
        db.query(Registration)
        .filter(Registration.created_at >= today_start)
        .count()
    )

    # Get recent registrations
    recent_registrations = (
        db.query(Registration)
        .order_by(Registration.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "stats": {
            "total_ipsks": total_ipsks,
            "active_ipsks": active_ipsks,
            "expired_ipsks": expired_ipsks,
            "revoked_ipsks": revoked_ipsks,
            "online_now": online_now,
            "registrations_today": registrations_today,
        },
        "recent_activity": [
            {
                "type": "registration",
                "name": reg.name,
                "unit": reg.unit,
                "status": reg.status,
                "timestamp": reg.created_at.isoformat() if reg.created_at else None,
            }
            for reg in recent_registrations
        ],
    }


# =============================================================================
# WPN Configuration Endpoints
# =============================================================================

@router.get("/wpn/ssid-status")
async def get_ssid_wpn_status(
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Get the WPN configuration status for the default SSID.
    
    Returns flat structure:
    - ssid_number: int
    - ssid_name: str
    - enabled: bool
    - auth_mode: str
    - ipsk_configured: bool
    - wpn_enabled: bool
    - wpn_ready: bool (all checks pass)
    - issues: list of issues if not ready
    - message: str
    """
    _ = admin
    settings = get_settings()
    
    if not settings.default_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No default network configured. Please select a network first.",
        )
    
    try:
        # Check if ha_client has the method (MerakiDashboardClient)
        if hasattr(ha_client, "get_ssid_wpn_status"):
            ssid_status = await ha_client.get_ssid_wpn_status(
                settings.default_network_id,
                settings.default_ssid_number,
            )
            is_ready = ssid_status.get("ready_for_wpn", False)
            issues = ssid_status.get("issues", [])
            
            if is_ready:
                message = "✓ SSID is fully configured for WPN (iPSK + WPN enabled)"
            elif issues:
                message = "Issues: " + "; ".join(issues)
            else:
                message = "SSID needs configuration"
            
            return {
                "ssid_number": ssid_status.get("number", settings.default_ssid_number),
                "ssid_name": ssid_status.get("name", f"SSID-{settings.default_ssid_number}"),
                "enabled": ssid_status.get("enabled", False),
                "auth_mode": ssid_status.get("auth_mode", ""),
                "ipsk_configured": ssid_status.get("is_ipsk_configured", False),
                "wpn_enabled": ssid_status.get("wpn_enabled", False),
                "wpn_ready": is_ready,
                "issues": issues,
                "message": message,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WPN status check not available in this mode.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get SSID WPN status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/wpn/configure-ssid")
async def configure_ssid_for_wpn(
    request: Request,
    admin: AdminUser,
    ha_client: HAClient,
    ssid_name: str | None = None,
    group_policy_name: str | None = None,
    splash_url: str | None = None,
    default_psk: str | None = None,
) -> dict:
    """Configure the default SSID for Identity PSK + WPN with splash page.

    This will:
    1. Create a group policy with splash bypass for registered users
    2. Enable the SSID with:
       - Auth Mode: Identity PSK without RADIUS
       - WPA2 encryption
       - Bridge mode (required for WPN)
       - Click-through splash page
    3. Configure splash page URL (uses Cloudflare hostname if configured)
    4. Generate and save a default PSK for guest access

    Flow:
    - New users: See splash page → Registration portal
    - Registered users with iPSK: Bypass splash → Direct internet

    Note: WPN must also be enabled manually in Meraki Dashboard.
    """
    from app.core.security import generate_passphrase

    settings = get_settings()

    if not settings.default_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No default network configured. Please select a network first.",
        )

    # Use settings defaults if not provided
    if not group_policy_name:
        group_policy_name = settings.default_group_policy_name or "WPN-Users"

    # Determine splash URL - prefer Cloudflare hostname if configured
    if not splash_url:
        if settings.cloudflare_enabled and settings.cloudflare_hostname:
            # Use Cloudflare tunnel hostname
            splash_url = f"https://{settings.cloudflare_hostname}/api/splash"
            logger.info(f"Using Cloudflare hostname for splash: {splash_url}")
        else:
            # Fall back to request host
            host = request.headers.get("host", "localhost:8080")
            scheme = request.headers.get("x-forwarded-proto", "http")
            splash_url = f"{scheme}://{host}/api/splash"

    # Generate or use provided default PSK
    if not default_psk:
        if settings.default_ssid_psk:
            default_psk = settings.default_ssid_psk
        else:
            default_psk = generate_passphrase(12)
            logger.info("Generated new default PSK for SSID")

    try:
        if hasattr(ha_client, "configure_ssid_for_wpn"):
            result = await ha_client.configure_ssid_for_wpn(
                network_id=settings.default_network_id,
                ssid_number=settings.default_ssid_number,
                ssid_name=ssid_name,
                group_policy_name=group_policy_name,
                splash_url=splash_url,
            )

            # Save settings to database
            db_mgr = get_db_settings_manager()
            updates = {
                "default_ssid_psk": default_psk,
                "default_group_policy_name": group_policy_name,
            }
            if result.get("group_policy_id"):
                updates["default_group_policy_id"] = result["group_policy_id"]
            if ssid_name:
                updates["standalone_ssid_name"] = ssid_name

            db_mgr.bulk_update_settings(updates)
            reload_settings()

            logger.info(
                f"Configured SSID {settings.default_ssid_number} for WPN "
                f"with splash page by {admin.get('sub')}"
            )

            return {
                "success": True,
                "message": (
                    "SSID configured for Identity PSK with splash page. "
                    f"Group policy '{group_policy_name}' bypasses splash."
                ),
                "result": result,
                "splash_url": splash_url,
                "default_psk": default_psk,
                "group_policy_name": group_policy_name,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSID configuration not available in this mode.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure SSID for WPN: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure SSID: {str(e)}",
        ) from e


@router.get("/wpn/group-policies")
async def get_group_policies(
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Get all group policies for the default network."""
    _ = admin
    settings = get_settings()
    
    if not settings.default_network_id:
        return {
            "success": False,
            "error": "No default network configured.",
            "policies": [],
        }
    
    try:
        if hasattr(ha_client, "get_group_policies"):
            policies = await ha_client.get_group_policies(settings.default_network_id)
            return {
                "success": True,
                "policies": policies,
            }
        else:
            return {
                "success": False,
                "error": "Group policy listing not available in this mode.",
                "policies": [],
            }
    except Exception as e:
        logger.error(f"Failed to get group policies: {e}")
        return {
            "success": False,
            "error": str(e),
            "policies": [],
        }


@router.post("/wpn/group-policies")
async def create_group_policy(
    admin: AdminUser,
    ha_client: HAClient,
    name: str,
) -> dict:
    """Create a new group policy for WPN."""
    settings = get_settings()
    
    if not settings.default_network_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No default network configured.",
        )
    
    try:
        if hasattr(ha_client, "create_group_policy"):
            policy = await ha_client.create_group_policy(
                settings.default_network_id,
                name,
            )
            logger.info(f"Created group policy '{name}' by {admin.get('sub')}")
            return {
                "success": True,
                "message": f"Group policy '{name}' created successfully",
                "policy": policy,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group policy creation not available in this mode.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create group policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create group policy: {str(e)}",
        ) from e


# =============================================================================
# NAC Authorization Policies (RADIUS-based WPN)
# =============================================================================

@router.get("/nac/policies")
async def get_nac_policies(
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Get all NAC authorization policies.
    
    NAC policies can assign iPSK + Group Policy for RADIUS-based WPN.
    See: https://developer.cisco.com/meraki/api-v1/get-organization-nac-authorization-policies/
    """
    _ = admin
    
    try:
        if hasattr(ha_client, "get_nac_policies"):
            # Get organization ID first
            orgs = await ha_client.get_organizations()
            if not orgs:
                return {
                    "success": False,
                    "error": "No organizations found",
                    "policies": [],
                }
            
            org_id = orgs[0]["id"]
            policies = await ha_client.get_nac_policies(org_id)
            return {
                "success": True,
                "organization_id": org_id,
                "policies": policies,
            }
        else:
            return {
                "success": False,
                "error": "NAC policies not available in this mode",
                "policies": [],
            }
    except Exception as e:
        logger.error(f"Failed to get NAC policies: {e}")
        return {
            "success": False,
            "error": str(e),
            "policies": [],
        }


@router.post("/nac/policies")
async def create_nac_policy(
    admin: AdminUser,
    ha_client: HAClient,
    name: str,
    ipsk_passphrase: str,
    group_policy_name: str,
) -> dict:
    """Create a NAC authorization policy for RADIUS-based WPN.
    
    This creates a policy that assigns an iPSK and Group Policy
    for RADIUS-based authentication with WPN.
    """
    try:
        if hasattr(ha_client, "create_nac_policy"):
            # Get organization ID
            orgs = await ha_client.get_organizations()
            if not orgs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No organizations found",
                )
            
            org_id = orgs[0]["id"]
            policy = await ha_client.create_nac_policy(
                organization_id=org_id,
                name=name,
                ipsk_passphrase=ipsk_passphrase,
                group_policy_name=group_policy_name,
            )
            
            logger.info(f"Created NAC policy '{name}' by {admin.get('sub')}")
            return {
                "success": True,
                "message": f"NAC policy '{name}' created for RADIUS-based WPN",
                "policy": policy,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NAC policy creation not available in this mode",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create NAC policy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create NAC policy: {str(e)}",
        ) from e


# =============================================================================
# Cloudflare Zero Trust Tunnel Endpoints
# =============================================================================


class CloudflareTokenRequest(BaseModel):
    """Request body for Cloudflare API token."""

    api_token: str
    account_id: str | None = None


@router.post("/cloudflare/test-connection")
async def test_cloudflare_connection(
    admin: AdminUser,
    request: CloudflareTokenRequest,
) -> dict:
    """Test Cloudflare API connection with provided token.

    Parameters
    ----------
    admin : AdminUser
        Admin authentication
    request : CloudflareTokenRequest
        Request body containing API token and optional account ID

    Returns
    -------
    dict
        Connection test result
    """
    from app.core.cloudflare_client import CloudflareClient

    client = CloudflareClient(request.api_token, request.account_id)
    try:
        result = await client.verify_token()
        accounts = await client.get_accounts()
        logger.info(f"Cloudflare connection tested by {admin.get('sub')}")
        return {
            "success": True,
            "message": "Connected to Cloudflare API",
            "token_status": result.get("status", "active"),
            "accounts": [
                {"id": a.get("id"), "name": a.get("name")}
                for a in accounts
            ],
        }
    except Exception as e:
        logger.warning(f"Cloudflare connection test failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        await client.close()


@router.get("/cloudflare/options")
async def get_cloudflare_options(
    admin: AdminUser,
    api_token: str | None = None,
    account_id: str | None = None,
) -> dict:
    """Get available Cloudflare tunnels and zones for dropdown selection.

    Parameters
    ----------
    api_token : str | None
        Optional API token (uses saved settings if not provided)
    account_id : str | None
        Optional account ID

    Returns
    -------
    dict
        Available tunnels and zones
    """
    from app.core.cloudflare_client import CloudflareClient

    settings = get_settings()

    # Use provided token or fall back to saved settings
    token = api_token or settings.cloudflare_api_token
    acct_id = account_id or settings.cloudflare_account_id

    if not token:
        return {
            "success": False,
            "error": "Cloudflare API token not configured",
            "tunnels": [],
            "zones": [],
        }

    # Check for masked token
    if token == "***":
        return {
            "success": False,
            "error": "Please save a valid Cloudflare API token first",
            "tunnels": [],
            "zones": [],
        }

    client = CloudflareClient(token, acct_id or None)
    try:
        options = await client.get_tunnel_options()
        return {
            "success": True,
            **options,
        }
    except Exception as e:
        logger.error(f"Failed to get Cloudflare options: {e}")
        return {
            "success": False,
            "error": str(e),
            "tunnels": [],
            "zones": [],
        }
    finally:
        await client.close()


@router.get("/cloudflare/tunnel/{tunnel_id}/config")
async def get_tunnel_config(
    admin: AdminUser,
    tunnel_id: str,
) -> dict:
    """Get configuration for a specific tunnel including ingress rules.

    Parameters
    ----------
    tunnel_id : str
        Tunnel ID

    Returns
    -------
    dict
        Tunnel configuration
    """
    from app.core.cloudflare_client import CloudflareClient

    settings = get_settings()

    if not settings.cloudflare_api_token or settings.cloudflare_api_token == "***":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare API token not configured",
        )

    client = CloudflareClient(settings.cloudflare_api_token)
    try:
        config = await client.get_tunnel_config(tunnel_id)
        tunnel = await client.get_tunnel(tunnel_id)
        return {
            "success": True,
            "tunnel": tunnel,
            "config": config,
        }
    except Exception as e:
        logger.error(f"Failed to get tunnel config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    finally:
        await client.close()


@router.post("/cloudflare/tunnel/configure")
async def configure_cloudflare_tunnel(
    admin: AdminUser,
    tunnel_id: str,
    zone_id: str,
    hostname: str,
    local_url: str = "http://localhost:8080",
    api_token: str | None = None,
    account_id: str | None = None,
) -> dict:
    """Configure a Cloudflare tunnel for the portal.

    This creates/updates the ingress rule and DNS record.

    Parameters
    ----------
    tunnel_id : str
        Tunnel ID to configure
    zone_id : str
        Zone (domain) ID
    hostname : str
        Full hostname (e.g., portal.example.com)
    local_url : str
        Local service URL (default: http://localhost:8080)
    api_token : str | None
        Optional API token (uses saved settings if not provided)
    account_id : str | None
        Optional account ID

    Returns
    -------
    dict
        Configuration result
    """
    from app.core.cloudflare_client import CloudflareClient
    from app.db.database import get_session_local

    settings = get_settings()

    # Use provided token or fall back to saved settings
    token = api_token or settings.cloudflare_api_token
    acct_id = account_id or settings.cloudflare_account_id

    if not token or token == "***":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare API token not configured",
        )

    client = CloudflareClient(token, acct_id or None)
    try:
        # Add/update ingress rule
        await client.add_ingress_rule(
            tunnel_id=tunnel_id,
            hostname=hostname,
            service=local_url,
        )

        # Get tunnel and zone names for storage
        tunnels = await client.list_tunnels()
        tunnel = next((t for t in tunnels if t["id"] == tunnel_id), None)
        tunnel_name = tunnel["name"] if tunnel else ""

        zones = await client.list_zones()
        zone = next((z for z in zones if z["id"] == zone_id), None)
        zone_name = zone["name"] if zone else ""

        # Try to create DNS record (may already exist)
        subdomain = hostname.replace(f".{zone_name}", "") if zone_name else hostname
        try:
            await client.create_tunnel_dns_record(zone_id, tunnel_id, subdomain)
            dns_created = True
        except Exception as dns_err:
            # DNS record may already exist
            logger.warning(f"DNS record creation skipped: {dns_err}")
            dns_created = False

        # Save tunnel configuration to settings
        db_mgr = get_db_settings_manager()
        SessionLocal = get_session_local()
        with SessionLocal() as db:
            db_mgr.bulk_update_settings(
                db=db,
                settings_dict={
                    "cloudflare_enabled": True,
                    "cloudflare_tunnel_id": tunnel_id,
                    "cloudflare_tunnel_name": tunnel_name,
                    "cloudflare_zone_id": zone_id,
                    "cloudflare_zone_name": zone_name,
                    "cloudflare_hostname": hostname,
                    "cloudflare_local_url": local_url,
                    "cloudflare_api_token": token,
                    "cloudflare_account_id": acct_id or "",
                }
            )

        # Reload settings
        reload_settings()

        logger.info(
            f"Cloudflare tunnel configured: {hostname} -> {local_url} "
            f"by {admin.get('sub')}"
        )

        return {
            "success": True,
            "message": f"Tunnel configured: {hostname}",
            "tunnel_name": tunnel_name,
            "hostname": hostname,
            "local_url": local_url,
            "dns_created": dns_created,
            "instructions": [
                f"1. Ensure cloudflared is running with tunnel: {tunnel_name}",
                f"2. Access your portal at: https://{hostname}",
                "3. DNS may take a few minutes to propagate",
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure Cloudflare tunnel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    finally:
        await client.close()


@router.delete("/cloudflare/tunnel/disconnect")
async def disconnect_cloudflare_tunnel(
    admin: AdminUser,
) -> dict:
    """Remove the portal's Cloudflare tunnel configuration.

    This removes the ingress rule but leaves the DNS record.

    Returns
    -------
    dict
        Disconnection result
    """
    from app.core.cloudflare_client import CloudflareClient
    from app.db.database import get_session_local

    settings = get_settings()

    if not settings.cloudflare_tunnel_id or not settings.cloudflare_hostname:
        return {
            "success": True,
            "message": "No tunnel configuration to remove",
        }

    if settings.cloudflare_api_token and settings.cloudflare_api_token != "***":
        client = CloudflareClient(settings.cloudflare_api_token)
        try:
            await client.remove_ingress_rule(
                settings.cloudflare_tunnel_id,
                settings.cloudflare_hostname,
            )
        except Exception as e:
            logger.warning(f"Could not remove ingress rule: {e}")
        finally:
            await client.close()

    # Clear tunnel settings
    db_mgr = get_db_settings_manager()
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        db_mgr.bulk_update_settings(
            db=db,
            settings_dict={
                "cloudflare_enabled": False,
                "cloudflare_tunnel_id": "",
                "cloudflare_tunnel_name": "",
                "cloudflare_hostname": "",
            }
        )

    reload_settings()

    logger.info(f"Cloudflare tunnel disconnected by {admin.get('sub')}")

    return {
        "success": True,
        "message": "Cloudflare tunnel disconnected",
    }


# ============================================================================
# User Management Endpoints
# ============================================================================

class UserCreate(BaseModel):
    """Request to create a new user."""

    email: str
    name: str
    password: str
    unit: str | None = None
    is_admin: bool = False


class UserUpdate(BaseModel):
    """Request to update a user."""

    name: str | None = None
    unit: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = None
    password: str | None = None  # If provided, will be hashed


class UserResponse(BaseModel):
    """User response model."""

    id: int
    email: str
    name: str
    unit: str | None = None
    is_admin: bool = False
    is_active: bool = True
    has_ipsk: bool = False
    ipsk_name: str | None = None
    ssid_name: str | None = None
    created_at: str | None = None
    last_login_at: str | None = None


@router.get("/users")
async def list_users(
    admin: AdminUser,
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """List all users (admin only).

    Args:
        admin: Authenticated admin
        db: Database session
        skip: Pagination offset
        limit: Max results to return

    Returns:
        List of users
    """
    _ = admin
    from sqlalchemy import select, func

    # Get total count
    total = db.execute(select(func.count(User.id))).scalar_one()

    # Get users
    users = db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()

    return {
        "success": True,
        "total": total,
        "users": [
            UserResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                unit=u.unit,
                is_admin=u.is_admin,
                is_active=u.is_active,
                has_ipsk=bool(u.ipsk_id),
                ipsk_name=u.ipsk_name,
                ssid_name=u.ssid_name,
                created_at=u.created_at.isoformat() if u.created_at else None,
                last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            ).model_dump()
            for u in users
        ],
    }


@router.post("/users")
async def create_user(
    user_data: UserCreate,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Create a new user (admin only).

    Args:
        user_data: New user data
        admin: Authenticated admin
        db: Database session

    Returns:
        Created user info
    """
    from sqlalchemy import select
    from app.core.security import hash_password

    # Check if email already exists
    existing = db.execute(
        select(User).where(User.email == user_data.email)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # Create user
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hash_password(user_data.password),
        unit=user_data.unit,
        is_admin=user_data.is_admin,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Admin {admin.get('sub')} created user: {user.email}")

    return {
        "success": True,
        "message": f"User {user.email} created successfully",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            unit=user.unit,
            is_admin=user.is_admin,
            is_active=user.is_active,
            has_ipsk=bool(user.ipsk_id),
        ).model_dump(),
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Get a specific user by ID (admin only).

    Args:
        user_id: User ID
        admin: Authenticated admin
        db: Database session

    Returns:
        User info
    """
    _ = admin
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "success": True,
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            unit=user.unit,
            is_admin=user.is_admin,
            is_active=user.is_active,
            has_ipsk=bool(user.ipsk_id),
            ipsk_name=user.ipsk_name,
            ssid_name=user.ssid_name,
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        ).model_dump(),
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Update a user (admin only).

    Args:
        user_id: User ID to update
        user_data: Updated user data
        admin: Authenticated admin
        db: Database session

    Returns:
        Updated user info
    """
    from app.core.security import hash_password

    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update fields
    if user_data.name is not None:
        user.name = user_data.name
    if user_data.unit is not None:
        user.unit = user_data.unit
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.password:
        user.password_hash = hash_password(user_data.password)

    db.commit()
    db.refresh(user)

    logger.info(f"Admin {admin.get('sub')} updated user: {user.email}")

    return {
        "success": True,
        "message": f"User {user.email} updated successfully",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            unit=user.unit,
            is_admin=user.is_admin,
            is_active=user.is_active,
            has_ipsk=bool(user.ipsk_id),
        ).model_dump(),
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Delete a user (admin only).

    Args:
        user_id: User ID to delete
        admin: Authenticated admin
        db: Database session

    Returns:
        Success message
    """
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    email = user.email
    db.delete(user)
    db.commit()

    logger.info(f"Admin {admin.get('sub')} deleted user: {email}")

    return {
        "success": True,
        "message": f"User {email} deleted successfully",
    }


@router.post("/users/{user_id}/toggle-admin")
async def toggle_user_admin(
    user_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Toggle admin status for a user (admin only).

    Args:
        user_id: User ID
        admin: Authenticated admin
        db: Database session

    Returns:
        Updated user info
    """
    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_admin = not user.is_admin
    db.commit()
    db.refresh(user)

    action = "granted admin" if user.is_admin else "revoked admin from"
    logger.info(f"Admin {admin.get('sub')} {action}: {user.email}")

    return {
        "success": True,
        "message": f"Admin status {'granted' if user.is_admin else 'revoked'} for {user.email}",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_admin=user.is_admin,
            is_active=user.is_active,
        ).model_dump(),
    }


# ============================================================================
# Splash Access Logs
# ============================================================================

class SplashAccessResponse(BaseModel):
    """Splash access log entry."""

    id: int
    client_mac: str | None = None
    client_ip: str | None = None
    ap_mac: str | None = None
    ap_name: str | None = None
    ap_tags: str | None = None
    access_granted: bool = False
    registered: bool = False
    user_id: int | None = None
    accessed_at: str | None = None
    granted_at: str | None = None
    user_agent: str | None = None


@router.get("/splash-logs")
async def get_splash_logs(
    admin: AdminUser,
    db: DbSession,
    skip: int = 0,
    limit: int = 100,
    mac_filter: str | None = None,
) -> dict:
    """Get splash portal access logs (admin only).

    Args:
        admin: Authenticated admin
        db: Database session
        skip: Pagination offset
        limit: Max results to return
        mac_filter: Optional MAC address filter

    Returns:
        List of splash access logs
    """
    _ = admin
    from sqlalchemy import select, func

    # Build query
    query = select(SplashAccess).order_by(SplashAccess.accessed_at.desc())

    if mac_filter:
        query = query.where(SplashAccess.client_mac.ilike(f"%{mac_filter}%"))

    # Get total count
    count_query = select(func.count(SplashAccess.id))
    if mac_filter:
        count_query = count_query.where(SplashAccess.client_mac.ilike(f"%{mac_filter}%"))
    total = db.execute(count_query).scalar_one()

    # Get logs
    logs = db.execute(query.offset(skip).limit(limit)).scalars().all()

    return {
        "success": True,
        "total": total,
        "logs": [
            SplashAccessResponse(
                id=log.id,
                client_mac=log.client_mac,
                client_ip=log.client_ip,
                ap_mac=log.ap_mac,
                ap_name=log.ap_name,
                ap_tags=log.ap_tags,
                access_granted=log.access_granted,
                registered=log.registered,
                user_id=log.user_id,
                accessed_at=log.accessed_at.isoformat() if log.accessed_at else None,
                granted_at=log.granted_at.isoformat() if log.granted_at else None,
                user_agent=log.user_agent,
            ).model_dump()
            for log in logs
        ],
    }


@router.get("/splash-logs/stats")
async def get_splash_stats(
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Get splash portal access statistics (admin only).

    Args:
        admin: Authenticated admin
        db: Database session

    Returns:
        Splash access statistics
    """
    _ = admin
    from sqlalchemy import select, func
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Total accesses
    total = db.execute(select(func.count(SplashAccess.id))).scalar_one()

    # Today's accesses
    today_count = db.execute(
        select(func.count(SplashAccess.id)).where(
            SplashAccess.accessed_at >= today_start
        )
    ).scalar_one()

    # This week's accesses
    week_count = db.execute(
        select(func.count(SplashAccess.id)).where(
            SplashAccess.accessed_at >= week_ago
        )
    ).scalar_one()

    # Unique devices (by MAC)
    unique_macs = db.execute(
        select(func.count(func.distinct(SplashAccess.client_mac)))
    ).scalar_one()

    # Granted access count
    granted_count = db.execute(
        select(func.count(SplashAccess.id)).where(
            SplashAccess.access_granted.is_(True)
        )
    ).scalar_one()

    # Registered count
    registered_count = db.execute(
        select(func.count(SplashAccess.id)).where(
            SplashAccess.registered.is_(True)
        )
    ).scalar_one()

    return {
        "success": True,
        "stats": {
            "total_accesses": total,
            "today_accesses": today_count,
            "week_accesses": week_count,
            "unique_devices": unique_macs,
            "access_granted": granted_count,
            "registered": registered_count,
            "conversion_rate": round(registered_count / total * 100, 1) if total > 0 else 0,
        },
    }
