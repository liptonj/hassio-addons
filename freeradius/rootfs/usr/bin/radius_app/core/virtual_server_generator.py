"""Virtual server configuration generator for FreeRADIUS.

Generates virtual server configurations that integrate SQL module
for dynamic PSK lookups per FreeRADIUS SQL documentation.

Uses Jinja2 templates for clean, maintainable configuration generation.
Supports both FreeRADIUS v3 and v4 syntax via conditional templating.
"""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.db.models import RadiusRadSecConfig

logger = logging.getLogger(__name__)

# Default to v3 syntax (Alpine currently packages v3.x)
DEFAULT_FREERADIUS_VERSION = 3


class VirtualServerGenerator:
    """Generate FreeRADIUS virtual server configurations using Jinja2 templates."""
    
    def __init__(self):
        """Initialize virtual server generator."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.radius_config_path)
        self.sites_available = self.config_path / "sites-available"
        self.sites_enabled = self.config_path / "sites-enabled"
        
        # Ensure directories exist
        self.sites_available.mkdir(parents=True, exist_ok=True)
        self.sites_enabled.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        logger.info(f"Virtual server generator initialized: {self.config_path}")
    
    def _check_eap_enabled(self) -> bool:
        """Check if EAP module is enabled.
        
        Returns:
            True if EAP module is enabled and valid, False otherwise
        """
        eap_symlink = self.config_path / "mods-enabled" / "eap"
        eap_enabled = False
        
        if eap_symlink.exists():
            try:
                # If it's a symlink, resolve it and check if target exists
                if eap_symlink.is_symlink():
                    target = eap_symlink.resolve()
                    eap_enabled = target.exists() and target.is_file()
                # If it's a regular file, it's enabled
                elif eap_symlink.is_file():
                    eap_enabled = True
            except (OSError, RuntimeError):
                # Symlink is broken or can't be resolved
                eap_enabled = False
        
        return eap_enabled
    
    def generate_default_server_with_sql(
        self, 
        db: Session, 
        use_sql: bool = True,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION
    ) -> str:
        """Generate default virtual server with optional SQL module integration.
        
        Per FreeRADIUS SQL documentation:
        - SQL module can be used in authorize section for user lookups
        - SQL module queries radcheck/radreply tables at runtime
        - Can be combined with files module (files checked first, then SQL)
        
        Args:
            db: Database session (unused but kept for API compatibility)
            use_sql: Whether to include SQL module in authorize section
            freeradius_version: FreeRADIUS version (3 or 4) for syntax selection
            
        Returns:
            Virtual server configuration as string
        """
        # Check if EAP module is enabled
        eap_enabled = self._check_eap_enabled()
        logger.info(f"Generating default server configuration (SQL: {use_sql}, EAP: {eap_enabled}, v{freeradius_version})")
        
        try:
            # Load and render template
            template = self.jinja_env.get_template("virtual_server_default.j2")
            config_content = template.render(
                use_sql=use_sql,
                eap_enabled=eap_enabled,
                freeradius_version=freeradius_version
            )
            return config_content
        except TemplateNotFound:
            logger.error("Virtual server template not found - falling back to code generation")
            # Fallback to code-based generation if template missing
            return self._generate_fallback_config(use_sql, eap_enabled)
        except Exception as e:
            logger.error(f"Error rendering virtual server template: {e}", exc_info=True)
            # Fallback to code-based generation on error
            return self._generate_fallback_config(use_sql, eap_enabled)
    
    def _generate_fallback_config(self, use_sql: bool, eap_enabled: bool) -> str:
        """Fallback configuration generation if template fails.
        
        This method provides a backup if Jinja2 template is unavailable.
        
        Args:
            use_sql: Whether to include SQL module
            eap_enabled: Whether EAP module is enabled
            
        Returns:
            Virtual server configuration as string
        """
        logger.warning("Using fallback code-based configuration generation")
        
        config_lines = [
            "# Default virtual server for RADIUS authentication and accounting",
            "# Generated from database (fallback mode)",
            "#",
            "server default {",
            "",
            "    listen {",
            "        type = auth",
            "        ipaddr = *",
            "        port = 1812",
            "    }",
            "",
            "    listen {",
            "        type = acct",
            "        ipaddr = *",
            "        port = 1813",
            "    }",
            "",
            "    authorize {",
            "        filter_username",
            "        preprocess",
            "        files",
        ]
        
        if use_sql:
            config_lines.extend([
                "        sql {",
                "            ok = return",
                "            notfound = noop",
                "            noop = noop",
                "        }",
            ])
        
        if eap_enabled:
            config_lines.extend([
                "        eap {",
                "            ok = return",
                "        }",
            ])
        
        config_lines.extend([
            "        pap",
            "    }",
            "",
            "    authenticate {",
            "        Auth-Type PAP {",
            "            pap",
            "        }",
        ])
        
        if eap_enabled:
            config_lines.extend([
                "        Auth-Type eap {",
                "            eap",
                "        }",
            ])
        
        # Add CHAP and MS-CHAP authentication types
        config_lines.extend([
            "        Auth-Type CHAP {",
            "            chap",
            "        }",
            "        Auth-Type MS-CHAP {",
            "            mschap",
            "        }",
        ])
        
        # Note: SQL module is NOT used in authenticate section
        # SQL only retrieves credentials; PAP/CHAP/MS-CHAP handle authentication
        
        config_lines.extend([
            "    }",
            "",
            "    post-auth {",
        ])
        
        if use_sql:
            config_lines.append("        sql")
        
        config_lines.extend([
            "        detail",
            "    }",
            "",
            "    accounting {",
        ])
        
        if use_sql:
            config_lines.append("        sql")
        
        config_lines.extend([
            "        detail",
            "        unix",
            "    }",
            "",
            "    session {",
            "    }",
            "",
            "    pre-proxy {",
            "    }",
            "",
            "    post-proxy {",
        ])
        
        if eap_enabled:
            config_lines.append("        eap")
        
        config_lines.extend([
            "    }",
            "}",
        ])
        
        return "\n".join(config_lines)
    
    def write_default_server(self, db: Session, use_sql: bool = True) -> Path:
        """Write default virtual server config and enable it.
        
        Args:
            db: Database session
            use_sql: Whether to include SQL module
            
        Returns:
            Path to the enabled virtual server config
        """
        logger.info("Writing default virtual server configuration")
        
        # Generate config
        config_content = self.generate_default_server_with_sql(db, use_sql)
        
        # Always overwrite existing file (may have been copied from template with EAP references)
        default_file = self.sites_available / "default"
        if default_file.exists():
            logger.debug(f"Overwriting existing virtual server config: {default_file}")
        default_file.write_text(config_content)
        default_file.chmod(0o644)
        logger.info(f"✅ Wrote virtual server config: {default_file}")
        
        # Enable by creating symlink in sites-enabled
        enabled_link = self.sites_enabled / "default"
        if enabled_link.exists():
            if enabled_link.is_symlink():
                enabled_link.unlink()
            else:
                logger.warning(f"Removing existing non-symlink file: {enabled_link}")
                enabled_link.unlink()
        
        # Create symlink
        enabled_link.symlink_to("../sites-available/default")
        logger.info(f"✅ Enabled virtual server: {enabled_link}")
        
        return enabled_link
    
    def _check_sql_enabled(self) -> bool:
        """Check if SQL module is enabled.
        
        Returns:
            True if SQL module is enabled, False otherwise
        """
        sql_symlink = self.config_path / "mods-enabled" / "sql"
        return sql_symlink.exists()
    
    def generate_radsec_server(
        self,
        db: Session,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
        **config_overrides: Any
    ) -> str:
        """Generate RadSec virtual server for RADIUS over TLS.
        
        Per FreeRADIUS documentation:
        - RadSec uses TLS for secure RADIUS communication
        - Typically used for Meraki Dashboard or cloud services
        - Authentication logic mirrors the default server
        
        Args:
            db: Database session for fetching RadSec configuration
            freeradius_version: FreeRADIUS version (3 or 4) for syntax selection
            **config_overrides: Override default configuration values
            
        Returns:
            RadSec virtual server configuration as string
        """
        # Check module availability
        use_sql = self._check_sql_enabled()
        eap_enabled = self._check_eap_enabled()
        
        # Get RadSec config from database if available
        radsec_config = db.query(RadiusRadSecConfig).filter_by(is_active=True).first()
        
        # Build template context
        context = {
            "use_sql": use_sql,
            "eap_enabled": eap_enabled,
            "freeradius_version": freeradius_version,
            "listen_address": "*",
            "listen_port": 2083,
            "max_connections": 16,
            "connection_timeout": 0,
            "idle_timeout": 30,
            "require_client_cert": False,
            "verify_client_cert": False,
            "tls_min_version": "1.2",
            "tls_max_version": "1.3",
            "cipher_list": "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!MD5:!PSK:!RC4",
        }
        
        # Override with database config if available
        if radsec_config:
            context.update({
                "listen_address": radsec_config.listen_address or "*",
                "listen_port": radsec_config.listen_port or 2083,
                "certificate_file": radsec_config.certificate_file,
                "private_key_file": radsec_config.private_key_file,
                "ca_file": radsec_config.ca_certificate_file,
                "require_client_cert": radsec_config.require_client_cert,
                "verify_client_cert": radsec_config.verify_client_cert,
                "tls_min_version": radsec_config.tls_min_version,
                "tls_max_version": radsec_config.tls_max_version,
                "cipher_list": radsec_config.cipher_list,
                "max_connections": radsec_config.max_connections,
            })
        
        # Apply any additional overrides
        context.update(config_overrides)
        
        logger.info(f"Generating RadSec server configuration (SQL: {use_sql}, EAP: {eap_enabled}, v{freeradius_version})")
        
        try:
            template = self.jinja_env.get_template("radsec_virtual_server.j2")
            return template.render(**context)
        except TemplateNotFound:
            logger.error("RadSec virtual server template not found")
            raise
        except Exception as e:
            logger.error(f"Error rendering RadSec virtual server template: {e}", exc_info=True)
            raise
    
    def write_radsec_server(self, db: Session, freeradius_version: int = DEFAULT_FREERADIUS_VERSION) -> Path:
        """Write RadSec virtual server config and enable it.
        
        Args:
            db: Database session
            freeradius_version: FreeRADIUS version (3 or 4)
            
        Returns:
            Path to the enabled virtual server config
        """
        logger.info("Writing RadSec virtual server configuration")
        
        config_content = self.generate_radsec_server(db, freeradius_version)
        
        radsec_file = self.sites_available / "radsec"
        radsec_file.write_text(config_content)
        radsec_file.chmod(0o644)
        logger.info(f"✅ Wrote RadSec virtual server config: {radsec_file}")
        
        # Enable by creating symlink
        enabled_link = self.sites_enabled / "radsec"
        if enabled_link.exists():
            enabled_link.unlink()
        enabled_link.symlink_to("../sites-available/radsec")
        logger.info(f"✅ Enabled RadSec virtual server: {enabled_link}")
        
        return enabled_link
    
    def generate_status_server(
        self,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
        **config_overrides: Any
    ) -> str:
        """Generate Status virtual server for monitoring.
        
        Per FreeRADIUS documentation:
        - Status-Server allows monitoring tools to check if RADIUS is alive
        - Responds to Status-Server requests with Access-Accept
        - Should be restricted to trusted networks/clients
        
        Args:
            freeradius_version: FreeRADIUS version (3 or 4) for syntax selection
            **config_overrides: Override default configuration values
            
        Returns:
            Status virtual server configuration as string
        """
        # Build template context with defaults
        context = {
            "freeradius_version": freeradius_version,
            "listen_address": "127.0.0.1",  # Localhost only by default for security
            "listen_port": 18121,
            "max_connections": 16,
            "include_stats": False,
            "status_clients": [],
        }
        
        # Apply any overrides
        context.update(config_overrides)
        
        logger.info(f"Generating Status server configuration (v{freeradius_version})")
        
        try:
            template = self.jinja_env.get_template("status_server.j2")
            return template.render(**context)
        except TemplateNotFound:
            logger.error("Status virtual server template not found")
            raise
        except Exception as e:
            logger.error(f"Error rendering Status virtual server template: {e}", exc_info=True)
            raise
    
    def write_status_server(
        self, 
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
        enable: bool = False
    ) -> Path:
        """Write Status virtual server config.
        
        Note: Status server is NOT enabled by default for security.
        Enable only if you need monitoring from trusted networks.
        
        Args:
            freeradius_version: FreeRADIUS version (3 or 4)
            enable: Whether to enable the status server (default: False)
            
        Returns:
            Path to the virtual server config file
        """
        logger.info("Writing Status virtual server configuration")
        
        config_content = self.generate_status_server(freeradius_version)
        
        status_file = self.sites_available / "status"
        status_file.write_text(config_content)
        status_file.chmod(0o644)
        logger.info(f"✅ Wrote Status virtual server config: {status_file}")
        
        if enable:
            # Enable by creating symlink
            enabled_link = self.sites_enabled / "status"
            if enabled_link.exists():
                enabled_link.unlink()
            enabled_link.symlink_to("../sites-available/status")
            logger.info(f"✅ Enabled Status virtual server: {enabled_link}")
            return enabled_link
        else:
            logger.info("⚠️ Status server NOT enabled (use enable=True if needed)")
            return status_file
    
    def enable_virtual_server(self, server_name: str) -> bool:
        """Enable a virtual server by creating symlink.
        
        Args:
            server_name: Name of the virtual server to enable
            
        Returns:
            True if enabled successfully, False otherwise
        """
        available_file = self.sites_available / server_name
        if not available_file.exists():
            logger.error(f"Virtual server '{server_name}' not found in sites-available")
            return False
        
        enabled_link = self.sites_enabled / server_name
        if enabled_link.exists():
            enabled_link.unlink()
        
        enabled_link.symlink_to(f"../sites-available/{server_name}")
        logger.info(f"✅ Enabled virtual server: {server_name}")
        return True
    
    def disable_virtual_server(self, server_name: str) -> bool:
        """Disable a virtual server by removing symlink.
        
        Args:
            server_name: Name of the virtual server to disable
            
        Returns:
            True if disabled successfully, False otherwise
        """
        enabled_link = self.sites_enabled / server_name
        if not enabled_link.exists():
            logger.warning(f"Virtual server '{server_name}' already disabled")
            return True
        
        enabled_link.unlink()
        logger.info(f"✅ Disabled virtual server: {server_name}")
        return True
    
    def write_all_virtual_servers(
        self,
        db: Session,
        freeradius_version: int = DEFAULT_FREERADIUS_VERSION,
        enable_status: bool = False
    ) -> dict[str, Path]:
        """Write all virtual server configurations.
        
        Args:
            db: Database session
            freeradius_version: FreeRADIUS version (3 or 4)
            enable_status: Whether to enable the status server
            
        Returns:
            Dictionary of server name -> path
        """
        results = {}
        
        # Check if SQL is enabled
        use_sql = self._check_sql_enabled()
        
        # Write default server
        results["default"] = self.write_default_server(db, use_sql=use_sql)
        
        # Write RadSec server (if RadSec config exists)
        radsec_config = db.query(RadiusRadSecConfig).filter_by(is_active=True).first()
        if radsec_config:
            results["radsec"] = self.write_radsec_server(db, freeradius_version)
        else:
            logger.info("⚠️ No active RadSec configuration - skipping RadSec virtual server")
        
        # Write status server (not enabled by default)
        results["status"] = self.write_status_server(freeradius_version, enable=enable_status)
        
        logger.info(f"✅ Wrote {len(results)} virtual server configurations")
        return results