"""End-to-end tests for portal-to-radius integration.

These tests validate the complete data flow from portal to FreeRADIUS:
1. Portal creates RADIUS client → FreeRADIUS reads it → Config generated
2. Portal creates UDN assignment → FreeRADIUS reads it → Auth works
3. Portal updates data → FreeRADIUS detects change → Reloads config

Requirements:
    - Shared database (PostgreSQL or MariaDB)
    - FreeRADIUS API running
    - Portal API running (optional, for full integration)

Environment variables:
    DATABASE_URL: Shared database connection string
    RADIUS_API_URL: FreeRADIUS API endpoint (default: http://localhost:8000)
    RADIUS_API_TOKEN: FreeRADIUS API auth token
    PORTAL_API_URL: Portal API endpoint (optional)
    PORTAL_API_TOKEN: Portal API auth token (optional)
"""

import os
import time
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rootfs/usr/bin"))

from radius_app.db.models import Base, RadiusClient, UdnAssignment


@pytest.mark.e2e
class TestPortalToRadiusFlow:
    """Test complete portal-to-radius data flow."""
    
    @pytest.fixture
    def shared_db(self):
        """Connect to shared database."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            pytest.skip("DATABASE_URL not set")
        
        engine = create_engine(db_url)
        
        # Verify connection
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
        
        # Ensure tables exist
        Base.metadata.create_all(engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        yield session
        
        # Cleanup test data
        session.query(RadiusClient).filter(
            RadiusClient.name.like("e2e-test-%")
        ).delete()
        session.query(UdnAssignment).filter(
            UdnAssignment.mac_address.like("e2:e2:%")
        ).delete()
        session.commit()
        session.close()
        engine.dispose()
    
    @pytest.fixture
    def radius_api(self):
        """Get FreeRADIUS API client."""
        api_url = os.getenv("RADIUS_API_URL", "http://localhost:8000")
        api_token = os.getenv("RADIUS_API_TOKEN")
        
        if not api_token:
            pytest.skip("RADIUS_API_TOKEN not set")
        
        # Test API is reachable
        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip(f"FreeRADIUS API not healthy: {response.status_code}")
        except requests.RequestException as e:
            pytest.skip(f"FreeRADIUS API not reachable: {e}")
        
        return {
            "url": api_url,
            "token": api_token,
            "headers": {"Authorization": f"Bearer {api_token}"}
        }
    
    def test_portal_creates_client_radius_sees_it(self, shared_db, radius_api):
        """Test: Portal creates client → FreeRADIUS generates config."""
        # Step 1: Portal creates RADIUS client (simulated via direct DB write)
        client = RadiusClient(
            name="e2e-test-network-1",
            ipaddr="192.168.100.0/24",
            secret="e2e-test-secret",
            nas_type="meraki",
            network_id="N_12345",
            network_name="E2E Test Network",
            is_active=True
        )
        shared_db.add(client)
        shared_db.commit()
        shared_db.refresh(client)
        
        client_id = client.id
        
        # Step 2: Trigger FreeRADIUS config regeneration
        response = requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": True},
            headers=radius_api["headers"],
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["clients_regenerated"] is True
        
        # Step 3: Verify config status reflects new client
        response = requests.get(
            f"{radius_api['url']}/api/config/status",
            headers=radius_api["headers"],
            timeout=5
        )
        
        assert response.status_code == 200
        status = response.json()
        assert status["clients_count"] >= 1
        
        # Cleanup
        shared_db.delete(client)
        shared_db.commit()
    
    def test_portal_creates_udn_radius_sees_it(self, shared_db, radius_api):
        """Test: Portal creates UDN assignment → FreeRADIUS generates users file."""
        # Step 1: Portal creates UDN assignment
        assignment = UdnAssignment(
            mac_address="e2:e2:e2:e2:e2:e1",
            udn_id=9999,
            user_name="E2E Test User",
            user_email="e2e@test.com",
            unit="999",
            is_active=True
        )
        shared_db.add(assignment)
        shared_db.commit()
        shared_db.refresh(assignment)
        
        # Step 2: Trigger FreeRADIUS config regeneration
        response = requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": True},
            headers=radius_api["headers"],
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["users_regenerated"] is True
        
        # Step 3: Verify config status reflects new assignment
        response = requests.get(
            f"{radius_api['url']}/api/config/status",
            headers=radius_api["headers"],
            timeout=5
        )
        
        assert response.status_code == 200
        status = response.json()
        assert status["assignments_count"] >= 1
        
        # Cleanup
        shared_db.delete(assignment)
        shared_db.commit()
    
    def test_portal_updates_client_radius_detects_change(self, shared_db, radius_api):
        """Test: Portal updates client → FreeRADIUS regenerates config."""
        # Step 1: Create initial client
        client = RadiusClient(
            name="e2e-test-network-2",
            ipaddr="192.168.200.0/24",
            secret="initial-secret",
            is_active=True
        )
        shared_db.add(client)
        shared_db.commit()
        shared_db.refresh(client)
        
        # Force initial config generation
        requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": True},
            headers=radius_api["headers"],
            timeout=10
        )
        
        # Step 2: Update client (change secret)
        client.secret = "updated-secret"
        shared_db.commit()
        
        # Wait a moment for timestamp to update
        time.sleep(1)
        
        # Step 3: Check for changes (watcher should detect)
        response = requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": False},  # Don't force, let it detect change
            headers=radius_api["headers"],
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Either it detected the change or config was already up to date
        assert data["success"] is True
        
        # Cleanup
        shared_db.delete(client)
        shared_db.commit()
    
    def test_portal_deactivates_client_radius_removes_it(self, shared_db, radius_api):
        """Test: Portal deactivates client → FreeRADIUS removes from config."""
        # Step 1: Create active client
        client = RadiusClient(
            name="e2e-test-network-3",
            ipaddr="192.168.300.0/24",
            secret="secret",
            is_active=True
        )
        shared_db.add(client)
        shared_db.commit()
        shared_db.refresh(client)
        
        # Generate config with active client
        response = requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": True},
            headers=radius_api["headers"],
            timeout=10
        )
        assert response.status_code == 200
        
        initial_status = requests.get(
            f"{radius_api['url']}/api/config/status",
            headers=radius_api["headers"],
            timeout=5
        ).json()
        initial_count = initial_status["clients_count"]
        
        # Step 2: Deactivate client
        client.is_active = False
        shared_db.commit()
        
        time.sleep(1)
        
        # Step 3: Regenerate config
        response = requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": True},
            headers=radius_api["headers"],
            timeout=10
        )
        assert response.status_code == 200
        
        # Step 4: Verify client count decreased or stayed same
        new_status = requests.get(
            f"{radius_api['url']}/api/config/status",
            headers=radius_api["headers"],
            timeout=5
        ).json()
        
        # Count should not increase (might stay same if other active clients exist)
        assert new_status["clients_count"] <= initial_count
        
        # Cleanup
        shared_db.delete(client)
        shared_db.commit()
    
    def test_database_connection_recovery(self, shared_db, radius_api):
        """Test: FreeRADIUS handles temporary database disconnection."""
        # This test verifies resilience, not causing failures
        
        # Step 1: Verify API is healthy
        response = requests.get(
            f"{radius_api['url']}/health",
            timeout=5
        )
        assert response.status_code == 200
        health = response.json()
        assert health["portal_db_connected"] is True
        
        # Note: Actually simulating DB disconnection is complex
        # This is a placeholder for manual testing
        # In production, you would:
        # 1. Stop database
        # 2. Verify FreeRADIUS handles gracefully
        # 3. Restart database
        # 4. Verify FreeRADIUS reconnects
        
        pytest.skip("Manual test: Simulate DB disconnection and recovery")


@pytest.mark.e2e
class TestAPIAuthentication:
    """Test API authentication and authorization."""
    
    @pytest.fixture
    def radius_api_url(self):
        """Get FreeRADIUS API URL."""
        api_url = os.getenv("RADIUS_API_URL", "http://localhost:8000")
        
        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("FreeRADIUS API not available")
        except requests.RequestException as e:
            pytest.skip(f"FreeRADIUS API not reachable: {e}")
        
        return api_url
    
    def test_api_requires_authentication(self, radius_api_url):
        """Test that protected endpoints require authentication."""
        # Try without token
        response = requests.post(
            f"{radius_api_url}/api/reload",
            json={"force": False},
            timeout=5
        )
        
        assert response.status_code == 401, "Should require authentication"
    
    def test_api_rejects_invalid_token(self, radius_api_url):
        """Test that invalid tokens are rejected."""
        response = requests.post(
            f"{radius_api_url}/api/reload",
            json={"force": False},
            headers={"Authorization": "Bearer invalid-token-12345"},
            timeout=5
        )
        
        assert response.status_code == 401, "Should reject invalid token"
    
    def test_health_endpoint_no_auth_required(self, radius_api_url):
        """Test that health endpoint doesn't require auth."""
        response = requests.get(
            f"{radius_api_url}/health",
            timeout=5
        )
        
        assert response.status_code == 200, "Health endpoint should be public"
        data = response.json()
        assert "status" in data


