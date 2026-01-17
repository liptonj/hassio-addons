"""Integration tests for configuration generation.

These tests verify that generated FreeRADIUS configuration files are valid
and can be parsed by the actual FreeRADIUS daemon.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rootfs/usr/bin"))

from radius_app.core.config_generator import ConfigGenerator
from radius_app.db.models import Base, RadiusClient, UdnAssignment


def create_mock_settings(tmp_path: Path) -> MagicMock:
    """Create a mock settings object for testing."""
    mock = MagicMock()
    mock.radius_config_path = str(tmp_path / "raddb")
    mock.radius_clients_path = str(tmp_path / "clients")
    mock.radius_certs_path = str(tmp_path / "certs")
    # Create directories
    Path(mock.radius_config_path).mkdir(parents=True, exist_ok=True)
    Path(mock.radius_clients_path).mkdir(parents=True, exist_ok=True)
    Path(mock.radius_certs_path).mkdir(parents=True, exist_ok=True)
    return mock


@pytest.mark.integration
class TestConfigGeneration:
    """Test configuration file generation."""
    
    @pytest.fixture
    def test_db(self, tmp_path):
        """Create test database with sample data."""
        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Add sample data
        client = RadiusClient(
            name="test-network",
            ipaddr="192.168.1.0/24",
            secret="T3st1ngS3cr3tP@ss!",
            nas_type="meraki",
            shortname="test-net",
            require_message_authenticator=True,
            is_active=True,
            created_by="test",
        )
        session.add(client)
        
        assignment = UdnAssignment(
            user_id=1,  # Required - UDN is assigned to user
            mac_address="00:11:22:33:44:55",
            udn_id=1000,
            user_name="John Doe",
            user_email="john@example.com",
            unit="101",
            is_active=True
        )
        session.add(assignment)
        
        session.commit()
        
        yield session
        
        session.close()
        engine.dispose()
    
    def test_generate_clients_conf_valid_syntax(self, test_db, tmp_path):
        """Test that generated clients.conf has valid FreeRADIUS syntax."""
        mock_settings = create_mock_settings(tmp_path)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            config_generator = ConfigGenerator()
            clients_path = config_generator.generate_clients_conf(test_db)
            
            assert clients_path.exists()
            content = clients_path.read_text()
            
            # Verify FreeRADIUS syntax elements
            assert "test-network" in content or "test-net" in content
            assert "192.168.1.0/24" in content
            assert "secret" in content.lower()
            
            # Verify no syntax errors (basic check)
            assert content.count("{") == content.count("}")
    
    def test_generate_users_file_valid_syntax(self, test_db, tmp_path):
        """Test that generated users file has valid FreeRADIUS syntax."""
        mock_settings = create_mock_settings(tmp_path)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings):
            
            config_generator = ConfigGenerator()
            users_path = config_generator.generate_users_file(test_db)
            
            assert users_path.exists()
            content = users_path.read_text()
            
            # Verify content contains UDN-related info
            assert "1000" in content or "udn" in content.lower() or "John" in content
    
    def test_radiusd_can_parse_clients_conf(self, test_db, tmp_path):
        """Test that FreeRADIUS can parse the generated clients.conf.
        
        This requires FreeRADIUS to be installed. Skips if not available.
        """
        # Check if radiusd is available
        try:
            subprocess.run(
                ["radiusd", "-v"],
                capture_output=True,
                timeout=5
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("FreeRADIUS not installed")
        
        mock_settings = create_mock_settings(tmp_path)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            config_generator = ConfigGenerator()
            clients_path = config_generator.generate_clients_conf(test_db)
            
            # Create minimal radiusd.conf that includes our clients.conf
            config_dir = Path(mock_settings.radius_config_path)
            config_dir.mkdir(exist_ok=True)
            
            radiusd_conf = config_dir / "radiusd.conf"
            radiusd_conf.write_text(f"""
# Minimal test config
prefix = /usr
exec_prefix = /usr
sysconfdir = /etc
localstatedir = /var
logdir = {config_dir}/log
raddbdir = {config_dir}

# Include our generated clients
$INCLUDE {clients_path}

