"""Unit tests for unlang authorization policies with profile linking."""

import pytest
from datetime import datetime, timezone

from radius_app.db.models import RadiusUnlangPolicy, RadiusPolicy
from radius_app.schemas.unlang_policy import (
    UnlangPolicyCreate,
    UnlangPolicyUpdate,
    UnlangPolicyResponse,
)


@pytest.fixture
def sample_profile(db) -> RadiusPolicy:
    """Create sample profile for linking."""
    profile = RadiusPolicy(
        name="link-test-profile",
        description="Profile for linking tests",
        priority=100,
        policy_type="user",
        vlan_id=100,
        is_active=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@pytest.fixture
def sample_unlang_policy(db, sample_profile) -> RadiusUnlangPolicy:
    """Create sample unlang policy with profile link."""
    policy = RadiusUnlangPolicy(
        name="test-unlang-policy",
        description="Test unlang authorization policy",
        priority=50,
        policy_type="authorization",
        section="authorize",
        condition_type="attribute",
        condition_attribute="User-Name",
        condition_operator="exists",
        action_type="apply_profile",
        authorization_profile_id=sample_profile.id,
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@pytest.mark.unit
class TestUnlangPolicyModel:
    """Test unlang policy model."""
    
    def test_create_unlang_policy(self, db):
        """Test creating unlang policy."""
        policy = RadiusUnlangPolicy(
            name="new-policy",
            description="New unlang policy",
            priority=100,
            policy_type="authorization",
            section="authorize",
            condition_type="attribute",
            action_type="accept",
            is_active=True,
        )
        db.add(policy)
        db.commit()
        
        assert policy.id is not None
        assert policy.name == "new-policy"
        assert policy.section == "authorize"
        assert policy.action_type == "accept"
    
    def test_unlang_policy_with_profile_link(self, db, sample_profile):
        """Test unlang policy linked to profile."""
        policy = RadiusUnlangPolicy(
            name="linked-policy",
            priority=50,
            section="authorize",
            condition_type="attribute",
            action_type="apply_profile",
            authorization_profile_id=sample_profile.id,
            is_active=True,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        assert policy.authorization_profile_id == sample_profile.id
    
    def test_unlang_policy_with_conditions(self, db):
        """Test unlang policy with attribute conditions."""
        policy = RadiusUnlangPolicy(
            name="condition-policy",
            priority=100,
            section="authorize",
            condition_type="attribute",
            condition_attribute="Calling-Station-Id",
            condition_operator="=~",
            condition_value="^aa:bb:.*",
            action_type="accept",
            is_active=True,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        assert policy.condition_attribute == "Calling-Station-Id"
        assert policy.condition_operator == "=~"
        assert policy.condition_value == "^aa:bb:.*"
    
    def test_unlang_policy_repr(self, sample_unlang_policy):
        """Test unlang policy string representation."""
        assert sample_unlang_policy.name in str(sample_unlang_policy)


@pytest.mark.unit
class TestUnlangPolicySchemas:
    """Test unlang policy Pydantic schemas."""
    
    def test_unlang_policy_create_valid(self):
        """Test creating valid unlang policy schema."""
        data = UnlangPolicyCreate(
            name="test-policy",
            description="Test description",
            priority=50,
            policy_type="authorization",
            section="authorize",
            condition_type="attribute",
            condition_attribute="User-Name",
            condition_operator="exists",
            action_type="apply_profile",
            authorization_profile_id=1,
            is_active=True,
        )
        
        assert data.name == "test-policy"
        assert data.priority == 50
        assert data.authorization_profile_id == 1
    
    def test_unlang_policy_create_minimal(self):
        """Test creating policy with minimal fields."""
        data = UnlangPolicyCreate(name="minimal-policy")
        
        assert data.name == "minimal-policy"
        assert data.priority == 100  # default
        assert data.is_active is True  # default
    
    def test_unlang_policy_update_partial(self):
        """Test partial unlang policy update."""
        update = UnlangPolicyUpdate(authorization_profile_id=5)
        
        assert update.authorization_profile_id == 5
        assert update.name is None


@pytest.mark.unit  
class TestUnlangPolicyProfileLinking:
    """Test profile linking functionality."""
    
    def test_policy_links_to_profile(self, db, sample_profile):
        """Test that policy correctly links to profile."""
        policy = RadiusUnlangPolicy(
            name="linking-test",
            priority=100,
            section="authorize",
            condition_type="attribute",
            action_type="apply_profile",
            authorization_profile_id=sample_profile.id,
            is_active=True,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        assert policy.authorization_profile_id == sample_profile.id
        
        # Verify the profile exists
        linked_profile = db.query(RadiusPolicy).filter(
            RadiusPolicy.id == policy.authorization_profile_id
        ).first()
        assert linked_profile is not None
        assert linked_profile.name == "link-test-profile"
    
    def test_policy_without_profile_link(self, db):
        """Test policy without profile link (reject action)."""
        policy = RadiusUnlangPolicy(
            name="reject-policy",
            priority=100,
            section="authorize",
            condition_type="attribute",
            action_type="reject",
            authorization_profile_id=None,
            is_active=True,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        assert policy.authorization_profile_id is None
        assert policy.action_type == "reject"
    
    def test_update_policy_profile_link(self, db, sample_unlang_policy, sample_profile):
        """Test updating policy's profile link."""
        # Create a new profile to link to
        new_profile = RadiusPolicy(
            name="new-link-profile",
            priority=50,
            policy_type="user",
            vlan_id=200,
            is_active=True,
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)
        
        # Update policy to link to new profile
        sample_unlang_policy.authorization_profile_id = new_profile.id
        db.commit()
        db.refresh(sample_unlang_policy)
        
        assert sample_unlang_policy.authorization_profile_id == new_profile.id
