"""Unit tests for policy generator with authentication configurations."""

import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.core.policy_generator import PolicyGenerator
from radius_app.db.models import (
    Base,
    RadiusEapConfig,
    RadiusEapMethod,
    RadiusMacBypassConfig,
    RadiusPolicy,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def policy_generator(temp_config_dir, monkeypatch):
    """Create policy generator with temp directory."""
    monkeypatch.setenv("RADIUS_CONFIG_PATH", str(temp_config_dir))
    generator = PolicyGenerator()
    return generator


@pytest.fixture
def sample_eap_config(db_session):
    """Create sample EAP configuration."""
    eap_config = RadiusEapConfig(
        name="test-eap",
        description="Test EAP configuration",
        default_eap_type="peap",
        enabled_methods=["peap", "ttls", "tls"],
        tls_min_version="1.2",
        tls_max_version="1.3",
        is_active=True,
        created_by="test",
    )
    db_session.add(eap_config)
    db_session.flush()
    
    # Create EAP methods with statistics
    for method_name in ["peap", "ttls", "tls"]:
        method = RadiusEapMethod(
            eap_config_id=eap_config.id,
            method_name=method_name,
            is_enabled=True,
            auth_attempts=100,
            auth_successes=95,
            auth_failures=5,
        )
        db_session.add(method)
    
    db_session.commit()
    return eap_config


@pytest.fixture
def sample_mac_bypass(db_session):
    """Create sample MAC bypass configuration."""
    config = RadiusMacBypassConfig(
        name="test-bypass",
        description="Test MAC bypass configuration",
        mac_addresses=["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"],
        bypass_mode="whitelist",
        require_registration=False,
        is_active=True,
        created_by="test",
    )
    db_session.add(config)
    db_session.commit()
    return config


@pytest.fixture
def sample_policies(db_session):
    """Create sample authorization policies."""
    policies = [
        RadiusPolicy(
            name="psk-policy",
            description="PSK authentication policy",
            priority=100,
            is_active=True,
            psk_validation_required=True,
            mac_matching_enabled=False,
            match_on_psk_only=True,
            include_udn=True,
            registered_group_policy="registered",
            created_by="test",
        ),
        RadiusPolicy(
            name="unregistered-policy",
            description="Unregistered users policy",
            priority=50,
            is_active=True,
            splash_url="/splash",
            unregistered_group_policy="unregistered",
            created_by="test",
        ),
    ]
    for policy in policies:
        db_session.add(policy)
    db_session.commit()
    return policies


class TestPolicyGeneratorWithAuthConfig:
    """Test policy generator includes authentication configurations."""
    
    def test_policy_file_includes_mac_bypass_section(
        self, policy_generator, db_session, sample_mac_bypass
    ):
        """Test that policy file includes MAC bypass section."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check for MAC bypass section header
        assert "# MAC BYPASS CONFIGURATIONS" in content
        assert "# MAC addresses that bypass normal authentication" in content
        
        # Check for MAC bypass config details
        assert "test-bypass" in content
        assert "Test MAC bypass configuration" in content
        assert "whitelist" in content
        assert "aa:bb:cc:dd:ee:ff" in content
        assert "11:22:33:44:55:66" in content
    
    def test_policy_file_includes_eap_methods_section(
        self, policy_generator, db_session, sample_eap_config
    ):
        """Test that policy file includes EAP methods section."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check for EAP methods section header
        assert "# EAP AUTHENTICATION METHODS" in content
        assert "# Enabled EAP methods for 802.1X authentication" in content
        
        # Check for EAP config details
        assert "test-eap" in content
        assert "Test EAP configuration" in content
        assert "peap" in content
        assert "ttls" in content
        assert "tls" in content
        assert "1.2" in content
        assert "1.3" in content
        
        # Check for method details
        assert "EAP Method Details:" in content
        assert "PEAP: ENABLED" in content or "peap: ENABLED" in content
        assert "TTLS: ENABLED" in content or "ttls: ENABLED" in content
        assert "TLS: ENABLED" in content or "tls: ENABLED" in content
    
    def test_policy_file_includes_authorization_policies_section(
        self, policy_generator, db_session, sample_policies
    ):
        """Test that policy file includes authorization policies section."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check for authorization policies section header
        assert "# AUTHORIZATION POLICIES" in content
        assert "# Policies are evaluated in priority order" in content
        
        # Check for policy details
        assert "psk-policy" in content
        assert "unregistered-policy" in content
        assert "PSK authentication policy" in content
        assert "Unregistered users policy" in content
    
    def test_policy_file_complete_structure(
        self,
        policy_generator,
        db_session,
        sample_eap_config,
        sample_mac_bypass,
        sample_policies,
    ):
        """Test that policy file has complete structure with all sections."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check section order (should be: MAC bypass, EAP methods, Authorization policies)
        sections = [
            "# MAC BYPASS CONFIGURATIONS",
            "# EAP AUTHENTICATION METHODS",
            "# AUTHORIZATION POLICIES",
        ]
        
        positions = [content.find(section) for section in sections]
        
        # All sections should be present
        assert all(pos != -1 for pos in positions)
        
        # Sections should be in order
        assert positions[0] < positions[1] < positions[2]
    
    def test_policy_file_includes_summary_statistics(
        self,
        policy_generator,
        db_session,
        sample_eap_config,
        sample_mac_bypass,
        sample_policies,
    ):
        """Test that policy file includes summary information."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check for summary information
        assert "Total Policies:" in content
        assert "Total bypass configs:" in content or "MAC bypass" in content
        
        # Check that counts are present
        assert "2" in content  # Should have 2 policies
    
    def test_policy_file_handles_empty_configs(
        self, policy_generator, db_session
    ):
        """Test that policy file handles empty configurations gracefully."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Should still have section headers
        assert "# MAC BYPASS CONFIGURATIONS" in content
        assert "# EAP AUTHENTICATION METHODS" in content
        assert "# AUTHORIZATION POLICIES" in content
        
        # Should indicate no configs
        assert "No active" in content or "No active MAC bypass" in content or "No active EAP" in content
    
    def test_policy_file_includes_timestamp(self, policy_generator, db_session):
        """Test that policy file includes generation timestamp."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check for timestamp
        assert "Timestamp:" in content or "Generated from shared database" in content
        assert "DO NOT EDIT MANUALLY" in content
    
    def test_policy_file_policies_sorted_by_priority(
        self, policy_generator, db_session, sample_policies
    ):
        """Test that policies in file are sorted by priority."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Find policy positions in content
        unregistered_pos = content.find("unregistered-policy")
        psk_pos = content.find("psk-policy")
        
        # unregistered-policy (priority 50) should come before psk-policy (priority 100)
        assert unregistered_pos < psk_pos
    
    def test_policy_file_includes_eap_method_statistics(
        self, policy_generator, db_session, sample_eap_config
    ):
        """Test that EAP method statistics are included."""
        policy_file_path = policy_generator.generate_policy_file(db_session)
        
        assert policy_file_path.exists()
        content = policy_file_path.read_text()
        
        # Check for statistics
        assert "Attempts:" in content or "100" in content
        assert "Successes:" in content or "95" in content
        assert "Failures:" in content or "5" in content
        assert "Success Rate:" in content or "95.0%" in content
