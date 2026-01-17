"""FreeRADIUS Configuration Management API - Main Application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from radius_app.api import (
    config_router,
    health_router,
    clients_router,
    udn_assignments_router,
    monitoring_router,
    nads_router,
    policies_router,
    radsec_router,
    mac_bypass_router,
    auth_config_router,
    sql_sync_router,
    sql_counter_router,
    performance_router,
    coa_router,
    cloudflare_router,
    eap_router,
    psk_config_router,
    unlang_policies_router,
)
from radius_app.config import get_settings
from radius_app.core.db_watcher import DatabaseWatcher
from radius_app.core.health_monitor import HealthMonitor
from radius_app.db.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database watcher task
_watcher_task: asyncio.Task | None = None
# Health monitoring task
_health_monitor_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _watcher_task, _health_monitor_task
    
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Starting FreeRADIUS Configuration API...")
    logger.info("=" * 60)
    
    # Load settings
    settings = get_settings()
    logger.info(f"Deployment mode: {settings.deployment_mode.value}")
    logger.info(f"Database: {settings.database_url.split('://')[0]}")
    logger.info(f"Config path: {settings.radius_config_path}")
    logger.info(f"Clients path: {settings.radius_clients_path}")
    
    # Initialize database connection (schema only, no default data yet)
    logger.info("Initializing database connection...")
    try:
        from radius_app.db.database import get_engine
        from radius_app.db.init_schema import create_schema
        
        engine = get_engine()
        create_schema(engine)
        logger.info("✅ Database schema initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database schema: {e}")
        logger.error("Continuing anyway - will retry on first request")
    
    # Run database migrations BEFORE initializing default data
    # This ensures all columns exist before we try to insert data
    logger.info("Running database migrations...")
    try:
        from radius_app.db.migrations import run_migrations
        run_migrations()
        logger.info("✅ Database migrations completed")
    except Exception as e:
        logger.warning(f"⚠️  Migration warning: {e}")
        logger.info("Continuing - migrations may already be applied")
    
    # Now initialize default data (after migrations have added missing columns)
    logger.info("Initializing default data...")
    try:
        from radius_app.db.init_schema import init_default_data, apply_eap_migrations
        engine = get_engine()
        apply_eap_migrations(engine)
        init_default_data(engine)
        logger.info("✅ Default data initialized")
    except Exception as e:
        logger.warning(f"⚠️  Default data warning: {e}")
        logger.info("Continuing - default data may already exist")
    
    # Start database watcher
    logger.info("Starting database watcher...")
    watcher = DatabaseWatcher(poll_interval=5)
    _watcher_task = asyncio.create_task(watcher.watch_loop())
    logger.info("✅ Database watcher started (poll interval: 5s)")
    
    # Start health monitor
    logger.info("Starting NAD health monitor...")
    health_monitor = HealthMonitor(check_interval=60)
    _health_monitor_task = asyncio.create_task(health_monitor.monitor_loop())
    logger.info("✅ Health monitor started (check interval: 60s)")
    
    logger.info("=" * 60)
    logger.info("✅ FreeRADIUS Configuration API is ready!")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Shutting down FreeRADIUS Configuration API...")
    
    # Stop database watcher
    if _watcher_task:
        logger.info("Stopping database watcher...")
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            logger.info("Database watcher stopped")
    
    # Stop health monitor
    if _health_monitor_task:
        logger.info("Stopping health monitor...")
        _health_monitor_task.cancel()
        try:
            await _health_monitor_task
        except asyncio.CancelledError:
            logger.info("Health monitor stopped")
    
    logger.info("Shutdown complete")


# Create FastAPI application with enhanced OpenAPI configuration
app = FastAPI(
    title="FreeRADIUS Management API",
    description="""
    # FreeRADIUS Management API
    
    Full CRUD API for managing FreeRADIUS clients and UDN (User Defined Network) assignments for Meraki WPN.
    
    ## Features
    
    - **RADIUS Client Management**: Create, read, update, and delete RADIUS clients with validation
    - **UDN Assignment Management**: Manage MAC address to UDN ID mappings for network segmentation
    - **Monitoring & Statistics**: Real-time stats, logs, and configuration file inspection
    - **Automatic Configuration**: Changes are automatically synced to FreeRADIUS within 5 seconds
    - **Security**: Bearer token authentication on all protected endpoints
    
    ## Authentication
    
    All API endpoints (except `/health` and `/`) require Bearer token authentication:
    
    ```
    Authorization: Bearer YOUR_TOKEN_HERE
    ```
    
    Use the 🔒 Authorize button above to set your token for trying out the API.
    
    ## Database Integration
    
    This API shares a database with the Meraki WPN Portal. All changes are automatically
    propagated to FreeRADIUS configuration files and the RADIUS daemon is signaled to reload.
    
    ## OpenAPI Specification
    
    Download the complete OpenAPI specification at `/openapi.json`
    """,
    version="2.0.0",
    contact={
        "name": "FreeRADIUS Admin",
        "url": "https://github.com/yourusername/hassio-addons",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "Health",
            "description": "Health check and status endpoints (no authentication required)",
        },
        {
            "name": "NADs",
            "description": "Network Access Device management - Enhanced RADIUS client management with health monitoring, CoA, and RadSec support",
        },
        {
            "name": "Policies",
            "description": "Authorization policy management - VLAN assignment, bandwidth limits, time restrictions, and dynamic attributes",
        },
        {
            "name": "RadSec",
            "description": "RadSec (RADIUS over TLS) configuration - Secure RADIUS transport with certificate management and TLS settings",
        },
        {
            "name": "Clients",
            "description": "RADIUS client management - Create, read, update, delete RADIUS clients",
        },
        {
            "name": "UDN Assignments",
            "description": "User Defined Network ID assignments - Manage MAC address to UDN ID mappings for WPN segmentation",
        },
        {
            "name": "Configuration",
            "description": "Configuration reload and status - Manually trigger config reload and check status",
        },
        {
            "name": "Monitoring",
            "description": "Statistics and monitoring - View stats, logs, and generated config files",
        },
        {
            "name": "CoA",
            "description": "Change of Authorization - Disconnect users and modify active session parameters (RFC 5176)",
        },
        {
            "name": "Cloudflare",
            "description": "Cloudflare DNS and Let's Encrypt - DNS-01 certificate provisioning without exposing port 80",
        },
        {
            "name": "EAP Methods",
            "description": "EAP authentication method management - Enable/disable EAP-TLS, EAP-TTLS, PEAP and configure per-method policies",
        },
        {
            "name": "PSK Config",
            "description": "PSK (Pre-Shared Key) configuration - Generic and user-specific PSK authentication settings",
        },
        {
            "name": "Authorization Policies",
            "description": "Unlang authorization policies - Conditions and rules that determine which RADIUS profile to apply",
        },
    ],
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
    },
)


# Include routers with tags
app.include_router(health_router, tags=["Health"])
app.include_router(nads_router, tags=["NADs"])
app.include_router(policies_router, tags=["Policies"])
app.include_router(radsec_router, tags=["RadSec"])
app.include_router(clients_router, tags=["Clients"])
app.include_router(udn_assignments_router, tags=["UDN Assignments"])
app.include_router(config_router, tags=["Configuration"])
app.include_router(monitoring_router, tags=["Monitoring"])
app.include_router(mac_bypass_router, prefix="/api/v1", tags=["MAC Bypass"])
app.include_router(eap_router, prefix="/api/v1/eap", tags=["EAP Methods"])
app.include_router(psk_config_router, prefix="/api/v1", tags=["PSK Config"])
app.include_router(unlang_policies_router, prefix="/api/v1", tags=["Authorization Policies"])
app.include_router(sql_sync_router, prefix="/api/v1", tags=["SQL Module"])
app.include_router(sql_counter_router, prefix="/api/v1", tags=["SQL Counter"])
app.include_router(auth_config_router, tags=["Authentication Config"])
app.include_router(performance_router, tags=["Performance Testing"])
app.include_router(coa_router, tags=["CoA"])
app.include_router(cloudflare_router, tags=["Cloudflare"])


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": "FreeRADIUS Configuration API",
        "version": "2.0.0",
        "status": "operational",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please check logs."},
    )


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    # Set log level from config
    logging.getLogger().setLevel(getattr(logging, settings.log_level.upper()))
    
    # API binds to localhost by default for security
    # Set API_HOST=0.0.0.0 to expose externally (not recommended without auth)
    api_host = settings.api_host
    
    logger.info(f"Starting server on {api_host}:{settings.api_port}...")
    if api_host == "127.0.0.1":
        logger.info("⚠️  API bound to localhost only - use Ingress or local network access")
    
    uvicorn.run(
        "radius_app.main:app",
        host=api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        reload=False,
    )
