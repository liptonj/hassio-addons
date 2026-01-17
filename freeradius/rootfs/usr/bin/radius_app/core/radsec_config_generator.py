"""RadSec configuration generator for FreeRADIUS.

Uses Jinja2 templates for clean, maintainable configuration generation.
"""

import logging
from datetime import datetime, UTC
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy import select
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.db.models import RadiusRadSecConfig

logger = logging.getLogger(__name__)


class RadSecConfigGenerator:
    """Generates FreeRADIUS RadSec listener configuration."""
    
    def __init__(self):
        """Initialize RadSec config generator."""
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
        
        logger.info(f"RadSec config generator initialized: {self.config_path}")
    
    def generate_radsec_conf(self, db: Session) -> Path:
        """Generate RadSec listener configuration from database.
        
        Args:
            db: Database session
            
        Returns:
            Path to generated RadSec config file
        """
        # Query active RadSec configurations
        stmt = select(RadiusRadSecConfig).where(
            RadiusRadSecConfig.is_active == True
        ).order_by(RadiusRadSecConfig.created_at.asc())
        
        configs = db.execute(stmt).scalars().all()
        
        # Build template context
        context = {
            "timestamp": datetime.now(UTC).isoformat(),
            "configs": configs,
        }
        
        try:
            template = self.jinja_env.get_template("radsec_listener.j2")
            config_content = template.render(**context)
        except TemplateNotFound:
            logger.error("RadSec template not found - falling back to code generation")
            config_content = self._generate_fallback_radsec_config(configs)
        except Exception as e:
            logger.error(f"Error rendering RadSec template: {e}", exc_info=True)
            config_content = self._generate_fallback_radsec_config(configs)
        
        # Write to file
        output_path = self.config_path / "radsec.conf"
        output_path.write_text(config_content)
        output_path.chmod(0o644)
        
        logger.info(f"✅ Generated radsec.conf with {len(configs)} configurations")
        return output_path
    
    def _generate_fallback_radsec_config(self, configs: list) -> str:
        """Fallback RadSec config generation if template fails.
        
        Args:
            configs: List of RadSec configurations
            
        Returns:
            RadSec configuration as string
        """
        logger.warning("Using fallback code-based RadSec configuration generation")
        
        config = "# RadSec configuration - Generated (fallback mode)\n"
        config += f"# Timestamp: {datetime.now(UTC).isoformat()}\n\n"
        
        if not configs:
            config += "# No active RadSec configurations\n"
            return config
        
        for radsec_config in configs:
            config += f"# RadSec Configuration: {radsec_config.name}\n"
            config += "listen {\n"
            config += "    type = auth+acct\n"
            config += f"    ipaddr = {radsec_config.listen_address}\n"
            config += f"    port = {radsec_config.listen_port}\n"
            config += "    proto = tcp\n\n"
            config += "    tls {\n"
            config += f"        certificate_file = {radsec_config.certificate_file}\n"
            config += f"        private_key_file = {radsec_config.private_key_file}\n"
            config += f"        ca_file = {radsec_config.ca_certificate_file}\n"
            config += f'        tls_min_version = "{radsec_config.tls_min_version}"\n'
            config += f'        tls_max_version = "{radsec_config.tls_max_version}"\n'
            config += "    }\n\n"
            config += f"    max_connections = {radsec_config.max_connections}\n"
            config += "}\n\n"
        
        return config
    
    def generate_radsec_include(self) -> Path:
        """Generate an include file for RadSec in sites-enabled.
        
        This creates a small include file that can be added to the
        FreeRADIUS sites configuration.
        
        Returns:
            Path to generated include file
        """
        include_content = "# Include RadSec listener configuration\n"
        include_content += "# Add this to your FreeRADIUS sites-enabled configuration:\n"
        include_content += "#   $INCLUDE ${confdir}/radsec-includes\n\n"
        include_content += "$INCLUDE ${confdir}/radsec.conf\n"
        
        output_path = self.config_path / "radsec-includes"
        output_path.write_text(include_content)
        output_path.chmod(0o644)
        
        logger.info("✅ Generated RadSec include file")
        return output_path
