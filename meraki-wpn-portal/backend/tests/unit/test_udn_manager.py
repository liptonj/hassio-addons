"""
Unit tests for UDN (User Defined Network) Manager.

Tests MAC address normalization, UDN ID assignment, Cisco-AVPair formatting,
and RADIUS users file generation.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.udn_manager import (
    UdnManager,
    normalize_mac_address,
    validate_udn_id,
    format_cisco_avpair,
    InvalidMacAddress,
    UdnError,
    UdnPoolExhausted,
    UDN_MIN_ID,
    UDN_MAX_ID,
)
from app.db.models import Base, UdnAssignment


@pytest.fixture
def db_session():
    """Create in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def udn_manager(db_session):
    """Create UDN manager instance."""
    return UdnManager(db_session)


@pytest.mark.unit
@pytest.mark.udn
class TestMacAddressNormalization:
    """Test MAC address normalization and validation."""

    def test_normalize_colon_separated_mac(self):
        """Test normalizing colon-separated MAC address."""
        mac = "AA:BB:CC:DD:EE:FF"
        normalized = normalize_mac_address(mac)
        assert normalized == "aa:bb:cc:dd:ee:ff"

    def test_normalize_dash_separated_mac(self):
        """Test normalizing dash-separated MAC address."""
        mac = "AA-BB-CC-DD-EE-FF"
        normalized = normalize_mac_address(mac)
        assert normalized == "aa:bb:cc:dd:ee:ff"

    def test_normalize_no_separator_mac(self):
        """Test normalizing MAC address without separators."""
        mac = "AABBCCDDEEFF"
        normalized = normalize_mac_address(mac)
        assert normalized == "aa:bb:cc:dd:ee:ff"

    def test_normalize_lowercase_mac(self):
        """Test normalizing already lowercase MAC address."""
        mac = "aa:bb:cc:dd:ee:ff"
        normalized = normalize_mac_address(mac)
        assert normalized == "aa:bb:cc:dd:ee:ff"

    def test_normalize_mixed_case_mac(self):
        """Test normalizing mixed case MAC address."""
        mac = "Aa:Bb:Cc:Dd:Ee:Ff"
        normalized = normalize_mac_address(mac)
        assert normalized == "aa:bb:cc:dd:ee:ff"

    def test_invalid_mac_too_short(self):
        """Test rejection of MAC address that's too short."""
        with pytest.raises(InvalidMacAddress):
            normalize_mac_address("AA:BB:CC:DD:EE")

    def test_invalid_mac_too_long(self):
        """Test rejection of MAC address that's too long."""
        with pytest.raises(InvalidMacAddress):
            normalize_mac_address("AA:BB:CC:DD:EE:FF:00")

    def test_invalid_mac_invalid_characters(self):
        """Test rejection of MAC address with invalid characters."""
        with pytest.raises(InvalidMacAddress):
            normalize_mac_address("GG:HH:II:JJ:KK:LL")

    def test_invalid_mac_wrong_format(self):
        """Test rejection of improperly formatted MAC address."""
        with pytest.raises(InvalidMacAddress):
            normalize_mac_address("AA:BB:CC-DD-EE-FF")  # Mixed separators


@pytest.mark.unit
@pytest.mark.udn
class TestUdnIdValidation:
    """Test UDN ID validation."""

    def test_validate_minimum_udn_id(self):
        """Test validation of minimum UDN ID (2)."""
        assert validate_udn_id(UDN_MIN_ID) is True

    def test_validate_maximum_udn_id(self):
        """Test validation of maximum UDN ID."""
        assert validate_udn_id(UDN_MAX_ID) is True

    def test_validate_mid_range_udn_id(self):
        """Test validation of mid-range UDN ID."""
        assert validate_udn_id(1000) is True

    def test_reject_udn_id_zero(self):
        """Test rejection of UDN ID 0."""
        with pytest.raises(UdnError, match="out of range"):
            validate_udn_id(0)

    def test_reject_udn_id_one(self):
        """Test rejection of UDN ID 1 (reserved by Meraki)."""
        with pytest.raises(UdnError, match="out of range"):
            validate_udn_id(1)

    def test_reject_udn_id_negative(self):
        """Test rejection of negative UDN ID."""
        with pytest.raises(UdnError, match="out of range"):
            validate_udn_id(-1)

    def test_reject_udn_id_too_large(self):
        """Test rejection of UDN ID exceeding maximum."""
        with pytest.raises(UdnError, match="out of range"):
            validate_udn_id(UDN_MAX_ID + 1)


