"""Unit tests for authentication configuration API endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from radius_app.db.models import (
    Base,
    RadiusEapConfig,
    RadiusEapMethod,
    RadiusMacBypassConfig,
    RadiusPolicy,
)
from radius_app.main import app


# Use StaticPool to ensure in-memory SQLite works across threads
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def test_client(db_session, monkeypatch):
    """Create test client with database dependency override."""
    # Set API token for testing
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    
    def get_db_override():
        yield db_session
    
    app.dependency_overrides = {}
    from radius_app.db.database import get_db as get_db_original
    app.dependency_overrides[get_db_original] = get_db_override
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    """Admin authentication headers."""
    return {"Authorization": "Bearer test-token"}


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
    
    # Create EAP methods
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
        description="Test MAC bypass",
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
            name="test-policy-1",
            description="Test policy 1",
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
            name="test-policy-2",
            description="Test policy 2",
            priority=50,
            is_active=True,
            psk_validation_required=False,
            mac_matching_enabled=True,
            match_on_psk_only=False,
            include_udn=False,
            splash_url="/splash",
            unregistered_group_policy="unregistered",
            created_by="test",
        ),
    ]
    for policy in policies:
        db_session.add(policy)
    db_session.commit()
    return policies


class TestAuthConfigAPI:
    """Test authentication configuration API endpoint."""
    
    def test_get_auth_config_empty(self, test_client, admin_headers):
        """Test getting auth config when database is empty."""
        response = test_client.get("/api/v1/auth-config", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "mac_bypass_configs" in data
        assert "eap_config" in data
        assert "authorization_policies" in data
        assert "summary" in data
        
        assert data["mac_bypass_configs"] == []
        assert data["eap_config"] is None
        assert data["authorization_policies"] == []
        
        summary = data["summary"]
        assert summary["mac_bypass_configs_count"] == 0
        assert summary["enabled_eap_methods_count"] == 0
        assert summary["authorization_policies_count"] == 0
    
    def test_get_auth_config_with_eap(
        self, test_client, admin_headers, db_session, sample_eap_config
    ):
        """Test getting auth config with EAP configuration."""
        response = test_client.get("/api/v1/auth-config", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["eap_config"] is not None
        eap_config = data["eap_config"]
        
        assert eap_config["name"] == "test-eap"
        assert eap_config["default_eap_type"] == "peap"
        assert set(eap_config["enabled_methods"]) == {"peap", "ttls", "tls"}
        assert eap_config["tls_min_version"] == "1.2"
        assert eap_config["tls_max_version"] == "1.3"
        assert eap_config["is_active"] is True
        
        assert len(eap_config["methods"]) == 3
        method_names = {m["method_name"] for m in eap_config["methods"]}
        assert method_names == {"peap", "ttls", "tls"}
        
        # Check method statistics
        for method in eap_config["methods"]:
            assert method["is_enabled"] is True
            assert method["auth_attempts"] == 100
            assert method["auth_successes"] == 95
            assert method["auth_failures"] == 5
            assert method["success_rate"] == 95.0
    
    def test_get_auth_config_with_mac_bypass(
        self, test_client, admin_headers, db_session, sample_mac_bypass
    ):
        """Test getting auth config with MAC bypass configuration."""
        response = test_client.get("/api/v1/auth-config", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["mac_bypass_configs"]) == 1
        bypass_config = data["mac_bypass_configs"][0]
        
        assert bypass_config["name"] == "test-bypass"
        assert bypass_config["description"] == "Test MAC bypass"
        assert bypass_config["bypass_mode"] == "whitelist"
        assert bypass_config["require_registration"] is False
        assert bypass_config["is_active"] is True
        assert len(bypass_config["mac_addresses"]) == 2
        assert "aa:bb:cc:dd:ee:ff" in bypass_config["mac_addresses"]
        assert "11:22:33:44:55:66" in bypass_config["mac_addresses"]
    
    def test_get_auth_config_with_policies(
        self, test_client, admin_headers, db_session, sample_policies
    ):
        """Test getting auth config with authorization policies."""
        response = test_client.get("/api/v1/auth-config", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["authorization_policies"]) == 2
        
        # Policies should be sorted by priority (ascending)
        policies = data["authorization_policies"]
        assert policies[0]["name"] == "test-policy-2"  # Priority 50
        assert policies[1]["name"] == "test-policy-1"  # Priority 100
        
        # Check first policy
        policy1 = policies[0]
        assert policy1["priority"] == 50
        assert policy1["splash_url"] == "/splash"
        assert policy1["unregistered_group_policy"] == "unregistered"
        assert policy1["mac_matching_enabled"] is True
        assert policy1["match_on_psk_only"] is False
        
        # Check second policy
        policy2 = policies[1]
        assert policy2["priority"] == 100
        assert policy2["registered_group_policy"] == "registered"
        assert policy2["psk_validation_required"] is True
        assert policy2["match_on_psk_only"] is True
        assert policy2["include_udn"] is True
    
    def test_get_auth_config_complete(
        self,
        test_client,
        admin_headers,
        db_session,
        sample_eap_config,
        sample_mac_bypass,
        sample_policies,
    ):
        """Test getting complete auth config with all components."""
        response = test_client.get("/api/v1/auth-config", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all components present
        assert len(data["mac_bypass_configs"]) == 1
        assert data["eap_config"] is not None
        assert len(data["authorization_policies"]) == 2
        
        # Verify summary statistics
        summary = data["summary"]
        assert summary["mac_bypass_configs_count"] == 1
        assert summary["active_mac_bypass_configs"] == 1
        assert summary["total_mac_addresses"] == 2
        assert summary["eap_config_active"] is True
        assert summary["enabled_eap_methods_count"] == 3
        assert set(summary["enabled_eap_methods"]) == {"peap", "ttls", "tls"}
        assert summary["authorization_policies_count"] == 2
        assert summary["active_policies_count"] == 2
        assert summary["policies_with_udn"] == 1
        assert summary["policies_with_splash_url"] == 1
        assert summary["psk_only_policies"] == 1
    
    def test_get_auth_config_active_only(
        self, test_client, admin_headers, db_session
    ):
        """Test filtering by active status."""
        # Create inactive configs
        inactive_eap = RadiusEapConfig(
            name="inactive-eap",
            default_eap_type="tls",
            enabled_methods=["tls"],
            is_active=False,
            created_by="test",
        )
        db_session.add(inactive_eap)
        
        inactive_bypass = RadiusMacBypassConfig(
            name="inactive-bypass",
            mac_addresses=[],
            is_active=False,
            created_by="test",
        )
        db_session.add(inactive_bypass)
        
        inactive_policy = RadiusPolicy(
            name="inactive-policy",
            priority=100,
            is_active=False,
            created_by="test",
        )
        db_session.add(inactive_policy)
        db_session.commit()
        
        # Request active only (default)
        response = test_client.get("/api/v1/auth-config", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include inactive configs
        assert data["eap_config"] is None
        assert len(data["mac_bypass_configs"]) == 0
        assert len(data["authorization_policies"]) == 0
    
    def test_get_auth_config_unauthorized(self, test_client):
        """Test that unauthenticated requests are rejected."""
        response = test_client.get("/api/v1/auth-config")
        
        assert response.status_code == 401
    
    def test_get_auth_config_invalid_token(self, test_client):
        """Test that invalid token is rejected."""
        response = test_client.get(
            "/api/v1/auth-config",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401
