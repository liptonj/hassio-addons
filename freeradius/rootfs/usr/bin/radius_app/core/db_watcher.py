"""Database watcher for automatic config regeneration."""

import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.core.config_generator import ConfigGenerator
from radius_app.core.policy_generator import PolicyGenerator
from radius_app.core.radsec_config_generator import RadSecConfigGenerator
from radius_app.db.database import get_db
from radius_app.db.models import RadiusClient, UdnAssignment, RadiusPolicy, RadiusRadSecConfig

logger = logging.getLogger(__name__)


class DatabaseWatcher:
    """Watches database for changes and regenerates configuration."""
    
    def __init__(self, poll_interval: int = 5):
        """Initialize database watcher.
        
        Args:
            poll_interval: How often to check for changes (seconds)
        """
        self.poll_interval = poll_interval
        self.config_generator = ConfigGenerator()
        self.policy_generator = PolicyGenerator()
        self.radsec_generator = RadSecConfigGenerator()
        self.last_clients_update: datetime | None = None
        self.last_assignments_update: datetime | None = None
        self.last_policies_update: datetime | None = None
        self.last_radsec_update: datetime | None = None
        self.last_mac_bypass_update: datetime | None = None
        self.running = False
        self._initialized = False  # Track if we've done initial sync
        logger.info(f"Database watcher initialized (poll interval: {poll_interval}s)")
    
    def _initialize_timestamps(self, db: Session) -> None:
        """Initialize timestamps from database without regenerating.
        
        Called on first poll to establish baseline state.
        """
        self.last_clients_update = self._get_last_update_timestamp(db, RadiusClient)
        self.last_assignments_update = self._get_last_update_timestamp(db, UdnAssignment)
        self.last_policies_update = self._get_last_update_timestamp(db, RadiusPolicy)
        self.last_radsec_update = self._get_last_update_timestamp(db, RadiusRadSecConfig)
        
        from radius_app.db.models import RadiusMacBypassConfig
        self.last_mac_bypass_update = self._get_last_update_timestamp(db, RadiusMacBypassConfig)
        
        self._initialized = True
        logger.info("📊 Database watcher initialized timestamps (no regeneration needed)")
    
    def _get_last_update_timestamp(self, db: Session, table_class) -> datetime | None:
        """Get the most recent update timestamp from a table.
        
        Args:
            db: Database session
            table_class: SQLAlchemy model class
            
        Returns:
            Most recent updated_at timestamp or None
        """
        try:
            stmt = select(func.max(table_class.updated_at))
            result = db.execute(stmt).scalar()
            return result
        except Exception as e:
            logger.error(f"Failed to get last update timestamp: {e}")
            return None
    
    def _reload_radiusd(self) -> bool:
        """Reload FreeRADIUS daemon to apply configuration changes.
        
        Returns:
            True if reload successful
        """
        try:
            # Send HUP signal to radiusd to reload config
            result = subprocess.run(
                ["killall", "-HUP", "radiusd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("✅ FreeRADIUS daemon reloaded successfully")
                return True
            else:
                logger.warning(f"Failed to reload radiusd: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Timeout while reloading radiusd")
            return False
        except Exception as e:
            logger.error(f"Error reloading radiusd: {e}")
            return False
    
    def _validate_all_configs(self) -> bool:
        """Validate all generated configuration files before reloading.
        
        Returns:
            True if all configs are valid, False otherwise
        """
        from radius_app.core.config_validator import get_validator
        from radius_app.config import get_settings
        
        validator = get_validator()
        settings = get_settings()
        config_path = Path(settings.radius_config_path)
        clients_path = Path(settings.radius_clients_path)
        
        validation_errors = []
        
        # Validate clients.conf if it exists
        clients_file = clients_path / "clients.conf"
        if clients_file.exists():
            try:
                validator.validate_clients_conf(clients_file.read_text(), config_path)
                logger.debug("✅ clients.conf validated")
            except Exception as e:
                validation_errors.append(f"clients.conf: {e}")
        
        # Validate users file if it exists
        users_file = config_path / "users"
        if users_file.exists():
            try:
                validator.validate_users_file(users_file.read_text(), config_path)
                logger.debug("✅ users file validated")
            except Exception as e:
                validation_errors.append(f"users: {e}")
        
        # Validate policy file if it exists
        policy_file = config_path / "policies"
        if policy_file.exists():
            try:
                validator.validate_policy_file(policy_file.read_text(), config_path)
                logger.debug("✅ policies file validated")
            except Exception as e:
                validation_errors.append(f"policies: {e}")
        
        # Validate MAC bypass file if it exists
        mac_bypass_file = config_path / "users-mac-bypass"
        if mac_bypass_file.exists():
            try:
                validator.validate_users_file(mac_bypass_file.read_text(), config_path)
                logger.debug("✅ MAC bypass file validated")
            except Exception as e:
                validation_errors.append(f"users-mac-bypass: {e}")
        
        # Validate PSK users file if it exists
        psk_users_file = config_path / "users-psk"
        if psk_users_file.exists():
            try:
                validator.validate_users_file(psk_users_file.read_text(), config_path)
                logger.debug("✅ PSK users file validated")
            except Exception as e:
                validation_errors.append(f"users-psk: {e}")
        
        if validation_errors:
            logger.error("❌ Configuration validation errors:")
            for error in validation_errors:
                logger.error(f"  - {error}")
            return False
        
        logger.info("✅ All configuration files validated successfully")
        return True
    
    async def check_and_regenerate(self, force: bool = False) -> dict[str, bool]:
        """Check for database changes and regenerate config if needed.
        
        Args:
            force: Force regeneration regardless of timestamps
            
        Returns:
            Dictionary with regeneration status
        """
        result = {
            "clients_regenerated": False,
            "users_regenerated": False,
            "policies_regenerated": False,
            "radsec_regenerated": False,
            "reloaded": False,
        }
        
        # Get database session using context manager pattern
        db_generator = get_db()
        db = next(db_generator)
        
        try:
            # On first run, check if config files already exist
            # If they do, just initialize timestamps without regenerating
            settings = get_settings()
            config_path = Path(settings.radius_config_path)
            clients_path = Path(settings.radius_clients_path)
            
            configs_exist = (
                (clients_path / "clients.conf").exists() and
                (config_path / "users").exists() and
                (config_path / "sites-enabled" / "default").exists()
            )
            
            if not self._initialized and configs_exist and not force:
                # Config files exist - just initialize timestamps, don't regenerate
                self._initialize_timestamps(db)
                return result
            
            # Check RADIUS clients
            current_clients_update = self._get_last_update_timestamp(db, RadiusClient)
            
            if force or self.last_clients_update is None or (
                current_clients_update and self.last_clients_update and 
                current_clients_update > self.last_clients_update
            ):
                logger.info("🔄 Regenerating clients.conf (database changed)")
                self.config_generator.generate_clients_conf(db)
                self.last_clients_update = current_clients_update
                result["clients_regenerated"] = True
            elif self.last_clients_update is None:
                # First run - just set timestamp
                self.last_clients_update = current_clients_update
            
            # Check UDN assignments
            current_assignments_update = self._get_last_update_timestamp(db, UdnAssignment)
            
            if force or (
                current_assignments_update and self.last_assignments_update and 
                current_assignments_update > self.last_assignments_update
            ):
                logger.info("🔄 Regenerating users file (database changed)")
                self.config_generator.generate_users_file(db)
                self.last_assignments_update = current_assignments_update
                result["users_regenerated"] = True
            elif self.last_assignments_update is None:
                self.last_assignments_update = current_assignments_update
            
            # Check policies
            current_policies_update = self._get_last_update_timestamp(db, RadiusPolicy)
            
            if force or (
                current_policies_update and self.last_policies_update and 
                current_policies_update > self.last_policies_update
            ):
                logger.info("🔄 Regenerating policy file (database changed)")
                self.policy_generator.generate_policy_file(db)
                self.policy_generator.generate_policy_include()
                self.last_policies_update = current_policies_update
                result["policies_regenerated"] = True
            elif self.last_policies_update is None:
                self.last_policies_update = current_policies_update
            
            # Check MAC bypass configs
            from radius_app.db.models import RadiusMacBypassConfig
            current_mac_bypass_update = self._get_last_update_timestamp(db, RadiusMacBypassConfig)
            
            if force or (
                current_mac_bypass_update and self.last_mac_bypass_update and 
                current_mac_bypass_update > self.last_mac_bypass_update
            ):
                logger.info("🔄 Regenerating MAC bypass file (database changed)")
                from radius_app.core.psk_config_generator import PskConfigGenerator
                psk_generator = PskConfigGenerator()
                psk_generator.generate_mac_bypass_file(db)
                self.last_mac_bypass_update = current_mac_bypass_update
                result["mac_bypass_regenerated"] = True
            elif self.last_mac_bypass_update is None:
                self.last_mac_bypass_update = current_mac_bypass_update
            
            # Generate PSK users file only if force or assignments changed
            if force or result.get("users_regenerated"):
                try:
                    from radius_app.core.psk_config_generator import PskConfigGenerator
                    psk_generator = PskConfigGenerator()
                    psk_generator.generate_psk_users_file(db)
                    result["psk_users_regenerated"] = True
                except Exception as e:
                    logger.warning(f"Failed to generate PSK users file: {e}")
            
            # Check RadSec configurations
            current_radsec_update = self._get_last_update_timestamp(db, RadiusRadSecConfig)
            
            if force or (
                current_radsec_update and self.last_radsec_update and 
                current_radsec_update > self.last_radsec_update
            ):
                logger.info("🔄 Regenerating RadSec configuration (database changed)")
                self.radsec_generator.generate_radsec_conf(db)
                self.radsec_generator.generate_radsec_include()
                self.last_radsec_update = current_radsec_update
                result["radsec_regenerated"] = True
            elif self.last_radsec_update is None:
                self.last_radsec_update = current_radsec_update
            
            self._initialized = True
            
            # Generate/enable all virtual servers (always regenerate on force/initial)
            # This ensures we overwrite any template files and sync all servers
            settings = get_settings()
            config_path = Path(settings.radius_config_path)
            if force or not (config_path / "sites-enabled" / "default").exists():
                logger.info("🔄 Generating/enabling all virtual servers")
                try:
                    from radius_app.core.virtual_server_generator import VirtualServerGenerator
                    virtual_server_generator = VirtualServerGenerator()
                    # Use comprehensive method to generate all virtual servers:
                    # - default (main auth/acct)
                    # - radsec (RADIUS over TLS) - if RadSec config exists
                    # - status (monitoring) - created but not enabled by default
                    virtual_servers = virtual_server_generator.write_all_virtual_servers(
                        db, 
                        enable_status=False  # Status server disabled by default for security
                    )
                    result["virtual_server_regenerated"] = True
                    logger.info(f"✅ Generated {len(virtual_servers)} virtual servers: {list(virtual_servers.keys())}")
                except Exception as e:
                    logger.warning(f"Failed to generate/enable virtual servers: {e}", exc_info=True)
            
            # Generate inner-tunnel virtual server for EAP (TTLS/PEAP)
            # This needs SQL support if users are in database
            eap_symlink = config_path / "mods-enabled" / "eap"
            if eap_symlink.exists() and (force or not (config_path / "sites-enabled" / "inner-tunnel").exists()):
                logger.info("🔄 Generating/enabling inner-tunnel virtual server")
                try:
                    from radius_app.core.eap_config_generator import EapConfigGenerator
                    eap_generator = EapConfigGenerator(config_path)
                    sql_enabled = (config_path / "mods-enabled" / "sql").exists()
                    inner_tunnel_config = eap_generator.generate_inner_tunnel(db, use_sql=sql_enabled)
                    
                    # Write inner-tunnel to sites-available
                    inner_tunnel_file = config_path / "sites-available" / "inner-tunnel"
                    inner_tunnel_file.write_text(inner_tunnel_config)
                    inner_tunnel_file.chmod(0o644)
                    
                    # Enable via symlink
                    inner_tunnel_enabled = config_path / "sites-enabled" / "inner-tunnel"
                    if inner_tunnel_enabled.exists():
                        inner_tunnel_enabled.unlink()
                    inner_tunnel_enabled.symlink_to("../sites-available/inner-tunnel")
                    
                    result["inner_tunnel_regenerated"] = True
                    logger.info(f"✅ Generated inner-tunnel virtual server (SQL: {sql_enabled})")
                except Exception as e:
                    logger.warning(f"Failed to generate inner-tunnel: {e}", exc_info=True)
            
            # Validate all config files before reloading
            if any([
                result["clients_regenerated"],
                result["users_regenerated"],
                result["policies_regenerated"],
                result["radsec_regenerated"],
                result.get("mac_bypass_regenerated", False),
                result.get("psk_users_regenerated", False)
            ]):
                # Validate all generated files before reloading
                validation_passed = self._validate_all_configs()
                
                if not validation_passed:
                    logger.error("❌ Configuration validation failed - NOT reloading FreeRADIUS")
                    logger.error("⚠️  FreeRADIUS will continue using previous configuration")
                    result["reloaded"] = False
                    result["validation_failed"] = True
                else:
                    # All validations passed - safe to reload
                    result["reloaded"] = self._reload_radiusd()
                    result["validation_failed"] = False
            
        except Exception as e:
            logger.error(f"Error checking/regenerating config: {e}", exc_info=True)
        finally:
            # Properly close the database session
            db.close()
        
        return result
    
    async def watch_loop(self):
        """Main watch loop - runs continuously."""
        logger.info("🔍 Starting database watch loop...")
        self.running = True
        
        # Initial check - only force if config files don't exist
        settings = get_settings()
        config_path = Path(settings.radius_config_path)
        clients_path = Path(settings.radius_clients_path)
        
        configs_exist = (
            (clients_path / "clients.conf").exists() and
            (config_path / "users").exists() and
            (config_path / "sites-enabled" / "default").exists()
        )
        
        if configs_exist:
            logger.info("📊 Config files exist - initializing timestamps only")
            await self.check_and_regenerate(force=False)
        else:
            logger.info("⚠️ Config files missing - performing initial generation")
            await self.check_and_regenerate(force=True)
        
        # Watch loop
        while self.running:
            try:
                await asyncio.sleep(self.poll_interval)
                await self.check_and_regenerate()
                
            except asyncio.CancelledError:
                logger.info("Watch loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in watch loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(self.poll_interval)
        
        logger.info("Database watch loop stopped")
    
    def stop(self):
        """Stop the watch loop."""
        self.running = False