@pytest.mark.unit
@pytest.mark.udn
class TestCiscoAvpairFormatting:
    """Test Cisco-AVPair VSA formatting."""

    def test_format_cisco_avpair_basic(self):
        """Test basic Cisco-AVPair formatting."""
        avpair = format_cisco_avpair(100)
        assert avpair == 'Cisco-AVPair := "udn:private-group-id=100"'

    def test_format_cisco_avpair_minimum_id(self):
        """Test formatting with minimum UDN ID."""
        avpair = format_cisco_avpair(UDN_MIN_ID)
        assert avpair == f'Cisco-AVPair := "udn:private-group-id={UDN_MIN_ID}"'

    def test_format_cisco_avpair_maximum_id(self):
        """Test formatting with maximum UDN ID."""
        avpair = format_cisco_avpair(UDN_MAX_ID)
        assert avpair == f'Cisco-AVPair := "udn:private-group-id={UDN_MAX_ID}"'

    def test_format_cisco_avpair_case_sensitivity(self):
        """Test that Cisco-AVPair format is case-sensitive."""
        avpair = format_cisco_avpair(500)
        
        # Verify exact format
        assert "Cisco-AVPair" in avpair, "Attribute name must be exactly 'Cisco-AVPair'"
        assert "udn:private-group-id" in avpair, "VSA format must be exactly 'udn:private-group-id'"
        assert avpair == 'Cisco-AVPair := "udn:private-group-id=500"'

    def test_format_cisco_avpair_invalid_id(self):
        """Test formatting rejects invalid UDN ID."""
        with pytest.raises(UdnError):
            format_cisco_avpair(0)


@pytest.mark.unit
@pytest.mark.udn
class TestUdnAssignment:
    """Test UDN ID assignment functionality."""

    def test_assign_udn_id_basic(self, udn_manager, db_session):
        """Test basic UDN ID assignment."""
        assignment = udn_manager.assign_udn_id(
            mac_address="AA:BB:CC:DD:EE:FF",
            user_name="Test User",
            user_email="test@example.com",
            unit="101",
        )
        
        assert assignment is not None
        assert assignment.udn_id >= UDN_MIN_ID
        assert assignment.udn_id <= UDN_MAX_ID
        assert assignment.mac_address == "aa:bb:cc:dd:ee:ff"
        assert assignment.user_name == "Test User"
        assert assignment.user_email == "test@example.com"
        assert assignment.unit == "101"
        assert assignment.is_active is True

    def test_assign_udn_id_normalizes_mac(self, udn_manager):
        """Test that MAC address is normalized during assignment."""
        assignment = udn_manager.assign_udn_id(
            mac_address="AA-BB-CC-DD-EE-FF",  # Dash format
            user_name="Test User",
        )
        
        assert assignment.mac_address == "aa:bb:cc:dd:ee:ff"  # Normalized to colon format

    def test_assign_specific_udn_id(self, udn_manager):
        """Test assigning a specific UDN ID."""
        assignment = udn_manager.assign_udn_id(
            mac_address="AA:BB:CC:DD:EE:FF",
            specific_udn_id=1000,
        )
        
        assert assignment.udn_id == 1000

    def test_duplicate_mac_returns_existing_assignment(self, udn_manager):
        """Test that assigning same MAC returns existing assignment."""
        # First assignment
        assignment1 = udn_manager.assign_udn_id(
            mac_address="AA:BB:CC:DD:EE:FF",
            user_name="User 1",
        )
        
        # Try to assign same MAC again
        assignment2 = udn_manager.assign_udn_id(
            mac_address="aa:bb:cc:dd:ee:ff",  # Different format, same MAC
            user_name="User 2",
        )
        
        # Should return same assignment
        assert assignment1.id == assignment2.id
        assert assignment1.udn_id == assignment2.udn_id

    def test_assign_udn_id_conflict_specific_id(self, udn_manager):
        """Test that specific UDN ID assignment detects conflicts."""
        # Assign UDN ID 500 to first MAC
        udn_manager.assign_udn_id(
            mac_address="AA:BB:CC:DD:EE:FF",
            specific_udn_id=500,
        )
        
        # Try to assign same UDN ID to different MAC
        with pytest.raises(UdnError, match="already assigned"):
            udn_manager.assign_udn_id(
                mac_address="11:22:33:44:55:66",
                specific_udn_id=500,
            )

    def test_assign_multiple_different_macs(self, udn_manager):
        """Test assigning UDN IDs to multiple different MACs."""
        assignment1 = udn_manager.assign_udn_id(mac_address="AA:BB:CC:DD:EE:01")
        assignment2 = udn_manager.assign_udn_id(mac_address="AA:BB:CC:DD:EE:02")
        assignment3 = udn_manager.assign_udn_id(mac_address="AA:BB:CC:DD:EE:03")
        
        # Should all have different UDN IDs
        assert assignment1.udn_id != assignment2.udn_id
        assert assignment2.udn_id != assignment3.udn_id
        assert assignment1.udn_id != assignment3.udn_id


