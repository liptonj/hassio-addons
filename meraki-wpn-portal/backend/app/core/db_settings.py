"""Database-backed settings manager with dynamic reload."""

import json
import logging
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.db.models import PortalSetting

logger = logging.getLogger(__name__)


class DatabaseSettingsManager:
    """Manage settings in database for dynamic reload without restart."""

    def __init__(self, encryption_key: bytes):
        """Initialize with encryption key.
        
        Args:
            encryption_key: Fernet encryption key for secrets
        """
        self.cipher = Fernet(encryption_key)

    def _encrypt_value(self, value: str) -> str:
        """Encrypt a sensitive value.
        
        Args:
            value: Value to encrypt
            
        Returns:
            Encrypted string
        """
        return self.cipher.encrypt(value.encode()).decode()

    def _decrypt_value(self, encrypted: str) -> str:
        """Decrypt an encrypted value.
        
        Args:
            encrypted: Encrypted string
            
        Returns:
            Decrypted value
        """
        try:
            return self.cipher.decrypt(encrypted.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            return ""

    def get_setting(self, db: Session, key: str, default: Any = None) -> Any:
        """Get a setting value from database.
        
        Args:
            db: Database session
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        setting = db.query(PortalSetting).filter(PortalSetting.key == key).first()
        
        if not setting or setting.value is None:
            return default
        
        # Decrypt if encrypted
        if setting.value_type == "encrypted":
            return self._decrypt_value(setting.value)
        
        # Convert types
        if setting.value_type == "int":
            return int(setting.value)
        if setting.value_type == "bool":
            return setting.value.lower() in ("true", "1", "yes")
        if setting.value_type == "json":
            return json.loads(setting.value)
        
        return setting.value

    def set_setting(
        self,
        db: Session,
        key: str,
        value: Any,
        value_type: str = "string",
        description: str | None = None,
        category: str | None = None,
        updated_by: str | None = None,
    ) -> bool:
        """Set a setting value in database.
        
        Args:
            db: Database session
            key: Setting key
            value: Value to set
            value_type: Type hint (string, int, bool, json, encrypted)
            description: Optional description
            category: Optional category
            updated_by: Who updated this setting
            
        Returns:
            True if successful
        """
        try:
            # Get or create setting
            setting = db.query(PortalSetting).filter(PortalSetting.key == key).first()
            
            if not setting:
                setting = PortalSetting(
                    key=key,
                    value_type=value_type,
                    description=description,
                    category=category,
                )
                db.add(setting)
            
            # Convert value to string
            if value_type == "encrypted":
                setting.value = self._encrypt_value(str(value))
            elif value_type == "json":
                setting.value = json.dumps(value)
            elif value_type == "bool":
                setting.value = "true" if value else "false"
            else:
                setting.value = str(value) if value is not None else None
            
            setting.value_type = value_type
            setting.updated_by = updated_by
            
            if description:
                setting.description = description
            if category:
                setting.category = category
            
            db.commit()
            # Mask sensitive values in log
            log_value = "***" if value_type == "encrypted" else str(value)[:50]
            logger.info(f"✅ Saved: {key} = {log_value} (type: {value_type})")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to set setting {key}: {e}")
            return False

    def get_all_settings(self, db: Session, category: str | None = None) -> dict[str, Any]:
        """Get all settings from database.
        
        Args:
            db: Database session
            category: Optional category filter
            
        Returns:
            Dictionary of all settings
        """
        query = db.query(PortalSetting)
        
        if category:
            query = query.filter(PortalSetting.category == category)
        
        settings = {}
        for setting in query.all():
            if setting.value is None:
                continue
            
            # Decrypt if needed
            if setting.value_type == "encrypted":
                settings[setting.key] = self._decrypt_value(setting.value)
            elif setting.value_type == "int":
                settings[setting.key] = int(setting.value)
            elif setting.value_type == "bool":
                settings[setting.key] = setting.value.lower() in ("true", "1", "yes")
            elif setting.value_type == "json":
                settings[setting.key] = json.loads(setting.value)
            else:
                settings[setting.key] = setting.value
        
        return settings

    def delete_setting(self, db: Session, key: str) -> bool:
        """Delete a setting from database.
        
        Args:
            db: Database session
            key: Setting key to delete
            
        Returns:
            True if deleted
        """
        try:
            setting = db.query(PortalSetting).filter(PortalSetting.key == key).first()
            if setting:
                db.delete(setting)
                db.commit()
                logger.info(f"Deleted setting: {key}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete setting {key}: {e}")
            return False

    def bulk_update_settings(
        self,
        db: Session,
        settings_dict: dict[str, Any],
        updated_by: str | None = None,
    ) -> bool:
        """Bulk update multiple settings.
        
        Args:
            db: Database session
            settings_dict: Dictionary of key-value pairs
            updated_by: Who is updating
            
        Returns:
            True if all successful
        """
        try:
            # Define which keys should be encrypted
            encrypted_keys = {
                "meraki_api_key",
                "secret_key",
                "admin_password_hash",
                "duo_client_secret",
                "entra_client_secret",
                "default_ssid_psk",
                "ha_token",
                "cloudflare_api_token",
            }

            # Define which keys are booleans
            bool_keys = {
                "auth_self_registration",
                "auth_invite_codes",
                "auth_email_verification",
                "require_unit_number",
                "enable_oauth",
                "oauth_admin_only",
                "oauth_auto_provision",
                "cloudflare_enabled",
            }
            
            # Define which keys are integers
            int_keys = {
                "default_ssid_number",
                "default_ipsk_duration_hours",
                "passphrase_length",
            }
            
            for key, value in settings_dict.items():
                if value is None or value == "":
                    continue
                
                # Skip masked/placeholder values for sensitive keys
                # These indicate "keep existing value" not "set to ***"
                if key in encrypted_keys:
                    if value == "***" or (isinstance(value, str) and value.startswith("***")):
                        logger.debug(f"Skipping masked value for {key}")
                        continue
                
                # Determine value type
                if key in encrypted_keys:
                    value_type = "encrypted"
                elif key in bool_keys:
                    value_type = "bool"
                elif key in int_keys:
                    value_type = "int"
                else:
                    value_type = "string"
                
                # Set category
                category = "general"
                if key.startswith("meraki_"):
                    category = "meraki"
                elif key.startswith("auth_") or key == "require_unit_number":
                    category = "auth"
                elif key in ("property_name", "logo_url", "primary_color"):
                    category = "branding"
                elif key.startswith("default_") or "network" in key or "ssid" in key:
                    category = "network"
                elif key.startswith("oauth_") or key.startswith("duo_") or key.startswith("entra_"):
                    category = "oauth"
                elif key.startswith("cloudflare_"):
                    category = "cloudflare"
                
                self.set_setting(
                    db=db,
                    key=key,
                    value=value,
                    value_type=value_type,
                    category=category,
                    updated_by=updated_by,
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Bulk update failed: {e}")
            return False
