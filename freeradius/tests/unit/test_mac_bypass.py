"""Unit tests for MAC bypass configuration."""

import pytest
from datetime import datetime, timezone

from radius_app.db.models import RadiusMacBypassConfig, RadiusUnlangPolicy
from radius_app.schemas.mac_bypass import (
    MacBypassConfigCreate,
    MacBypassConfigUpdate,
)


@pytest.fixture
def sample_mac_bypass_config(db) -> RadiusMacBypassConfig:
    """Create sample MAC bypass configuration."""
    config = RadiusMacBypassConfig(
        name="test-bypass",
        description="Test MAC bypass configuration",
        mac_addresses=["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"],
        bypass_mode="whitelist",
        require_registration=False,
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@pytest.mark.unit
class TestMacBypassModel:
    """Test MAC bypass model."""
    
    def test_create_mac_bypass_config(self, db):
        """Test creating MAC bypass configuration."""
        config = RadiusMacBypassConfig(
            name="test-config",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            is_active=True,
        )
        db.add(config)
        db.commit()
        
        assert config.id is not None
        assert config.name == "test-config"
        assert config.bypass_mode == "whitelist"
        assert config.is_active is True
    
    def test_mac_bypass_config_repr(self, sample_mac_bypass_config):
        """Test MAC bypass config string representation."""
        repr_str = repr(sample_mac_bypass_config)
        assert "test-bypass" in repr_str
        assert "whitelist" in repr_str
    
    def test_mac_addresses_stored_as_list(self, db):
        """Test that MAC addresses are stored as JSON list."""
        config = RadiusMacBypassConfig(
            name="test",
            mac_addresses=["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"],
            bypass_mode="whitelist",
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        
        assert isinstance(config.mac_addresses, list)
        assert len(config.mac_addresses) == 2
        assert "aa:bb:cc:dd:ee:ff" in config.mac_addresses


@pytest.mark.unit
class TestMacBypassSchemas:
    """Test MAC bypass Pydantic schemas."""
    
    def test_mac_bypass_config_create_valid(self):
        """Test creating valid MAC bypass config."""
        data = MacBypassConfigCreate(
            name="test-config",
            description="Test description",
            mac_addresses=["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff"],
            bypass_mode="whitelist",
            require_registration=True,
            is_active=True,
        )
        
        assert data.name == "test-config"
        assert data.bypass_mode == "whitelist"
        # MAC addresses should be normalized
        assert len(data.mac_addresses) == 2
    
    def test_mac_bypass_config_create_invalid_mode(self):
        """Test creating config with invalid bypass mode."""
        with pytest.raises(ValueError, match="bypass_mode must be"):
            MacBypassConfigCreate(
                name="test",
                bypass_mode="invalid",
            )
    
    def test_mac_bypass_config_update_partial(self):
        """Test partial update of MAC bypass config."""
        update = MacBypassConfigUpdate(
            name="updated-name",
            is_active=False,
        )
        
        assert update.name == "updated-name"
        assert update.is_active is False
        assert update.mac_addresses is None


@pytest.mark.unit
class TestMacBypassAPI:
    """Test MAC bypass API endpoints.
    
    Uses the shared 'client' fixture from conftest.py which properly
    overrides the database dependency to use the test database.
    """
    
    def test_list_mac_bypass_configs(self, client, sample_mac_bypass_config):
        """Test listing MAC bypass configurations."""
        response = client.get(
            "/api/v1/mac-bypass/config",
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(c["name"] == "test-bypass" for c in data)
    
    def test_get_mac_bypass_config(self, client, sample_mac_bypass_config):
        """Test getting specific MAC bypass configuration."""
        response = client.get(
            f"/api/v1/mac-bypass/config/{sample_mac_bypass_config.id}",
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-bypass"
        assert data["bypass_mode"] == "whitelist"
        assert len(data["mac_addresses"]) == 2
    
    def test_create_mac_bypass_config(self, client, db):
        """Test creating new MAC bypass configuration."""
        payload = {
            "name": "new-bypass",
            "description": "New bypass config",
            "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
            "bypass_mode": "whitelist",
            "require_registration": False,
            "is_active": True,
        }
        
        response = client.post(
            "/api/v1/mac-bypass/config",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new-bypass"
        assert data["id"] is not None
        
        # Verify it was created in database
        config = db.query(RadiusMacBypassConfig).filter_by(name="new-bypass").first()
        assert config is not None
    
    def test_create_mac_bypass_config_duplicate_name(self, client, sample_mac_bypass_config):
        """Test creating config with duplicate name fails."""
        payload = {
            "name": "test-bypass",  # Same as existing
            "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
            "bypass_mode": "whitelist",
        }
        
        response = client.post(
            "/api/v1/mac-bypass/config",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()
    
    def test_update_mac_bypass_config(self, client, sample_mac_bypass_config):
        """Test updating MAC bypass configuration."""
        payload = {
            "name": "updated-bypass",
            "mac_addresses": ["11:22:33:44:55:66"],
            "bypass_mode": "blacklist",
        }
        
        response = client.put(
            f"/api/v1/mac-bypass/config/{sample_mac_bypass_config.id}",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-bypass"
        assert data["bypass_mode"] == "blacklist"
    
    def test_delete_mac_bypass_config(self, client, sample_mac_bypass_config):
        """Test deleting MAC bypass configuration."""
        config_id = sample_mac_bypass_config.id
        
        response = client.delete(
            f"/api/v1/mac-bypass/config/{config_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 204
        
        # Verify it was deleted
        response = client.get(
            f"/api/v1/mac-bypass/config/{config_id}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 404
    
    def test_list_mac_bypass_configs_active_only(self, client, db):
        """Test listing only active MAC bypass configurations."""
        # Create active and inactive configs
        active_config = RadiusMacBypassConfig(
            name="active-config",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            is_active=True,
        )
        inactive_config = RadiusMacBypassConfig(
            name="inactive-config",
            mac_addresses=["11:22:33:44:55:66"],
            bypass_mode="whitelist",
            is_active=False,
        )
        db.add(active_config)
        db.add(inactive_config)
        db.commit()
        
        response = client.get(
            "/api/v1/mac-bypass/config?active_only=true",
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert all(c["is_active"] for c in data)
        assert not any(c["name"] == "inactive-config" for c in data)


@pytest.mark.unit
class TestMacBypassPolicyFields:
    """Test MAC bypass configuration with policy ID fields."""
    
    def test_create_mac_bypass_with_policy_ids(self, db):
        """Test creating MAC bypass config with policy IDs."""
        # First create the policies that will be referenced
        registered_policy = RadiusUnlangPolicy(
            name="registered-policy",
            description="Policy for registered MACs",
            priority=100,
            condition_type="always",
            action_type="allow",
            is_active=True,
        )
        unregistered_policy = RadiusUnlangPolicy(
            name="unregistered-policy",
            description="Policy for unregistered MACs",
            priority=50,
            condition_type="always",
            action_type="reject",
            is_active=True,
        )
        db.add(registered_policy)
        db.add(unregistered_policy)
        db.commit()
        db.refresh(registered_policy)
        db.refresh(unregistered_policy)
        
        config = RadiusMacBypassConfig(
            name="policy-test",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            registered_policy_id=registered_policy.id,
            unregistered_policy_id=unregistered_policy.id,
            is_active=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        
        assert config.registered_policy_id == registered_policy.id
        assert config.unregistered_policy_id == unregistered_policy.id
    
    def test_mac_bypass_policy_ids_nullable(self, db):
        """Test that policy IDs are nullable."""
        config = RadiusMacBypassConfig(
            name="no-policies",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            registered_policy_id=None,
            unregistered_policy_id=None,
            is_active=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        
        assert config.registered_policy_id is None
        assert config.unregistered_policy_id is None
    
    def test_mac_bypass_schema_with_policy_ids(self):
        """Test MAC bypass schema includes policy IDs."""
        data = MacBypassConfigCreate(
            name="test-config",
            mac_addresses=["aa:bb:cc:dd:ee:ff"],
            bypass_mode="whitelist",
            registered_policy_id=1,
            unregistered_policy_id=2,
        )
        
        assert data.registered_policy_id == 1
        assert data.unregistered_policy_id == 2
    
    def test_mac_bypass_update_policy_ids(self):
        """Test updating MAC bypass config policy IDs."""
        update = MacBypassConfigUpdate(
            registered_policy_id=5,
            unregistered_policy_id=10,
        )
        
        assert update.registered_policy_id == 5
        assert update.unregistered_policy_id == 10
    
    def test_create_mac_bypass_api_with_policy_ids(self, client, db):
        """Test creating MAC bypass config with policy IDs via API."""
        payload = {
            "name": "api-policy-test",
            "mac_addresses": ["aa:bb:cc:dd:ee:ff"],
            "bypass_mode": "whitelist",
            "registered_policy_id": None,  # Valid but no policy
            "unregistered_policy_id": None,
            "is_active": True,
        }
        
        response = client.post(
            "/api/v1/mac-bypass/config",
            json=payload,
            headers={"Authorization": "Bearer test-token"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["registered_policy_id"] is None
        assert data["unregistered_policy_id"] is None
        # Policy names should also be null
        assert data.get("registered_policy_name") is None
        assert data.get("unregistered_policy_name") is None
