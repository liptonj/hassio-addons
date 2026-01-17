"""Unit tests for performance testing API endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, RadiusClient
from radius_app.main import app


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    # Use shared cache for in-memory database so connections can share the same database
    engine = create_engine(
        "sqlite:///:memory:?cache=shared",
        connect_args={"check_same_thread": False},
        poolclass=None,
        pool_pre_ping=True
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def test_client(db_session, monkeypatch):
    """Create test client with database dependency override."""
    # Set API token for testing
    monkeypatch.setenv("API_AUTH_TOKEN", "test-token")
    
    # Ensure tables are created - get engine from session and create tables
    engine = db_session.get_bind()
    if engine:
        # Force table creation - this ensures tables exist for all tests
        Base.metadata.create_all(bind=engine, checkfirst=True)
        # Commit any pending changes to ensure tables are visible
        db_session.commit()
    
    def get_db_override():
        # Return the same db_session that has tables created
        try:
            yield db_session
        finally:
            pass  # Don't close session here, fixture handles it
    
    app.dependency_overrides = {}
    from radius_app.db.database import get_db as get_db_original
    app.dependency_overrides[get_db_original] = get_db_override
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    """Admin authentication headers."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def mock_performance_tester():
    """Mock performance tester."""
    with patch('radius_app.api.performance.get_performance_tester') as mock:
        tester = MagicMock()
        tester.radclient_available = True
        tester.create_test_file.return_value = MagicMock(exists=lambda: True, unlink=lambda: None)
        tester.run_performance_test.return_value = MagicMock(
            total_requests=100,
            successful_requests=100,
            failed_requests=0,
            elapsed_time=2.5,
            requests_per_second=40.0,
            average_latency_ms=25.0,
            p50_latency_ms=25.0,
            p95_latency_ms=37.5,
            p99_latency_ms=50.0,
            latencies=[],
            output="Test output",
            error=None
        )
        tester.benchmark_configuration.return_value = {
            "results": [],
            "average": tester.run_performance_test.return_value,
            "iterations": 3
        }
        mock.return_value = tester
        yield tester


@pytest.fixture
def mock_test_user_generator():
    """Mock test user generator."""
    with patch('radius_app.api.performance.get_test_user_generator') as mock:
        generator = MagicMock()
        generator.generate_users.return_value = [
            {"username": f"testuser{i:06d}", "password": f"password{i}"}
            for i in range(100)
        ]
        generator.generate_mac_based_users.return_value = [
            {"username": f"aa:bb:cc:00:00:{i:02x}", "password": f"password{i}"}
            for i in range(100)
        ]
        mock.return_value = generator
        yield generator


class TestPerformanceAPI:
    """Test performance testing API endpoints."""
    
    def test_get_performance_status(self, test_client, admin_headers):
        """Test getting performance test status."""
        with patch('radius_app.api.performance.get_performance_tester') as mock:
            tester = MagicMock()
            tester.radclient_available = True
            mock.return_value = tester
            
            response = test_client.get(
                "/api/v1/performance/status",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["radclient_available"] is True
            assert "capabilities" in data
            assert "limits" in data
    
    def test_run_performance_test_basic(
        self, test_client, admin_headers, mock_performance_tester, mock_test_user_generator
    ):
        """Test basic performance test."""
        response = test_client.post(
            "/api/v1/performance/test",
            headers=admin_headers,
            json={
                "num_users": 100,
                "iterations": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_requests"] == 100
        assert data["successful_requests"] == 100
        assert data["requests_per_second"] == 40.0
    
    def test_run_performance_test_with_client(
        self, test_client, admin_headers, mock_performance_tester, mock_test_user_generator, db_session
    ):
        """Test performance test with client ID."""
        # Create test client in the database
        client = RadiusClient(
            name="test-client",
            ipaddr="192.168.1.100",
            secret="test-secret",
            is_active=True
        )
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)
        
        # The test_client fixture already sets up the db dependency override
        # Just make the API call
        response = test_client.post(
            "/api/v1/performance/test",
            headers=admin_headers,
            json={
                "client_id": client.id,
                "num_users": 50
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_run_performance_test_benchmark(
        self, test_client, admin_headers, mock_performance_tester, mock_test_user_generator
    ):
        """Test benchmark mode (multiple iterations)."""
        response = test_client.post(
            "/api/v1/performance/test",
            headers=admin_headers,
            json={
                "num_users": 100,
                "iterations": 3
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["iterations"] == 3
    
    def test_run_performance_test_mac_addresses(
        self, test_client, admin_headers, mock_performance_tester, mock_test_user_generator
    ):
        """Test performance test with MAC addresses."""
        response = test_client.post(
            "/api/v1/performance/test",
            headers=admin_headers,
            json={
                "num_users": 100,
                "use_mac_addresses": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify MAC-based users were generated
        mock_test_user_generator.generate_mac_based_users.assert_called_once()
    
    def test_run_performance_test_radclient_not_available(
        self, test_client, admin_headers
    ):
        """Test performance test when radclient not available."""
        with patch('radius_app.api.performance.get_performance_tester') as mock:
            tester = MagicMock()
            tester.radclient_available = False
            mock.return_value = tester
            
            response = test_client.post(
                "/api/v1/performance/test",
                headers=admin_headers,
                json={"num_users": 100}
            )
            
            assert response.status_code == 503
            data = response.json()
            assert "radclient" in data["detail"].lower()
    
    def test_run_performance_test_client_not_found(
        self, test_client, admin_headers, mock_performance_tester, mock_test_user_generator, db_session
    ):
        """Test performance test with non-existent client."""
        # Ensure database tables exist - create and keep a dummy client to ensure table exists
        # This is similar to test_run_performance_test_with_client which passes
        # SQLite in-memory databases need at least one row to properly recognize the table
        dummy_client = RadiusClient(
            name="dummy-client",
            ipaddr="127.0.0.1",
            secret="dummy-secret",
            is_active=True
        )
        db_session.add(dummy_client)
        db_session.commit()
        db_session.refresh(dummy_client)
        
        # Keep the dummy client (don't delete) - SQLite needs it to recognize the table
        # Now test with a different non-existent client ID
        response = test_client.post(
            "/api/v1/performance/test",
            headers=admin_headers,
            json={
                "client_id": 99999,  # Different ID than dummy_client.id
                "num_users": 100
            }
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_run_performance_test_validation_error(
        self, test_client, admin_headers
    ):
        """Test performance test with validation errors."""
        response = test_client.post(
            "/api/v1/performance/test",
            headers=admin_headers,
            json={
                "num_users": 0  # Invalid: must be >= 1
            }
        )
        
        assert response.status_code == 422
    
    def test_run_performance_test_unauthorized(self, test_client):
        """Test performance test without authentication."""
        response = test_client.post(
            "/api/v1/performance/test",
            json={"num_users": 100}
        )
        
        assert response.status_code == 401
