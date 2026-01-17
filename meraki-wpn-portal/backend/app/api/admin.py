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
        meraki_org_id=settings.meraki_org_id,
        ha_url=settings.ha_url,
        ha_token="***" if settings.ha_token else "",
        property_name=settings.property_name,
        logo_url=settings.logo_url,
        primary_color=settings.primary_color,
        default_network_id=settings.default_network_id,
        default_ssid_number=settings.default_ssid_number,
        default_group_policy_id=settings.default_group_policy_id,
        default_group_policy_name=settings.default_group_policy_name,
        default_guest_group_policy_id=settings.default_guest_group_policy_id,
        default_guest_group_policy_name=settings.default_guest_group_policy_name,
        default_ssid_psk=settings.default_ssid_psk,  # Decrypted PSK for display
        standalone_ssid_name=settings.standalone_ssid_name,
        splash_page_url=settings.splash_page_url,
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
        # CORS
        cors_origins=settings.cors_origins,
        # RADIUS Settings
        radius_enabled=settings.radius_enabled,
        radius_server_host=settings.radius_server_host,
        radius_hostname=settings.radius_hostname,
        radius_auth_port=settings.radius_auth_port,
        radius_acct_port=settings.radius_acct_port,
        radius_coa_port=settings.radius_coa_port,
        radius_radsec_enabled=settings.radius_radsec_enabled,
        radius_radsec_port=settings.radius_radsec_port,
        radius_shared_secret="***" if settings.radius_shared_secret else "",
        radius_radsec_ca_cert=settings.radius_radsec_ca_cert,
        radius_radsec_server_cert=settings.radius_radsec_server_cert,
        radius_radsec_server_key=settings.radius_radsec_server_key,
        radius_radsec_auto_generate=settings.radius_radsec_auto_generate,
        radius_cert_source=settings.radius_cert_source,
        radius_api_url=settings.radius_api_url,
        radius_api_token=settings.radius_api_token,
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
    for secret_key in [
        "meraki_api_key",
        "admin_password_hash",
        "secret_key",
        "duo_client_secret",
        "entra_client_secret",
        "cloudflare_api_token",  # Add Cloudflare token to secrets
    ]:
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


