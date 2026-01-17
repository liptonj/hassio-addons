"""Database migrations module.

Runs database migrations on application startup to ensure schema is up to date.
Migrations are idempotent - safe to run multiple times.
"""

import logging
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from radius_app.db.database import get_engine

logger = logging.getLogger(__name__)


def column_exists(session: Session, table_name: str, column_name: str, is_mysql: bool) -> bool:
    """Check if a column exists in a table."""
    try:
        if is_mysql:
            result = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ), {"table": table_name, "column": column_name})
            count = result.fetchone()[0]
            return count > 0
        else:
            # SQLite
            result = session.execute(text(f"PRAGMA table_info({table_name})"))
            for row in result:
                if row[1] == column_name:
                    return True
            return False
    except Exception as e:
        logger.warning(f"Error checking column {column_name}: {e}")
        return False


def table_exists(session: Session, table_name: str, is_mysql: bool) -> bool:
    """Check if a table exists."""
    try:
        if is_mysql:
            result = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = :table"
            ), {"table": table_name})
            count = result.fetchone()[0]
            return count > 0
        else:
            # SQLite
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:table"
            ), {"table": table_name})
            return result.fetchone() is not None
    except Exception as e:
        logger.warning(f"Error checking table {table_name}: {e}")
        return False


def add_column_if_not_exists(session: Session, table_name: str, column_name: str, 
                              column_def: str, is_mysql: bool) -> bool:
    """Add a column if it doesn't exist."""
    if column_exists(session, table_name, column_name, is_mysql):
        return False
    
    try:
        session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
        logger.info(f"  ✅ Added column {table_name}.{column_name}")
        return True
    except Exception as e:
        logger.warning(f"  ⚠️  Failed to add column {column_name}: {e}")
        return False


