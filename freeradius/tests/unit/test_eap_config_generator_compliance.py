"""Unit tests for EAP configuration generator compliance with FreeRADIUS documentation.

Tests ensure compliance with:
https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/eap/index.html
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from radius_app.core.eap_config_generator import EapConfigGenerator
from radius_app.db.models import RadiusEapConfig, RadiusEapMethod


@pytest.mark.unit
class TestEapConfigGeneratorCompliance:
    """Test EAP config generator compliance with FreeRADIUS documentation."""
    
    def test_always_includes_at_least_one_eap_type(self, db, temp_config_dir):
        """Test that EAP config always includes at least one EAP-Type sub-stanza.
        
        Per FreeRADIUS docs: "You cannot have empty eap stanza. 
        At least one EAP-Type sub-stanza should be defined"
        """
        # Create EAP config with empty enabled_methods
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="tls",
            enabled_methods=[],  # Empty!
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            config = generator.generate_eap_module(db)
            
            # Should include at least one EAP type (default_eap_type)
            assert "tls {" in config or "md5 {" in config
            assert "default_eap_type = tls" in config
    
    def test_default_eap_type_in_enabled_methods(self, db, temp_config_dir):
        """Test that default_eap_type is always in enabled_methods."""
        # Create EAP config where default_eap_type is not in enabled_methods
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="md5",
            enabled_methods=["tls"],  # Different from default!
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            config = generator.generate_eap_module(db)
            
            # Should include both md5 (default) and tls (enabled)
            assert "md5 {" in config
            assert "tls {" in config
    
    def test_eap_config_format_compliance(self, db, temp_config_dir):
        """Test that EAP config follows FreeRADIUS format."""
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="tls",
            enabled_methods=["tls", "ttls"],
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            config = generator.generate_eap_module(db)
            
            # Should have proper structure
            assert "eap {" in config
            assert "default_eap_type = tls" in config
            assert "tls {" in config
            assert "ttls {" in config
            assert config.strip().endswith("}")
    
    def test_eap_md5_support(self, db, temp_config_dir):
        """Test EAP-MD5 support (does not require additional packages)."""
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="md5",
            enabled_methods=["md5"],
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            config = generator.generate_eap_module(db)
            
            # Should include MD5 method
            assert "md5 {" in config
            assert "default_eap_type = md5" in config
    
    def test_multiple_eap_types_enabled(self, db, temp_config_dir):
        """Test that multiple EAP types can be enabled simultaneously."""
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="tls",
            enabled_methods=["tls", "ttls", "peap"],
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            config = generator.generate_eap_module(db)
            
            # Should include all three methods
            assert "tls {" in config
            assert "ttls {" in config
            assert "peap {" in config
            # Main default_eap_type (nested ones in ttls/peap are for inner auth)
            assert config.count("default_eap_type = tls") >= 1  # Main EAP default
            # TTLS and PEAP have their own default_eap_type for inner auth (mschapv2)
            assert "default_eap_type = mschapv2" in config  # Inner auth default
    
    def test_tls_config_shared_by_multiple_methods(self, db, temp_config_dir):
        """Test that TLS config is shared by TLS, TTLS, and PEAP."""
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="tls",
            enabled_methods=["tls", "ttls", "peap"],
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            config = generator.generate_eap_module(db)
            
            # Should have tls-config tls-common defined once
            assert config.count("tls-config tls-common {") == 1
            # All three methods should reference it
            assert "tls = tls-common" in config
            # Count how many times "tls = tls-common" appears (should be 3)
            assert config.count("tls = tls-common") >= 3
    
    def test_inner_tunnel_virtual_server(self, db, temp_config_dir):
        """Test that inner-tunnel virtual server is configured for TTLS/PEAP."""
        eap_config = RadiusEapConfig(
            name="test-config",
            default_eap_type="ttls",
            enabled_methods=["ttls"],
            is_active=True,
        )
        db.add(eap_config)
        db.commit()
        
        with patch('radius_app.config.get_settings') as mock_settings:
            mock_settings.return_value.radius_config_path = str(temp_config_dir)
            
            generator = EapConfigGenerator()
            eap_config_str = generator.generate_eap_module(db)
            inner_tunnel_config = generator.generate_inner_tunnel(db)
            
            # TTLS should reference inner-tunnel
            assert "virtual_server = inner-tunnel" in eap_config_str
            # Inner tunnel should be properly configured
            assert "server inner-tunnel {" in inner_tunnel_config
            assert "listen {" in inner_tunnel_config
            assert "authorize {" in inner_tunnel_config
            assert "authenticate {" in inner_tunnel_config
