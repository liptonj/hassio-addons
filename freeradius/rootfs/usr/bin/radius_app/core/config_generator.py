"""FreeRADIUS configuration file generator from database."""

import logging
import re
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.db.models import RadiusClient, UdnAssignment

logger = logging.getLogger(__name__)

# UDN constants
UDN_VSA_ATTRIBUTE = "Cisco-AVPair"
UDN_VSA_FORMAT = "udn:private-group-id={udn_id}"


class ConfigGenerator:
    """Generates FreeRADIUS configuration files from database."""
    
    def __init__(self):
        """Initialize config generator."""
        self.settings = get_settings()
        self.clients_path = Path(self.settings.radius_clients_path)
        self.config_path = Path(self.settings.radius_config_path)
        
        # Ensure directories exist
        self.clients_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Config generator initialized: {self.clients_path}")
    
    def generate_clients_conf(self, db: Session) -> Path:
        """Generate clients.conf from database.
        
        Args:
            db: Database session
            
        Returns:
            Path to generated clients.conf file
        """
        # Query active RADIUS clients
        stmt = select(RadiusClient).where(RadiusClient.is_active == True)  # noqa: E712
        clients = db.execute(stmt).scalars().all()
        
        # Generate config file content
        config = "# Auto-generated RADIUS clients configuration\n"
        config += "# Generated from shared database\n"
        config += f"# Timestamp: {datetime.now(UTC).isoformat()}\n"
        config += f"# Total clients: {len(clients)}\n"
        config += "# DO NOT EDIT MANUALLY - Changes will be overwritten\n\n"
        
        for client in clients:
            config += f"# Client: {client.name}\n"
            if client.network_name:
                config += f"# Network: {client.network_name} ({client.network_id})\n"
            
            # Use shortname or name as identifier, sanitized for FreeRADIUS config
            raw_identifier = client.shortname or client.name
            # Replace spaces and special chars with underscores
            identifier = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_identifier).lower()
            
            config += f"client {identifier} {{\n"
            config += f"    ipaddr = {client.ipaddr}\n"
            config += f'    secret = "{client.secret}"\n'
            config += f"    nas_type = {client.nas_type}\n"
            
            if client.shortname:
                # Sanitize shortname for FreeRADIUS config
                safe_shortname = re.sub(r'[^a-zA-Z0-9_-]', '_', client.shortname)
                config += f"    shortname = {safe_shortname}\n"
            
            if client.require_message_authenticator:
                config += "    require_message_authenticator = yes\n"
            
            config += "}\n\n"
        
        # Validate and write safely - prevents invalid configs
        from radius_app.core.config_validator import safe_write_config_file
        output_path = self.clients_path / "clients.conf"
        safe_write_config_file(output_path, config, file_type="clients")
        
        logger.info(f"✅ Generated clients.conf with {len(clients)} clients")
        return output_path
    
    def generate_users_file(self, db: Session) -> Path:
        """Generate users file from UDN assignments.
        
        Args:
            db: Database session
            
        Returns:
            Path to generated users file
        """
        # Query active UDN assignments
        stmt = select(UdnAssignment).where(UdnAssignment.is_active == True).order_by(UdnAssignment.udn_id)  # noqa: E712
        assignments = db.execute(stmt).scalars().all()
        
        # Generate users file content
        users_file = "# Auto-generated RADIUS users for WPN UDN assignment\n"
        users_file += "# Generated from shared database\n"
        users_file += f"# Timestamp: {datetime.now(UTC).isoformat()}\n"
        users_file += f"# Total assignments: {len(assignments)}\n"
        users_file += "# DO NOT EDIT MANUALLY - Changes will be overwritten\n\n"
        
        for assignment in assignments:
            # User comment
            user_info = f"User ID: {assignment.user_id}"
            if assignment.user_name:
                user_info += f" - {assignment.user_name}"
            if assignment.unit:
                user_info += f" - Unit {assignment.unit}"
            users_file += f"# {user_info}\n"
            
            # UDN assignment entry
            # Note: UDN is assigned to USER, not MAC. MAC is optional.
            # For PSK authentication, the user will authenticate with PSK and UDN will be looked up via USER->PSK
            # For MAC-based auth (if MAC provided), include MAC entry
            cisco_avpair = UDN_VSA_FORMAT.format(udn_id=assignment.udn_id)
            reply_message = f"WPN Access - User {assignment.user_id}"
            if assignment.user_name:
                reply_message += f" - {assignment.user_name}"
            if assignment.unit:
                reply_message += f" - Unit {assignment.unit}"
            
            if assignment.mac_address:
                # MAC-based authentication entry (if MAC provided)
                users_file += f'{assignment.mac_address} Cleartext-Password := ""\n'
                users_file += f'    {UDN_VSA_ATTRIBUTE} := "{cisco_avpair}",\n'
                users_file += f'    Reply-Message := "{reply_message}"\n\n'
            else:
                # User-based entry (no MAC) - PSK authentication will handle UDN lookup
                # This is a placeholder - actual PSK entries are generated by PSK config generator
                users_file += f'# User {assignment.user_id} - UDN {assignment.udn_id} (PSK authentication)\n'
                users_file += f'# PSK entries are generated separately by PSK config generator\n\n'
        
        # Add default deny at the end
        users_file += "# Default deny for non-registered MACs\n"
        users_file += "DEFAULT Auth-Type := Reject\n"
        users_file += '    Reply-Message := "Access denied - Device not registered"\n'
        
        # Validate and write safely - prevents invalid configs
        from radius_app.core.config_validator import safe_write_config_file
        output_path = self.config_path / "users"
        safe_write_config_file(output_path, users_file, file_type="users")
        
        logger.info(f"✅ Generated users file with {len(assignments)} assignments")
        return output_path
    
    
    def generate_all(self, db: Session) -> dict[str, Path]:
        """Generate all configuration files including PSK and MAC bypass.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary mapping config type to file path
        """
        from radius_app.core.psk_config_generator import PskConfigGenerator
        from radius_app.core.policy_generator import PolicyGenerator
        
        configs = {
            "clients": self.generate_clients_conf(db),
            "users": self.generate_users_file(db),
        }
        
        # Generate and enable SQL module (if database configured)
        # Note: SQL module configs are FreeRADIUS module configs validated at load time
        from radius_app.core.sql_config_generator import SqlConfigGenerator
        sql_generator = SqlConfigGenerator()
        configs["sql-module"] = sql_generator.write_sql_module_config(db)
        
        # Check if SQL module is enabled (PSK should use SQL, not static files)
        sql_module_enabled = (Path(self.settings.radius_config_path) / "mods-enabled" / "sql").exists()
        
        psk_generator = PskConfigGenerator()
        
        if not sql_module_enabled:
            # Only generate PSK file if SQL module not enabled (fallback mode)
            logger.info("SQL module not enabled - generating PSK users file (fallback)")
            configs["users-psk"] = psk_generator.generate_psk_users_file(db)
        else:
            logger.info("SQL module enabled - skipping PSK file generation (using radcheck/radreply for dynamic PSK)")
            # PSK authentication will use SQL module via radcheck/radreply tables
            # Use sync_psk_to_radcheck() to populate radcheck/radreply tables
        
        # Generate MAC bypass file (validation enforced - exceptions propagate)
        # Note: MAC bypass is separate from PSK and still uses static files
        configs["users-mac-bypass"] = psk_generator.generate_mac_bypass_file(db)
        
        # Generate and enable SQL Counter module (if SQL module enabled)
        from radius_app.core.sql_counter_generator import SqlCounterGenerator
        sql_counter_generator = SqlCounterGenerator()
        configs["sqlcounter-module"] = sql_counter_generator.write_sql_counter_config(db)
        
        # Generate policies (validation enforced - exceptions propagate)
        policy_generator = PolicyGenerator()
        configs["policies"] = policy_generator.generate_policy_file(db)
        
        # Generate and enable default virtual server (with SQL if configured)
        # Note: Virtual server configs are FreeRADIUS site configs validated at load time
        from radius_app.core.virtual_server_generator import VirtualServerGenerator
        virtual_server_generator = VirtualServerGenerator()
        # Check if SQL module is enabled (if sql-module config exists)
        use_sql = "sql-module" in configs
        configs["virtual-server-default"] = virtual_server_generator.write_default_server(db, use_sql=use_sql)
        
        return configs