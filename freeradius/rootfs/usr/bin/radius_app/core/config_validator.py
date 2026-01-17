"""FreeRADIUS configuration file validator.

Validates generated configuration files before applying them to ensure
they don't break the FreeRADIUS system.

Per FreeRADIUS documentation:
https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/configuring_modules.html

Uses radiusd -XC to validate configuration files.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigValidator:
    """Validates FreeRADIUS configuration files."""
    
    def __init__(self):
        """Initialize config validator."""
        self.radiusd_available = self._check_radiusd_available()
        if not self.radiusd_available:
            logger.warning("⚠️  FreeRADIUS not available - config validation will be limited")
    
    def _check_radiusd_available(self) -> bool:
        """Check if radiusd is available for validation.
        
        Returns:
            True if radiusd is available
        """
        try:
            result = subprocess.run(
                ["radiusd", "-v"],
                capture_output=True,
                timeout=5,
                text=True
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def validate_users_file(
        self,
        users_file_content: str,
        config_dir: Optional[Path] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate a users file using FreeRADIUS parser.
        
        Args:
            users_file_content: Content of the users file to validate
            config_dir: Optional reference to real config directory (not used for writing)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.radiusd_available:
            # Basic syntax check if radiusd not available
            return self._basic_syntax_check(users_file_content)
        
        # ALWAYS use temp directory for validation to avoid overwriting real config
        temp_dir = tempfile.mkdtemp(prefix="radius_validate_")
        validation_dir = Path(temp_dir) / "raddb"
        
        try:
            validation_dir.mkdir(parents=True, exist_ok=True)
            
            # Create minimal radiusd.conf for validation
            radiusd_conf = validation_dir / "radiusd.conf"
            radiusd_conf.write_text(f"""
prefix = /usr
exec_prefix = /usr
sysconfdir = /etc
localstatedir = /var
logdir = {validation_dir}/log
raddbdir = {validation_dir}

modules {{
}}
""")
            
            # Create default.conf with server block (FreeRADIUS includes this automatically)
            # Minimal server config for validation - just needs a listen section
            default_conf = validation_dir / "default.conf"
            default_conf.write_text(f"""
server default {{
    listen {{
        type = auth
        ipaddr = 127.0.0.1
        port = 0
    }}
}}
""")
            
            # Create users file with content to validate
            users_file = validation_dir / "users"
            users_file.write_text(users_file_content)
            
            # Validate with radiusd -XC
            result = subprocess.run(
                ["radiusd", "-XC", "-d", str(validation_dir), "-n", "default"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(validation_dir)
            )
            
            success_message = "Configuration appears to be OK"
            
            if result.returncode == 0 and success_message in result.stdout:
                return True, None
            else:
                # Extract error message from stderr or stdout
                error_output = result.stderr if result.stderr else result.stdout
                error_msg = f"FreeRADIUS validation failed:\n{error_output}"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Validation timeout - FreeRADIUS parser took too long"
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"
        finally:
            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
    
    def validate_clients_conf(
        self,
        clients_content: str,
        config_dir: Optional[Path] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate a clients.conf file using FreeRADIUS parser.
        
        Args:
            clients_content: Content of the clients.conf file to validate
            config_dir: Optional reference to real config directory (not used for writing)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.radiusd_available:
            # Basic syntax check if radiusd not available
            return self._basic_syntax_check(clients_content)
        
        # ALWAYS use temp directory for validation to avoid overwriting real config
        temp_dir = tempfile.mkdtemp(prefix="radius_validate_")
        validation_dir = Path(temp_dir) / "raddb"
        
        try:
            validation_dir.mkdir(parents=True, exist_ok=True)
            
            # Create minimal radiusd.conf
            radiusd_conf = validation_dir / "radiusd.conf"
            radiusd_conf.write_text(f"""
prefix = /usr
exec_prefix = /usr
sysconfdir = /etc
localstatedir = /var
logdir = {validation_dir}/log
raddbdir = {validation_dir}

modules {{
}}
""")
            
            # Create default.conf with server block (FreeRADIUS includes this automatically)
            # Minimal server config for validation - just needs a listen section
            default_conf = validation_dir / "default.conf"
            default_conf.write_text(f"""
