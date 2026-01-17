"""Database connection and session management.

Supports multiple database types:
- SQLite (development, testing, small deployments)
- PostgreSQL (production, cloud deployments)
- MySQL/MariaDB (HA addon with core-mariadb, production)

Database type is auto-detected from the DATABASE_URL connection string.
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.models import Base, InviteCode, PortalSetting, Registration, User, SplashAccess

logger = logging.getLogger(__name__)

# Engine and session factory will be initialized on first use
_engine = None
_SessionLocal = None


def create_database_engine():
    """Create SQLAlchemy engine with database-specific configuration.
    
    Automatically detects database type from URL and applies optimal settings:
    - SQLite: Single-threaded, static pool
    - PostgreSQL: Connection pooling, pre-ping
    - MySQL/MariaDB: Connection pooling, pre-ping, charset
    
    Returns
    -------
        SQLAlchemy engine configured for the detected database type
        
    Raises
    ------
        ValueError
            If database URL is unsupported or invalid
    """
    settings = get_settings()
    db_url = settings.database_url
    
    if not db_url:
        raise ValueError("DATABASE_URL is required but not configured")
    
    engine_kwargs = {
        "echo": settings.is_standalone and False,  # Debug SQL in dev only
    }
    
    # Database-specific configuration
    if db_url.startswith("sqlite"):
        logger.info("📊 Database: SQLite (file-based)")
        engine_kwargs.update({
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,  # SQLite doesn't need connection pooling
        })
    
    elif db_url.startswith("postgresql"):
        logger.info("📊 Database: PostgreSQL (connection pooling enabled)")
        engine_kwargs.update({
            "pool_pre_ping": True,  # Verify connections before use
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        })
    
    elif db_url.startswith("mysql"):
        logger.info("📊 Database: MySQL/MariaDB (connection pooling enabled)")
        engine_kwargs.update({
            "pool_pre_ping": True,  # Verify connections before use
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 3600,  # Recycle connections after 1 hour
        })
        
        # MariaDB-specific: Set charset to utf8mb4 if not in URL
        if "charset" not in db_url:
            engine_kwargs["connect_args"] = {"charset": "utf8mb4"}
    
    else:
        raise ValueError(f"Unsupported database URL: {db_url}")
    
    engine = create_engine(db_url, **engine_kwargs)
    
    # SQLite-specific: Enable foreign keys (disabled by default in SQLite)
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
    
    Returns
    -------
        SQLAlchemy engine (cached after first call)
    """
    global _engine
    if _engine is None:
        _engine = create_database_engine()
    return _engine


def get_session_local():
    """Get or create the session factory.
    
    Returns
    -------
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


def run_migrations(engine) -> None:
    """Run database migrations to add missing columns.
    
    Different databases have different ALTER TABLE capabilities:
    - SQLite: Limited ALTER TABLE support (can add columns)
    - PostgreSQL: Full ALTER TABLE support
    - MySQL/MariaDB: Full ALTER TABLE support
    
    This function checks each table for missing columns and adds them.
    For production, consider using Alembic for full migration management.
    
    Parameters
    ----------
    engine : Engine
        SQLAlchemy engine connected to the database
    """
    inspector = inspect(engine)
    db_url = str(engine.url)
    is_sqlite = db_url.startswith("sqlite")
    is_postgres = db_url.startswith("postgresql")
    is_mysql = db_url.startswith("mysql")

    # Define expected columns for each table (column_name, sql_type, default)
    # Types are specified per database for compatibility
    expected_columns = {
        "users": [
            ("username", "VARCHAR(100)", None),
            ("password_hash", "VARCHAR(255)", None),
            ("is_admin", "BOOLEAN" if not is_sqlite else "INTEGER", "0" if is_sqlite else "FALSE"),
            ("last_login_at", "TIMESTAMP" if not is_sqlite else "DATETIME", None),
            ("ipsk_passphrase_encrypted", "TEXT", None),
            ("ssid_name", "VARCHAR(255)", None),
            # Unified authentication fields (NEW)
            ("auth_type", "VARCHAR(20)", "'local'"),
            ("oauth_provider_id", "VARCHAR(255)", None),
            ("radius_enabled", "BOOLEAN" if not is_sqlite else "INTEGER", "0" if is_sqlite else "FALSE"),
            ("radius_username", "VARCHAR(255)", None),
            ("radius_password_hash", "VARCHAR(255)", None),
        ],
        "splash_access": [],  # New table, will be created by create_all
    }

    with engine.connect() as conn:
        for table_name, columns in expected_columns.items():
            # Check if table exists
            if table_name not in inspector.get_table_names():
                logger.info(f"Table {table_name} doesn't exist, will be created")
                continue

            # Get existing columns
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

            # Add missing columns
            for col_name, col_type, default in columns:
                if col_name not in existing_cols:
                    # Build ALTER TABLE statement based on database type
                    if is_postgres:
                        # PostgreSQL syntax
                        default_clause = f" DEFAULT {default}" if default else ""
                        sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type}{default_clause}'
                    elif is_mysql:
                        # MySQL/MariaDB syntax
                        default_clause = f" DEFAULT {default}" if default else ""
                        sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type}{default_clause}"
                    else:
                        # SQLite syntax
                        default_clause = f" DEFAULT {default}" if default else ""
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{default_clause}"
                    
                    try:
                        conn.execute(text(sql))
                        conn.commit()
                        logger.info(f"✅ Migration: Added column {table_name}.{col_name}")
                    except Exception as e:
                        # Column might already exist or other issue
                        logger.debug(f"Migration skip {table_name}.{col_name}: {e}")

        # Final commit for any pending changes
        try:
            conn.commit()
        except Exception:
            pass  # Already committed or no changes


def init_db() -> None:
    """Initialize the database, creating all tables and running migrations."""
    logger.info("Initializing database tables...")
    engine = get_engine()

    # Run migrations first to add missing columns to existing tables
    run_migrations(engine)

    # Create any new tables that don't exist
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


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
