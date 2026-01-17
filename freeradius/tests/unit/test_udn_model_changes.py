"""Unit tests for UDN model changes (USER assignment, optional MAC)."""

import pytest
from sqlalchemy.exc import IntegrityError

from radius_app.db.models import UdnAssignment


@pytest.mark.unit
class TestUdnModelChanges:
    """Test UDN model changes - USER assignment, optional MAC."""
    
    def test_udn_assignment_requires_user_id(self, db):
        """Test that UDN assignment requires user_id."""
        # This should fail because user_id is required
        assignment = UdnAssignment(
            udn_id=100,
            # user_id missing - should fail
            mac_address="aa:bb:cc:dd:ee:ff",
            is_active=True,
        )
        
        db.add(assignment)
        with pytest.raises((IntegrityError, ValueError)):
            db.commit()
    
    def test_udn_assignment_without_mac(self, db):
        """Test that UDN assignment can be created without MAC address."""
        assignment = UdnAssignment(
            udn_id=100,
            user_id=1,  # Required
            # mac_address is optional
            user_email="test@example.com",
            is_active=True,
        )
        
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        
        assert assignment.user_id == 1
        assert assignment.mac_address is None
        assert assignment.udn_id == 100
    
    def test_udn_assignment_with_mac(self, db):
        """Test that UDN assignment can include optional MAC address."""
        assignment = UdnAssignment(
            udn_id=100,
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",  # Optional
            user_email="test@example.com",
            is_active=True,
        )
        
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        
        assert assignment.user_id == 1
        assert assignment.mac_address == "aa:bb:cc:dd:ee:ff"
    
    def test_udn_assignment_repr_without_mac(self, db):
        """Test UDN assignment string representation without MAC."""
        assignment = UdnAssignment(
            udn_id=100,
            user_id=1,
            is_active=True,
        )
        
        repr_str = repr(assignment)
        assert "User 1" in repr_str
        assert "no MAC" in repr_str
        assert "UDN 100" in repr_str
    
    def test_udn_assignment_repr_with_mac(self, db):
        """Test UDN assignment string representation with MAC."""
        assignment = UdnAssignment(
            udn_id=100,
            user_id=1,
            mac_address="aa:bb:cc:dd:ee:ff",
            is_active=True,
        )
        
        repr_str = repr(assignment)
        assert "User 1" in repr_str
        assert "MAC aa:bb:cc:dd:ee:ff" in repr_str
        assert "UDN 100" in repr_str
    
    def test_udn_assignment_unique_udn_id(self, db):
        """Test that UDN ID must be unique."""
        assignment1 = UdnAssignment(
            udn_id=100,
            user_id=1,
            is_active=True,
        )
        db.add(assignment1)
        db.commit()
        
        # Try to create another assignment with same UDN ID
        assignment2 = UdnAssignment(
            udn_id=100,  # Same UDN ID
            user_id=2,
            is_active=True,
        )
        db.add(assignment2)
        
        with pytest.raises(IntegrityError):
            db.commit()
    
    def test_udn_assignment_same_user_multiple_udns(self, db):
        """Test that same user can have multiple UDN assignments (if UDN IDs differ)."""
        assignment1 = UdnAssignment(
            udn_id=100,
            user_id=1,
            is_active=True,
        )
        assignment2 = UdnAssignment(
            udn_id=101,  # Different UDN ID
            user_id=1,  # Same user
            is_active=True,
        )
        
        db.add(assignment1)
        db.add(assignment2)
        db.commit()
        
        # Both should be created successfully
        assert assignment1.id is not None
        assert assignment2.id is not None
        assert assignment1.user_id == assignment2.user_id
        assert assignment1.udn_id != assignment2.udn_id
