"""Application configuration loaded from environment variables and database."""

import json
import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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

    # Run Mode: "standalone" or "homeassistant"
    run_mode: str = "standalone"

    # Encryption key for sensitive settings (loaded from env or file)
    settings_encryption_key: str = ""

    # Meraki Dashboard API (for standalone mode)
    meraki_api_key: str = ""

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
    default_group_policy_id: str = ""
    default_group_policy_name: str = "WPN-Users"
    default_ssid_psk: str = ""

    # Authentication Methods
    auth_self_registration: bool = True
    auth_invite_codes: bool = True
    auth_email_verification: bool = False
    auth_sms_verification: bool = False

    # Registration Options
    require_unit_number: bool = True
    unit_source: str = "manual_list"  # Default to manual_list for standalone
    manual_units: str = '["101", "102", "201", "202", "301", "302"]'

    # IPSK Settings
    default_ipsk_duration_hours: int = 0
    passphrase_length: int = 12

    # Admin Settings
    admin_notification_email: str = ""

    # Database
    database_url: str = "sqlite:///./meraki_wpn_portal.db"

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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
        return self.run_mode.lower() == "standalone"

    @property
    def is_homeassistant(self) -> bool:
        """Check if running in Home Assistant mode."""
        return self.run_mode.lower() == "homeassistant"

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
            "Settings loaded: run_mode=%s, property=%s",
            _settings.run_mode,
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
    global _settings
    _settings = None
    new_settings = get_settings()
    
    # Now apply database settings AFTER initial creation (avoids circular import)
    if new_settings.is_standalone and new_settings.editable_settings:
        db_settings = _load_db_settings()
        
        if db_settings:
            logger.info(f"🔧 Applying {len(db_settings)} database settings...")
            applied_count = 0
            # Only apply database settings if env var is not set
            for key, value in db_settings.items():
                if hasattr(new_settings, key):
                    # Check if value came from env (not default)
                    env_key = key.upper()
                    if env_key not in os.environ:
                        setattr(new_settings, key, value)
                        applied_count += 1
                        logger.debug(f"Applied: {key} = {value if key not in ['meraki_api_key', 'secret_key'] else '***'}")
                    else:
                        logger.debug(f"Skipped {key} (set via environment variable)")
            logger.info(f"✨ Applied {applied_count}/{len(db_settings)} database settings")
    
    return new_settings
