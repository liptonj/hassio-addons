"""FastAPI main application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api import (
    admin,
    auth,
    auth_config,
    devices,
    email,
    ipsk,
    ipsk_admin,
    qr_codes,
    radius,
    radius_proxy,
    registration,
    user_account,
    user_certificates,
)
from app.api.deps import DbSession
from app.config import get_settings, reload_settings
from app.db.init_schema import init_db
from app.db.models import PortalSetting

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for detailed logging
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_client_for_mode(settings):
    """Get the appropriate client based on run mode.
    
    - Standalone mode: Direct Meraki Dashboard API integration
    - Home Assistant mode: HA WebSocket API with meraki_ha integration
    - Test mode: Mock client (no real API calls)
    """
    # Use mock client in test mode
    if settings.run_mode == "test" or os.getenv("USE_MOCK_MERAKI") == "true":
        from app.core.mock_meraki_client import MockMerakiDashboardClient
        logger.info("Running in TEST mode - using Mock Meraki client")
        return MockMerakiDashboardClient(api_key="test-api-key")
    
    if settings.is_standalone:
        if settings.meraki_api_key:
            from app.core.meraki_client import MerakiDashboardClient
            logger.info("Running in STANDALONE mode - direct Meraki Dashboard API")
            return MerakiDashboardClient(api_key=settings.meraki_api_key)
        else:
            # Fall back to mock for demo/testing without API key
            from app.core.mock_ha_client import MockHomeAssistantClient
            logger.info("Running in STANDALONE mode - demo mode (no API key)")
            return MockHomeAssistantClient()
    else:
        from app.core.ha_client import HomeAssistantClient
        logger.info("Running in HOME ASSISTANT mode - connecting to HA")
        return HomeAssistantClient(
            url=settings.ha_url,
            token=settings.get_auth_token(),
        )


async def reinitialize_client(app: FastAPI):
    """Reinitialize the Meraki/HA client with current settings.
    
    Call this after settings are updated to use the new API key.
    """
    settings = reload_settings()
    
    # Disconnect old client if connected
    if hasattr(app.state, "ha_client") and app.state.ha_client:
        try:
            await app.state.ha_client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting old client: {e}")
    
    # Create and connect new client
    app.state.ha_client = get_client_for_mode(settings)
    try:
        await app.state.ha_client.connect()
        logger.info("✅ Client reinitialized with updated settings")
    except Exception as e:
        logger.error(f"❌ Failed to reinitialize client: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("Starting Meraki WPN Portal...")
    
    # Initialize database first
    logger.info("Initializing database...")
    init_db()
    
    # Get initial settings (without database settings to avoid circular import)
    settings = get_settings()
    logger.info(f"Run mode: {settings.run_mode.upper()}")
    logger.info(f"Property: {settings.property_name}")
    
    # Now reload settings to apply database settings (after DB is initialized)
    if settings.is_standalone and settings.editable_settings:
        logger.info("Loading settings from database...")
        settings = reload_settings()
        logger.info(f"Settings reloaded with database values")
        logger.info(f"Property (from DB): {settings.property_name}")

    # Initialize OAuth if enabled
    from app.core.oauth import init_oauth
    init_oauth()

    # Initialize appropriate client based on mode
    app.state.ha_client = get_client_for_mode(settings)

    try:
        await app.state.ha_client.connect()
        if settings.is_standalone:
            if settings.meraki_api_key:
                logger.info("Connected to Meraki Dashboard API (standalone mode)")
            else:
                logger.info("Demo mode active - no Meraki API key configured")
        else:
            logger.info("Connected to Home Assistant")
    except Exception as e:
        logger.warning(f"Failed to connect: {e}")
        if settings.is_standalone:
            # In standalone mode, use mock client as fallback for demo
            from app.core.mock_ha_client import MockHomeAssistantClient
            app.state.ha_client = MockHomeAssistantClient()
            await app.state.ha_client.connect()
            logger.info("Using demo mode as fallback (no Meraki connection)")
        else:
            logger.warning("Some features may not be available until HA connection is established")

    # Start iPSK expiration monitoring
    logger.info("Starting iPSK expiration monitor...")
    from app.core.ipsk_monitor import ipsk_monitor
    await ipsk_monitor.start()

    yield

    # Shutdown
    logger.info("Shutting down Meraki WPN Portal...")
    
    # Stop iPSK monitor
    await ipsk_monitor.stop()
    
    # Disconnect client
    if hasattr(app.state, "ha_client") and app.state.ha_client:
        await app.state.ha_client.disconnect()


# Create FastAPI application
app = FastAPI(
    title="Meraki WPN Portal",
    description="Self-service WiFi registration portal for Cisco Meraki networks",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS with configurable origins
_settings = get_settings()
_cors_origins = (
    _settings.cors_origins.split(",")
    if _settings.cors_origins and _settings.cors_origins != "*"
    else ["*"]
)
logger.info(f"CORS origins configured: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(registration.router, prefix="/api", tags=["Registration"])
app.include_router(user_account.router, prefix="/api", tags=["User Account"])
app.include_router(user_certificates.router, prefix="/api", tags=["User Certificates"])
app.include_router(qr_codes.router, prefix="/api", tags=["QR Codes"])
app.include_router(ipsk.router, prefix="/api/admin", tags=["IPSK Management"])
app.include_router(ipsk_admin.router, prefix="/api", tags=["iPSK Admin"])
app.include_router(devices.router, prefix="/api", tags=["Device Management"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(auth_config.router, prefix="/api/admin", tags=["Auth Config"])
app.include_router(radius.router, prefix="/api/admin/radius", tags=["RADIUS"])
app.include_router(radius_proxy.router, prefix="/api/radius", tags=["RADIUS Proxy"])
app.include_router(email.router, prefix="/api", tags=["Email"])


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "meraki-wpn-portal"}


def get_portal_setting_bool(db: Session, key: str, default: bool) -> bool:
    """Read a boolean portal setting with a safe default."""
    setting = db.query(PortalSetting).filter(PortalSetting.key == key).first()
    if not setting or setting.value is None:
        return default
    return str(setting.value).strip().lower() == "true"


@app.get("/api/options")
async def get_portal_options(db: DbSession) -> dict:
    """Get public portal configuration options."""
    settings = get_settings()

    # Determine units based on source
    units = []
    if settings.unit_source == "manual_list":
        units = [
            {"area_id": unit, "name": unit}
            for unit in settings.get_manual_units_list()
        ]
    # For ha_areas, units will be fetched from HA via separate endpoint
    
    # Parse custom fields from JSON string
    import json
    custom_fields = []
    try:
        if settings.custom_registration_fields:
            custom_fields = json.loads(settings.custom_registration_fields)
    except Exception:
        pass

    return {
        "property_name": settings.property_name,
        "logo_url": settings.logo_url,
        "primary_color": settings.primary_color,
        "unit_source": settings.unit_source,
        "units": units,
        "require_unit_number": settings.require_unit_number,
        "auth_methods": {
            # New registration modes
            "open_registration": getattr(settings, 'auth_open_registration', settings.auth_self_registration),
            "open_registration_approval": getattr(settings, 'auth_open_registration_approval', False),
            "account_only": getattr(settings, 'auth_account_only', False),
            "invite_code_account": getattr(settings, 'auth_invite_code_account', settings.auth_invite_codes),
            "invite_code_only": getattr(settings, 'auth_invite_code_only', False),
            # Legacy fields (for backwards compatibility)
            "self_registration": settings.auth_self_registration,
            "invite_codes": settings.auth_invite_codes,
            # Verification & Login Methods
            "email_verification": settings.auth_email_verification,
            "local": settings.auth_method_local,
            "oauth": settings.auth_method_oauth,
        },
        "auth_ipsk_enabled": get_portal_setting_bool(db, "ipsk_enabled", True),
        "auth_eap_enabled": get_portal_setting_bool(db, "eap_tls_enabled", False),
        # AUP Settings
        "aup_enabled": settings.aup_enabled,
        "aup_text": settings.aup_text,
        "aup_url": settings.aup_url,
        "aup_version": settings.aup_version,
        # Custom Fields
        "custom_fields": custom_fields,
        # PSK Customization
        "allow_custom_psk": settings.allow_custom_psk,
        "psk_requirements": {
            "min_length": settings.psk_min_length,
            "max_length": settings.psk_max_length,
        },
        # Invite Code Settings
        "invite_code_email_restriction": settings.invite_code_email_restriction,
        "invite_code_single_use": settings.invite_code_single_use,
        # Universal Login
        "universal_login_enabled": settings.universal_login_enabled,
        "show_login_method_selector": settings.show_login_method_selector,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# Serve React frontend with client-side routing support
STATIC_DIR = Path("static")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve React frontend with client-side routing support.
    
    This catches all non-API routes and serves the React app.
    """
    # Don't intercept API routes
    if full_path.startswith("api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not Found"},
        )
    
    # Try to serve the exact file first (for assets like JS, CSS, images)
    file_path = STATIC_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    
    # For all other routes, serve index.html (React router will handle it)
    index_path = STATIC_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    
    # No frontend available
    return JSONResponse(
        status_code=404,
        content={"detail": "Frontend not available. Running in API-only mode."},
    )
