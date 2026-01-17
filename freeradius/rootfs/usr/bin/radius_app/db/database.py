"""Database connection and session management - shared with portal."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from radius_app.config import get_settings
from radius_app.db.models import Base

logger = logging.getLogger(__name__)

# Engine and session factory will be initialized on first use
_engine = None
_SessionLocal = None


def create_database_engine():
    """Create SQLAlchemy engine with database-specific configuration.
    
    Automatically detects database type from URL and applies optimal settings:
    - SQLite: Single-threaded, static pool, WAL mode
    - PostgreSQL: Connection pooling, pre-ping
    - MySQL/MariaDB: Connection pooling, pre-ping, charset
    
    Returns:
        SQLAlchemy engine configured for the detected database type
        
    Raises:
        ValueError: If database URL is unsupported or invalid
    """
    settings = get_settings()
    db_url = settings.database_url
    
    if not db_url:
        raise ValueError("DATABASE_URL is required but not configured")
    
    engine_kwargs = {
        "echo": False,  # Set to True for SQL debugging
    }
    
    # Database-specific configuration
    if db_url.startswith("sqlite"):
        logger.info("📊 Database: SQLite (file-based, WAL mode)")
        engine_kwargs.update({
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,  # SQLite doesn't need connection pooling
        })
    
    elif db_url.startswith("postgresql"):
        logger.info("📊 Database: PostgreSQL (connection pooling enabled)")
        engine_kwargs.update({
            "pool_pre_ping": True,  # Verify connections before use
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        })
    
    elif db_url.startswith("mysql"):
        logger.info("📊 Database: MySQL/MariaDB (connection pooling enabled)")
        engine_kwargs.update({
            "pool_pre_ping": True,  # Verify connections before use
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        })
        
        # MariaDB-specific: Set charset to utf8mb4 if not in URL
        if "charset" not in db_url:
            engine_kwargs["connect_args"] = {"charset": "utf8mb4"}
    
    else:
        raise ValueError(f"Unsupported database URL: {db_url}")
    
    engine = create_engine(db_url, **engine_kwargs)
    
    # SQLite-specific: Enable foreign keys and WAL mode
    if db_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            cursor.close()
    
    logger.info(f"✅ Database engine created: {db_url.split('@')[0] if '@' in db_url else db_url.split(':')[0]}")
    return engine


def get_engine():
    """Get or create the database engine.
    
    Returns:
        SQLAlchemy engine (cached after first call)
    """
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


def get_session_local():
    """Get or create the session factory.
    
    Returns:
        SQLAlchemy sessionmaker (cached after first call)
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def init_db() -> None:
    """Initialize the database.
    
    Note: In standalone mode, creates tables if they don't exist.
    In addon mode, tables should already exist from portal initialization.
    """
    logger.info("Initializing database connection...")
    engine = get_engine()
    
    # Verify we can connect
    try:
        with engine.connect() as conn:
            logger.info("✅ Database connection verified")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        raise
    
    # Initialize schema (creates tables if they don't exist)
    from radius_app.db.init_schema import initialize_database
    initialize_database()


def get_db() -> Generator[Session, None, None]:
    """Get a database session.

    Yields:
        Database session that is automatically closed after use
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
