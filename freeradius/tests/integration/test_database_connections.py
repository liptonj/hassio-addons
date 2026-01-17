"""Integration tests for database connections.

These tests verify actual database connectivity for all supported database types.
Requires running database servers (configured via environment variables).

Environment variables:
    MARIADB_HOST: MariaDB hostname (default: localhost)
    MARIADB_PORT: MariaDB port (default: 3306)
    MARIADB_USER: MariaDB username (default: wpn_user)
    MARIADB_PASSWORD: MariaDB password
    MARIADB_DATABASE: Database name (default: wpn_radius_test)
    
    POSTGRES_HOST: PostgreSQL hostname (default: localhost)
    POSTGRES_PORT: PostgreSQL port (default: 5432)
    POSTGRES_USER: PostgreSQL username (default: wpn_user)
    POSTGRES_PASSWORD: PostgreSQL password
    POSTGRES_DATABASE: Database name (default: wpn_radius_test)
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rootfs/usr/bin"))

from radius_app.db.models import Base, RadiusClient, UdnAssignment


@pytest.mark.integration
class TestMariaDBConnection:
    """Test MariaDB connection and operations."""
    
    @pytest.fixture
    def mariadb_url(self):
        """Get MariaDB connection URL from environment."""
        host = os.getenv("MARIADB_HOST", "localhost")
        port = os.getenv("MARIADB_PORT", "3306")
        user = os.getenv("MARIADB_USER", "wpn_user")
        password = os.getenv("MARIADB_PASSWORD", "")
        database = os.getenv("MARIADB_DATABASE", "wpn_radius_test")
        
        if not password:
            pytest.skip("MARIADB_PASSWORD not set")
        
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    
    @pytest.fixture
    def mariadb_engine(self, mariadb_url):
        """Create MariaDB engine."""
        try:
            engine = create_engine(
                mariadb_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            yield engine
            engine.dispose()
        except OperationalError as e:
            pytest.skip(f"MariaDB not available: {e}")
    
    def test_mariadb_connection(self, mariadb_engine):
        """Test that we can connect to MariaDB."""
        with mariadb_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            assert result.scalar() == 1
    
    def test_mariadb_create_tables(self, mariadb_engine):
        """Test that we can create tables in MariaDB."""
        Base.metadata.create_all(mariadb_engine)
        
        # Verify tables exist
        with mariadb_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() "
                "AND table_name IN ('radius_clients', 'udn_assignments')"
            ))
            count = result.scalar()
            assert count == 2, "Expected 2 tables (radius_clients, udn_assignments)"
        
        # Cleanup
        Base.metadata.drop_all(mariadb_engine)
    
    def test_mariadb_crud_operations(self, mariadb_engine):
        """Test CRUD operations in MariaDB."""
        Base.metadata.create_all(mariadb_engine)
        
        Session = sessionmaker(bind=mariadb_engine)
        session = Session()
        
        try:
            # Create
            client = RadiusClient(
                name="test-mariadb-client",
                ipaddr="192.168.1.100",
                secret="test-secret",
                nas_type="other",
                is_active=True
            )
            session.add(client)
            session.commit()
            
            # Read
            retrieved = session.query(RadiusClient).filter_by(name="test-mariadb-client").first()
            assert retrieved is not None
            assert retrieved.ipaddr == "192.168.1.100"
            
            # Update
            retrieved.ipaddr = "192.168.1.200"
            session.commit()
            
            updated = session.query(RadiusClient).filter_by(name="test-mariadb-client").first()
            assert updated.ipaddr == "192.168.1.200"
            
            # Delete
            session.delete(updated)
            session.commit()
            
            deleted = session.query(RadiusClient).filter_by(name="test-mariadb-client").first()
            assert deleted is None
            
        finally:
            session.close()
            Base.metadata.drop_all(mariadb_engine)
    
    def test_mariadb_connection_pool(self, mariadb_engine):
        """Test connection pooling works correctly."""
        Session = sessionmaker(bind=mariadb_engine)
        
        # Create multiple sessions simultaneously
        sessions = [Session() for _ in range(3)]
        
        try:
            # Each should get a connection from pool
            for session in sessions:
                result = session.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            for session in sessions:
                session.close()


@pytest.mark.integration
class TestPostgreSQLConnection:
    """Test PostgreSQL connection and operations."""
    
    @pytest.fixture
    def postgres_url(self):
        """Get PostgreSQL connection URL from environment."""
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        user = os.getenv("POSTGRES_USER", "wpn_user")
        password = os.getenv("POSTGRES_PASSWORD", "")
        database = os.getenv("POSTGRES_DATABASE", "wpn_radius_test")
        
        if not password:
            pytest.skip("POSTGRES_PASSWORD not set")
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    @pytest.fixture
    def postgres_engine(self, postgres_url):
        """Create PostgreSQL engine."""
        try:
            engine = create_engine(
                postgres_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            yield engine
            engine.dispose()
        except OperationalError as e:
            pytest.skip(f"PostgreSQL not available: {e}")
    
    def test_postgres_connection(self, postgres_engine):
        """Test that we can connect to PostgreSQL."""
        with postgres_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            assert result.scalar() == 1
    
    def test_postgres_create_tables(self, postgres_engine):
        """Test that we can create tables in PostgreSQL."""
        Base.metadata.create_all(postgres_engine)
        
        # Verify tables exist
        with postgres_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name IN ('radius_clients', 'udn_assignments')"
            ))
            count = result.scalar()
            assert count == 2, "Expected 2 tables (radius_clients, udn_assignments)"
        
        # Cleanup
        Base.metadata.drop_all(postgres_engine)
    
    def test_postgres_crud_operations(self, postgres_engine):
        """Test CRUD operations in PostgreSQL."""
        Base.metadata.create_all(postgres_engine)
        
        Session = sessionmaker(bind=postgres_engine)
        session = Session()
        
        try:
            # Create
            assignment = UdnAssignment(
                user_id=1,  # Required - UDN is assigned to user
                mac_address="aa:bb:cc:dd:ee:ff",
                udn_id=100,
                user_name="Test User",
                user_email="test@example.com",
                unit="101",
                is_active=True
            )
            session.add(assignment)
            session.commit()
            
            # Read
            retrieved = session.query(UdnAssignment).filter_by(mac_address="aa:bb:cc:dd:ee:ff").first()
            assert retrieved is not None
            assert retrieved.udn_id == 100
            
            # Update
            retrieved.udn_id = 200
            session.commit()
            
            updated = session.query(UdnAssignment).filter_by(mac_address="aa:bb:cc:dd:ee:ff").first()
            assert updated.udn_id == 200
            
            # Delete
            session.delete(updated)
            session.commit()
            
            deleted = session.query(UdnAssignment).filter_by(mac_address="aa:bb:cc:dd:ee:ff").first()
            assert deleted is None
            
        finally:
            session.close()
            Base.metadata.drop_all(postgres_engine)


@pytest.mark.integration
class TestSQLiteConnection:
    """Test SQLite connection with WAL mode."""
    
    @pytest.fixture
    def sqlite_engine(self, tmp_path):
        """Create SQLite engine with WAL mode."""
        db_path = tmp_path / "test.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        
        # Enable WAL mode
        from sqlalchemy import event
        
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
        
        yield engine
        engine.dispose()
    
    def test_sqlite_wal_mode(self, sqlite_engine):
        """Test that WAL mode is enabled."""
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            assert mode.upper() == "WAL", f"Expected WAL mode, got {mode}"
    
    def test_sqlite_foreign_keys(self, sqlite_engine):
        """Test that foreign keys are enabled."""
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys"))
            enabled = result.scalar()
            assert enabled == 1, "Foreign keys should be enabled"
    
    def test_sqlite_crud_operations(self, sqlite_engine):
        """Test CRUD operations in SQLite."""
        Base.metadata.create_all(sqlite_engine)
        
        Session = sessionmaker(bind=sqlite_engine)
        session = Session()
        
        try:
            # Create
            client = RadiusClient(
                name="test-sqlite-client",
                ipaddr="10.0.0.1",
                secret="sqlite-secret",
                is_active=True
            )
            session.add(client)
            session.commit()
            
            # Read
            retrieved = session.query(RadiusClient).filter_by(name="test-sqlite-client").first()
            assert retrieved is not None
            assert retrieved.secret == "sqlite-secret"
            
        finally:
            session.close()
            Base.metadata.drop_all(sqlite_engine)