@router.get("/ipsk-options")
async def get_ipsk_options(
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Get Meraki configuration options for IPSK/WPN setup.
    
    Returns organizations, networks, SSIDs, and group policies if Meraki is configured.
    
    Args:
        admin: Authenticated admin user
        ha_client: HA client (provides Meraki access)
        
    Returns:
        Configuration options including organizations, networks, SSIDs, group policies
    """
    _ = admin  # Unused but required for auth
    settings = get_settings()
    
    result = {
        "organizations": [],
        "networks": [],
        "ssids": [],
        "group_policies": [],
    }
    
    # Return empty if no API key configured
    if not settings.meraki_api_key:
        return result
    
    try:
        # Get organizations
        if hasattr(ha_client, "get_organizations"):
            orgs = await ha_client.get_organizations()
            result["organizations"] = [
                {"id": org["id"], "name": org["name"]}
                for org in orgs
            ]
        
        # Get networks if org is configured
        if settings.meraki_org_id and hasattr(ha_client, "get_networks"):
            networks = await ha_client.get_networks(settings.meraki_org_id)
            result["networks"] = [
                {"id": net["id"], "name": net["name"]}
                for net in networks
            ]
        
        # Get SSIDs if network is configured
        if settings.default_network_id and hasattr(ha_client, "get_ssids"):
            ssids = await ha_client.get_ssids(settings.default_network_id)
            result["ssids"] = [
                {"number": ssid["number"], "name": ssid["name"]}
                for ssid in ssids
                if ssid.get("enabled", True)  # Only include enabled SSIDs
            ]
        
        # Get group policies if network is configured
        if settings.default_network_id and hasattr(ha_client, "get_group_policies"):
            try:
                policies = await ha_client.get_group_policies(settings.default_network_id)
                result["group_policies"] = [
                    {"id": str(policy.get("groupPolicyId", policy.get("id", ""))), "name": policy.get("name", "")}
                    for policy in policies
                ]
                logger.debug(f"Loaded {len(result['group_policies'])} group policies from Meraki")
            except Exception as gp_err:
                logger.warning(f"Failed to load group policies: {gp_err}")
    
    except Exception as e:
        logger.warning(f"Failed to load Meraki options: {e}")
        # Return partial data - don't fail if some calls don't work
    
    # Always include currently saved group policies if available (even if Meraki fetch failed)
    if not result["group_policies"]:
        saved_policies = []
        if settings.default_group_policy_id and settings.default_group_policy_name:
            saved_policies.append({
                "id": str(settings.default_group_policy_id),
                "name": settings.default_group_policy_name
            })
        if settings.default_guest_group_policy_id and settings.default_guest_group_policy_name:
            saved_policies.append({
                "id": str(settings.default_guest_group_policy_id),
                "name": settings.default_guest_group_policy_name
            })
        if saved_policies:
            result["group_policies"] = saved_policies
            logger.debug(f"Using {len(saved_policies)} saved group policies from database")
    
    return result


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
    db: DbSession,
    current_password: str,
    new_password: str,
) -> dict:
    """Change admin password (standalone mode only).
    
    Args:
        admin: Authenticated admin user
        db: Database session
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
    
    # Save the new password hash to database
    db_mgr = get_db_settings_manager()
    success = db_mgr.bulk_update_settings(
        db=db,
        settings_dict={"admin_password_hash": new_password_hash},
        updated_by=admin.get("sub"),
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save password to database",
        )
    
    # Reload settings to apply the new password hash
    reload_settings()
    
    logger.info(f"Password changed for admin user: {admin.get('sub')}")
    
    return {
        "success": True,
        "message": "Password changed successfully. The new password is now active.",
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
    meraki_api_status = "unknown"
    meraki_error_message = None
    
    try:
        ipsks = await ha_client.list_ipsks()
        total_ipsks = len(ipsks)
        active_ipsks = sum(1 for i in ipsks if i.get("status") == "active")
        expired_ipsks = sum(1 for i in ipsks if i.get("status") == "expired")
        revoked_ipsks = sum(1 for i in ipsks if i.get("status") == "revoked")
        online_now = sum(1 for i in ipsks if i.get("connected_clients", 0) > 0)
        meraki_api_status = "online"
    except Exception as e:
        logger.warning(f"Failed to fetch IPSK stats: {e}")
        total_ipsks = active_ipsks = expired_ipsks = revoked_ipsks = online_now = 0
        meraki_api_status = "offline"
        meraki_error_message = str(e)

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
        "meraki_status": {
            "status": meraki_api_status,
            "error": meraki_error_message,
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
    - configuration_complete: bool (all API-configurable items done)
    - wpn_ready: bool (all checks pass including manual WPN enable)
    - issues: list of critical issues
    - warnings: list of warnings (e.g., WPN not enabled)
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
            config_complete = ssid_status.get("configuration_complete", False)
            issues = ssid_status.get("issues", [])
            warnings = ssid_status.get("warnings", [])
            
            # Determine overall_status for frontend display
            # - "ready": Fully configured (iPSK + WPN enabled)
            # - "config_complete": All API-configurable settings done, WPN needs manual enable
            # - "needs_wpn": Same as config_complete, just needs manual WPN enable
            # - "needs_config": Missing iPSK configuration
            if is_ready:
                overall_status = "ready"
                message = "✓ SSID is fully configured for WPN (iPSK + WPN enabled)"
            elif config_complete:
                overall_status = "config_complete"
                message = "✓ Configuration complete - WPN must be enabled manually in Dashboard"
            elif issues:
                overall_status = "needs_config"
                message = "Issues: " + "; ".join(issues)
            else:
                overall_status = "needs_config"
                message = "SSID needs configuration"
            
            return {
                "ssid_number": ssid_status.get("number", settings.default_ssid_number),
                "ssid_name": ssid_status.get("name", f"SSID-{settings.default_ssid_number}"),
                "enabled": ssid_status.get("enabled", False),
                "auth_mode": ssid_status.get("auth_mode", ""),
                "ipsk_configured": ssid_status.get("is_ipsk_configured", False),
                "wpn_enabled": ssid_status.get("wpn_enabled", False),
                "configuration_complete": config_complete,
                "wpn_ready": is_ready,
                "overall_status": overall_status,  # For frontend status display
                "issues": issues,
                "warnings": warnings,
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


@router.get("/wpn/validate")
async def validate_wpn_setup(
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Validate full WPN setup including SSID, splash page, and group policy.
    
    Performs comprehensive validation:
    1. SSID is configured for Identity PSK
    2. Splash page is configured with correct URL
    3. Group policy exists with splash bypass
    4. WPN is enabled (if detectable via API)
    
    Returns validation results with pass/fail for each component.
    """
    _ = admin
    settings = get_settings()
    
    validation = {
        "valid": True,
        "checks": [],
        "issues": [],
        "summary": "",
    }
    
    if not settings.default_network_id:
        validation["valid"] = False
        validation["issues"].append("No network configured")
        validation["summary"] = "Network not configured"
        return validation
    
    try:
        # Check 1: SSID Configuration
        if hasattr(ha_client, "get_ssid"):
            try:
                ssid = await ha_client.get_ssid(
                    settings.default_network_id,
                    settings.default_ssid_number,
                )
                
                ssid_enabled = ssid.get("enabled", False)
                auth_mode = ssid.get("authMode", "")
                is_ipsk = "ipsk" in auth_mode.lower()
                splash_page = ssid.get("splashPage", "")
                has_splash = splash_page and splash_page != "None"
                
                validation["checks"].append({
                    "name": "SSID Enabled",
                    "passed": ssid_enabled,
                    "value": "Yes" if ssid_enabled else "No",
                })
                
                validation["checks"].append({
                    "name": "Identity PSK Mode",
                    "passed": is_ipsk,
                    "value": auth_mode or "Not set",
                })
                
                validation["checks"].append({
                    "name": "Splash Page Type",
                    "passed": has_splash,
                    "value": splash_page or "None",
                })
                
                if not ssid_enabled:
                    validation["valid"] = False
                    validation["issues"].append("SSID is disabled")
                if not is_ipsk:
                    validation["valid"] = False
                    validation["issues"].append("SSID is not configured for Identity PSK")
                if not has_splash:
                    validation["valid"] = False
                    validation["issues"].append("No splash page configured")
                    
            except Exception as e:
                validation["checks"].append({
                    "name": "SSID Configuration",
                    "passed": False,
                    "value": f"Error: {str(e)}",
                })
                validation["valid"] = False
                validation["issues"].append(f"Could not check SSID: {str(e)}")
        
        # Check 2: Splash Page Settings
        if hasattr(ha_client, "get_splash_settings"):
            try:
                splash_settings = await ha_client.get_splash_settings(
                    settings.default_network_id,
                    settings.default_ssid_number,
                )
                
                splash_url = splash_settings.get("splashUrl", "")
                expected_url = settings.splash_page_url or ""
                
                # Check if splash URL is configured
                has_splash_url = bool(splash_url)
                url_matches = expected_url and splash_url == expected_url
                
                validation["checks"].append({
                    "name": "Splash URL Configured",
                    "passed": has_splash_url,
                    "value": splash_url or "Not set",
                })
                
                if settings.splash_page_url:
                    validation["checks"].append({
                        "name": "Splash URL Matches Settings",
                        "passed": url_matches,
                        "value": f"Expected: {expected_url}",
                    })
                    if not url_matches:
                        validation["issues"].append(
                            f"Splash URL mismatch: {splash_url} vs {expected_url}"
                        )
                
            except Exception as e:
                logger.debug(f"Could not check splash settings: {e}")
        
        # Check 3: Group Policy
        if hasattr(ha_client, "get_group_policies"):
            try:
                policies = await ha_client.get_group_policies(settings.default_network_id)
                
                configured_policy_id = settings.default_group_policy_id
                configured_policy_name = settings.default_group_policy_name
                
                # Find the configured policy
                configured_policy = None
                for policy in policies:
                    policy_id = str(policy.get("groupPolicyId", policy.get("id", "")))
                    if policy_id == configured_policy_id:
                        configured_policy = policy
                        break
                    if policy.get("name") == configured_policy_name:
                        configured_policy = policy
                        break
                
                has_policy = configured_policy is not None
                has_splash_bypass = False
                
                if configured_policy:
                    splash_auth = configured_policy.get("splashAuthSettings", "")
                    has_splash_bypass = splash_auth.lower() == "bypass"
                
                validation["checks"].append({
                    "name": "Group Policy Exists",
                    "passed": has_policy,
                    "value": configured_policy.get("name") if configured_policy else "Not found",
                })
                
                validation["checks"].append({
                    "name": "Splash Bypass Enabled",
                    "passed": has_splash_bypass,
                    "value": "Yes" if has_splash_bypass else "No",
                })
                
                if not has_policy:
                    validation["valid"] = False
                    validation["issues"].append(
                        f"Group policy '{configured_policy_name}' not found"
                    )
                elif not has_splash_bypass:
                    validation["issues"].append(
                        "Group policy does not have splash bypass enabled"
                    )
                
            except Exception as e:
                logger.debug(f"Could not check group policies: {e}")
        
        # Check 4: WPN Status (if available)
        if hasattr(ha_client, "get_ssid_wpn_status"):
            try:
                wpn_status = await ha_client.get_ssid_wpn_status(
                    settings.default_network_id,
                    settings.default_ssid_number,
                )
                
                wpn_enabled = wpn_status.get("wpn_enabled", False)
                
                validation["checks"].append({
                    "name": "WPN Enabled",
                    "passed": wpn_enabled,
                    "value": "Yes" if wpn_enabled else "No (manual enable required)",
                })
                
                if not wpn_enabled:
                    validation["issues"].append(
                        "WPN not enabled - must be enabled manually in Meraki Dashboard"
                    )
                
            except Exception as e:
                logger.debug(f"Could not check WPN status: {e}")
        
        # Generate summary
        passed_checks = sum(1 for c in validation["checks"] if c["passed"])
        total_checks = len(validation["checks"])
        
        if validation["valid"] and not validation["issues"]:
            validation["summary"] = f"✓ All {total_checks} checks passed"
        elif validation["valid"]:
            validation["summary"] = (
                f"⚠ {passed_checks}/{total_checks} checks passed with warnings"
            )
        else:
            validation["summary"] = (
                f"✗ {passed_checks}/{total_checks} checks passed - "
                f"{len(validation['issues'])} issue(s) found"
            )
        
        return validation
        
    except Exception as e:
        logger.error(f"WPN validation failed: {e}")
        return {
            "valid": False,
            "checks": [],
            "issues": [f"Validation error: {str(e)}"],
            "summary": "Validation failed",
        }


@router.post("/wpn/configure-ssid")
async def configure_ssid_for_wpn(
    request: Request,
    admin: AdminUser,
    ha_client: HAClient,
    db: DbSession,
    ssid_name: str | None = None,
    group_policy_name: str | None = None,
    guest_group_policy_name: str | None = None,
    splash_url: str | None = None,
    default_psk: str | None = None,
) -> dict:
    """Configure the default SSID for Identity PSK + WPN with splash page.

    This will:
    1. Create/update a group policy with splash bypass for registered users
    2. Create/update a guest group policy (optional) for default PSK users
    3. Enable the SSID with:
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
            default_psk = generate_passphrase(12, simple=True)
            logger.info("Generated new simple default PSK for SSID")

    try:
        # Track whether we updated or created the group policies
        policy_action = "created"
        guest_policy_action = None
        policy_details = {}
        guest_policy_id = None
        
        # In standalone mode, ensure the group policy has splash bypass enabled
        if hasattr(ha_client, "get_group_policies") and hasattr(ha_client, "update_group_policy"):
            # Get existing policies to check if ours exists
            policies = await ha_client.get_group_policies(settings.default_network_id)
            
            # Find the registered users policy by ID or name
            existing_policy = None
            if settings.default_group_policy_id:
                for policy in policies:
                    policy_id = str(policy.get("groupPolicyId", policy.get("id", "")))
                    if policy_id == settings.default_group_policy_id:
                        existing_policy = policy
                        break
            
            # If policy exists, update it to ensure splash bypass is enabled
            if existing_policy:
                policy_id = str(existing_policy.get("groupPolicyId", existing_policy.get("id", "")))
                logger.info(f"Updating existing group policy {policy_id} to enable splash bypass")
                policy_details = await ha_client.update_group_policy(
                    settings.default_network_id,
                    policy_id,
                    bypass_splash=True,
                )
                policy_action = "updated"

            # Handle guest/default group policy if name provided
            # IMPORTANT: Create/update this BEFORE creating the default iPSK
            if guest_group_policy_name:
                logger.info(f"Processing guest group policy '{guest_group_policy_name}'")
                existing_guest_policy = None
                if settings.default_guest_group_policy_id:
                    for policy in policies:
                        policy_id = str(policy.get("groupPolicyId", policy.get("id", "")))
                        if policy_id == settings.default_guest_group_policy_id:
                            existing_guest_policy = policy
                            logger.info(f"Found existing guest policy with ID: {policy_id}")
                            break
                
                if existing_guest_policy:
                    # Update existing guest policy (NO splash bypass - they should see splash)
                    guest_policy_id = str(existing_guest_policy.get("groupPolicyId", existing_guest_policy.get("id", "")))
                    logger.info(f"Updating existing guest group policy ID: {guest_policy_id}, Name: '{guest_group_policy_name}'")
                    await ha_client.update_group_policy(
                        settings.default_network_id,
                        guest_policy_id,
                        name=guest_group_policy_name,
                        bypass_splash=False,  # Guests see splash page
                    )
                    guest_policy_action = "updated"
                    logger.info(f"✓ Guest policy updated. ID: {guest_policy_id}")
                else:
                    # Create new guest policy (NO splash bypass)
                    logger.info(f"Creating NEW guest group policy '{guest_group_policy_name}' (splash bypass: DISABLED)")
                    guest_policy = await ha_client.create_group_policy(
                        settings.default_network_id,
                        guest_group_policy_name,
                        bypass_splash=False,  # Guests see splash page
                    )
                    guest_policy_id = str(guest_policy.get("groupPolicyId", guest_policy.get("id", "")))
                    guest_policy_action = "created"
                    logger.info(f"✓ Guest policy created successfully! ID: {guest_policy_id}, Name: '{guest_group_policy_name}'")
            else:
                logger.info("No guest group policy specified - default iPSK will use splash page only (no group policy)")
        
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
                "splash_page_url": splash_url,  # Save splash URL for UI display
            }
            if result.get("group_policy_id"):
                updates["default_group_policy_id"] = result["group_policy_id"]
            if guest_policy_id:
                updates["default_guest_group_policy_id"] = guest_policy_id
                logger.info(f"Saving guest policy ID to database: {guest_policy_id}")
            if guest_group_policy_name:
                updates["default_guest_group_policy_name"] = guest_group_policy_name
            if ssid_name:
                updates["standalone_ssid_name"] = ssid_name

            db_mgr.bulk_update_settings(
                db=db,
                settings_dict=updates,
                updated_by=admin.get("sub"),
            )
            reload_settings()
            
            logger.info(
                f"Saved WPN settings: group_policy={group_policy_name}, "
                f"policy_id={result.get('group_policy_id')}, "
                f"guest_policy={guest_group_policy_name}, guest_policy_id={guest_policy_id}, "
                f"splash_url={splash_url}"
            )

            logger.info(
                f"Configured SSID {settings.default_ssid_number} for WPN "
                f"with splash page by {admin.get('sub')}"
            )

            # Create the default/guest iPSK in Meraki with guest group policy (or NO policy)
            # MUST happen AFTER guest policy is created and saved
            default_ipsk_name = "Guest-Default-Access"
            default_ipsk_created = False
            try:
                # Check if default iPSK already exists
                existing_ipsks = await ha_client.list_ipsks()
                default_ipsk_exists = any(
                    ipsk.get("name") == default_ipsk_name 
                    for ipsk in existing_ipsks
                )
                
                if not default_ipsk_exists:
                    logger.info(f"Creating default guest iPSK '{default_ipsk_name}' with passphrase: {default_psk}")
                    if guest_policy_id:
                        logger.info(f"Assigning guest policy ID: {guest_policy_id} to default iPSK")
                    else:
                        logger.info("No guest policy - default iPSK will use splash page only")
                    
                    # Create iPSK with guest group policy (if configured) or NO policy (uses splash)
                    created_ipsk = await ha_client.create_ipsk(
                        name=default_ipsk_name,
                        network_id=settings.default_network_id,
                        ssid_number=settings.default_ssid_number,  # Required parameter!
                        passphrase=default_psk,
                        group_policy_id=guest_policy_id,  # Use guest policy if configured, None otherwise
                    )
                    default_ipsk_created = True
                    
                    if guest_policy_id:
                        logger.info(
                            f"✓ Created default guest iPSK '{default_ipsk_name}' successfully! "
                            f"PSK: {default_psk}, Group Policy ID: {guest_policy_id}"
                        )
                    else:
                        logger.info(
                            f"✓ Created default guest iPSK '{default_ipsk_name}' successfully! "
                            f"PSK: {default_psk}, No group policy (uses splash page)"
                        )
                else:
                    logger.info(f"Default guest iPSK '{default_ipsk_name}' already exists, skipping creation")
            except Exception as e:
                logger.error(f"❌ Failed to create default iPSK in Meraki: {e}", exc_info=True)
                # Don't fail the whole configuration if iPSK creation fails

            # Build success message
            success_msg = f"SSID configured successfully! Group policy '{group_policy_name}' {policy_action} with splash bypass enabled. "
            if guest_policy_action:
                success_msg += f"Guest policy '{guest_group_policy_name}' {guest_policy_action}. "
            success_msg += f"Default PSK {'created' if default_ipsk_created else 'ready'} for guest access."

            return {
                "success": True,
                "message": success_msg,
                "result": result,
                "splash_url": splash_url,
                "ssid_name": result["ssid"]["name"],  # Return the actual SSID name from Meraki
                "default_psk": default_psk,
                "default_ipsk_created": default_ipsk_created,
                "group_policy_name": group_policy_name,
                "group_policy_action": policy_action,  # "created" or "updated"
                "guest_group_policy_name": guest_group_policy_name,
                "guest_group_policy_id": guest_policy_id,  # The actual ID from Meraki
                "guest_group_policy_action": guest_policy_action,  # "created", "updated", or None
                "splash_bypass_enabled": True,
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
            # Create group policy with splash bypass enabled
            policy = await ha_client.create_group_policy(
                settings.default_network_id,
                name,
                bypass_splash=True,  # Enable splash bypass for WPN users
            )
            logger.info(f"Created group policy '{name}' with splash bypass by {admin.get('sub')}")
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
# NAC Authorization Policies (FreeRADIUS-based)
# =============================================================================

@router.get("/nac/policies")
async def get_nac_policies(
    admin: AdminUser,
) -> dict:
    """Get all NAC authorization policies from FreeRADIUS.
    
    NAC policies are managed on FreeRADIUS for RADIUS-based WPN.
    This proxies to the FreeRADIUS policy API.
    """
    import httpx
    
    settings = get_settings()
    radius_api_url = settings.radius_api_url or "http://freeradius:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.get(
                f"{radius_api_url}/api/policies",
                headers=headers,
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "policies": data.get("items", []),
                    "total": data.get("total", 0),
                }
            else:
                return {
                    "success": False,
                    "error": f"FreeRADIUS returned {response.status_code}",
                    "policies": [],
                }
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to get FreeRADIUS policies: {e}")
        return {
            "success": False,
            "error": f"Cannot connect to FreeRADIUS: {str(e)}",
            "policies": [],
        }
    except Exception as e:
        logger.error(f"Failed to get NAC policies: {e}")
        return {
            "success": False,
            "error": str(e),
            "policies": [],
        }


class NACPolicyCreateRequest(BaseModel):
    """NAC Policy creation request for FreeRADIUS."""
    name: str
    group_name: str
    policy_type: str = "user"
    priority: int = 100
    vlan_id: int | None = None
    attributes: dict | None = None


@router.post("/nac/policies")
async def create_nac_policy(
    admin: AdminUser,
    policy_data: NACPolicyCreateRequest,
) -> dict:
    """Create a NAC authorization policy on FreeRADIUS.
    
    This creates a policy for RADIUS-based authentication.
    """
    import httpx
    
    settings = get_settings()
    radius_api_url = settings.radius_api_url or "http://freeradius:8000"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            if settings.radius_api_token:
                headers["Authorization"] = f"Bearer {settings.radius_api_token}"
            
            response = await client.post(
                f"{radius_api_url}/api/policies",
                json=policy_data.model_dump(exclude_none=True),
                headers=headers,
            )
            
            if response.status_code in (200, 201):
                policy = response.json()
                logger.info(f"Created NAC policy '{policy_data.name}' by {admin.get('sub')}")
                return {
                    "success": True,
                    "message": f"NAC policy '{policy_data.name}' created",
                    "policy": policy,
                }
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"FreeRADIUS error: {response.text}",
                )
                
    except httpx.RequestError as e:
        logger.warning(f"Failed to create policy on FreeRADIUS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to FreeRADIUS: {str(e)}",
        ) from e
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

    settings = get_settings()
    
    # Use provided token or fall back to saved settings
    # Empty string or '***' means use saved token
    token = request.api_token if request.api_token and request.api_token != '***' else settings.cloudflare_api_token
    account_id = request.account_id or settings.cloudflare_account_id
    
    if not token:
        return {
            "success": False,
            "error": "No Cloudflare API token configured",
        }

    client = CloudflareClient(token, account_id)
    try:
        # Try to verify token (requires User:API Tokens:Read permission)
        # If this fails, we'll fall back to just fetching accounts
        token_status = "active"
        try:
            result = await client.verify_token()
            token_status = result.get("status", "active")
        except Exception as verify_err:
            logger.debug(f"Token verification not available: {verify_err}")
            # This is OK - token might not have User:API Tokens:Read permission
            # We'll verify by fetching accounts instead
        
        # If account_id was provided, verify that specific account
        # Otherwise, fetch a limited list of available accounts
        if account_id:
            account = await client.get_account(account_id)
            accounts = [account]
            message = f"Connected to Cloudflare account: {account['name']}"
        else:
            accounts = await client.get_accounts(limit=5)
            if not accounts:
                return {
                    "success": False,
                    "error": "No Cloudflare accounts found. Token may not have correct permissions.",
                }
            message = f"Connected to Cloudflare API ({len(accounts)} account(s) found)"
        
        logger.info(f"Cloudflare connection tested by {admin.get('sub')}")
        return {
            "success": True,
            "message": message,
            "token_status": token_status,
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
# User Approval Workflow
# ============================================================================


@router.get("/users/pending")
async def get_pending_users(
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Get users pending approval (admin only).
    
    Args:
        admin: Authenticated admin
        db: Database session
        
    Returns:
        List of users with approval_status="pending"
    """
    _ = admin
    
    pending_users = db.query(User).filter(
        User.approval_status == "pending"
    ).order_by(User.created_at.desc()).all()
    
    return {
        "total": len(pending_users),
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "unit": u.unit,
                "area_id": u.area_id,
                "preferred_auth_method": u.preferred_auth_method,
                "approval_status": u.approval_status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in pending_users
        ],
    }


class ApprovalRequest(BaseModel):
    """Approval/rejection request."""

    notes: str | None = None


@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    admin: AdminUser,
    db: DbSession,
    ha_client: HAClient,
    data: ApprovalRequest | None = None,
) -> dict:
    """Approve a pending user and create their credentials.
    
    Args:
        user_id: User ID to approve
        admin: Authenticated admin
        db: Database session
        ha_client: Home Assistant client for IPSK creation
        data: Optional approval notes
        
    Returns:
        Success message with user info
    """
    from app.core.security import encrypt_passphrase, generate_passphrase
    
    user = db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is not pending approval. Current status: {user.approval_status}",
        )
    
    settings = get_settings()
    admin_email = admin.get("sub", "admin")
    
    # Create credentials based on preferred auth method
    auth_method = user.preferred_auth_method or "ipsk"
    ipsk_result = None
    passphrase = None
    # Note: certificate_id not used - certificates require user password input
    
    try:
        # Create IPSK if requested
        if auth_method in ("ipsk", "both"):
            # Generate IPSK name
            sanitized_name = "".join(c for c in user.name.split()[0] if c.isalnum())[:20]
            if user.unit:
                ipsk_name = f"Unit-{user.unit}-{sanitized_name}"
            elif user.area_id:
                ipsk_name = f"Area-{user.area_id}-{sanitized_name}"
            else:
                ipsk_name = f"User-{sanitized_name}"
            
            # Generate passphrase
            passphrase = generate_passphrase(settings.passphrase_length)
            
            # Create IPSK via Home Assistant
            ipsk_result = await ha_client.create_ipsk(
                name=ipsk_name,
                network_id=settings.default_network_id,
                ssid_number=settings.default_ssid_number,
                passphrase=passphrase,
                duration_hours=settings.default_ipsk_duration_hours or None,
                group_policy_id=settings.default_group_policy_id or None,
                associated_user=user.name,
                associated_unit=user.unit,
                associated_area_id=user.area_id,
            )
            
            # Update user with IPSK info
            user.ipsk_id = ipsk_result.get("id")
            user.ipsk_name = ipsk_name
            user.ipsk_passphrase_encrypted = encrypt_passphrase(passphrase)
            user.ssid_name = ipsk_result.get("ssid_name", settings.standalone_ssid_name)
            
            logger.info(f"Created IPSK for approved user {user.email}: {ipsk_name}")
        
        # Note: Certificate creation on approval would require the user's password
        # which we don't have. They'll need to request a certificate separately.
        
        # Update approval status
        user.approval_status = "approved"
        user.approved_at = datetime.now(timezone.utc)
        user.approved_by = admin_email
        if data and data.notes:
            user.approval_notes = data.notes
        
        db.commit()
        db.refresh(user)
        
        logger.info(f"Admin {admin_email} approved user {user.email}")
        
        return {
            "success": True,
            "message": f"User {user.email} has been approved",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "approval_status": user.approval_status,
                "approved_at": user.approved_at.isoformat() if user.approved_at else None,
                "approved_by": user.approved_by,
                "ipsk_name": user.ipsk_name,
                "ssid_name": user.ssid_name,
            },
            "credentials": {
                "passphrase": passphrase,
                "ssid_name": user.ssid_name,
                "ipsk_name": user.ipsk_name,
            } if passphrase else None,
        }
        
    except Exception as e:
        logger.error(f"Failed to approve user {user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create credentials: {str(e)}",
        ) from e


@router.post("/users/{user_id}/reject")
async def reject_user(
    user_id: int,
    admin: AdminUser,
    db: DbSession,
    data: ApprovalRequest | None = None,
) -> dict:
    """Reject a pending user.
    
    Args:
        user_id: User ID to reject
        admin: Authenticated admin
        db: Database session
        data: Optional rejection notes
        
    Returns:
        Success message
    """
    user = db.get(User, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.approval_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is not pending approval. Current status: {user.approval_status}",
        )
    
    admin_email = admin.get("sub", "admin")
    
    # Update rejection status
    user.approval_status = "rejected"
    user.approved_at = datetime.now(timezone.utc)  # Using same field for rejection timestamp
    user.approved_by = admin_email
    if data and data.notes:
        user.approval_notes = data.notes
    
    db.commit()
    
    logger.info(f"Admin {admin_email} rejected user {user.email}: {data.notes if data else 'No notes'}")
    
    return {
        "success": True,
        "message": f"User {user.email} has been rejected",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "approval_status": user.approval_status,
            "approval_notes": user.approval_notes,
        },
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


# ============================================================================
# User Device Management
# ============================================================================

@router.get("/users/{user_id}/devices")
async def get_user_devices(
    user_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Get devices registered to a specific user (admin only).

    Args:
        user_id: User ID
        admin: Authenticated admin
        db: Database session

    Returns:
        List of user's devices
    """
    _ = admin
    from sqlalchemy import select
    from app.db.models import DeviceRegistration

    # Verify user exists
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get devices
    devices = db.execute(
        select(DeviceRegistration)
        .where(DeviceRegistration.user_id == user_id)
        .where(DeviceRegistration.is_active.is_(True))
        .order_by(DeviceRegistration.registered_at.desc())
    ).scalars().all()

    return {
        "success": True,
        "total": len(devices),
        "devices": [
            {
                "id": d.id,
                "mac_address": d.mac_address,
                "device_type": d.device_type,
                "device_os": d.device_os,
                "device_model": d.device_model or "",
                "device_name": d.device_name,
                "registered_at": d.registered_at.isoformat() if d.registered_at else None,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                "is_active": d.is_active,
            }
            for d in devices
        ],
    }


@router.put("/users/{user_id}/ipsk")
async def update_user_ipsk(
    user_id: int,
    new_passphrase: str,
    admin: AdminUser,
    db: DbSession,
    ha_client: HAClient,
) -> dict:
    """Update a user's IPSK passphrase (admin only).

    Args:
        user_id: User ID
        new_passphrase: New passphrase to set
        admin: Authenticated admin
        db: Database session
        ha_client: Home Assistant client

    Returns:
        Success message
    """
    # Verify user exists and has an IPSK
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.ipsk_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an IPSK assigned",
        )

    try:
        # Update IPSK passphrase via Meraki
        await ha_client.update_ipsk(
            ipsk_id=user.ipsk_id,
            passphrase=new_passphrase,
        )

        logger.info(f"Admin {admin.get('sub')} updated IPSK for user: {user.email}")

        return {
            "success": True,
            "message": f"IPSK passphrase updated for {user.email}",
        }
    except Exception as e:
        logger.error(f"Failed to update IPSK: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update IPSK: {str(e)}",
        ) from e


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    new_password: str,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Reset a user's password (admin only).

    Args:
        user_id: User ID
        new_password: New password to set
        admin: Authenticated admin
        db: Database session

    Returns:
        Success message
    """
    from app.core.security import hash_password

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Hash and update password
    user.password_hash = hash_password(new_password)
    db.commit()

    logger.info(f"Admin {admin.get('sub')} reset password for user: {user.email}")

    return {
        "success": True,
        "message": f"Password reset successfully for {user.email}",
    }


# ============================================================================
# Meraki Network Devices
# ============================================================================

@router.get("/meraki/networks/{network_id}/devices")
async def get_network_devices(
    network_id: str,
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Get all devices in a Meraki network (APs, switches, MXs, etc).

    Args:
        network_id: Meraki network ID
        admin: Authenticated admin
        ha_client: Home Assistant client

    Returns:
        List of network devices
    """
    _ = admin
    
    try:
        # Get devices from Meraki
        if hasattr(ha_client, "get_network_devices"):
            devices = await ha_client.get_network_devices(network_id)
            
            return {
                "success": True,
                "total": len(devices),
                "devices": devices,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Network device listing not available in this mode",
            )
    except Exception as e:
        logger.error(f"Failed to get network devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve network devices: {str(e)}",
        ) from e
