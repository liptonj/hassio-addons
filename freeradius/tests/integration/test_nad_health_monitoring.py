"""Integration tests for NAD health monitoring."""

import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from radius_app.db.models import Base, RadiusClient, RadiusNadExtended, RadiusNadHealth
from radius_app.core.health_monitor import HealthMonitor


@pytest.fixture
def db_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create test database session."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_nad_in_db(db_session):
    """Create sample NAD in database."""
    client = RadiusClient(
        name="test-nad",
        ipaddr="127.0.0.1",  # Localhost for testing
        secret="SecureTestSecret123!",
        nas_type="other",
        is_active=True,
        created_by="test-user",
    )
    db_session.add(client)
    db_session.flush()
    
    extended = RadiusNadExtended(
        radius_client_id=client.id,
        vendor="Test Vendor",
        model="Test Model",
    )
    db_session.add(extended)
    db_session.flush()
    
    health = RadiusNadHealth(
        nad_id=extended.id,
        is_reachable=False,
        request_count=0,
        success_count=0,
        failure_count=0,
    )
    db_session.add(health)
    db_session.commit()
    
    return {"client": client, "extended": extended, "health": health}


class TestHealthMonitor:
    """Test health monitoring functionality."""
    
    def test_health_monitor_initialization(self):
        """Test health monitor initialization."""
        monitor = HealthMonitor(check_interval=30)
        assert monitor.check_interval == 30
        assert monitor.running is False
    
    def test_connectivity_test_localhost(self):
        """Test connectivity to localhost."""
        monitor = HealthMonitor()
        
        # Test localhost (should be reachable, though port might be closed)
        is_reachable, latency = monitor._test_nad_connectivity("127.0.0.1")
        
        # Localhost should respond (even if connection refused)
        assert isinstance(is_reachable, bool)
        if latency:
            assert latency >= 0
    
    def test_connectivity_test_unreachable(self):
        """Test connectivity to unreachable host."""
        monitor = HealthMonitor()
        
        # Test unreachable IP (private network, likely no response)
        is_reachable, latency = monitor._test_nad_connectivity("192.0.2.1")
        
        # Should timeout or fail
        assert is_reachable is False
        assert latency is None
    
    def test_connectivity_test_cidr_extraction(self):
        """Test CIDR notation handling."""
        monitor = HealthMonitor()
        
        # Should extract IP from CIDR
        is_reachable, latency = monitor._test_nad_connectivity("127.0.0.1/32")
        
        # Should work with extracted IP
        assert isinstance(is_reachable, bool)
    
    @pytest.mark.asyncio
    async def test_check_all_nads(self, db_session, sample_nad_in_db):
        """Test checking all NADs."""
        monitor = HealthMonitor(check_interval=10)
        
        # Run check
        checked_count = await monitor.check_all_nads(db_session)
        
        # Should have checked 1 NAD
        assert checked_count == 1
        
        # Verify health record was updated
        health = db_session.query(RadiusNadHealth).filter_by(
            nad_id=sample_nad_in_db["extended"].id
        ).first()
        
        assert health is not None
        assert health.checked_at is not None
        # Localhost should be reachable (even if port closed)
        # is_reachable can be True or False depending on whether port 1812 is open
    
    @pytest.mark.asyncio
    async def test_health_monitor_creates_missing_records(self, db_session):
        """Test that health monitor creates missing extended/health records."""
        # Create client without extended info
        client = RadiusClient(
            name="test-client-no-extended",
            ipaddr="192.168.1.1",
            secret="SecureTestSecret123!",
            nas_type="other",
            is_active=True,
            created_by="test-user",
        )
        db_session.add(client)
        db_session.commit()
        
        monitor = HealthMonitor()
        
        # Run check
        checked_count = await monitor.check_all_nads(db_session)
        
        # Should have checked and created records
        assert checked_count == 1
        
        # Verify extended and health records were created
        extended = db_session.query(RadiusNadExtended).filter_by(
            radius_client_id=client.id
        ).first()
        assert extended is not None
        
        health = db_session.query(RadiusNadHealth).filter_by(
            nad_id=extended.id
        ).first()
        assert health is not None
    
    @pytest.mark.asyncio
    async def test_health_monitor_updates_last_seen(self, db_session, sample_nad_in_db):
        """Test that last_seen is updated when reachable."""
        monitor = HealthMonitor()
        health = sample_nad_in_db["health"]
        
        # Record time before check
        time_before = datetime.now(timezone.utc)
        
        # Run check
        await monitor.check_all_nads(db_session)
        
        # Refresh health record
        db_session.refresh(health)
        
        # If reachable, last_seen should be updated
        if health.is_reachable:
            assert health.last_seen is not None
            assert health.last_seen >= time_before
    
    @pytest.mark.asyncio
    async def test_health_monitor_calculates_avg_response_time(self, db_session, sample_nad_in_db):
        """Test average response time calculation."""
        monitor = HealthMonitor()
        health = sample_nad_in_db["health"]
        
        # Set initial average
        health.avg_response_time_ms = 20.0
        health.is_reachable = True
        db_session.commit()
        
        # Run check (if reachable, will update avg)
        await monitor.check_all_nads(db_session)
        
        # Refresh
        db_session.refresh(health)
        
        # If still reachable, average should be updated
        if health.is_reachable and health.avg_response_time_ms:
            # Average should have changed (weighted average)
            assert isinstance(health.avg_response_time_ms, float)
    
    @pytest.mark.asyncio
    async def test_health_monitor_skips_inactive_nads(self, db_session):
        """Test that inactive NADs are not checked."""
        # Create inactive client
        client = RadiusClient(
            name="inactive-nad",
            ipaddr="192.168.1.1",
            secret="SecureTestSecret123!",
            nas_type="other",
            is_active=False,  # Inactive
            created_by="test-user",
        )
        db_session.add(client)
        db_session.commit()
        
        monitor = HealthMonitor()
        
        # Run check
        checked_count = await monitor.check_all_nads(db_session)
        
        # Should not have checked inactive NAD
        assert checked_count == 0
    
    @pytest.mark.asyncio
    async def test_health_monitor_handles_multiple_nads(self, db_session):
        """Test checking multiple NADs."""
        # Create multiple NADs
        for i in range(3):
            client = RadiusClient(
                name=f"test-nad-{i}",
                ipaddr=f"192.168.1.{i+1}",
                secret="SecureTestSecret123!",
                nas_type="other",
                is_active=True,
                created_by="test-user",
            )
            db_session.add(client)
        
        db_session.commit()
        
        monitor = HealthMonitor()
        
        # Run check
        checked_count = await monitor.check_all_nads(db_session)
        
        # Should have checked all 3 NADs
        assert checked_count == 3
        
        # Verify all have extended and health records
        extended_count = db_session.query(RadiusNadExtended).count()
        health_count = db_session.query(RadiusNadHealth).count()
        
        assert extended_count == 3
        assert health_count == 3


class TestHealthMonitorErrorHandling:
    """Test error handling in health monitor."""
    
    @pytest.mark.asyncio
    async def test_health_monitor_handles_db_errors(self, db_session):
        """Test health monitor handles database errors gracefully."""
        monitor = HealthMonitor()
        
        # Close session to simulate error
        db_session.close()
        
        # Should handle error and return 0
        checked_count = await monitor.check_all_nads(db_session)
        
        # Error handled, no NADs checked
        assert checked_count == 0
    
    def test_connectivity_test_handles_invalid_ip(self):
        """Test connectivity test handles invalid IP."""
        monitor = HealthMonitor()
        
        # Invalid IP should be handled
        is_reachable, latency = monitor._test_nad_connectivity("invalid-ip")
        
        # Should fail gracefully
        assert is_reachable is False
        assert latency is None
    
    def test_connectivity_test_handles_empty_ip(self):
        """Test connectivity test handles empty IP."""
        monitor = HealthMonitor()
        
        # Empty IP should be handled
        is_reachable, latency = monitor._test_nad_connectivity("")
        
        # Should fail gracefully
        assert is_reachable is False
        assert latency is None
