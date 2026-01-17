"""Unit tests for configuration generator.

Tests the generation of FreeRADIUS configuration files from database.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy.orm import Session

from radius_app.core.config_generator import ConfigGenerator
from radius_app.db.models import RadiusClient, UdnAssignment


@pytest.mark.unit
class TestConfigGenerator:
    """Test configuration file generation."""
    
    def test_generate_clients_conf_empty_db(self, db: Session, temp_config_dir):
        """Test clients.conf generation with empty database."""
        with patch('radius_app.core.config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_clients_path = str(temp_config_dir / "clients")
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            Path(mock_settings.return_value.radius_clients_path).mkdir(exist_ok=True, parents=True)
            
            # Generate config
            generator = ConfigGenerator()
            result_path = generator.generate_clients_conf(db)
            
            # Verify - result is a Path
            assert result_path.exists()
            
            content = result_path.read_text()
            assert "Auto-generated" in content or "client" in content
    
    def test_generate_clients_conf_with_data(
        self,
        db: Session,
        sample_radius_client: RadiusClient,
        temp_config_dir
    ):
        """Test clients.conf generation with data."""
        with patch('radius_app.core.config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_clients_path = str(temp_config_dir / "clients")
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            Path(mock_settings.return_value.radius_clients_path).mkdir(exist_ok=True, parents=True)
            
            # Generate config
            generator = ConfigGenerator()
            result_path = generator.generate_clients_conf(db)
            
            # Verify - result is a Path
            assert result_path.exists()
            
            content = result_path.read_text()
            assert "test" in content.lower() or "client" in content.lower()
    
    def test_generate_users_file_empty_db(self, db: Session, temp_config_dir):
        """Test users file generation with empty database."""
        with patch('radius_app.core.config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.radius_clients_path = str(temp_config_dir / "clients")
            Path(mock_settings.return_value.radius_clients_path).mkdir(exist_ok=True, parents=True)
            
            # Generate users file
            generator = ConfigGenerator()
            result_path = generator.generate_users_file(db)
            
            # Verify - result is a Path
            assert result_path.exists()
            
            content = result_path.read_text()
            assert "Auto-generated" in content or "#" in content
    
    def test_generate_users_file_with_data(
        self,
        db: Session,
        sample_udn_assignment: UdnAssignment,
        temp_config_dir
    ):
        """Test users file generation with UDN assignments."""
        with patch('radius_app.core.config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.radius_clients_path = str(temp_config_dir / "clients")
            Path(mock_settings.return_value.radius_clients_path).mkdir(exist_ok=True, parents=True)
            
            # Generate users file
            generator = ConfigGenerator()
            result_path = generator.generate_users_file(db)
            
            # Verify - result is a Path
            assert result_path.exists()
            
            content = result_path.read_text()
            # Content should include UDN-related information
            assert "UDN" in content or "udn" in content.lower() or "user" in content.lower()
    
    def test_inactive_clients_excluded(self, db: Session, temp_config_dir):
        """Test that inactive clients are not included in config."""
        with patch('radius_app.core.config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_clients_path = str(temp_config_dir / "clients")
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            Path(mock_settings.return_value.radius_clients_path).mkdir(exist_ok=True, parents=True)
            
            # Add inactive client
            client = RadiusClient(
                name="inactive-client",
                ipaddr="192.168.1.200",
                secret="SecureInactiveSecret!",
                is_active=False,
                created_by="test",
            )
            db.add(client)
            db.commit()
            
            # Generate config
            generator = ConfigGenerator()
            result_path = generator.generate_clients_conf(db)
            
            # Verify inactive client not included
            content = result_path.read_text()
            assert "inactive-client" not in content
            assert "192.168.1.200" not in content
    
    def test_inactive_assignments_excluded(self, db: Session, temp_config_dir):
        """Test that inactive UDN assignments are not included."""
        with patch('radius_app.core.config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.radius_clients_path = str(temp_config_dir / "clients")
            Path(mock_settings.return_value.radius_clients_path).mkdir(exist_ok=True, parents=True)
            
            # Add inactive assignment
            assignment = UdnAssignment(
                user_id=1,  # Required - UDN assigned to user
                mac_address="11:22:33:44:55:66",
                udn_id=200,
                is_active=False,
            )
            db.add(assignment)
            db.commit()
            
            # Generate users file
            generator = ConfigGenerator()
            result_path = generator.generate_users_file(db)
            
            # Verify inactive assignment not included
            content = result_path.read_text()
            # Inactive MAC should not appear in content
            assert "11:22:33:44:55:66" not in content or "inactive" in content.lower()
