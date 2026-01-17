"""End-to-End Integration Tests for Config File Creation

These tests verify that when entities are created via API/UI,
the corresponding FreeRADIUS configuration files are actually generated
and contain the correct content.
"""

import pytest
from pathlib import Path
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from radius_app.core.config_generator import ConfigGenerator
from radius_app.core.psk_config_generator import PskConfigGenerator
from radius_app.core.policy_generator import PolicyGenerator
from radius_app.core.eap_config_generator import EapConfigGenerator
from radius_app.db.models import (
    RadiusClient,
    RadiusPolicy,
    RadiusMacBypassConfig,
    RadiusEapConfig,
    RadiusEapMethod,
    UdnAssignment,
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
class TestConfigFileCreationE2E:
    """Test that creating entities creates config files."""
    
    def test_create_client_creates_clients_conf(self, db: Session, temp_config_dir):
        """Test that creating a RADIUS client creates/updates clients.conf."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            clients_path = temp_config_dir / "clients" / "clients.conf"
            
            # Create a RADIUS client
            client = RadiusClient(
                name="test-client-e2e",
                ipaddr="10.0.0.1",
                secret="S3cur3T3stS3cr3t!",
                nas_type="meraki",
                shortname="test-client",
                is_active=True,
                created_by="test",
            )
            db.add(client)
            db.commit()
            
            # Generate config
            generator = ConfigGenerator()
            output_path = generator.generate_clients_conf(db)
            
            # Verify file was created/updated
            assert output_path.exists()
            
            # Verify content includes our client
            content = output_path.read_text()
            assert "test-client-e2e" in content or "test-client" in content
            assert "10.0.0.1" in content
    
    def test_create_policy_creates_policy_file(self, db: Session, temp_config_dir):
        """Test that creating a RADIUS policy creates/updates policy file."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings):
            # Create a policy
            policy = RadiusPolicy(
                name="test-policy-e2e",
                group_name="test-group",
                policy_type="user",
                priority=100,
                is_active=True,
                created_by="test",
            )
            db.add(policy)
            db.commit()
            
            # Generate policy file
            generator = PolicyGenerator()
            output_path = generator.generate_policy_file(db)
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify content includes our policy
            content = output_path.read_text()
            assert "test-policy-e2e" in content
    
    def test_create_mac_bypass_creates_mac_bypass_file(self, db: Session, temp_config_dir):
        """Test that creating MAC bypass config creates/updates MAC bypass file."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings):
            # Create MAC bypass config
            mac_bypass = RadiusMacBypassConfig(
                name="test-bypass-e2e",
                mac_addresses=["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"],
                bypass_mode="whitelist",
                is_active=True,
                created_by="test",
            )
            db.add(mac_bypass)
            db.commit()
            
            # Generate MAC bypass file
            generator = PskConfigGenerator()
            output_path = generator.generate_mac_bypass_file(db)
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify content includes our MAC bypass config
            content = output_path.read_text()
            assert "test-bypass-e2e" in content
    
    def test_create_user_with_udn_creates_users_file(self, db: Session, temp_config_dir):
        """Test that creating UDN assignment creates/updates users file."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings):
            
            # Create UDN assignment (represents user registration)
            assignment = UdnAssignment(
                user_id=1,
                mac_address="00:11:22:33:44:55",
                udn_id=2000,
                user_email="testuser@example.com",
                user_name="Test User",
                unit="101",
                is_active=True,
            )
            db.add(assignment)
            db.commit()
            
            # Generate users file
            generator = ConfigGenerator()
            output_path = generator.generate_users_file(db)
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify content includes our assignment
            content = output_path.read_text()
            assert "2000" in content or "UDN" in content.upper()
    
    def test_create_eap_config_creates_eap_files(self, db: Session, temp_config_dir):
        """Test that creating EAP config creates EAP config files."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        # EapConfigGenerator imports get_settings inside __init__, so patch at the source
        with patch('radius_app.config.get_settings', return_value=mock_settings):
            # Create EAP config
            eap_config = RadiusEapConfig(
                name="test-eap-config",
                default_eap_type="tls",
                enabled_methods=["tls", "peap"],
                tls_min_version="1.2",
                tls_max_version="1.3",
                is_active=True,
                created_by="test",
            )
            db.add(eap_config)
            db.commit()
            
            # Generate EAP config files
            generator = EapConfigGenerator()
            result = generator.write_config_files(db)
            
            # Verify files were created
            assert result.get("eap_module", False) or result.get("eap", False)
    
    def test_create_all_entities_generates_all_config_files(self, db: Session, temp_config_dir):
        """Test that creating all entity types generates all config files."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        # Create all entity types first
        client = RadiusClient(
            name="e2e-client",
            ipaddr="192.168.1.1",
            secret="S3cur3E2EPassw0rd!",
            is_active=True,
            created_by="test",
        )
        db.add(client)
        
        policy = RadiusPolicy(
            name="e2e-policy",
            group_name="e2e-group",
            is_active=True,
            created_by="test",
        )
        db.add(policy)
        
        mac_bypass = RadiusMacBypassConfig(
            name="e2e-bypass",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            is_active=True,
            created_by="test",
        )
        db.add(mac_bypass)
        
        assignment = UdnAssignment(
            user_id=1,
            udn_id=3000,
            user_email="e2e@example.com",
            is_active=True,
        )
        db.add(assignment)
        
        db.commit()
        
        # Patch all modules that use get_settings
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_counter_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.virtual_server_generator.get_settings', return_value=mock_settings):
            
            # NOW create ConfigGenerator (after patching)
            config_gen = ConfigGenerator()
            configs = config_gen.generate_all(db)
            
            # Verify essential config files were generated
            assert "clients" in configs
            assert "policies" in configs
            
            # Verify all files exist
            for config_type, path in configs.items():
                assert path.exists(), f"{config_type} file not generated: {path}"
    
    def test_update_entity_updates_config_file(self, db: Session, temp_config_dir):
        """Test that updating an entity updates the config file."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            # Create client
            client = RadiusClient(
                name="update-test",
                ipaddr="10.0.0.1",
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
    
    def test_delete_entity_updates_config_file(self, db: Session, temp_config_dir):
        """Test that deleting an entity updates the config file."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings):
            # Create clients
            client1 = RadiusClient(
                name="delete-test-keep",
                ipaddr="10.0.0.1",
                secret="K33pM3S3cur3Pass!",
                is_active=True,
                created_by="test",
            )
            client2 = RadiusClient(
                name="delete-test-remove",
                ipaddr="10.0.0.2",
                secret="R3m0v3M3S3cur3Pass!",
                is_active=True,
                created_by="test",
            )
            db.add(client1)
            db.add(client2)
            db.commit()
            
            # Generate initial config
            generator = ConfigGenerator()
            output_path = generator.generate_clients_conf(db)
            initial_content = output_path.read_text()
            assert "delete-test-keep" in initial_content
            assert "delete-test-remove" in initial_content
            
            # Delete one client
            db.delete(client2)
            db.commit()
            
            # Regenerate config
            output_path = generator.generate_clients_conf(db)
            updated_content = output_path.read_text()
            
            # Verify content was updated
            assert "delete-test-keep" in updated_content
            assert "delete-test-remove" not in updated_content
    
    def test_config_files_in_persistent_storage(self, db: Session, temp_config_dir):
        """Test that all generated config files are in persistent storage."""
        mock_settings = create_mock_settings(temp_config_dir)
        
        # Patch all modules that use get_settings
        with patch('radius_app.core.config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.psk_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.policy_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_config_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.sql_counter_generator.get_settings', return_value=mock_settings), \
             patch('radius_app.core.virtual_server_generator.get_settings', return_value=mock_settings):
            
            # Generate all configs
            config_gen = ConfigGenerator()
            configs = config_gen.generate_all(db)
            
            # Verify all files are in persistent storage (temp_config_dir, not /etc/raddb)
            for config_type, path in configs.items():
                path_str = str(path)
                
                # Should NOT be in /etc/raddb (ephemeral)
                assert "/etc/raddb" not in path_str, \
                    f"{config_type} file in non-persistent location: {path}"
                
                # Should be in temp_config_dir (simulating /config)
                assert str(temp_config_dir) in path_str, \
                    f"{config_type} file not in persistent storage: {path}"