@pytest.mark.unit
@pytest.mark.udn
class TestUdnPoolManagement:
    """Test UDN ID pool management."""

    def test_get_next_available_udn_id(self, udn_manager):
        """Test getting next available UDN ID."""
        udn_id = udn_manager.get_next_available_udn_id()
        
        # Should start at minimum ID
        assert udn_id == UDN_MIN_ID

    def test_get_next_available_udn_id_after_assignments(self, udn_manager):
        """Test getting next available ID skips assigned IDs."""
        # Assign first few IDs
        udn_manager.assign_udn_id("AA:BB:CC:DD:EE:01", specific_udn_id=2)
        udn_manager.assign_udn_id("AA:BB:CC:DD:EE:02", specific_udn_id=3)
        udn_manager.assign_udn_id("AA:BB:CC:DD:EE:03", specific_udn_id=4)
        
        # Next available should be 5
        next_id = udn_manager.get_next_available_udn_id()
        assert next_id == 5

    def test_get_udn_pool_status_empty(self, udn_manager):
        """Test pool status with no assignments."""
        status = udn_manager.get_udn_pool_status()
        
        assert status["total"] == UDN_MAX_ID - UDN_MIN_ID + 1
        assert status["assigned"] == 0
        assert status["available"] == status["total"]
        assert status["utilization_percent"] == 0.0

    def test_get_udn_pool_status_with_assignments(self, udn_manager):
        """Test pool status with some assignments."""
        # Assign 10 UDN IDs
        for i in range(10):
            udn_manager.assign_udn_id(f"AA:BB:CC:DD:EE:{i:02X}")
        
        status = udn_manager.get_udn_pool_status()
        
        assert status["assigned"] == 10
        assert status["available"] == status["total"] - 10
        assert status["utilization_percent"] > 0


@pytest.mark.unit
@pytest.mark.udn
class TestUdnLookup:
    """Test UDN assignment lookup operations."""

    def test_get_assignment_by_mac(self, udn_manager):
        """Test looking up assignment by MAC address."""
        # Create assignment
        original = udn_manager.assign_udn_id(
            mac_address="AA:BB:CC:DD:EE:FF",
            user_name="Test User",
        )
        
        # Lookup by MAC
        found = udn_manager.get_assignment_by_mac("aa:bb:cc:dd:ee:ff")
        
        assert found is not None
        assert found.id == original.id
        assert found.udn_id == original.udn_id

    def test_get_assignment_by_mac_not_found(self, udn_manager):
        """Test lookup of non-existent MAC address."""
        found = udn_manager.get_assignment_by_mac("11:22:33:44:55:66")
        assert found is None

    def test_get_assignment_by_udn_id(self, udn_manager):
        """Test looking up assignment by UDN ID."""
        # Create assignment
        original = udn_manager.assign_udn_id(
            mac_address="AA:BB:CC:DD:EE:FF",
            specific_udn_id=1000,
        )
        
        # Lookup by UDN ID
        found = udn_manager.get_assignment_by_udn_id(1000)
        
        assert found is not None
        assert found.id == original.id
        assert found.mac_address == original.mac_address

    def test_get_assignments_by_unit(self, udn_manager):
        """Test looking up all assignments for a unit."""
        # Create multiple assignments for same unit
        udn_manager.assign_udn_id("AA:BB:CC:DD:EE:01", unit="101")
        udn_manager.assign_udn_id("AA:BB:CC:DD:EE:02", unit="101")
        udn_manager.assign_udn_id("AA:BB:CC:DD:EE:03", unit="102")  # Different unit
        
        # Get assignments for unit 101
        assignments = udn_manager.get_assignments_by_unit("101")
        
        assert len(assignments) == 2
        assert all(a.unit == "101" for a in assignments)


