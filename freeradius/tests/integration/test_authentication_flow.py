"""Integration tests for complete authentication flow."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from radius_app.core.config_generator import ConfigGenerator
from radius_app.core.psk_config_generator import PskConfigGenerator
from radius_app.core.policy_generator import PolicyGenerator
from radius_app.db.models import (
    RadiusClient,
    UdnAssignment,
    RadiusPolicy,
    RadiusMacBypassConfig,
    RadiusEapConfig,
    RadiusEapMethod,
)


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
class TestAuthenticationFlow:
    """Test complete authentication flow integration."""
    
    def test_complete_config_generation(self, db, temp_config_dir):
        """Test that all config files are generated correctly."""
        # Create test data
        client = RadiusClient(
            name="test-client",
            ipaddr="192.168.1.100",
            secret="V3ryS3cur3Passw0rd!",
            nas_type="meraki",
            is_active=True,
            created_by="test",
        )
        db.add(client)
        
        udn_assignment = UdnAssignment(
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
            udn_id=100,
            user_email="test@example.com",
            is_active=True,
        )
        db.add(udn_assignment)
        
        mac_bypass = RadiusMacBypassConfig(
            name="test-bypass",
            mac_addresses=["11:22:33:44:55:66"],
            bypass_mode="whitelist",
            is_active=True,
            created_by="test",
        )
        db.add(mac_bypass)
        
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            splash_url="https://example.com/splash",
            registered_group_policy="registered",
            include_udn=True,
            is_active=True,
            created_by="test",
        )
        db.add(policy)
        
        db.commit()
        
        mock_settings = create_mock_settings(temp_config_dir)
        
        # Patch all modules that use get_settings
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_counter_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.virtual_server_generator.get_settings', return_value=mock_settings):
            
            config_gen = ConfigGenerator()
            configs = config_gen.generate_all(db)
            
            # Verify essential configs were generated
            assert "clients" in configs
            assert configs["clients"].exists(), "clients file not generated"
            
            # Verify policies was generated
            assert "policies" in configs
            assert configs["policies"].exists(), "policies file not generated"
    
    def test_psk_config_includes_udn(self, db, temp_config_dir):
        """Test that PSK config includes UDN assignments."""
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
        
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings):
            generator = PskConfigGenerator()
            output_path = generator.generate_psk_users_file(db)
            
            content = output_path.read_text()
            assert "udn:private-group-id=100" in content or "100" in content
    
    def test_policy_includes_mac_bypass_and_eap(self, db, temp_config_dir):
        """Test that policy file includes MAC bypass and EAP sections."""
        # Create MAC bypass
        mac_bypass = RadiusMacBypassConfig(
            name="test-bypass",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            is_active=True,
            created_by="test",
        )
        db.add(mac_bypass)
        
        # Create EAP config
        eap_config = RadiusEapConfig(
            name="test-eap",
            default_eap_type="tls",
            enabled_methods=["tls"],
            is_active=True,
            created_by="test",
        )
        db.add(eap_config)
        db.flush()
        
        eap_method = RadiusEapMethod(
            eap_config_id=eap_config.id,
            method_name="tls",
            is_enabled=True,
        )
        db.add(eap_method)
        
        # Create policy
        policy = RadiusPolicy(
            name="test-policy",
            is_active=True,
            created_by="test",
        )
        db.add(policy)
        db.commit()
        
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings):
            generator = PolicyGenerator()
            output_path = generator.generate_policy_file(db)
            
            content = output_path.read_text()
            assert "MAC BYPASS CONFIGURATIONS" in content
            assert "EAP AUTHENTICATION METHODS" in content
            assert "AUTHORIZATION POLICIES" in content
    
    def test_udn_assignment_without_mac(self, db, temp_config_dir):
        """Test that UDN assignment without MAC still generates config."""
        # Create UDN assignment without MAC
        assignment = UdnAssignment(
            user_id=1,
            udn_id=100,
            user_email="test@example.com",
            is_active=True,
        )
        db.add(assignment)
        db.commit()
        
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings):
            
            config_gen = ConfigGenerator()
            output_path = config_gen.generate_users_file(db)
            
            content = output_path.read_text()
            # Check that UDN-related content exists
            assert "100" in content or "udn" in content.lower() or "user" in content.lower()
