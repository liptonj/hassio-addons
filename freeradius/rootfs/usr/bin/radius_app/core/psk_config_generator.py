"""PSK configuration generator for FreeRADIUS.

Reads PSK data from database (users table) via sync and generates
FreeRADIUS users file entries for PSK authentication.

Alternative approach: Use FreeRADIUS SQL module for dynamic lookups.
See sql_config_generator.py for SQL-based PSK authentication.
"""

import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.db.models import UdnAssignment

logger = logging.getLogger(__name__)


class PskConfigGenerator:
    """Generates FreeRADIUS users file entries for PSK authentication."""
    
    def __init__(self):
        """Initialize PSK config generator."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.radius_config_path)
        
        # Ensure directory exists
        self.config_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"PSK config generator initialized: {self.config_path}")
    
    def _decrypt_passphrase(self, encrypted_passphrase: str, portal_db_url: Optional[str] = None) -> Optional[str]:
        """Decrypt PSK passphrase for FreeRADIUS config.
        
        Args:
            encrypted_passphrase: Encrypted passphrase from database
            portal_db_url: Portal database URL (for decryption if needed)
            
        Returns:
            Decrypted passphrase or None if decryption fails
            
        Note:
            In production, passphrase decryption should use a shared encryption key
            or key management system. For now, this is a placeholder that will need
            to be implemented based on the portal's encryption mechanism.
        """
        try:
            # TODO: Implement proper passphrase decryption
            # This should use the same encryption key as the portal
            # For now, return None to indicate decryption is not yet implemented
            logger.warning("Passphrase decryption not yet implemented - PSK entries will need manual configuration")
            return None
        except Exception as e:
            logger.error(f"Failed to decrypt passphrase: {e}")
            return None
    
    def generate_psk_users_file(self, db: Session, portal_db_url: Optional[str] = None) -> Path:
        """Generate FreeRADIUS users file from PSK data in portal database.
        
        Args:
            db: FreeRADIUS database session
            portal_db_url: Portal database URL (if different from FreeRADIUS DB)
            
        Returns:
            Path to generated users file
        """
        users_file = "# Auto-generated RADIUS users for PSK authentication\n"
        users_file += "# Generated from portal database (users table)\n"
        users_file += f"# Timestamp: {datetime.now(UTC).isoformat()}\n"
        users_file += "# DO NOT EDIT MANUALLY - Changes will be overwritten\n"
        users_file += "#\n"
        users_file += "# Format: PSK Cleartext-Password := \"passphrase\"\n"
        users_file += "#         Auth-Type := Accept\n"
        users_file += "#         Reply-Attribute := value\n\n"
        
        # Query users with PSK from portal database
        # Note: This assumes we can query the portal database directly
        # In production, this might use a sync mechanism or API
        
        try:
            # Try to query portal database directly if URL provided
            if portal_db_url:
                from sqlalchemy import create_engine
                portal_engine = create_engine(portal_db_url)
                with portal_engine.connect() as portal_conn:
                    # Query users with PSK
                    result = portal_conn.execute(text("""
                        SELECT 
                            id,
                            email,
                            ipsk_id,
                            ipsk_passphrase_encrypted,
                            ipsk_name,
                            ssid_name,
                            unit
                        FROM users
                        WHERE ipsk_passphrase_encrypted IS NOT NULL
                          AND ipsk_passphrase_encrypted != ''
                          AND is_active = true
                        ORDER BY email
                    """))
                    
                    users = result.fetchall()
                    logger.info(f"Found {len(users)} users with PSK")
                    
                    for user in users:
                        user_id = user[0]
                        email = user[1]
                        ipsk_id = user[2]
                        encrypted_passphrase = user[3]
                        ipsk_name = user[4]
                        ssid_name = user[5]
                        unit = user[6]
                        
                        # Decrypt passphrase
                        passphrase = self._decrypt_passphrase(encrypted_passphrase, portal_db_url)
                        if not passphrase:
                            logger.warning(f"Could not decrypt passphrase for user {email} - skipping PSK entry")
                            # Still add entry with placeholder - admin will need to configure manually
                            users_file += f"# User {user_id} ({email}) - PSK passphrase needs to be configured manually\n"
                            users_file += f"# Encrypted passphrase stored in database\n\n"
                            continue
                        
                        # Look up UDN ID for this user
                        udn_stmt = select(UdnAssignment).where(
                            UdnAssignment.user_id == user_id,
                            UdnAssignment.is_active == True
                        )
                        udn_assignment = db.execute(udn_stmt).scalar_one_or_none()
                        
                        # Generate user entry
                        users_file += f"# User: {email}"
                        if unit:
                            users_file += f", Unit: {unit}"
                        users_file += f"\n"
                        users_file += f"# IPSK: {ipsk_name or ipsk_id}\n"
                        
                        # Use PSK as username (or email, or IPSK ID)
                        # FreeRADIUS will match on Cleartext-Password
                        username = ipsk_id or email
                        
                        users_file += f'"{username}" Cleartext-Password := "{passphrase}"\n'
                        users_file += "    Auth-Type := Accept\n"
                        
                        # Add UDN ID if available
                        if udn_assignment:
                            users_file += f'    Cisco-AVPair := "udn:private-group-id={udn_assignment.udn_id}"\n'
                        
                        # Add SSID name if available
                        if ssid_name:
                            users_file += f'    Reply-Message := "SSID: {ssid_name}"\n'
                        
                        users_file += "\n"
            
            else:
                # Fallback: Query from UDN assignments (if they have PSK info)
                stmt = select(UdnAssignment).where(
                    UdnAssignment.is_active == True,
                    UdnAssignment.ipsk_id.isnot(None)
                ).order_by(UdnAssignment.user_id)
                
                assignments = db.execute(stmt).scalars().all()
                logger.info(f"Found {len(assignments)} UDN assignments with PSK")
                
                for assignment in assignments:
                    if not assignment.ipsk_id:
                        continue
                    
                    # Note: We don't have the passphrase here - it's in portal DB
                    # This is a placeholder - actual implementation should sync passphrase
                    users_file += f"# User ID: {assignment.user_id}"
                    if assignment.user_email:
                        users_file += f", Email: {assignment.user_email}"
                    if assignment.unit:
                        users_file += f", Unit: {assignment.unit}"
                    users_file += "\n"
                    users_file += f"# IPSK ID: {assignment.ipsk_id}\n"
                    users_file += f"# Note: Passphrase must be synced from portal database\n"
                    users_file += f'"{assignment.ipsk_id}" Auth-Type := Accept\n'
                    users_file += f'    Cisco-AVPair := "udn:private-group-id={assignment.udn_id}"\n'
                    users_file += "\n"
        
        except Exception as e:
            logger.error(f"Failed to generate PSK users file: {e}", exc_info=True)
            users_file += f"# ERROR: Failed to generate PSK entries: {e}\n"
        
        # Add generic PSK entry if configured
        # This would come from settings/config
        generic_psk = getattr(self.settings, 'generic_psk_passphrase', None)
        if generic_psk:
            users_file += "# Generic PSK (allows all MAC addresses)\n"
            users_file += f'"generic-psk" Cleartext-Password := "{generic_psk}"\n'
            users_file += "    Auth-Type := Accept\n"
            users_file += '    Reply-Message := "Generic PSK Access"\n'
            users_file += "\n"
        
        # Validate and write safely - prevents invalid configs
        from radius_app.core.config_validator import safe_write_config_file
        output_path = self.config_path / "users-psk"
        safe_write_config_file(output_path, users_file, file_type="users")
        
        logger.info(f"✅ Generated PSK users file: {output_path}")
        return output_path
    
    def generate_mac_bypass_file(self, db: Session) -> Path:
        """Generate MAC bypass configuration file.
        
        Args:
            db: Database session
            
        Returns:
            Path to generated MAC bypass file
        """
        from radius_app.db.models import RadiusMacBypassConfig
        
        stmt = select(RadiusMacBypassConfig).where(
            RadiusMacBypassConfig.is_active == True
        )
        bypass_configs = db.execute(stmt).scalars().all()
        
        bypass_file = "# Auto-generated MAC bypass configuration\n"
        bypass_file += f"# Timestamp: {datetime.now(UTC).isoformat()}\n"
        bypass_file += f"# Total bypass configs: {len(bypass_configs)}\n"
        bypass_file += "# DO NOT EDIT MANUALLY\n\n"
        
        for config in bypass_configs:
            bypass_file += f"# Bypass Config: {config.name}\n"
            if config.description:
                bypass_file += f"# Description: {config.description}\n"
            bypass_file += f"# Mode: {config.bypass_mode}\n"
            
            if config.mac_addresses:
                for mac in config.mac_addresses:
                    bypass_file += f'"{mac}" Auth-Type := Accept\n'
                    bypass_file += f'    Reply-Message := "MAC Bypass: {config.name}"\n'
                    bypass_file += "\n"
        
        # Validate and write safely - prevents invalid configs
        from radius_app.core.config_validator import safe_write_config_file
        output_path = self.config_path / "users-mac-bypass"
        safe_write_config_file(output_path, bypass_file, file_type="users")
        
        logger.info(f"✅ Generated MAC bypass file: {output_path}")
        return output_path