@pytest.mark.unit
@pytest.mark.udn
class TestUdnRevocation:
    """Test UDN assignment revocation."""

    def test_revoke_assignment(self, udn_manager):
        """Test revoking a UDN assignment."""
        # Create assignment
        assignment = udn_manager.assign_udn_id(mac_address="AA:BB:CC:DD:EE:FF")
        assert assignment.is_active is True
        
        # Revoke it
        success = udn_manager.revoke_assignment("aa:bb:cc:dd:ee:ff")
        assert success is True
        
        # Verify it's revoked
        found = udn_manager.get_assignment_by_mac("aa:bb:cc:dd:ee:ff")
        assert found is None or found.is_active is False

    def test_revoke_non_existent_assignment(self, udn_manager):
        """Test revoking assignment that doesn't exist."""
        success = udn_manager.revoke_assignment("11:22:33:44:55:66")
        assert success is False


@pytest.mark.unit
@pytest.mark.udn
class TestRadiusUsersFileGeneration:
    """Test RADIUS users file generation."""

    def test_generate_radius_users_entry(self, udn_manager, db_session):
        """Test generating single RADIUS users file entry."""
        # Create assignment
        assignment = udn_manager.assign_udn_id(
            mac_address="aa:bb:cc:dd:ee:ff",
            user_name="Test User",
            unit="101",
            specific_udn_id=500,
        )
        
        # Generate entry
        entry = udn_manager.generate_radius_users_entry(assignment)
        
        # Verify format
        assert "aa:bb:cc:dd:ee:ff" in entry
        assert "Cleartext-Password" in entry
        assert "Cisco-AVPair" in entry
        assert "udn:private-group-id=500" in entry
        assert "Test User" in entry or "Unit 101" in entry

    def test_generate_all_radius_users(self, udn_manager):
        """Test generating complete RADIUS users file."""
        # Create multiple assignments
        udn_manager.assign_udn_id("aa:bb:cc:dd:ee:01", user_name="User 1", specific_udn_id=100)
        udn_manager.assign_udn_id("aa:bb:cc:dd:ee:02", user_name="User 2", specific_udn_id=200)
        udn_manager.assign_udn_id("aa:bb:cc:dd:ee:03", user_name="User 3", specific_udn_id=300)
        
        # Generate users file
        users_file = udn_manager.generate_all_radius_users()
        
        # Verify all assignments included
        assert "aa:bb:cc:dd:ee:01" in users_file
        assert "aa:bb:cc:dd:ee:02" in users_file
        assert "aa:bb:cc:dd:ee:03" in users_file
        
        # Verify UDN IDs included
        assert "udn:private-group-id=100" in users_file
        assert "udn:private-group-id=200" in users_file
        assert "udn:private-group-id=300" in users_file
        
        # Verify default deny rule at end
        assert "DEFAULT Auth-Type := Reject" in users_file
        assert "Authentication failed" in users_file

    def test_generate_radius_users_excludes_inactive(self, udn_manager):
        """Test that inactive assignments are excluded from users file."""
        # Create active assignment
        udn_manager.assign_udn_id("aa:bb:cc:dd:ee:01", specific_udn_id=100)
        
        # Create and revoke another assignment
        udn_manager.assign_udn_id("aa:bb:cc:dd:ee:02", specific_udn_id=200)
        udn_manager.revoke_assignment("aa:bb:cc:dd:ee:02")
        
        # Generate users file
        users_file = udn_manager.generate_all_radius_users()
        
        # Should include active assignment
        assert "aa:bb:cc:dd:ee:01" in users_file
        
        # Should NOT include revoked assignment
        assert "aa:bb:cc:dd:ee:02" not in users_file
