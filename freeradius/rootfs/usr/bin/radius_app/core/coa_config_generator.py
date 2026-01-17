"""CoA (Change of Authorization) configuration generator for FreeRADIUS.

Uses Jinja2 templates for clean, maintainable configuration generation.
Supports CoA-Request and Disconnect-Request handling per RFC 5176.
"""

import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.db.models import RadiusClient, RadiusClientExtended

logger = logging.getLogger(__name__)


class CoAConfigGenerator:
    """Generates FreeRADIUS CoA/DM server configuration."""
    
    def __init__(self):
        """Initialize CoA config generator."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.radius_config_path)
        
        # Ensure directory exists
        self.config_path.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        logger.info(f"CoA config generator initialized: {self.config_path}")
    
    def get_coa_enabled_nads(self, db: Session) -> list[dict]:
        """Get list of NADs with CoA enabled.
        
        Args:
            db: Database session
            
        Returns:
            List of NAD configurations with CoA enabled
        """
        # Query NADs with CoA enabled
        stmt = select(
            RadiusClient, RadiusClientExtended
        ).outerjoin(
            RadiusClientExtended,
            RadiusClient.id == RadiusClientExtended.radius_client_id
        ).where(
            RadiusClient.is_active == True
        )
        
        results = db.execute(stmt).all()
        
        nads_with_coa = []
        for client, extended in results:
            if extended and extended.coa_enabled:
                nads_with_coa.append({
                    "id": client.id,
                    "name": client.name,
                    "ipaddr": client.ipaddr,
                    "secret": client.secret,
                    "coa_enabled": extended.coa_enabled,
                    "coa_port": extended.coa_port or 3799,
                    "vendor": extended.vendor,
                    "model": extended.model,
                })
        
        return nads_with_coa
    
    def generate_coa_conf(
        self,
        db: Session,
        listen_address: str = "*",
        coa_port: int = 3799,
        validate_nas_source: bool = True,
        sql_session_check: bool = False,
        log_coa_to_detail: bool = True,
        max_connections: int = 16,
    ) -> Path:
        """Generate CoA server configuration from database.
        
        Args:
            db: Database session
            listen_address: IP address to listen on
            coa_port: Port for CoA/DM (default 3799)
            validate_nas_source: Verify requests from known NADs
            sql_session_check: Check sessions in SQL database
            log_coa_to_detail: Log CoA events to detail file
            max_connections: Maximum concurrent connections
            
        Returns:
            Path to generated CoA config file
        """
        # Get NADs with CoA enabled
        nads_with_coa = self.get_coa_enabled_nads(db)
        
        # Build template context
        context = {
            "timestamp": datetime.now(UTC).isoformat(),
            "listen_address": listen_address,
            "coa_port": coa_port,
            "validate_nas_source": validate_nas_source,
            "sql_session_check": sql_session_check,
            "log_coa_to_detail": log_coa_to_detail,
            "max_connections": max_connections,
            "nads_with_coa": nads_with_coa,
        }
        
        try:
            template = self.jinja_env.get_template("coa_server.j2")
            config_content = template.render(**context)
        except TemplateNotFound:
            logger.error("CoA template not found - falling back to code generation")
            config_content = self._generate_fallback_coa_config(context)
        except Exception as e:
            logger.error(f"Error rendering CoA template: {e}", exc_info=True)
            config_content = self._generate_fallback_coa_config(context)
        
        # Write to file
        output_path = self.config_path / "sites-available" / "coa-dynamic"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(config_content)
        output_path.chmod(0o644)
        
        # Create symlink in sites-enabled
        enabled_path = self.config_path / "sites-enabled" / "coa-dynamic"
        enabled_path.parent.mkdir(parents=True, exist_ok=True)
        if not enabled_path.exists():
            try:
                enabled_path.symlink_to(output_path)
                logger.info("✅ Created symlink for coa-dynamic in sites-enabled")
            except OSError as e:
                logger.warning(f"Could not create symlink: {e}")
        
        logger.info(
            f"✅ Generated coa-dynamic with {len(nads_with_coa)} CoA-enabled NADs"
        )
        return output_path
    
    def _generate_fallback_coa_config(self, context: dict) -> str:
        """Fallback CoA config generation if template fails.
        
        Args:
            context: Configuration context dictionary
            
        Returns:
            CoA configuration as string
        """
        logger.warning("Using fallback code-based CoA configuration generation")
        
        config = "# CoA/DM configuration - Generated (fallback mode)\n"
        config += f"# Timestamp: {context['timestamp']}\n\n"
        
        config += "server coa-dynamic {\n"
        config += "    listen {\n"
        config += "        type = coa\n"
        config += f"        ipaddr = {context['listen_address']}\n"
        config += f"        port = {context['coa_port']}\n"
        config += "    }\n\n"
        
        config += "    recv CoA-Request {\n"
        config += "        ok\n"
        config += "    }\n\n"
        
        config += "    send CoA-ACK {\n"
        config += "        ok\n"
        config += "    }\n\n"
        
        config += "    send CoA-NAK {\n"
        config += "        ok\n"
        config += "    }\n\n"
        
        config += "    recv Disconnect-Request {\n"
        config += "        ok\n"
        config += "    }\n\n"
        
        config += "    send Disconnect-ACK {\n"
        config += "        ok\n"
        config += "    }\n\n"
        
        config += "    send Disconnect-NAK {\n"
        config += "        ok\n"
        config += "    }\n"
        
        config += "}\n"
        
        return config


class CoAClient:
    """Client for sending CoA/DM requests to NADs.
    
    Used to disconnect users or change session parameters on NADs.
    """
    
    def __init__(self):
        """Initialize CoA client."""
        self.settings = get_settings()
        logger.info("CoA client initialized")
    
    async def send_disconnect_request(
        self,
        nad_ip: str,
        nad_port: int,
        shared_secret: str,
        user_name: Optional[str] = None,
        session_id: Optional[str] = None,
        nas_port: Optional[int] = None,
        calling_station_id: Optional[str] = None,
    ) -> dict:
        """Send Disconnect-Request to a NAD.
        
        Args:
            nad_ip: IP address of the NAD
            nad_port: CoA port on the NAD (typically 3799)
            shared_secret: Shared secret for authentication
            user_name: User to disconnect
            session_id: Session ID to disconnect
            nas_port: NAS port of the session
            calling_station_id: MAC address of client
            
        Returns:
            Response dictionary with success status and details
        """
        import subprocess
        
        if not user_name and not session_id and not calling_station_id:
            return {
                "success": False,
                "error": "Must provide user_name, session_id, or calling_station_id"
            }
        
        # Build radclient command
        cmd = [
            "radclient",
            "-t", "3",  # 3 second timeout
            "-r", "3",  # 3 retries
            "-x",       # Debug output
            f"{nad_ip}:{nad_port}",
            "disconnect",
            shared_secret,
        ]
        
        # Build attributes
        attrs = []
        if user_name:
            attrs.append(f"User-Name = \"{user_name}\"")
        if session_id:
            attrs.append(f"Acct-Session-Id = \"{session_id}\"")
        if nas_port:
            attrs.append(f"NAS-Port = {nas_port}")
        if calling_station_id:
            attrs.append(f"Calling-Station-Id = \"{calling_station_id}\"")
        
        # Add NAS-Identifier
        attrs.append(f"NAS-Identifier = \"{self.settings.server_name if hasattr(self.settings, 'server_name') else 'freeradius'}\"")
        
        attrs_input = "\n".join(attrs)
        
        try:
            result = subprocess.run(
                cmd,
                input=attrs_input,
                capture_output=True,
                text=True,
                timeout=15,
            )
            
            success = result.returncode == 0 and "Received Disconnect-ACK" in result.stdout
            
            return {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "nad_ip": nad_ip,
                "nad_port": nad_port,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout waiting for NAD response",
                "nad_ip": nad_ip,
                "nad_port": nad_port,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "nad_ip": nad_ip,
                "nad_port": nad_port,
            }
    
    async def send_coa_request(
        self,
        nad_ip: str,
        nad_port: int,
        shared_secret: str,
        user_name: Optional[str] = None,
        session_id: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> dict:
        """Send CoA-Request to change session parameters.
        
        Args:
            nad_ip: IP address of the NAD
            nad_port: CoA port on the NAD
            shared_secret: Shared secret for authentication
            user_name: User to modify
            session_id: Session ID to modify
            attributes: Dictionary of attributes to change
            
        Returns:
            Response dictionary with success status and details
        """
        import subprocess
        
        if not user_name and not session_id:
            return {
                "success": False,
                "error": "Must provide user_name or session_id"
            }
        
        # Build radclient command
        cmd = [
            "radclient",
            "-t", "3",
            "-r", "3",
            "-x",
            f"{nad_ip}:{nad_port}",
            "coa",
            shared_secret,
        ]
        
        # Build attributes
        attrs = []
        if user_name:
            attrs.append(f"User-Name = \"{user_name}\"")
        if session_id:
            attrs.append(f"Acct-Session-Id = \"{session_id}\"")
        
        # Add custom attributes
        if attributes:
            for attr_name, attr_value in attributes.items():
                if isinstance(attr_value, str):
                    attrs.append(f"{attr_name} = \"{attr_value}\"")
                else:
                    attrs.append(f"{attr_name} = {attr_value}")
        
        attrs_input = "\n".join(attrs)
        
        try:
            result = subprocess.run(
                cmd,
                input=attrs_input,
                capture_output=True,
                text=True,
                timeout=15,
            )
            
            success = result.returncode == 0 and "Received CoA-ACK" in result.stdout
            
            return {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "nad_ip": nad_ip,
                "nad_port": nad_port,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout waiting for NAD response",
                "nad_ip": nad_ip,
                "nad_port": nad_port,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "nad_ip": nad_ip,
                "nad_port": nad_port,
            }
