"""Application configuration loaded from environment variables and database."""

import json
import logging
import os
from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DeploymentMode(str, Enum):
    """Deployment mode enumeration."""
    HA_ADDON = "ha_addon"
    STANDALONE = "standalone"


def detect_deployment_mode() -> DeploymentMode:
    """Auto-detect deployment mode based on environment and filesystem.
    
    Detection methods (in order of precedence):
    1. Explicit DEPLOYMENT_MODE environment variable
    2. SUPERVISOR_TOKEN presence (HA Supervisor injects this)
    3. HA-specific filesystem paths (/data/options.json, /config)
    4. Default to STANDALONE
    
    Returns
    -------
        DeploymentMode enum value
    """
    # Method 1: Explicit environment variable
    mode_env = os.getenv("DEPLOYMENT_MODE", "").lower()
    if mode_env == "ha_addon":
        logger.info("🏠 Deployment mode: HA Addon (explicit env variable)")
        return DeploymentMode.HA_ADDON
    elif mode_env == "standalone":
        logger.info("🐳 Deployment mode: Standalone (explicit env variable)")
        return DeploymentMode.STANDALONE
    
    # Method 2: Check for SUPERVISOR_TOKEN (HA Supervisor injects this)
    if os.getenv("SUPERVISOR_TOKEN"):
        logger.info("🏠 Deployment mode: HA Addon (SUPERVISOR_TOKEN detected)")
        return DeploymentMode.HA_ADDON
    
    # Method 3: Check for HA-specific filesystem paths
    ha_paths = [
        Path("/data/options.json"),  # HA addon config file
        Path("/config"),  # HA config directory
    ]
    
    for path in ha_paths:
        if path.exists():
            logger.info(f"🏠 Deployment mode: HA Addon (found {path})")
            return DeploymentMode.HA_ADDON
    
    # Default: Standalone mode
    logger.info("🐳 Deployment mode: Standalone (default)")
    return DeploymentMode.STANDALONE