# Minimal modules
modules {{
}}

# Minimal server
server default {{
    listen {{
        type = auth
        ipaddr = *
        port = 0
    }}
}}
""")
            
            # Test parsing with radiusd -XC (config check with debug)
            result = subprocess.run(
                ["radiusd", "-XC", "-d", str(config_dir), "-n", "default"],
                capture_output=True,
                timeout=10
            )
            
            # Check for syntax errors
            if result.returncode != 0:
                pytest.fail(f"FreeRADIUS config check failed: {result.stderr.decode()}")
    
    def test_config_file_permissions(self, test_db, tmp_path):
        """Test that generated config files have correct permissions."""
        mock_settings = create_mock_settings(tmp_path)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            config_generator = ConfigGenerator()
            clients_path = config_generator.generate_clients_conf(test_db)
            
            # Check file exists
            assert clients_path.exists()
            
            # Check file is readable
            assert os.access(clients_path, os.R_OK)
            
            # Check content is not empty
            content = clients_path.read_text()
            assert len(content) > 0
    
    def test_config_regeneration_is_idempotent(self, test_db, tmp_path):
        """Test that regenerating config produces same content (ignoring timestamp)."""
        import re
        mock_settings = create_mock_settings(tmp_path)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            config_generator = ConfigGenerator()
            
            # Generate first time
            clients_path_1 = config_generator.generate_clients_conf(test_db)
            content_1 = clients_path_1.read_text()
            
            # Generate second time
            clients_path_2 = config_generator.generate_clients_conf(test_db)
            content_2 = clients_path_2.read_text()
            
            # Remove timestamp lines for comparison (timestamps will differ)
            timestamp_pattern = r'# Timestamp:.*\n'
            content_1_no_ts = re.sub(timestamp_pattern, '', content_1)
            content_2_no_ts = re.sub(timestamp_pattern, '', content_2)
            
            # Content should be the same (idempotent, ignoring timestamp)
            assert content_1_no_ts == content_2_no_ts


@pytest.mark.integration
class TestDatabaseWatcher:
    """Test database watcher functionality."""
    
    def test_initial_config_generation(self, db, temp_config_dir):
        """Test that initial config is generated when watcher starts."""
        mock_settings = MagicMock()
        mock_settings.radius_config_path = str(temp_config_dir)
        mock_settings.radius_clients_path = str(temp_config_dir / "clients")
        mock_settings.radius_certs_path = str(temp_config_dir / "certs")
        
        # Create directories
        Path(mock_settings.radius_clients_path).mkdir(parents=True, exist_ok=True)
        Path(mock_settings.radius_certs_path).mkdir(parents=True, exist_ok=True)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            # Create config generator
            config_gen = ConfigGenerator()
            
            # Generate clients config
            clients_path = config_gen.generate_clients_conf(db)
            
            # Verify file was created
            assert clients_path.exists()
    
    def test_config_regenerates_on_db_change(self, db, temp_config_dir):
        """Test that config is regenerated when database changes."""
        mock_settings = MagicMock()
        mock_settings.radius_config_path = str(temp_config_dir)
        mock_settings.radius_clients_path = str(temp_config_dir / "clients")
        mock_settings.radius_certs_path = str(temp_config_dir / "certs")
        
        # Create directories
        Path(mock_settings.radius_clients_path).mkdir(parents=True, exist_ok=True)
        Path(mock_settings.radius_certs_path).mkdir(parents=True, exist_ok=True)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            config_gen = ConfigGenerator()
            
            # Initial config (may be empty)
            clients_path = config_gen.generate_clients_conf(db)
            initial_content = clients_path.read_text()
            
            # Add a new client
            new_client = RadiusClient(
                name="new-client",
                ipaddr="10.0.0.1",
                secret="N3wCl13ntS3cr3t!",
                is_active=True,
                created_by="test",
            )
            db.add(new_client)
            db.commit()
            
            # Regenerate config
            clients_path = config_gen.generate_clients_conf(db)
            updated_content = clients_path.read_text()
            
            # Content should now include the new client
            assert "new-client" in updated_content
            assert "10.0.0.1" in updated_content
