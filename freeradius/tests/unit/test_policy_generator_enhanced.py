"""Unit tests for enhanced policy generator with new fields."""

import pytest
from pathlib import Path
from unittest.mock import patch

from radius_app.core.policy_generator import PolicyGenerator
from radius_app.db.models import RadiusPolicy, RadiusMacBypassConfig, RadiusEapConfig, RadiusEapMethod


@pytest.mark.unit
class TestPolicyGeneratorEnhanced:
    """Test enhanced policy generator with new fields."""
    
    def test_build_check_items_with_psk_validation(self, db, temp_config_dir):
        """Test building check items with PSK validation."""
        policy = RadiusPolicy(
            name="psk-policy",
            match_username=".*",
            psk_validation_required=True,
            mac_matching_enabled=False,
            match_on_psk_only=True,
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            check_items = generator._build_check_items(policy)
            
            # Should include PSK validation check
            assert any("Cleartext-Password" in item for item in check_items)
            # Should not include MAC matching if disabled
            assert not any("Calling-Station-Id" in item for item in check_items)
    
    def test_build_check_items_with_mac_matching_disabled(self, db, temp_config_dir):
        """Test building check items with MAC matching disabled."""
        policy = RadiusPolicy(
            name="psk-only-policy",
            match_username=".*",
            mac_matching_enabled=False,
            match_on_psk_only=True,
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            check_items = generator._build_check_items(policy)
            
            # Should not include MAC address checks
            assert not any("Calling-Station-Id" in item for item in check_items)
    
    def test_build_reply_items_with_splash_url(self, db, temp_config_dir):
        """Test building reply items with splash URL."""
        policy = RadiusPolicy(
            name="splash-policy",
            splash_url="https://example.com/splash",
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            reply_items = generator._build_reply_items(policy)
            
            # Should include splash URL
            assert any("splash" in item.lower() or "redirect" in item.lower() for item in reply_items)
    
    def test_build_reply_items_with_group_policies(self, db, temp_config_dir):
        """Test building reply items with group policies.
        
        Note: Default vendor is 'meraki' which uses Filter-Id for group policies.
        Use group_policy_vendor='cisco_aireos' to get air-group-policy-name.
        """
        policy = RadiusPolicy(
            name="group-policy-policy",
            registered_group_policy="registered-users",
            unregistered_group_policy="unregistered-users",
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            reply_items = generator._build_reply_items(policy)
            
            # Default vendor (meraki) uses Filter-Id for group policy
            assert any("Filter-Id" in item and "registered-users" in item for item in reply_items)
    
    def test_build_reply_items_with_udn_inclusion(self, db, temp_config_dir):
        """Test building reply items with UDN inclusion.
        
        Note: UDN is included as a comment in the policy file header,
        not as a reply item, since UDN lookup happens dynamically at runtime.
        """
        policy = RadiusPolicy(
            name="udn-policy",
            include_udn=True,
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            # Generate policy file to check UDN comment
            policy_file_path = generator.generate_policy_file(db)
            policy_file = policy_file_path.read_text() if hasattr(policy_file_path, 'read_text') else str(policy_file_path)
            
            # Should include UDN comment in policy file header
            assert "UDN" in policy_file or "udn" in policy_file.lower()
    
    def test_generate_policy_file_includes_mac_bypass(self, db, temp_config_dir):
        """Test that policy file generation includes MAC bypass section."""
        # Create MAC bypass config
        mac_bypass = RadiusMacBypassConfig(
            name="test-bypass",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            is_active=True,
        )
        db.add(mac_bypass)
        
        # Create policy
        policy = RadiusPolicy(
            name="test-policy",
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            output_path = generator.generate_policy_file(db)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "MAC BYPASS CONFIGURATIONS" in content
            assert "test-bypass" in content
    
    def test_generate_policy_file_includes_eap_methods(self, db, temp_config_dir):
        """Test that policy file generation includes EAP methods section."""
        # Create EAP config
        eap_config = RadiusEapConfig(
            name="test-eap",
            default_eap_type="tls",
            enabled_methods=["tls", "ttls"],
            tls_min_version="1.2",
            tls_max_version="1.3",
            is_active=True,
        )
        db.add(eap_config)
        db.flush()
        
        # Create EAP method
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
        )
        db.add(policy)
        db.commit()
        
        with patch('radius_app.core.policy_generator.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = PolicyGenerator()
            output_path = generator.generate_policy_file(db)
            
            assert output_path.exists()
            content = output_path.read_text()
            assert "EAP AUTHENTICATION METHODS" in content
            assert "test-eap" in content
