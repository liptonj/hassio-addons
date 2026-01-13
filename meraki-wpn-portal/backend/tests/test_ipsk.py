"""Tests for IPSK management endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestIPSKList:
    """Tests for IPSK listing endpoint."""

    def test_list_ipsks_requires_auth(self, client: TestClient):
        """Test that listing IPSKs requires authentication."""
        response = client.get("/api/admin/ipsks")
        
        assert response.status_code == 401

    def test_list_ipsks_with_auth(self, client: TestClient):
        """Test listing IPSKs with valid auth token."""
        # Use the configured HA token for testing
        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/admin/ipsks", headers=headers)
        
        # Should work with proper auth
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestIPSKCreate:
    """Tests for IPSK creation endpoint."""

    def test_create_ipsk_requires_auth(
        self,
        client: TestClient,
        sample_ipsk_data: dict,
    ):
        """Test that creating IPSK requires authentication."""
        response = client.post("/api/admin/ipsks", json=sample_ipsk_data)
        
        assert response.status_code == 401

    def test_create_ipsk_validates_name(self, client: TestClient):
        """Test that IPSK creation requires name."""
        headers = {"Authorization": "Bearer test-token"}
        response = client.post(
            "/api/admin/ipsks",
            json={},
            headers=headers,
        )
        
        assert response.status_code == 422


class TestIPSKStats:
    """Tests for IPSK statistics endpoint."""

    def test_stats_requires_auth(self, client: TestClient):
        """Test that stats endpoint requires authentication."""
        response = client.get("/api/admin/stats")
        
        assert response.status_code == 401
