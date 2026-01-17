"""Application configuration with auto-detection for addon vs standalone mode."""

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
    """Auto-detect deployment mode based on environment and filesystem."""
    # Check for explicit DEPLOYMENT_MODE
    mode_env = os.getenv("DEPLOYMENT_MODE", "").lower()
    if mode_env == "ha_addon":
        return DeploymentMode.HA_ADDON
    elif mode_env == "standalone":
        return DeploymentMode.STANDALONE
    
    # Check for SUPERVISOR_TOKEN (HA Supervisor injects this)
    if os.getenv("SUPERVISOR_TOKEN"):
        return DeploymentMode.HA_ADDON
    
    # Check for HA-specific filesystem paths
    if Path("/data/options.json").exists():
        return DeploymentMode.HA_ADDON
    
    return DeploymentMode.STANDALONE


def get_database_url() -> str:
    """Get database URL from environment or generate default.
    
    Priority:
    1. DATABASE_URL environment variable
    2. PORTAL_DB_* vars for MariaDB connection
    3. SQLite fallback
    """
    # Check for explicit DATABASE_URL first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        logger.info(f"📊 Database URL from environment: {db_url.split('@')[0].split('://')[0]}://...")
        return db_url
    
    # Check for portal DB settings (HA addon mode)
    portal_host = os.getenv("PORTAL_DB_HOST")
    if portal_host:
        portal_port = os.getenv("PORTAL_DB_PORT", "3306")
        portal_db = os.getenv("PORTAL_DB_NAME", "wpn_radius")
        portal_user = os.getenv("PORTAL_DB_USER", "wpn_user")
        portal_pass = os.getenv("PORTAL_DB_PASSWORD", "")
        db_url = f"mysql+pymysql://{portal_user}:{portal_pass}@{portal_host}:{portal_port}/{portal_db}"
        logger.info(f"📊 Database: MariaDB ({portal_host})")
        return db_url
    
    # Fallback to SQLite
    data_dir = Path(os.getenv("DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{data_dir}/wpn_radius.db"
    logger.info(f"📊 Database: SQLite ({data_dir}/wpn_radius.db)")
    return db_url


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # These are read directly from environment by pydantic-settings
    deployment_mode: DeploymentMode = DeploymentMode.STANDALONE
    database_url: str = ""
    radius_config_path: str = "/config/raddb"  # Persistent storage
    radius_clients_path: str = "/config/clients"
    radius_certs_path: str = "/config/certs"
    api_port: int = 8000
    api_host: str = "127.0.0.1"  # Bind to localhost by default for security
    api_auth_token: str = ""
    log_level: str = "INFO"
    
    # Let's Encrypt settings
    letsencrypt_standalone: bool = False
    letsencrypt_domain: str = ""
    letsencrypt_email: str = ""
    letsencrypt_http_port: int = 80
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton with lazy initialization
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get settings instance.
    
    Creates fresh settings each time if critical values are missing,
    to handle cases where env vars aren't available during early imports.
    """
    global _settings
    
    # Always read fresh from environment for critical values
    db_url = os.getenv("DATABASE_URL", "")
    api_token = os.getenv("API_AUTH_TOKEN", "")
    config_path = os.getenv("RADIUS_CONFIG_PATH", "/config/raddb")
    
    # If we have cached settings AND they match current env, use cache
    if _settings is not None:
        if (_settings.database_url == db_url and 
            _settings.api_auth_token == api_token and
            _settings.radius_config_path == config_path):
            return _settings
    
    # Create new settings
    mode = detect_deployment_mode()
    
    # Build settings with explicit values from environment
    settings_data = {
        "deployment_mode": mode,
        "database_url": db_url if db_url else get_database_url(),
        "api_auth_token": api_token,
        "radius_config_path": config_path,
    }
    
    _settings = Settings(**settings_data)
    
    logger.info(
        "⚙️  FreeRADIUS settings loaded: mode=%s, db=%s, api_token=%s",
        _settings.deployment_mode.value,
        "MariaDB" if "mysql" in _settings.database_url 
        else "PostgreSQL" if "postgresql" in _settings.database_url 
        else "SQLite",
        "SET" if _settings.api_auth_token else "NOT SET",
    )
    
    return _settings
