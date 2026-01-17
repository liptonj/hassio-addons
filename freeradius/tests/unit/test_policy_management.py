"""Unit tests for policy management operations."""

import pytest
from datetime import datetime, time, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, RadiusPolicy
from radius_app.schemas.policy import (
    PolicyCreate,
    PolicyUpdate,
    ReplyAttribute,
    CheckAttribute,
    TimeRestriction,
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
def sample_policy():
    """Sample policy data for testing."""
    return PolicyCreate(
        name="guest-network-policy",
        description="Policy for guest network users",
        priority=100,
        group_name="guests",
        policy_type="user",
        match_username="guest.*",
        match_calling_station=".*",
        vlan_id=100,
        vlan_name="Guest_VLAN",
        bandwidth_limit_up=5000,
        bandwidth_limit_down=10000,
        session_timeout=3600,
        idle_timeout=600,
        reply_attributes=[
            ReplyAttribute(attribute="Reply-Message", operator=":=", value="Guest Access")
        ],
        is_active=True,
    )


class TestPolicyValidation:
    """Test policy data validation."""
    
    def test_valid_policy_creation(self, sample_policy):
        """Test valid policy creation."""
        assert sample_policy.name == "guest-network-policy"
        assert sample_policy.priority == 100
        assert sample_policy.vlan_id == 100
        assert sample_policy.session_timeout == 3600
    
    def test_priority_validation(self):
        """Test priority validation."""
        with pytest.raises(ValueError):
            PolicyCreate(
                name="test",
                priority=1001,  # Too high (> 1000)
            )
        
        with pytest.raises(ValueError):
            PolicyCreate(
                name="test",
                priority=-1,  # Negative not allowed
            )
    
    def test_vlan_id_validation(self):
        """Test VLAN ID validation."""
        with pytest.raises(ValueError):
            PolicyCreate(
                name="test",
                vlan_id=5000,  # Too high (> 4094)
            )
        
        with pytest.raises(ValueError):
            PolicyCreate(
                name="test",
                vlan_id=0,  # Too low (< 1)
            )
    
    def test_bandwidth_limit_validation(self):
        """Test bandwidth limit validation."""
        with pytest.raises(ValueError):
            PolicyCreate(
                name="test",
                bandwidth_limit_up=-100,  # Negative not allowed
            )


class TestPolicyDatabaseOperations:
    """Test policy database operations."""
    
    def test_create_policy(self, db_session, sample_policy):
        """Test creating policy in database."""
        policy = RadiusPolicy(
            name=sample_policy.name,
            description=sample_policy.description,
            priority=sample_policy.priority,
            group_name=sample_policy.group_name,
            policy_type=sample_policy.policy_type,
            match_username=sample_policy.match_username,
            vlan_id=sample_policy.vlan_id,
            vlan_name=sample_policy.vlan_name,
            bandwidth_limit_up=sample_policy.bandwidth_limit_up,
            bandwidth_limit_down=sample_policy.bandwidth_limit_down,
            session_timeout=sample_policy.session_timeout,
            idle_timeout=sample_policy.idle_timeout,
            reply_attributes=[attr.model_dump() for attr in sample_policy.reply_attributes],
            is_active=sample_policy.is_active,
            created_by="test-user",
        )
        db_session.add(policy)
        db_session.commit()
        
        # Verify
        assert policy.id is not None
        assert policy.name == "guest-network-policy"
        assert policy.priority == 100
        assert policy.vlan_id == 100
    
    def test_policy_priority_ordering(self, db_session):
        """Test that policies can be ordered by priority."""
        # Create policies with different priorities
        policy1 = RadiusPolicy(
            name="high-priority",
            priority=10,
            is_active=True,
            created_by="test-user",
        )
        policy2 = RadiusPolicy(
            name="low-priority",
            priority=100,
            is_active=True,
            created_by="test-user",
        )
        policy3 = RadiusPolicy(
            name="medium-priority",
            priority=50,
            is_active=True,
            created_by="test-user",
        )
        
        db_session.add_all([policy1, policy2, policy3])
        db_session.commit()
        
        # Query ordered by priority
        policies = db_session.query(RadiusPolicy).order_by(RadiusPolicy.priority.asc()).all()
        
        assert policies[0].name == "high-priority"
        assert policies[1].name == "medium-priority"
        assert policies[2].name == "low-priority"
    
    def test_update_policy(self, db_session, sample_policy):
        """Test updating policy."""
        policy = RadiusPolicy(
            name=sample_policy.name,
            priority=sample_policy.priority,
            vlan_id=sample_policy.vlan_id,
            is_active=True,
            created_by="test-user",
        )
        db_session.add(policy)
        db_session.commit()
        
        # Update
        policy.priority = 200
        policy.vlan_id = 200
        db_session.commit()
        
        # Verify
        db_session.refresh(policy)
        assert policy.priority == 200
        assert policy.vlan_id == 200
    
    def test_delete_policy(self, db_session, sample_policy):
        """Test deleting policy."""
        policy = RadiusPolicy(
            name=sample_policy.name,
            priority=sample_policy.priority,
            is_active=True,
            created_by="test-user",
        )
        db_session.add(policy)
        db_session.commit()
        
        policy_id = policy.id
        
        # Delete
        db_session.delete(policy)
        db_session.commit()
        
        # Verify
        result = db_session.query(RadiusPolicy).filter_by(id=policy_id).first()
        assert result is None


class TestPolicyAttributes:
    """Test policy attributes (reply and check)."""
    
    def test_reply_attribute_creation(self):
        """Test creating reply attributes."""
        attr = ReplyAttribute(
            attribute="Session-Timeout",
            operator=":=",
            value="3600"
        )
        assert attr.attribute == "Session-Timeout"
        assert attr.operator == ":="
        assert attr.value == "3600"
    
    def test_check_attribute_creation(self):
        """Test creating check attributes."""
        attr = CheckAttribute(
            attribute="NAS-IP-Address",
            operator="==",
            value="192.168.1.1"
        )
        assert attr.attribute == "NAS-IP-Address"
        assert attr.operator == "=="
        assert attr.value == "192.168.1.1"
    
    def test_time_restriction_creation(self):
        """Test creating time restrictions."""
        restriction = TimeRestriction(
            days_of_week=[0, 1, 2, 3, 4],  # Weekdays
            time_start=time(9, 0),
            time_end=time(17, 0),
            timezone="America/New_York"
        )
        assert restriction.days_of_week == [0, 1, 2, 3, 4]
        assert restriction.time_start == time(9, 0)
        assert restriction.time_end == time(17, 0)


class TestPolicyMatching:
    """Test policy matching logic."""
    
    def test_username_pattern_matching(self):
        """Test username pattern matching."""
        import re
        
        pattern = "guest.*"
        
        assert re.match(pattern, "guest123")
        assert re.match(pattern, "guest-user")
        assert not re.match(pattern, "employee123")
    
    def test_mac_address_pattern_matching(self):
        """Test MAC address pattern matching."""
        import re
        
        pattern = "^aa:bb:cc:.*"
        
        assert re.match(pattern, "aa:bb:cc:dd:ee:ff")
        assert not re.match(pattern, "11:22:33:44:55:66")
    
    def test_nas_ip_pattern_matching(self):
        """Test NAS IP pattern matching."""
        import re
        
        pattern = "192\\.168\\.1\\..*"
        
        assert re.match(pattern, "192.168.1.1")
        assert re.match(pattern, "192.168.1.100")
        assert not re.match(pattern, "10.0.0.1")


class TestPolicyUsageTracking:
    """Test policy usage tracking."""
    
    def test_usage_count_increment(self, db_session):
        """Test incrementing usage count."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            usage_count=0,
            is_active=True,
            created_by="test-user",
        )
        db_session.add(policy)
        db_session.commit()
        
        # Increment usage
        policy.usage_count += 1
        policy.last_used = datetime.now(timezone.utc)
        db_session.commit()
        
        # Verify
        db_session.refresh(policy)
        assert policy.usage_count == 1
        assert policy.last_used is not None
    
    def test_last_used_timestamp(self, db_session):
        """Test last used timestamp."""
        policy = RadiusPolicy(
            name="test-policy",
            priority=100,
            last_used=None,
            is_active=True,
            created_by="test-user",
        )
        db_session.add(policy)
        db_session.commit()
        
        # Update last used
        now = datetime.now(timezone.utc)
        policy.last_used = now
        policy.usage_count = 1
        db_session.commit()
        
        # Verify
        db_session.refresh(policy)
        assert policy.last_used is not None
        # Just verify we can store and retrieve the timestamp
        assert policy.usage_count == 1


class TestPolicyGrouping:
    """Test policy grouping functionality."""
    
    def test_policies_by_group(self, db_session):
        """Test querying policies by group."""
        # Create policies in different groups
        policy1 = RadiusPolicy(
            name="guest-1",
            group_name="guests",
            priority=100,
            is_active=True,
            created_by="test-user",
        )
        policy2 = RadiusPolicy(
            name="guest-2",
            group_name="guests",
            priority=110,
            is_active=True,
            created_by="test-user",
        )
        policy3 = RadiusPolicy(
            name="employee-1",
            group_name="employees",
            priority=50,
            is_active=True,
            created_by="test-user",
        )
        
        db_session.add_all([policy1, policy2, policy3])
        db_session.commit()
        
        # Query guest policies
        guest_policies = db_session.query(RadiusPolicy).filter_by(group_name="guests").all()
        assert len(guest_policies) == 2
        
        # Query employee policies
        employee_policies = db_session.query(RadiusPolicy).filter_by(group_name="employees").all()
        assert len(employee_policies) == 1
    
    def test_unique_group_names(self, db_session):
        """Test getting unique group names."""
        # Create policies in different groups
        groups = ["guests", "employees", "contractors", "guests", "employees"]
        for i, group in enumerate(groups):
            policy = RadiusPolicy(
                name=f"policy-{i}",
                group_name=group,
                priority=100 + i,
                is_active=True,
                created_by="test-user",
            )
            db_session.add(policy)
        db_session.commit()
        
        # Get distinct groups
        distinct_groups = db_session.query(RadiusPolicy.group_name).distinct().all()
        unique_groups = {g[0] for g in distinct_groups}
        
        assert len(unique_groups) == 3
        assert "guests" in unique_groups
        assert "employees" in unique_groups
        assert "contractors" in unique_groups
