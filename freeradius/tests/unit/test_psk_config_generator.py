"""Unit tests for PSK configuration generator."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from radius_app.core.psk_config_generator import PskConfigGenerator
from radius_app.db.models import UdnAssignment, RadiusMacBypassConfig


@pytest.mark.unit
class TestPskConfigGenerator:
    """Test PSK configuration generator."""
    
    def test_init(self, temp_config_dir):
        """Test PSK config generator initialization."""
        with patch('radius_app.core.psk_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PskConfigGenerator()
            assert generator.config_path == temp_config_dir
    
    def test_generate_psk_users_file_no_portal_db(self, db, temp_config_dir):
        """Test generating PSK users file without portal database."""
        # Create UDN assignment with PSK info
        assignment = UdnAssignment(
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
            udn_id=100,
            ipsk_id="test-ipsk-123",
            user_email="test@example.com",
            is_active=True,
        )
        db.add(assignment)
        db.commit()
        
        with patch('radius_app.core.psk_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PskConfigGenerator()
            output_path = generator.generate_psk_users_file(db)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "# Auto-generated RADIUS users for PSK authentication" in content
            assert "test-ipsk-123" in content
    
    def test_generate_psk_users_file_with_generic_psk(self, db, temp_config_dir):
        """Test generating PSK users file with generic PSK."""
        with patch('radius_app.core.psk_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            mock_settings.return_value.generic_psk_passphrase = "generic-psk-123"
            
            generator = PskConfigGenerator()
            output_path = generator.generate_psk_users_file(db)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "generic-psk" in content
            assert "generic-psk-123" in content
    
    def test_generate_mac_bypass_file(self, db, temp_config_dir):
        """Test generating MAC bypass file."""
        # Create MAC bypass config
        config = RadiusMacBypassConfig(
            name="test-bypass",
            description="Test bypass",
            mac_addresses=["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"],
            bypass_mode="whitelist",
            is_active=True,
        )
        db.add(config)
        db.commit()
        
        with patch('radius_app.core.psk_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PskConfigGenerator()
            output_path = generator.generate_mac_bypass_file(db)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "# Auto-generated MAC bypass configuration" in content
            assert "test-bypass" in content
            assert "aa:bb:cc:dd:ee:ff" in content
    
    def test_generate_mac_bypass_file_empty(self, db, temp_config_dir):
        """Test generating MAC bypass file with no configs."""
        with patch('radius_app.core.psk_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PskConfigGenerator()
            output_path = generator.generate_mac_bypass_file(db)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "# Auto-generated MAC bypass configuration" in content
            assert "Total bypass configs: 0" in content
    
    def test_decrypt_passphrase_not_implemented(self, temp_config_dir):
        """Test that passphrase decryption returns None (not yet implemented)."""
        with patch('radius_app.core.psk_config_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PskConfigGenerator()
            result = generator._decrypt_passphrase("encrypted-passphrase")
            
            assert result is None
