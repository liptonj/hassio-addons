"""Unit tests for RADIUS profiles (authorization profiles)."""

import pytest
from datetime import datetime, timezone

from radius_app.db.models import RadiusPolicy
from radius_app.schemas.policy import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
)


@pytest.fixture
def sample_profile(db) -> RadiusPolicy:
    """Create sample profile (authorization profile)."""
    profile = RadiusPolicy(
        name="test-profile",
        description="Test RADIUS profile",
        priority=100,
        policy_type="user",
        vlan_id=100,
        vlan_name="TestVLAN",
        bandwidth_limit_up=10000,
        bandwidth_limit_down=50000,
        session_timeout=3600,
        is_active=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@pytest.mark.unit
class TestProfileModel:
    """Test profile model (RadiusPolicy)."""
    
    def test_create_profile(self, db):
        """Test creating a profile."""
        profile = RadiusPolicy(
            name="new-profile",
            description="New profile description",
            priority=50,
            policy_type="user",
            vlan_id=200,
            is_active=True,
        )
        db.add(profile)
        db.commit()
        
        assert profile.id is not None
        assert profile.name == "new-profile"
        assert profile.priority == 50
        assert profile.vlan_id == 200
        assert profile.is_active is True
    
    def test_profile_with_all_fields(self, db):
        """Test profile with all RADIUS attributes."""
        profile = RadiusPolicy(
            name="full-profile",
            description="Full profile with all fields",
            priority=10,
            policy_type="user",
            vlan_id=100,
            vlan_name="Corporate",
            bandwidth_limit_up=100000,
            bandwidth_limit_down=500000,
            session_timeout=7200,
            idle_timeout=600,
            max_concurrent_sessions=5,
            is_active=True,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
        assert profile.id is not None
        assert profile.vlan_id == 100
        assert profile.vlan_name == "Corporate"
        assert profile.bandwidth_limit_up == 100000
        assert profile.bandwidth_limit_down == 500000
        assert profile.session_timeout == 7200
        assert profile.idle_timeout == 600
        assert profile.max_concurrent_sessions == 5
    
    def test_profile_repr(self, sample_profile):
        """Test profile string representation."""
        repr_str = repr(sample_profile)
        # RadiusPolicy has a __repr__ method
        assert sample_profile.name in str(sample_profile)
    
    def test_update_profile(self, db, sample_profile):
        """Test updating a profile."""
        sample_profile.vlan_id = 200
        sample_profile.bandwidth_limit_up = 20000
        db.commit()
        db.refresh(sample_profile)
        
        assert sample_profile.vlan_id == 200
        assert sample_profile.bandwidth_limit_up == 20000
    
    def test_delete_profile(self, db, sample_profile):
        """Test deleting a profile."""
        profile_id = sample_profile.id
        db.delete(sample_profile)
        db.commit()
        
        deleted = db.query(RadiusPolicy).filter(RadiusPolicy.id == profile_id).first()
        assert deleted is None


@pytest.mark.unit
class TestProfileSchemas:
    """Test profile Pydantic schemas."""
    
    def test_policy_create_valid(self):
        """Test creating valid policy schema."""
        data = PolicyCreate(
            name="test-profile",
            description="Test description",
            priority=100,
            policy_type="user",
            vlan_id=100,
            bandwidth_limit_up=10000,
            is_active=True,
        )
        
        assert data.name == "test-profile"
        assert data.priority == 100
        assert data.vlan_id == 100
    
    def test_policy_create_with_minimal_fields(self):
        """Test creating policy with only required fields."""
        data = PolicyCreate(name="minimal-profile")
        
        assert data.name == "minimal-profile"
        assert data.priority == 100  # default
        assert data.is_active is True  # default
    
    def test_policy_update_partial(self):
        """Test partial policy update."""
        data = PolicyUpdate(vlan_id=200)
        
        # Only vlan_id should be set
        assert data.vlan_id == 200
        assert data.name is None
        assert data.bandwidth_limit_up is None
    
    def test_policy_with_session_limits(self):
        """Test policy with session timeout limits."""
        data = PolicyCreate(
            name="session-profile",
            session_timeout=3600,
            idle_timeout=600,
            max_concurrent_sessions=3,
        )
        
        assert data.session_timeout == 3600
        assert data.idle_timeout == 600
        assert data.max_concurrent_sessions == 3


@pytest.mark.unit
class TestProfileVlanValidation:
    """Test VLAN field validation in profiles."""
    
    def test_valid_vlan_id(self):
        """Test valid VLAN ID range."""
        data = PolicyCreate(name="test", vlan_id=1)
        assert data.vlan_id == 1
        
        data = PolicyCreate(name="test", vlan_id=4094)
        assert data.vlan_id == 4094
    
    def test_vlan_id_boundaries(self):
        """Test VLAN ID boundary validation."""
        # VLAN 1 is valid (min)
        data = PolicyCreate(name="test", vlan_id=1)
        assert data.vlan_id == 1
        
        # VLAN 4094 is valid (max)
        data = PolicyCreate(name="test", vlan_id=4094)
        assert data.vlan_id == 4094


@pytest.mark.unit
class TestProfileBandwidthFields:
    """Test bandwidth limit fields."""
    
    def test_bandwidth_limits(self):
        """Test bandwidth limit fields."""
        data = PolicyCreate(
            name="bandwidth-profile",
            bandwidth_limit_up=10000,
            bandwidth_limit_down=50000,
        )
        
        assert data.bandwidth_limit_up == 10000
        assert data.bandwidth_limit_down == 50000
    
    def test_zero_bandwidth(self):
        """Test zero bandwidth (unlimited)."""
        data = PolicyCreate(
            name="unlimited",
            bandwidth_limit_up=0,
            bandwidth_limit_down=0,
        )
        
        assert data.bandwidth_limit_up == 0
        assert data.bandwidth_limit_down == 0