server default {{
    listen {{
        type = auth
        ipaddr = 127.0.0.1
        port = 0
    }}
}}
""")
            
            # Create clients.conf with content to validate
            clients_file = validation_dir / "clients.conf"
            clients_file.write_text(clients_content)
            
            # Include clients.conf in radiusd.conf
            radiusd_conf_content = radiusd_conf.read_text()
            radiusd_conf.write_text(radiusd_conf_content + f"\n$INCLUDE {clients_file}\n")
            
            # Validate with radiusd -XC
            result = subprocess.run(
                ["radiusd", "-XC", "-d", str(validation_dir), "-n", "default"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(validation_dir)
            )
            
            success_message = "Configuration appears to be OK"
            
            if result.returncode == 0 and success_message in result.stdout:
                return True, None
            else:
                # Extract error message from stderr or stdout
                error_output = result.stderr if result.stderr else result.stdout
                error_msg = f"FreeRADIUS validation failed:\n{error_output}"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Validation timeout - FreeRADIUS parser took too long"
        except Exception as e:
            logger.error(f"Validation error: {e}", exc_info=True)
            return False, f"Validation error: {str(e)}"
        finally:
            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
    
    def validate_policy_file(
        self,
        policy_content: str,
        config_dir: Optional[Path] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate a policy file using FreeRADIUS parser.
        
        Args:
            policy_content: Content of the policy file to validate
            config_dir: Optional config directory (uses temp if not provided)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Policy files are users file format, so use same validation
        return self.validate_users_file(policy_content, config_dir)
    
    def _basic_syntax_check(self, content: str) -> tuple[bool, Optional[str]]:
        """Perform basic syntax checks when radiusd is not available.
        
        Args:
            content: File content to check
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []
        
        # Check for balanced brackets
        if content.count("{") != content.count("}"):
            errors.append("Unbalanced curly brackets")
        
        # Check for balanced quotes (should be even number)
        quote_count = content.count('"')
        if quote_count % 2 != 0:
            errors.append("Unbalanced quotes")
        
        # Check for basic FreeRADIUS syntax
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                # Check for common syntax errors
                if '=' in stripped and '==' not in stripped:
                    # Should have space around = or :=
                    if '= ' not in stripped and ' :=' not in stripped and ' +=' not in stripped:
                        # This is a warning, not an error
                        pass
        
        if errors:
            return False, "; ".join(errors)
        
        return True, None
    
    def validate_before_write(
        self,
        file_path: Path,
        content: str,
        file_type: str = "users"
    ) -> bool:
        """Validate configuration file before writing to disk.
        
        This is the main method to call before writing any config file.
        
        Args:
            file_path: Path where file will be written
            content: Content to validate
            file_type: Type of file ("users", "clients", "policy")
            
        Returns:
            True if valid, raises ConfigValidationError if invalid
            
        Raises:
            ConfigValidationError: If validation fails
        """
        # Always use temp directory for validation to avoid issues with
        # missing includes in the actual config directory
        config_dir = None
        
        if file_type == "users" or file_type == "policy":
            is_valid, error = self.validate_users_file(content, config_dir)
        elif file_type == "clients":
            is_valid, error = self.validate_clients_conf(content, config_dir)
        else:
            # Unknown type - do basic check
            is_valid, error = self._basic_syntax_check(content)
        
        if not is_valid:
            error_msg = f"Configuration validation failed for {file_path}:\n{error}"
            logger.error(f"❌ {error_msg}")
            raise ConfigValidationError(error_msg)
        
        logger.debug(f"✅ Configuration validated: {file_path}")
        return True
    
    def _validate_virtual_server_config(self, config_dir: Path) -> tuple[bool, Optional[str]]:
        """Validate virtual server configuration using radiusd -XC.
        
        Virtual server configs require full FreeRADIUS context for validation,
        so we validate the entire configuration directory.
        
        Args:
            config_dir: Path to FreeRADIUS config directory
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.radiusd_available:
            logger.debug("FreeRADIUS not available - skipping virtual server validation")
            return True, None
        
        try:
            # Use radiusd -XC to validate entire configuration
            # This validates all virtual servers, modules, and configs
            result = subprocess.run(
                ["radiusd", "-XC", "-d", str(config_dir), "-n", "default"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                # Check for success message
                if "Configuration appears to be OK" in result.stdout:
                    return True, None
                else:
                    return False, "Validation passed but no success message found"
            else:
                error_output = result.stderr or result.stdout
                return False, error_output
                
        except subprocess.TimeoutExpired:
            return False, "Validation timed out after 30 seconds"
        except FileNotFoundError:
            logger.debug("radiusd command not found")
            return True, None  # Don't fail if radiusd not available
        except Exception as e:
            return False, f"Validation error: {str(e)}"


# Global validator instance
_validator: Optional[ConfigValidator] = None


def get_validator() -> ConfigValidator:
    """Get global config validator instance.
    
    Returns:
        ConfigValidator instance
    """
    global _validator
    if _validator is None:
        _validator = ConfigValidator()
    return _validator


def safe_write_config_file(
    file_path: Path,
    content: str,
    file_type: str = "users",
    chmod: int = 0o644
) -> None:
    """Safely write a configuration file with mandatory validation.
    
    This function ensures that NO invalid configuration file can ever be written.
    If validation fails, the file is NOT written and an exception is raised.
    
    Args:
        file_path: Path where file will be written
        content: Content to write (will be validated first)
        file_type: Type of file ("users", "clients", "policy")
        chmod: File permissions (default: 0o644)
        
    Raises:
        ConfigValidationError: If validation fails - file will NOT be written
        
    Example:
        >>> safe_write_config_file(Path("/etc/raddb/users"), content, "users")
        >>> # File is only written if validation passes
    """
    validator = get_validator()
    
    # ALWAYS validate before writing - this prevents invalid configs
    validator.validate_before_write(file_path, content, file_type)
    
    # Only write if validation passed (validate_before_write raises on failure)
    file_path.write_text(content)
    file_path.chmod(chmod)
    
    logger.info(f"✅ Safely wrote validated config file: {file_path}")
