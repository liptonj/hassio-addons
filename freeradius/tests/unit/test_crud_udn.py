"""Unit tests for UDN assignment CRUD operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, UdnAssignment
from radius_app.schemas.udn_assignments import (
    UdnAssignmentCreate,
    UdnAssignmentUpdate,
    normalize_mac_address,
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
def sample_assignment():
    """Sample UDN assignment data for testing."""
    return UdnAssignmentCreate(
        udn_id=1000,
        mac_address="AA:BB:CC:DD:EE:FF",
        user_id=42,
        registration_id=100,
        user_name="John Doe",
        user_email="john@example.com",
        unit="101",
        network_id="L_123456789",
        ssid_number=1,
        is_active=True,
    )


class TestMacAddressNormalization:
    """Test MAC address normalization."""
    
    def test_normalize_colon_format(self):
        """Test normalizing colon-separated MAC address."""
        mac = normalize_mac_address("AA:BB:CC:DD:EE:FF")
        assert mac == "aa:bb:cc:dd:ee:ff"
    
    def test_normalize_dash_format(self):
        """Test normalizing dash-separated MAC address."""
        mac = normalize_mac_address("AA-BB-CC-DD-EE-FF")
        assert mac == "aa:bb:cc:dd:ee:ff"
    
    def test_normalize_no_separator(self):
        """Test normalizing MAC address without separators."""
        mac = normalize_mac_address("AABBCCDDEEFF")
        assert mac == "aa:bb:cc:dd:ee:ff"
    
    def test_lowercase_conversion(self):
        """Test that MAC address is converted to lowercase."""
        mac = normalize_mac_address("AA:BB:CC:DD:EE:FF")
        assert mac == "aa:bb:cc:dd:ee:ff"
        assert mac == mac.lower()
    
    def test_invalid_length(self):
        """Test rejection of MAC address with invalid length."""
        with pytest.raises(ValueError, match="12 hex characters"):
            normalize_mac_address("AA:BB:CC")
    
    def test_invalid_characters(self):
        """Test rejection of MAC address with invalid characters."""
        with pytest.raises(ValueError, match="hex characters"):
            normalize_mac_address("GG:HH:II:JJ:KK:LL")


class TestUdnValidation:
    """Test UDN assignment validation."""
    
    def test_valid_udn_range(self):
        """Test UDN ID within valid range."""
        assignment = UdnAssignmentCreate(
            udn_id=1000,
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
        )
        assert assignment.udn_id == 1000
    
    def test_udn_minimum_boundary(self):
        """Test UDN ID at minimum boundary."""
        assignment = UdnAssignmentCreate(
            udn_id=2,
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
        )
        assert assignment.udn_id == 2
    
    def test_udn_maximum_boundary(self):
        """Test UDN ID at maximum boundary."""
        assignment = UdnAssignmentCreate(
            udn_id=16777200,
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
        )
        assert assignment.udn_id == 16777200
    
    def test_udn_below_minimum(self):
        """Test rejection of UDN ID below minimum."""
        with pytest.raises(ValueError, match="greater than or equal to 2"):
            UdnAssignmentCreate(
                udn_id=1,
                user_id=1,
                mac_address="aa:bb:cc:dd:ee:ff",
            )
    
    def test_udn_above_maximum(self):
        """Test rejection of UDN ID above maximum."""
        with pytest.raises(ValueError, match="less than or equal to 16777200"):
            UdnAssignmentCreate(
                udn_id=16777201,
                user_id=1,
                mac_address="aa:bb:cc:dd:ee:ff",
            )
    
    def test_udn_auto_assign(self):
        """Test UDN ID can be None for auto-assignment."""
        assignment = UdnAssignmentCreate(
            udn_id=None,
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
        )
        assert assignment.udn_id is None


class TestUdnAssignmentCRUD:
    """Test CRUD operations for UDN assignments."""
    
    def test_create_assignment(self, db_session, sample_assignment):
        """Test creating a UDN assignment."""
        assignment = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment)
        db_session.commit()
        db_session.refresh(assignment)
        
        assert assignment.id is not None
        assert assignment.udn_id == 1000
        assert assignment.mac_address == "aa:bb:cc:dd:ee:ff"
        assert assignment.user_name == "John Doe"
    
    def test_read_assignment(self, db_session, sample_assignment):
        """Test reading a UDN assignment."""
        assignment = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment)
        db_session.commit()
        
        retrieved = db_session.get(UdnAssignment, assignment.id)
        assert retrieved is not None
        assert retrieved.udn_id == 1000
        assert retrieved.mac_address == "aa:bb:cc:dd:ee:ff"
    
    def test_update_assignment(self, db_session, sample_assignment):
        """Test updating a UDN assignment."""
        assignment = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment)
        db_session.commit()
        
        # Update assignment
        assignment.user_name = "Jane Smith"
        assignment.unit = "202"
        db_session.commit()
        
        # Verify update
        retrieved = db_session.get(UdnAssignment, assignment.id)
        assert retrieved.user_name == "Jane Smith"
        assert retrieved.unit == "202"
    
    def test_soft_delete_assignment(self, db_session, sample_assignment):
        """Test soft deleting a UDN assignment."""
        assignment = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment)
        db_session.commit()
        
        # Soft delete
        assignment.is_active = False
        db_session.commit()
        
        # Verify still exists but inactive
        retrieved = db_session.get(UdnAssignment, assignment.id)
        assert retrieved is not None
        assert retrieved.is_active is False
    
    def test_hard_delete_assignment(self, db_session, sample_assignment):
        """Test permanently deleting a UDN assignment."""
        assignment = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment)
        db_session.commit()
        assignment_id = assignment.id
        
        # Hard delete
        db_session.delete(assignment)
        db_session.commit()
        
        # Verify deleted
        retrieved = db_session.get(UdnAssignment, assignment_id)
        assert retrieved is None
    
    def test_mac_address_not_unique(self, db_session, sample_assignment):
        """Test that MAC addresses do NOT need to be unique.
        
        Note: UDN is assigned to USER, not MAC. Multiple assignments
        can share the same MAC (e.g., different users on same device).
        Only UDN ID must be unique.
        """
        # Create first assignment
        assignment1 = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment1)
        db_session.commit()
        
        # Create second assignment with same MAC but different UDN and user
        assignment2_data = sample_assignment.model_dump()
        assignment2_data["udn_id"] = 2000  # Different UDN
        assignment2_data["user_id"] = 99   # Different user
        assignment2 = UdnAssignment(**assignment2_data)
        db_session.add(assignment2)
        db_session.commit()  # Should succeed - MAC is not unique
        
        # Verify both exist
        assert db_session.get(UdnAssignment, assignment1.id) is not None
        assert db_session.get(UdnAssignment, assignment2.id) is not None
    
    def test_unique_udn_constraint(self, db_session, sample_assignment):
        """Test that UDN IDs must be unique."""
        # Create first assignment
        assignment1 = UdnAssignment(**sample_assignment.model_dump())
        db_session.add(assignment1)
        db_session.commit()
        
        # Try to create second assignment with same UDN
        assignment2_data = sample_assignment.model_dump()
        assignment2_data["mac_address"] = "11:22:33:44:55:66"  # Different MAC
        assignment2 = UdnAssignment(**assignment2_data)
        db_session.add(assignment2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()


class TestUdnAssignmentUpdate:
    """Test UDN assignment update schema."""
    
    def test_partial_update(self):
        """Test partial update with UdnAssignmentUpdate schema."""
        update_data = UdnAssignmentUpdate(
            user_name="New Name",
            # Other fields not provided
        )
        
        # Only user_name should be set
        dump = update_data.model_dump(exclude_unset=True)
        assert "user_name" in dump
        assert "mac_address" not in dump
        assert "udn_id" not in dump
    
    def test_update_validation(self):
        """Test that update schema validates fields."""
        # Invalid MAC
        with pytest.raises(ValueError, match="12 hex characters"):
            UdnAssignmentUpdate(mac_address="invalid")
        
        # Invalid UDN range
        with pytest.raises(ValueError, match="greater than or equal to 2"):
            UdnAssignmentUpdate(udn_id=1)


class TestUdnAllocation:
    """Test UDN ID allocation logic."""
    
    def test_allocate_sequential_udns(self, db_session):
        """Test allocating sequential UDN IDs."""
        # Create assignments with UDN IDs 2, 3, 4
        for i in range(2, 5):
            assignment = UdnAssignment(
                udn_id=i,
                user_id=i,  # Required - UDN assigned to user
                mac_address=f"aa:bb:cc:dd:ee:0{i}",
                is_active=True,
            )
            db_session.add(assignment)
        db_session.commit()
        
        # Next available should be 5
        from radius_app.api.udn_assignments import get_next_available_udn
        next_udn = get_next_available_udn(db_session)
        assert next_udn == 5
    
    def test_allocate_with_gaps(self, db_session):
        """Test allocating UDN IDs with gaps."""
        # Create assignments with UDN IDs 2, 4, 6 (skip 3 and 5)
        for i in [2, 4, 6]:
            assignment = UdnAssignment(
                udn_id=i,
                user_id=i,  # Required - UDN assigned to user
                mac_address=f"aa:bb:cc:dd:ee:0{i}",
                is_active=True,
            )
            db_session.add(assignment)
        db_session.commit()
        
        # Next available should be 3 (first gap)
        from radius_app.api.udn_assignments import get_next_available_udn
        next_udn = get_next_available_udn(db_session)
        assert next_udn == 3