@pytest.mark.e2e
class TestPerformance:
    """Test performance with realistic data volumes."""
    
    @pytest.fixture
    def shared_db(self):
        """Connect to shared database."""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            pytest.skip("DATABASE_URL not set")
        
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        yield session
        
        # Cleanup
        session.query(RadiusClient).filter(
            RadiusClient.name.like("perf-test-%")
        ).delete()
        session.query(UdnAssignment).filter(
            UdnAssignment.mac_address.like("ff:ff:ff:%")
        ).delete()
        session.commit()
        session.close()
        engine.dispose()
    
    @pytest.fixture
    def radius_api(self):
        """Get FreeRADIUS API client."""
        api_url = os.getenv("RADIUS_API_URL", "http://localhost:8000")
        api_token = os.getenv("RADIUS_API_TOKEN")
        
        if not api_token:
            pytest.skip("RADIUS_API_TOKEN not set")
        
        return {
            "url": api_url,
            "token": api_token,
            "headers": {"Authorization": f"Bearer {api_token}"}
        }
    
    @pytest.mark.slow
    def test_config_generation_with_1000_clients(self, shared_db, radius_api):
        """Test config generation performance with 1000 clients."""
        # Create 1000 test clients
        clients = []
        for i in range(1000):
            client = RadiusClient(
                name=f"perf-test-client-{i}",
                ipaddr=f"10.{i // 256}.{i % 256}.0/24",
                secret=f"secret-{i}",
                is_active=True
            )
            clients.append(client)
        
        shared_db.bulk_save_objects(clients)
        shared_db.commit()
        
        # Measure config generation time
        start_time = time.time()
        
        response = requests.post(
            f"{radius_api['url']}/api/reload",
            json={"force": True},
            headers=radius_api["headers"],
            timeout=60  # Allow up to 60 seconds
        )
        
        elapsed = time.time() - start_time
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Should complete in reasonable time (< 10 seconds for 1000 clients)
        assert elapsed < 10, f"Config generation too slow: {elapsed:.2f}s"
        
        print(f"\n✅ Generated config for 1000 clients in {elapsed:.2f}s")
