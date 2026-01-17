"""Unit tests for default data initialization."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import (
    Base,
    RadiusClient,
    RadiusEapConfig,
    RadiusEapMethod,
    RadiusMacBypassConfig,
    RadiusPolicy,
)
from radius_app.db.init_schema import init_default_data


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


class TestDefaultDataInitialization:
    """Test default data initialization on first run."""
    
    def test_creates_localhost_client(self, db_session):
        """Test that default localhost client is created."""
        init_default_data(db_session.bind)
        
        client = db_session.query(RadiusClient).filter_by(name="localhost").first()
        
        assert client is not None
        assert client.ipaddr == "127.0.0.1"
        assert client.secret == "testing123"
        assert client.nas_type == "other"
        assert client.is_active is True
        assert client.created_by == "system"
    
    def test_creates_default_eap_config(self, db_session):
        """Test that default EAP configuration is created."""
        init_default_data(db_session.bind)
        
        eap_config = db_session.query(RadiusEapConfig).filter_by(
            name="default",
            is_active=True
        ).first()
        
        assert eap_config is not None
        assert eap_config.description == "Default EAP configuration - created on first run"
        assert eap_config.default_eap_type == "peap"
        assert set(eap_config.enabled_methods) == {"peap", "ttls", "tls"}
        assert eap_config.tls_min_version == "1.2"
        assert eap_config.tls_max_version == "1.3"
        assert eap_config.created_by == "system"
    
    def test_creates_eap_methods(self, db_session):
        """Test that EAP methods are created."""
        init_default_data(db_session.bind)
        
        eap_config = db_session.query(RadiusEapConfig).filter_by(name="default").first()
        assert eap_config is not None
        
        methods = db_session.query(RadiusEapMethod).filter_by(
            eap_config_id=eap_config.id
        ).all()
        
        assert len(methods) == 3
        
        method_names = {m.method_name for m in methods}
        assert method_names == {"peap", "ttls", "tls"}
        
        # All methods should be enabled
        for method in methods:
            assert method.is_enabled is True
    
    def test_creates_default_mac_bypass(self, db_session):
        """Test that default MAC bypass configuration is created."""
        init_default_data(db_session.bind)
        
        bypass_config = db_session.query(RadiusMacBypassConfig).filter_by(
            name="default"
        ).first()
        
        assert bypass_config is not None
        assert bypass_config.description == "Default MAC bypass configuration - add MAC addresses to bypass authentication"
        assert bypass_config.bypass_mode == "whitelist"
        assert bypass_config.require_registration is False
        assert bypass_config.is_active is True
        assert bypass_config.mac_addresses == []
        assert bypass_config.created_by == "system"
    
    def test_creates_default_policies(self, db_session):
        """Test that default authorization policies are created."""
        init_default_data(db_session.bind)
        
        policies = db_session.query(RadiusPolicy).all()
        
        assert len(policies) == 3
        
        policy_names = {p.name for p in policies}
        assert policy_names == {
            "default-accept",
            "psk-registered-users",
            "unregistered-users",
        }
        
        # Check default-accept policy
        default_accept = db_session.query(RadiusPolicy).filter_by(
            name="default-accept"
        ).first()
        assert default_accept.priority == 1000  # Lowest priority
        assert default_accept.is_active is True
        assert default_accept.psk_validation_required is False
        assert default_accept.mac_matching_enabled is False
        assert default_accept.include_udn is True
        
        # Check psk-registered-users policy
        psk_policy = db_session.query(RadiusPolicy).filter_by(
            name="psk-registered-users"
        ).first()
        assert psk_policy.priority == 100
        assert psk_policy.psk_validation_required is True
        assert psk_policy.mac_matching_enabled is False
        assert psk_policy.match_on_psk_only is True
        assert psk_policy.include_udn is True
        assert psk_policy.registered_group_policy == "registered"
        
        # Check unregistered-users policy
        unregistered_policy = db_session.query(RadiusPolicy).filter_by(
            name="unregistered-users"
        ).first()
        assert unregistered_policy.priority == 50
        assert unregistered_policy.splash_url == "/splash"
        assert unregistered_policy.unregistered_group_policy == "unregistered"
        assert unregistered_policy.include_udn is False
    
    def test_idempotent_initialization(self, db_session):
        """Test that initialization is idempotent (safe to run multiple times)."""
        # Run initialization twice
        init_default_data(db_session.bind)
        first_run_clients = db_session.query(RadiusClient).count()
        first_run_eap_configs = db_session.query(RadiusEapConfig).count()
        first_run_policies = db_session.query(RadiusPolicy).count()
        
        init_default_data(db_session.bind)
        
        # Should not create duplicates
        assert db_session.query(RadiusClient).count() == first_run_clients
        assert db_session.query(RadiusEapConfig).count() == first_run_eap_configs
        assert db_session.query(RadiusPolicy).count() == first_run_policies
    
    def test_does_not_overwrite_existing_configs(self, db_session):
        """Test that existing configurations are not overwritten."""
        # Create existing localhost client with different values
        existing_client = RadiusClient(
            name="localhost",
            ipaddr="192.168.1.1",  # Different IP
            secret="different-secret",
            nas_type="meraki",
            is_active=True,
            created_by="user",
        )
        db_session.add(existing_client)
        db_session.commit()
        
        # Run initialization
        init_default_data(db_session.bind)
        
        # Should not overwrite
        client = db_session.query(RadiusClient).filter_by(name="localhost").first()
        assert client.ipaddr == "192.168.1.1"  # Original value preserved
        assert client.secret == "different-secret"
        assert client.created_by == "user"  # Original creator preserved
    
    def test_creates_all_required_defaults(self, db_session):
        """Test that all required default configurations are created."""
        init_default_data(db_session.bind)
        
        # Verify localhost client exists
        assert db_session.query(RadiusClient).filter_by(name="localhost").first() is not None
        
        # Verify EAP config exists
        eap_config = db_session.query(RadiusEapConfig).filter_by(
            name="default",
            is_active=True
        ).first()
        assert eap_config is not None
        
        # Verify EAP methods exist
        methods_count = db_session.query(RadiusEapMethod).filter_by(
            eap_config_id=eap_config.id
        ).count()
        assert methods_count == 3
        
        # Verify MAC bypass config exists
        assert db_session.query(RadiusMacBypassConfig).filter_by(
            name="default"
        ).first() is not None
        
        # Verify policies exist
        policies_count = db_session.query(RadiusPolicy).count()
        assert policies_count == 3
