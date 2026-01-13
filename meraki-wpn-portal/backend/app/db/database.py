"""Database connection and session management."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base, InviteCode, PortalSetting, Registration, User, SplashAccess

logger = logging.getLogger(__name__)

# Engine and session factory will be initialized on first use
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        logger.info(f"Creating database engine: {settings.database_url}")

        # SQLite-specific configuration
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine


def get_session_local():
    """Get or create the session factory."""
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

    SQLite doesn't support full ALTER TABLE, but we can add columns.
    This checks each table for missing columns and adds them.
    """
    inspector = inspect(engine)

    # Define expected columns for each table (column_name, sql_type, default)
    expected_columns = {
        "users": [
            ("username", "VARCHAR(100)", None),
            ("password_hash", "VARCHAR(255)", None),
            ("is_admin", "BOOLEAN", "0"),
            ("last_login_at", "DATETIME", None),
            ("ipsk_passphrase_encrypted", "TEXT", None),
            ("ssid_name", "VARCHAR(255)", None),
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
                    default_clause = f" DEFAULT {default}" if default else ""
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{default_clause}"
                    try:
                        conn.execute(text(sql))
                        logger.info(f"Migration: Added column {table_name}.{col_name}")
                    except Exception as e:
                        # Column might already exist or other issue
                        logger.debug(f"Migration skip {table_name}.{col_name}: {e}")

        conn.commit()


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