def get_default_database_url(mode: DeploymentMode) -> str:
    """Get default database URL based on deployment mode.
    
    Parameters
    ----------
    mode : DeploymentMode
        Current deployment mode
        
    Returns
    -------
        Database connection string
    """
    if mode == DeploymentMode.HA_ADDON:
        # HA Addon: Use MariaDB addon (core-mariadb)
        password = os.getenv("MARIADB_PASSWORD", "")
        db_url = f"mysql+pymysql://wpn_user:{password}@core-mariadb:3306/wpn_radius"
        logger.info("📊 Database: MariaDB (core-mariadb addon)")
        return db_url
    else:
        # Standalone: Default to SQLite (can be overridden via DATABASE_URL env var)
        data_dir = Path(os.getenv("DATA_DIR", "./data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{data_dir}/wpn_radius.db"
        logger.info(f"📊 Database: SQLite ({data_dir}/wpn_radius.db)")
        return db_url


def _load_db_settings() -> dict:
    """Load settings from database if available.

    Returns
    -------
        Dictionary of settings from database, or empty dict if not found
    """
    try:
        from pathlib import Path
        from cryptography.fernet import Fernet
        from app.core.db_settings import DatabaseSettingsManager
        from app.db.database import get_db
        
        # Get encryption key from environment OR file
        key_env = os.getenv("SETTINGS_ENCRYPTION_KEY")
        
        # If not in environment, try to load from file
        if not key_env:
            key_file = Path("/data/.encryption_key")
            if key_file.exists():
                key_env = key_file.read_text().strip()
                logger.debug("Loaded encryption key from /data/.encryption_key")
            else:
                logger.debug("No SETTINGS_ENCRYPTION_KEY and no key file found")
                return {}
        
        # Load settings from database
        db_mgr = DatabaseSettingsManager(key_env.encode())
        
        # Use get_db() generator properly
        db_gen = get_db()
        db = next(db_gen)
        try:
            db_settings = db_mgr.get_all_settings(db)
            if db_settings:
                logger.info(f"✅ Loaded {len(db_settings)} settings from database")
                logger.debug(f"Settings keys: {list(db_settings.keys())[:10]}...")
            else:
                logger.info("📝 No custom settings in database yet (using defaults)")
            return db_settings
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
    except ImportError as e:
        logger.debug(f"Database not available yet (normal on first import): {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Error loading settings from database: {e}", exc_info=True)
        return {}


class Settings(BaseSettings):
    """Application settings from environment variables and database.

    Priority (highest to lowest):
    1. Environment variables
    2. Database settings (portal_settings table) - in standalone mode
    3. Defaults defined here
    """

    # Deployment Mode (auto-detected)
    deployment_mode: DeploymentMode = DeploymentMode.STANDALONE
    
    # Run Mode: "standalone" or "homeassistant" (legacy, kept for compatibility)
    run_mode: str = "standalone"

    # Encryption key for sensitive settings (loaded from env or file)
    settings_encryption_key: str = ""

    # Meraki Dashboard API (for standalone mode)
    meraki_api_key: str = ""
    meraki_org_id: str = ""

    # Home Assistant Connection (for homeassistant mode)
    ha_url: str = "http://supervisor/core"
    ha_token: str = ""
    supervisor_token: str = ""

    # Branding
    property_name: str = "My Property"
    logo_url: str = ""
    primary_color: str = "#00A4E4"

    # Default Network Settings
    default_network_id: str = ""
    default_ssid_number: int = 0
    default_group_policy_id: str = ""  # Group policy for registered users with iPSK
    default_group_policy_name: str = "WPN-Users"  # Name for registered users policy
    default_guest_group_policy_id: str = ""  # Group policy for guest/default PSK users
    default_guest_group_policy_name: str = "WPN-Guests"  # Name for guest policy
    default_ssid_psk: str = ""
    splash_page_url: str = ""  # Custom splash page URL for the SSID

    # Registration Modes (can enable multiple)
    auth_open_registration: bool = True           # Open registration, immediate access
    auth_open_registration_approval: bool = False # Open registration + admin approval
    auth_account_only: bool = False               # Existing accounts only
    auth_invite_code_account: bool = False        # Invite code required to create account
    auth_invite_code_only: bool = False           # Enter code → get PSK (no account)
    
    # Legacy fields (for backwards compatibility)
    auth_self_registration: bool = True
    auth_invite_codes: bool = True
    
    # Registration Mode: "open" (immediate access), "invite_only" (code required), 
    # "approval_required" (admin approval needed)
    registration_mode: str = "open"
    approval_notification_email: str = ""  # Email to notify on new pending registrations
    
    # Verification
    auth_email_verification: bool = False
    auth_sms_verification: bool = False

    # Registration Options
    require_unit_number: bool = False  # Optional by default, can be enabled in settings
    unit_source: str = "manual_list"  # Default to manual_list for standalone
    manual_units: str = '["101", "102", "201", "202", "301", "302"]'

    # IPSK Settings
    default_ipsk_duration_hours: int = 0
    passphrase_length: int = 12
    
    # AUP Settings
    aup_enabled: bool = False
    aup_text: str = ""
    aup_url: str = ""
    aup_version: int = 1
    
    # Custom Registration Fields
    custom_registration_fields: str = "[]"  # JSON string
    
    # PSK Customization
    allow_custom_psk: bool = True
    psk_min_length: int = 8
    psk_max_length: int = 63
    
    # Invite Code Settings
    invite_code_email_restriction: bool = False
    invite_code_single_use: bool = False
    
    # Authentication Methods
    auth_method_local: bool = True
    auth_method_oauth: bool = False
    auth_method_invite_code: bool = True
    auth_method_self_registration: bool = True
    
    # Universal Login
    universal_login_enabled: bool = True
    show_login_method_selector: bool = False
    
    # iPSK Expiration Management
    ipsk_expiration_check_enabled: bool = True
    ipsk_expiration_check_interval_hours: int = 1
    ipsk_cleanup_action: str = "soft_delete"  # soft_delete, revoke_meraki, full_cleanup
    ipsk_expiration_warning_days: str = "7,3,1"
    ipsk_expiration_email_enabled: bool = False

    # Admin Settings
    admin_notification_email: str = ""

    # SMTP Email Settings
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_from_email: str = ""
    smtp_from_name: str = "WiFi Portal"
    smtp_timeout: int = 10

    # Database (auto-detected based on deployment mode)
    database_url: str = ""

    # Security
    secret_key: str = "change-this-in-production-use-strong-random-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Default Admin Credentials (for standalone/initial setup)
    admin_username: str = "admin"
    admin_password: str = "admin"  # CHANGE THIS IN PRODUCTION!
    admin_password_hash: str = ""  # If set, overrides admin_password

    # Standalone mode settings
    standalone_ssid_name: str = "Demo-WiFi"
    editable_settings: bool = True  # Allow settings changes in standalone mode

    # OAuth/SSO Settings
    enable_oauth: bool = False
    oauth_provider: str = "none"  # "none", "duo", "entra"

    # Duo OAuth
    duo_client_id: str = ""
    duo_client_secret: str = ""
    duo_api_hostname: str = ""

    # Microsoft Entra ID (Azure AD)
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_tenant_id: str = ""

    # OAuth Settings
    oauth_callback_url: str = "http://localhost:8080/api/auth/callback"
    oauth_admin_only: bool = False  # If true, only admin portal uses OAuth
    oauth_auto_provision: bool = True  # Auto-create users on first OAuth login

    # Cloudflare Zero Trust Tunnel
    cloudflare_enabled: bool = False
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    cloudflare_tunnel_id: str = ""
    cloudflare_tunnel_name: str = ""
    cloudflare_zone_id: str = ""
    cloudflare_zone_name: str = ""
    cloudflare_hostname: str = ""
    cloudflare_local_url: str = "http://localhost:8080"

    # RADIUS Server Settings
    radius_enabled: bool = False
    radius_server_host: str = "localhost"
    radius_hostname: str = ""  # Public hostname for RADIUS server
    radius_auth_port: int = 1812
    radius_acct_port: int = 1813
    radius_coa_port: int = 3799  # CoA/Disconnect-Message port
    radius_radsec_port: int = 2083
    radius_radsec_enabled: bool = True
    radius_shared_secret: str = ""
    radius_radsec_ca_cert: str = ""
    radius_radsec_server_cert: str = ""
    radius_radsec_server_key: str = ""
    radius_radsec_auto_generate: bool = True
    radius_cert_source: str = "selfsigned"  # selfsigned, letsencrypt, cloudflare
    radius_api_url: str = "http://localhost:8000"
    radius_api_token: str = ""

    # CORS Configuration (comma-separated list of allowed origins, or "*" for all)
    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    def __init__(self, **data):
        """Initialize settings with deployment mode detection."""
        # Detect deployment mode if not explicitly provided
        if "deployment_mode" not in data:
            data["deployment_mode"] = detect_deployment_mode()
        
        # Set database URL based on deployment mode if not provided
        if not data.get("database_url"):
            # Check environment variable first
            env_db_url = os.getenv("DATABASE_URL")
            if env_db_url:
                data["database_url"] = env_db_url
            else:
                # Auto-detect based on deployment mode
                data["database_url"] = get_default_database_url(data["deployment_mode"])
        
        # Set run_mode for backwards compatibility
        if data["deployment_mode"] == DeploymentMode.HA_ADDON:
            data["run_mode"] = "homeassistant"
        else:
            data["run_mode"] = "standalone"
        
        super().__init__(**data)

    def get_manual_units_list(self) -> list[str]:
        """Parse manual units from JSON string."""
        if not self.manual_units:
            return []
        try:
            return json.loads(self.manual_units)
        except json.JSONDecodeError:
            logger.warning("Failed to parse manual_units, returning empty list")
            return []

    def get_auth_token(self) -> str:
        """Get the best available auth token for Home Assistant."""
        # Prefer supervisor token if available
        if self.supervisor_token:
            return self.supervisor_token
        return self.ha_token

    @property
    def is_standalone(self) -> bool:
        """Check if running in standalone mode."""
        return self.deployment_mode == DeploymentMode.STANDALONE

    @property
    def is_homeassistant(self) -> bool:
        """Check if running in Home Assistant mode."""
        return self.deployment_mode == DeploymentMode.HA_ADDON
    
    @property
    def is_ha_addon(self) -> bool:
        """Check if running in Home Assistant addon mode (alias for is_homeassistant)."""
        return self.deployment_mode == DeploymentMode.HA_ADDON

    def model_post_init(self, __context) -> None:
        """Merge database settings after initial model creation.

        In standalone mode with editable_settings, database settings override defaults
        but environment variables still take precedence.
        """
        # Skip database loading during initial module import to avoid circular imports
        # Database settings will be loaded on reload_settings() after app startup
        pass


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get settings instance (cached after first call)."""
    global _settings
    if _settings is None:
        _settings = Settings()
        logger.info(
            "⚙️  Settings loaded: mode=%s, db=%s, property=%s",
            _settings.deployment_mode.value,
            "MariaDB" if "mysql" in _settings.database_url else "PostgreSQL" if "postgresql" in _settings.database_url else "SQLite",
            _settings.property_name
        )
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment and database.

    Useful after settings database has been updated.

    Returns
    -------
        New Settings instance with database settings applied
    """
    # System settings that should ONLY come from environment variables
    # These are infrastructure/security settings that shouldn't be changeable via UI
    SYSTEM_ONLY_SETTINGS = {
        'database_url',          # Can't store DB config in the DB itself
        'secret_key',            # Security critical - JWT signing key
        'run_mode',              # Deployment mode (standalone vs HA)
        'is_standalone',         # Derived from run_mode
        'deployment_mode',       # Alternative run_mode name
        'ha_url',                # Home Assistant connection (N/A in standalone)
        'ha_token',              # Home Assistant auth token
        'editable_settings',     # Feature flag for settings UI
    }
    
    global _settings
    _settings = None
    new_settings = get_settings()
    
    # Now apply database settings AFTER initial creation (avoids circular import)
    if new_settings.is_standalone and new_settings.editable_settings:
        db_settings = _load_db_settings()
        
        if db_settings:
            logger.info(f"🔧 Applying {len(db_settings)} database settings...")
            applied_count = 0
            skipped_system = 0
            skipped_env = 0
            
            for key, value in db_settings.items():
                if not hasattr(new_settings, key):
                    continue
                    
                # System-only settings: env var always wins
                if key in SYSTEM_ONLY_SETTINGS:
                    env_key = key.upper()
                    if env_key in os.environ:
                        logger.debug(f"Skipped {key} (system setting from environment)")
                        skipped_system += 1
                        continue
                
                # For all other settings: DATABASE WINS (real-time config)
                # Only skip if explicitly set via environment variable WITH a non-empty value
                env_key = key.upper()
                env_value = os.environ.get(env_key, "")
                
                # Check if env var has a meaningful value (not empty, not just whitespace)
                if env_value and env_value.strip():
                    # Env var exists AND has a non-empty value
                    logger.debug(f"Skipped {key} (explicitly set via environment variable: {env_value[:20]}...)")
                    skipped_env += 1
                else:
                    # Database value wins - enables real-time configuration
                    setattr(new_settings, key, value)
                    applied_count += 1
                    logger.debug(f"Applied: {key} = {value if key not in ['meraki_api_key', 'secret_key', 'admin_password'] else '***'}")
            
            logger.info(f"✨ Applied {applied_count}/{len(db_settings)} database settings")
            if skipped_system > 0:
                logger.info(f"🔒 Protected {skipped_system} system settings from override")
            if skipped_env > 0:
                logger.info(f"⚠️  Skipped {skipped_env} settings with explicit env vars")
    
    return new_settings