def run_migrations():
    """Run all database migrations.
    
    This function is idempotent - safe to run multiple times.
    It checks for missing columns/tables and adds them if needed.
    """
    from radius_app.config import get_settings
    
    settings = get_settings()
    engine = get_engine()
    is_mysql = "mysql" in settings.database_url.lower() or "mariadb" in settings.database_url.lower()
    
    logger.info(f"Running migrations on {'MariaDB/MySQL' if is_mysql else 'SQLite'} database...")
    
    with Session(engine) as session:
        try:
            changes_made = 0
            
            # Migration 1: Add missing policy columns to radius_policies
            if table_exists(session, "radius_policies", is_mysql):
                if is_mysql:
                    policy_columns = [
                        ("psk_validation_required", "BOOLEAN DEFAULT FALSE"),
                        ("mac_matching_enabled", "BOOLEAN DEFAULT FALSE"),
                        ("mac_validation_mode", "VARCHAR(50) DEFAULT 'exact'"),
                        ("match_on_psk_only", "BOOLEAN DEFAULT FALSE"),
                        ("splash_url", "VARCHAR(500)"),
                        ("unregistered_group_policy", "VARCHAR(100)"),
                        ("registered_group_policy", "VARCHAR(100)"),
                        ("include_udn", "BOOLEAN DEFAULT FALSE"),
                    ]
                else:
                    policy_columns = [
                        ("psk_validation_required", "BOOLEAN DEFAULT 0"),
                        ("mac_matching_enabled", "BOOLEAN DEFAULT 0"),
                        ("mac_validation_mode", "VARCHAR(50) DEFAULT 'exact'"),
                        ("match_on_psk_only", "BOOLEAN DEFAULT 0"),
                        ("splash_url", "VARCHAR(500)"),
                        ("unregistered_group_policy", "VARCHAR(100)"),
                        ("registered_group_policy", "VARCHAR(100)"),
                        ("include_udn", "BOOLEAN DEFAULT 0"),
                    ]
                
                for col_name, col_def in policy_columns:
                    if add_column_if_not_exists(session, "radius_policies", col_name, col_def, is_mysql):
                        changes_made += 1
            
            # Migration 2: Add policy reference columns to radius_mac_bypass_configs
            if table_exists(session, "radius_mac_bypass_configs", is_mysql):
                mac_bypass_columns = [
                    ("registered_policy_id", "INTEGER"),
                    ("unregistered_policy_id", "INTEGER"),
                ]
                for col_name, col_def in mac_bypass_columns:
                    if add_column_if_not_exists(session, "radius_mac_bypass_configs", col_name, col_def, is_mysql):
                        changes_made += 1
            
            # Migration 3: Add policy reference columns to radius_eap_methods
            if table_exists(session, "radius_eap_methods", is_mysql):
                eap_columns = [
                    ("success_policy_id", "INTEGER"),
                    ("failure_policy_id", "INTEGER"),
                ]
                for col_name, col_def in eap_columns:
                    if add_column_if_not_exists(session, "radius_eap_methods", col_name, col_def, is_mysql):
                        changes_made += 1
            
            # Migration 4: Create radius_unlang_policies table
            if not table_exists(session, "radius_unlang_policies", is_mysql):
                if is_mysql:
                    session.execute(text("""
                        CREATE TABLE radius_unlang_policies (
                            id INTEGER PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            priority INTEGER DEFAULT 100 NOT NULL,
                            condition_type VARCHAR(50) DEFAULT 'always',
                            condition_value VARCHAR(500),
                            action_type VARCHAR(50) DEFAULT 'allow',
                            authorization_profile_id INTEGER,
                            is_active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            created_by VARCHAR(255)
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_unlang_policies (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            priority INTEGER DEFAULT 100 NOT NULL,
                            condition_type VARCHAR(50) DEFAULT 'always',
                            condition_value VARCHAR(500),
                            action_type VARCHAR(50) DEFAULT 'allow',
                            authorization_profile_id INTEGER,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(255)
                        )
                    """))
                logger.info("  ✅ Created table radius_unlang_policies")
                changes_made += 1
            
            # Migration 5: Create radius_psk_configs table
            if not table_exists(session, "radius_psk_configs", is_mysql):
                if is_mysql:
                    session.execute(text("""
                        CREATE TABLE radius_psk_configs (
                            id INTEGER PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE DEFAULT 'global',
                            description TEXT,
                            default_policy_id INTEGER,
                            is_active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_psk_configs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE DEFAULT 'global',
                            description TEXT,
                            default_policy_id INTEGER,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                logger.info("  ✅ Created table radius_psk_configs")
                changes_made += 1
            
            # Migration 6: Create radius_authorization_profiles table
            if not table_exists(session, "radius_authorization_profiles", is_mysql):
                if is_mysql:
                    session.execute(text("""
                        CREATE TABLE radius_authorization_profiles (
                            id INTEGER PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            vlan_id INTEGER,
                            vlan_name VARCHAR(100),
                            bandwidth_limit_up INTEGER,
                            bandwidth_limit_down INTEGER,
                            session_timeout INTEGER,
                            idle_timeout INTEGER,
                            acl_name VARCHAR(100),
                            filter_id VARCHAR(255),
                            security_group_tag VARCHAR(100),
                            splash_url VARCHAR(500),
                            custom_attributes TEXT,
                            is_active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            created_by VARCHAR(255)
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_authorization_profiles (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            vlan_id INTEGER,
                            vlan_name VARCHAR(100),
                            bandwidth_limit_up INTEGER,
                            bandwidth_limit_down INTEGER,
                            session_timeout INTEGER,
                            idle_timeout INTEGER,
                            acl_name VARCHAR(100),
                            filter_id VARCHAR(255),
                            security_group_tag VARCHAR(100),
                            splash_url VARCHAR(500),
                            custom_attributes TEXT,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(255)
                        )
                    """))
                logger.info("  ✅ Created table radius_authorization_profiles")
                changes_made += 1
            
            # Commit all changes
            session.commit()
            
            if changes_made > 0:
                logger.info(f"✅ Migrations complete: {changes_made} changes applied")
            else:
                logger.info("✅ Migrations complete: database is up to date")
                
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration error: {e}")
            raise
