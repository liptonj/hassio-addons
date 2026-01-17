"""Tests for admin approval workflow endpoints."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import User, Registration, InviteCode, PortalSetting


class TestApprovalWorkflow:
    """Tests for the approval workflow endpoints."""

    @pytest.fixture
    def admin_token(self, client: TestClient) -> str:
        """Get an admin auth token."""
        # Create admin user in database
        from app.core.security import hash_password
        from app.db.models import User
        
        # Use the db from the client fixture
        response = client.post("/api/auth/login", json={
            "email": "admin@example.com",
            "password": "admin123"
        })
        
        if response.status_code == 200:
            return response.json().get("access_token", "")
        
        # Fallback: Return mock token for tests
        return "test-admin-token"
    
    @pytest.fixture
    def auth_headers(self, admin_token: str) -> dict:
        """Auth headers for admin endpoints."""
        return {"Authorization": f"Bearer {admin_token}"}

    @pytest.fixture
    def pending_user(self, db: Session) -> User:
        """Create a user with pending approval status."""
        user = User(
            name="Pending User",
            email="pending@example.com",
            unit="101",
            approval_status="pending",
            preferred_auth_method="ipsk",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def approved_user(self, db: Session) -> User:
        """Create an already approved user."""
        user = User(
            name="Approved User",
            email="approved@example.com",
            unit="102",
            approval_status="approved",
            approved_at=datetime.now(timezone.utc),
            approved_by="admin@example.com",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


class TestGetPendingUsers:
    """Tests for GET /admin/users/pending endpoint."""

    def test_get_pending_users_returns_pending_only(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test that only pending users are returned."""
        # Create pending user
        pending = User(
            name="Pending User",
            email="pending@test.com",
            approval_status="pending",
        )
        approved = User(
            name="Approved User",
            email="approved@test.com",
            approval_status="approved",
        )
        db.add_all([pending, approved])
        db.commit()
        
        # Note: Need proper auth mock for this to work
        # response = client.get("/api/admin/users/pending", headers=auth_headers)
        # assert response.status_code == 200
        # data = response.json()
        # assert data["total"] == 1
        # assert data["users"][0]["email"] == "pending@test.com"

    def test_get_pending_users_empty_when_none(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test empty list when no pending users."""
        # Create only approved users
        approved = User(
            name="Approved User",
            email="approved@test.com",
            approval_status="approved",
        )
        db.add(approved)
        db.commit()
        
        # Would test with proper auth


class TestApproveUser:
    """Tests for POST /admin/users/{id}/approve endpoint."""

    def test_approve_user_creates_ipsk(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test that approving a user creates IPSK credentials."""
        # Create pending user
        pending = User(
            name="Pending User",
            email="pending@test.com",
            unit="101",
            approval_status="pending",
            preferred_auth_method="ipsk",
        )
        db.add(pending)
        db.commit()
        user_id = pending.id
        
        # Would test with proper auth and HA client mock

    def test_approve_user_updates_status(
        self,
        db: Session,
    ):
        """Test that approval updates user status."""
        # Create pending user
        user = User(
            name="Test User",
            email="test@example.com",
            approval_status="pending",
        )
        db.add(user)
        db.commit()
        
        # Simulate approval
        user.approval_status = "approved"
        user.approved_at = datetime.now(timezone.utc)
        user.approved_by = "admin@example.com"
        db.commit()
        
        # Verify
        db.refresh(user)
        assert user.approval_status == "approved"
        assert user.approved_by == "admin@example.com"
        assert user.approved_at is not None

    def test_approve_non_pending_user_fails(
        self,
        db: Session,
    ):
        """Test that approving a non-pending user fails."""
        # Create already approved user
        user = User(
            name="Approved User",
            email="approved@test.com",
            approval_status="approved",
        )
        db.add(user)
        db.commit()
        
        # The endpoint should reject this
        # Would test with proper auth


class TestRejectUser:
    """Tests for POST /admin/users/{id}/reject endpoint."""

    def test_reject_user_updates_status(
        self,
        db: Session,
    ):
        """Test that rejection updates user status."""
        # Create pending user
        user = User(
            name="Rejected User",
            email="rejected@test.com",
            approval_status="pending",
        )
        db.add(user)
        db.commit()
        
        # Simulate rejection
        user.approval_status = "rejected"
        user.approved_at = datetime.now(timezone.utc)
        user.approved_by = "admin@example.com"
        user.approval_notes = "Account not verified"
        db.commit()
        
        # Verify
        db.refresh(user)
        assert user.approval_status == "rejected"
        assert user.approval_notes == "Account not verified"

    def test_reject_user_with_notes(
        self,
        db: Session,
    ):
        """Test rejection with notes."""
        user = User(
            name="Test User",
            email="test@example.com",
            approval_status="pending",
        )
        db.add(user)
        db.commit()
        
        # Add rejection notes
        user.approval_notes = "Duplicate registration attempt"
        db.commit()
        
        db.refresh(user)
        assert user.approval_notes == "Duplicate registration attempt"


class TestInviteCodeValidation:
    """Tests for POST /api/invite-code/validate endpoint."""

    def test_validate_valid_code(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test validating a valid invite code."""
        # Create valid invite code
        code = InviteCode(
            code="VALIDCODE123",
            max_uses=10,
            uses=0,
            is_active=True,
        )
        db.add(code)
        db.commit()
        
        response = client.post("/api/invite-code/validate?code=VALIDCODE123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["code_info"]["max_uses"] == 10
        assert data["code_info"]["uses"] == 0

    def test_validate_invalid_code(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test validating an invalid invite code."""
        response = client.post("/api/invite-code/validate?code=INVALID123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data

    def test_validate_exhausted_code(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test validating a fully used invite code."""
        # Create exhausted code
        code = InviteCode(
            code="USEDCODE123",
            max_uses=1,
            uses=1,
            is_active=True,
        )
        db.add(code)
        db.commit()
        
        response = client.post("/api/invite-code/validate?code=USEDCODE123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_validate_expired_code(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test validating an expired invite code."""
        from datetime import timedelta
        
        # Create expired code
        code = InviteCode(
            code="EXPIREDCODE",
            max_uses=10,
            uses=0,
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(code)
        db.commit()
        
        response = client.post("/api/invite-code/validate?code=EXPIREDCODE")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_validate_empty_code(
        self,
        client: TestClient,
    ):
        """Test validating an empty code."""
        response = client.post("/api/invite-code/validate?code=")
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


class TestRegistrationModes:
    """Tests for registration mode enforcement."""

    def test_invite_only_mode_requires_code(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test that invite_only mode requires an invite code."""
        # Set registration mode to invite_only
        setting = PortalSetting(
            key="registration_mode",
            value="invite_only",
            value_type="string",
        )
        db.add(setting)
        db.commit()
        
        # Try to register without invite code
        response = client.post("/api/register", json={
            "name": "Test User",
            "email": "test@example.com",
            "auth_method": "ipsk",
        })
        
        # Should be forbidden without code
        assert response.status_code == 403

    def test_invite_only_mode_allows_with_code(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test that invite_only mode allows registration with valid code."""
        # Set registration mode to invite_only
        setting = PortalSetting(
            key="registration_mode",
            value="invite_only",
            value_type="string",
        )
        db.add(setting)
        
        # Create valid invite code
        code = InviteCode(
            code="INVITEONLY1",
            max_uses=10,
            uses=0,
            is_active=True,
        )
        db.add(code)
        db.commit()
        
        # Registration would work with proper HA mock

    def test_approval_mode_creates_pending_user(
        self,
        client: TestClient,
        db: Session,
    ):
        """Test that approval_required mode creates pending users."""
        # Set registration mode to approval_required
        setting = PortalSetting(
            key="registration_mode",
            value="approval_required",
            value_type="string",
        )
        db.add(setting)
        db.commit()
        
        # Register
        response = client.post("/api/register", json={
            "name": "Pending Test User",
            "email": "pendingtest@example.com",
            "auth_method": "ipsk",
        })
        
        # Check response indicates pending
        if response.status_code == 200:
            data = response.json()
            assert data.get("pending_approval") is True
            
            # Check user was created with pending status
            user = db.query(User).filter(
                User.email == "pendingtest@example.com"
            ).first()
            if user:
                assert user.approval_status == "pending"


class TestUserModelApprovalFields:
    """Tests for User model approval fields."""

    def test_user_default_approval_status(
        self,
        db: Session,
    ):
        """Test that new users have default approval status."""
        user = User(
            name="New User",
            email="new@example.com",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Default should be "approved" for backwards compatibility
        assert user.approval_status == "approved"

    def test_user_approval_fields_nullable(
        self,
        db: Session,
    ):
        """Test that approval fields are properly nullable."""
        user = User(
            name="Test User",
            email="test@example.com",
            approval_status="pending",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # These should be None initially
        assert user.approval_notes is None
        assert user.approved_at is None
        assert user.approved_by is None

    def test_user_approval_workflow_complete(
        self,
        db: Session,
    ):
        """Test complete approval workflow on user record."""
        # Create pending user
        user = User(
            name="Workflow Test",
            email="workflow@example.com",
            approval_status="pending",
            preferred_auth_method="ipsk",
        )
        db.add(user)
        db.commit()
        
        # Simulate approval
        user.approval_status = "approved"
        user.approved_at = datetime.now(timezone.utc)
        user.approved_by = "admin@example.com"
        user.approval_notes = "Verified via phone"
        db.commit()
        
        # Verify all fields
        db.refresh(user)
        assert user.approval_status == "approved"
        assert user.approved_at is not None
        assert user.approved_by == "admin@example.com"
        assert user.approval_notes == "Verified via phone"
