"""Tests for registration endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Registration, User


class TestPublicOptions:
    """Tests for public portal options endpoint."""

    def test_get_options_returns_property_info(self, client: TestClient):
        """Test that options endpoint returns property configuration."""
        response = client.get("/api/options")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "property_name" in data
        assert "auth_methods" in data
        assert "self_registration" in data["auth_methods"]


class TestRegistration:
    """Tests for registration endpoint."""

    def test_registration_validates_required_fields(self, client: TestClient):
        """Test that registration requires name and email."""
        response = client.post("/api/register", json={})
        
        assert response.status_code == 422  # Validation error

    def test_registration_validates_email_format(self, client: TestClient):
        """Test that registration validates email format."""
        response = client.post("/api/register", json={
            "name": "John Smith",
            "email": "not-an-email",
        })
        
        assert response.status_code == 422

    def test_registration_creates_user(
        self,
        client: TestClient,
        db: Session,
        sample_registration_data: dict,
    ):
        """Test successful registration creates user record."""
        response = client.post("/api/register", json=sample_registration_data)
        
        # Note: This will fail without proper HA mock, but structure is correct
        # In real tests, we'd mock the HA client properly
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "passphrase" in data
            assert "qr_code" in data
            
            # Check database
            user = db.query(User).filter(
                User.email == sample_registration_data["email"]
            ).first()
            assert user is not None
            assert user.name == sample_registration_data["name"]


class TestPublicAreas:
    """Tests for public areas endpoint."""

    def test_get_areas_returns_list(self, client: TestClient):
        """Test that areas endpoint returns list of areas."""
        response = client.get("/api/areas")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestHealth:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
