"""Settings manager for persistent configuration in standalone mode.

This module handles loading, saving, and encrypting settings for the portal.
In standalone mode, all settings can be edited via the admin API.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages persistent settings storage and encryption.
    
    Settings are stored in a JSON file with secrets encrypted using Fernet.
    """

    def __init__(self, config_path: str = "/config/portal_settings.json"):
        """Initialize settings manager.
        
        Args:
            config_path: Path to settings JSON file
        """
        self.config_path = Path(config_path)
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Settings manager initialized with config: {self.config_path}")

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for secrets.
        
        The key is stored in an environment variable or generated on first run.
        
        Returns:
            Fernet encryption key
        """
        key_env = os.getenv("SETTINGS_ENCRYPTION_KEY")
        
        if key_env:
            return key_env.encode()
        
        # Generate new key
        key = Fernet.generate_key()
        logger.warning(
            "No SETTINGS_ENCRYPTION_KEY found. Generated new key. "
            "IMPORTANT: Set this in your environment to persist across restarts!"
        )
        logger.warning(f"SETTINGS_ENCRYPTION_KEY={key.decode()}")
        
        return key

    def _encrypt_value(self, value: str) -> str:
        """Encrypt a secret value.
        
        Args:
            value: Plain text value to encrypt
            
        Returns:
            Encrypted value as base64 string
        """
        if not value:
            return ""
        
        encrypted = self.cipher.encrypt(value.encode())
        return encrypted.decode()

    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a secret value.
        
        Args:
            encrypted_value: Encrypted value as base64 string
            
        Returns:
            Decrypted plain text value
        """
        if not encrypted_value:
            return ""
        
        try:
            decrypted = self.cipher.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to decrypt value (invalid encryption or wrong key): {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error during decryption: {e}")
            return ""

    def load_settings(self) -> dict[str, Any]:
        """Load settings from JSON file.
        
        Returns:
            Settings dictionary with decrypted secrets
        """
        if not self.config_path.exists():
            logger.info("No settings file found, using defaults")
            return {}
        
        try:
            with open(self.config_path, encoding="utf-8") as f:
                settings = json.load(f)
            
            # Decrypt secret fields
            if "secrets" in settings:
                for key, encrypted_value in settings["secrets"].items():
                    settings[key] = self._decrypt_value(encrypted_value)
                
                # Remove encrypted secrets block
                del settings["secrets"]
            
            logger.info(f"Loaded {len(settings)} settings from {self.config_path}")
            return settings
            
        except FileNotFoundError:
            logger.debug(f"Settings file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            return {}
        except PermissionError as e:
            logger.error(f"Permission denied reading settings file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading settings: {e}")
            return {}

    def save_settings(self, settings: dict[str, Any]) -> bool:
        """Save settings to JSON file.
        
        Secrets are encrypted before saving.
        
        Args:
            settings: Settings dictionary to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Separate secrets from regular settings
            secret_fields = {
                "secret_key",
                "admin_password",
                "admin_password_hash",
                "ha_token",
                "supervisor_token",
                "meraki_api_key",
                "duo_client_secret",
                "entra_client_secret",
                "oauth_client_secret",
                "radius_shared_secret",
                "radius_radsec_ca_cert",
                "radius_radsec_server_cert",
                "radius_radsec_server_key",
                "radius_api_token",
            }
            
            config_to_save = {}
            secrets_to_save = {}
            
            for key, value in settings.items():
                if key in secret_fields and value:
                    # Encrypt secrets
                    secrets_to_save[key] = self._encrypt_value(str(value))
                else:
                    config_to_save[key] = value
            
            # Add encrypted secrets block
            if secrets_to_save:
                config_to_save["secrets"] = secrets_to_save
            
            # Create backup of existing config
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix(".json.bak")
                self.config_path.rename(backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Write new config
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_to_save, f, indent=2, sort_keys=True)
            
            logger.info(f"Saved {len(settings)} settings to {self.config_path}")
            return True
            
        except PermissionError as e:
            logger.error(f"Permission denied writing settings file: {e}")
            # Restore backup if save failed
            backup_path = self.config_path.with_suffix(".json.bak")
            if backup_path.exists():
                backup_path.rename(self.config_path)
                logger.info("Restored backup due to permission error")
            return False
        except OSError as e:
            logger.error(f"OS error saving settings: {e}")
            # Restore backup if save failed
            backup_path = self.config_path.with_suffix(".json.bak")
            if backup_path.exists():
                backup_path.rename(self.config_path)
                logger.info("Restored backup due to OS error")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving settings: {e}")
            # Restore backup if save failed
            backup_path = self.config_path.with_suffix(".json.bak")
            if backup_path.exists():
                backup_path.rename(self.config_path)
                logger.info("Restored backup due to save failure")
            return False

    def update_setting(self, key: str, value: Any) -> bool:
        """Update a single setting.
        
        Args:
            key: Setting key to update
            value: New value
            
        Returns:
            True if successful, False otherwise
        """
        settings = self.load_settings()
        settings[key] = value
        return self.save_settings(settings)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value.
        
        Args:
            key: Setting key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            Setting value or default
        """
        settings = self.load_settings()
        return settings.get(key, default)

    def delete_setting(self, key: str) -> bool:
        """Delete a setting.
        
        Args:
            key: Setting key to delete
            
        Returns:
            True if successful, False otherwise
        """
        settings = self.load_settings()
        if key in settings:
            del settings[key]
            return self.save_settings(settings)
        return True

    def export_settings(self, include_secrets: bool = False) -> dict[str, Any]:
        """Export settings for backup or display.
        
        Args:
            include_secrets: If True, include decrypted secrets (use with caution!)
            
        Returns:
            Settings dictionary
        """
        settings = self.load_settings()
        
        if not include_secrets:
            # Mask secrets
            secret_fields = {
                "secret_key",
                "admin_password",
                "admin_password_hash",
                "ha_token",
                "supervisor_token",
                "meraki_api_key",
                "duo_client_secret",
                "entra_client_secret",
                "oauth_client_secret",
                "radius_shared_secret",
                "radius_radsec_ca_cert",
                "radius_radsec_server_cert",
                "radius_radsec_server_key",
                "radius_api_token",
            }
            
            masked_settings = settings.copy()
            for key in secret_fields:
                if key in masked_settings and masked_settings[key]:
                    masked_settings[key] = "***REDACTED***"
            
            return masked_settings
        
        return settings

    def import_settings(self, settings: dict[str, Any]) -> bool:
        """Import settings from backup or external source.
        
        Args:
            settings: Settings dictionary to import
            
        Returns:
            True if successful, False otherwise
        """
        return self.save_settings(settings)

    def reset_to_defaults(self) -> bool:
        """Reset all settings to defaults.
        
        Creates a backup before resetting.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup
            if self.config_path.exists():
                backup_path = self.config_path.with_suffix(
                    f".json.reset_backup_{int(Path(self.config_path).stat().st_mtime)}"
                )
                self.config_path.rename(backup_path)
                logger.info(f"Created reset backup: {backup_path}")
            
            # Save empty settings (will use environment defaults)
            return self.save_settings({})
            
        except OSError as e:
            logger.error(f"Failed to reset settings (filesystem error): {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error resetting settings: {e}")
            return False


# Singleton instance
_settings_manager: SettingsManager | None = None


def get_settings_manager() -> SettingsManager:
    """Get or create settings manager singleton.
    
    Returns:
        SettingsManager instance
    """
    global _settings_manager
    
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    
    return _settings_manager
