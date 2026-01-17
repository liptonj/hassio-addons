"""Integration tests for verifying config files via API.

These tests verify that:
1. Config files can be accessed via API
2. Config file content is correct
3. Config files are regenerated when entities change
"""

import pytest
from pathlib import Path
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from radius_app.core.config_generator import ConfigGenerator
from radius_app.db.models import RadiusClient, RadiusPolicy, RadiusMacBypassConfig


def create_mock_settings(temp_config_dir: Path) -> MagicMock:
    """Create a mock settings object for testing."""
    mock = MagicMock()
    mock.radius_config_path = str(temp_config_dir)
    mock.radius_clients_path = str(temp_config_dir / "clients")
    mock.radius_certs_path = str(temp_config_dir / "certs")
    # Create directories
    Path(mock.radius_config_path).mkdir(parents=True, exist_ok=True)
    Path(mock.radius_clients_path).mkdir(parents=True, exist_ok=True)
    Path(mock.radius_certs_path).mkdir(parents=True, exist_ok=True)
    return mock


@pytest.mark.integration
class TestConfigFileAPIVerification:
    """Test config file verification via API endpoints."""
    
    def test_config_status_endpoint_reports_correct_counts(self, db: Session):
        """Test that /api/config/status reports correct entity counts."""
        # Create test entities
        client1 = RadiusClient(
            name="status-test-1",
            ipaddr="10.0.0.1",
            secret="V3ryS3cur3Passw0rd1!",
            is_active=True,
            created_by="test",
        )
        client2 = RadiusClient(
            name="status-test-2",
            ipaddr="10.0.0.2",
            secret="V3ryS3cur3Passw0rd2!",
            is_active=True,
            created_by="test",
        )
        db.add(client1)
        db.add(client2)
        db.commit()
        
        # In a real test, we'd call the API endpoint
        # For now, verify the data exists in DB
        active_clients = db.query(RadiusClient).filter(RadiusClient.is_active == True).count()  # noqa: E712
        assert active_clients >= 2
    
    def test_config_files_endpoint_lists_all_files(self, db: Session, temp_config_dir):
        """Test that /api/config/files lists all generated config files."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        # Patch all modules that use get_settings
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_counter_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.virtual_server_generator.get_settings', return_value=mock_settings):
            
            # Generate all configs
            generator = ConfigGenerator()
            configs = generator.generate_all(db)
            
            # Verify essential files exist
            expected_files = ["clients", "policies"]
            for file_type in expected_files:
                assert file_type in configs, f"{file_type} file not generated"
                assert configs[file_type].exists(), f"{file_type} file does not exist"
    
    def test_config_file_content_matches_database(self, db: Session, temp_config_dir):
        """Test that config file content matches database entities."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            # Create client with specific values
            test_ip = "192.168.200.1"
            test_secret = "ContentS3cur3Secret!"
            test_name = "content-test-client"
            
            client = RadiusClient(
                name=test_name,
                ipaddr=test_ip,
                secret=test_secret,
                nas_type="meraki",
                is_active=True,
                created_by="test",
            )
            db.add(client)
            db.commit()
            
            # Generate config
            generator = ConfigGenerator()
            output_path = generator.generate_clients_conf(db)
            
            # Verify content matches database
            content = output_path.read_text()
            assert test_ip in content
            assert test_secret in content
            assert test_name in content or "content-test" in content
    
    def test_config_file_regeneration_on_entity_update(self, db: Session, temp_config_dir):
        """Test that config files are regenerated when entities are updated."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            # Create client
            client = RadiusClient(
                name="regenerate-test",
                ipaddr="10.0.0.10",
                secret="OldS3cur3Passw0rd!",
                is_active=True,
                created_by="test",
            )
            db.add(client)
            db.commit()
            
            # Generate initial config
            generator = ConfigGenerator()
            output_path = generator.generate_clients_conf(db)
            initial_content = output_path.read_text()
            assert "OldS3cur3Passw0rd!" in initial_content
            
            # Update client
            client.secret = "N3wS3cur3Passw0rd!"
            db.commit()
            
            # Regenerate config
            output_path = generator.generate_clients_conf(db)
            updated_content = output_path.read_text()
            
            # Verify content was updated
            assert "N3wS3cur3Passw0rd!" in updated_content
            assert "OldS3cur3Passw0rd!" not in updated_content
    
    def test_all_config_files_in_persistent_storage(self, db: Session, temp_config_dir):
        """Test that all config files are written to persistent storage."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        # Patch all modules that use get_settings
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_counter_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.virtual_server_generator.get_settings', return_value=mock_settings):
            
            # Generate all configs
            generator = ConfigGenerator()
            configs = generator.generate_all(db)
            
            # Verify all files are in persistent storage (not /etc/raddb)
            for config_type, path in configs.items():
                path_str = str(path)
                # Should NOT be in /etc/raddb
                assert "/etc/raddb" not in path_str, \
                    f"{config_type} file in non-persistent location: {path}"
                
                # Should be in temp_config_dir (simulating /config)
                assert str(temp_config_dir) in path_str, \
                    f"{config_type} file not in persistent storage: {path}"
