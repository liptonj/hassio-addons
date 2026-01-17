"""Database migration to add missing policy columns.

This migration adds columns that were added to the RadiusPolicy model
but may not exist in existing databases.

Supports both SQLite and MariaDB.
"""

import logging
import os
import sys

# Add radius_app to path
sys.path.insert(0, '/usr/bin')

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment or use default."""
    # Check for explicit DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        return db_url
    
    # Check for portal DB settings (HA addon mode)
    portal_host = os.getenv("PORTAL_DB_HOST")
    if portal_host:
        portal_port = os.getenv("PORTAL_DB_PORT", "3306")
        portal_db = os.getenv("PORTAL_DB_NAME", "wpn_radius")
        portal_user = os.getenv("PORTAL_DB_USER", "wpn_user")
        portal_pass = os.getenv("PORTAL_DB_PASSWORD", "")
        return f"mysql+pymysql://{portal_user}:{portal_pass}@{portal_host}:{portal_port}/{portal_db}"
    
    return "sqlite:///./radius.db"


def column_exists(session, table_name: str, column_name: str, is_mysql: bool) -> bool:
    """Check if a column exists in a table."""
    try:
        if is_mysql:
            result = session.execute(text(
                f"SELECT COUNT(*) FROM information_schema.columns "
                f"WHERE table_name = :table AND column_name = :column"
            ), {"table": table_name, "column": column_name})
        else:
            # SQLite
            result = session.execute(text(f"PRAGMA table_info({table_name})"))
            for row in result:
                if row[1] == column_name:
                    return True
            return False
        
        count = result.fetchone()[0]
        return count > 0
    except Exception as e:
        logger.warning(f"Error checking column {column_name}: {e}")
        return False


def table_exists(session, table_name: str, is_mysql: bool) -> bool:
    """Check if a table exists."""
    try:
        if is_mysql:
            result = session.execute(text(
                f"SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_name = :table"
            ), {"table": table_name})
            count = result.fetchone()[0]
            return count > 0
        else:
            # SQLite
            result = session.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name=:table"
            ), {"table": table_name})
            return result.fetchone() is not None
    except Exception as e:
        logger.warning(f"Error checking table {table_name}: {e}")
        return False


def add_column_if_not_exists(session, table_name: str, column_name: str, 
                              column_def: str, is_mysql: bool) -> bool:
    """Add a column if it doesn't exist."""
    if column_exists(session, table_name, column_name, is_mysql):
        logger.info(f"  Column {column_name} already exists, skipping")
        return False
    
    try:
        session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
        logger.info(f"  ✅ Added column {column_name}")
        return True
    except Exception as e:
        logger.warning(f"  ⚠️  Failed to add column {column_name}: {e}")
        return False


def run_migration():
    """Run the migration to add missing policy columns."""
    logger.info("=" * 60)
    logger.info("Migration 002: Add missing policy columns")
    logger.info("=" * 60)
    
    # Create engine
    database_url = get_database_url()
    is_mysql = "mysql" in database_url.lower() or "mariadb" in database_url.lower()
    
    logger.info(f"Database type: {'MariaDB/MySQL' if is_mysql else 'SQLite'}")
    logger.info(f"Database URL: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    engine = create_engine(database_url)
    
    with Session(engine) as session:
        try:
            # Check if radius_policies table exists
            if not table_exists(session, "radius_policies", is_mysql):
                logger.warning("⚠️  radius_policies table doesn't exist - run migration 001 first")
                return
            
            logger.info("Adding missing columns to radius_policies table...")
            
            # Define columns to add with their definitions
            # MariaDB/MySQL syntax
            if is_mysql:
                columns_to_add = [
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
                # SQLite syntax
                columns_to_add = [
                    ("psk_validation_required", "BOOLEAN DEFAULT 0"),
                    ("mac_matching_enabled", "BOOLEAN DEFAULT 0"),
                    ("mac_validation_mode", "VARCHAR(50) DEFAULT 'exact'"),
                    ("match_on_psk_only", "BOOLEAN DEFAULT 0"),
                    ("splash_url", "VARCHAR(500)"),
                    ("unregistered_group_policy", "VARCHAR(100)"),
                    ("registered_group_policy", "VARCHAR(100)"),
                    ("include_udn", "BOOLEAN DEFAULT 0"),
                ]
            
            columns_added = 0
            for column_name, column_def in columns_to_add:
                if add_column_if_not_exists(session, "radius_policies", column_name, column_def, is_mysql):
                    columns_added += 1
            
            # Also add columns to radius_mac_bypass_configs if needed
            if table_exists(session, "radius_mac_bypass_configs", is_mysql):
                logger.info("Adding policy reference columns to radius_mac_bypass_configs...")
                
                if is_mysql:
                    mac_bypass_columns = [
                        ("registered_policy_id", "INTEGER"),
                        ("unregistered_policy_id", "INTEGER"),
                    ]
                else:
                    mac_bypass_columns = [
                        ("registered_policy_id", "INTEGER"),
                        ("unregistered_policy_id", "INTEGER"),
                    ]
                
                for column_name, column_def in mac_bypass_columns:
                    if add_column_if_not_exists(session, "radius_mac_bypass_configs", 
                                                 column_name, column_def, is_mysql):
                        columns_added += 1
            
            # Add columns to radius_eap_methods if needed
            if table_exists(session, "radius_eap_methods", is_mysql):
                logger.info("Adding policy reference columns to radius_eap_methods...")
                
                eap_method_columns = [
                    ("success_policy_id", "INTEGER"),
                    ("failure_policy_id", "INTEGER"),
                ]
                
                for column_name, column_def in eap_method_columns:
                    if add_column_if_not_exists(session, "radius_eap_methods", 
                                                 column_name, column_def, is_mysql):
                        columns_added += 1
            
            # Create radius_unlang_policies table if it doesn't exist
            if not table_exists(session, "radius_unlang_policies", is_mysql):
                logger.info("Creating radius_unlang_policies table...")
                
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
                        CREATE TABLE radius_unlang_policies (
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
                logger.info("  ✅ Created radius_unlang_policies table")
                columns_added += 1
            
            # Create radius_psk_configs table if it doesn't exist
            if not table_exists(session, "radius_psk_configs", is_mysql):
                logger.info("Creating radius_psk_configs table...")
                
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
                        CREATE TABLE radius_psk_configs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE DEFAULT 'global',
                            description TEXT,
                            default_policy_id INTEGER,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                logger.info("  ✅ Created radius_psk_configs table")
                columns_added += 1
            
            # Create radius_authorization_profiles table if it doesn't exist
            if not table_exists(session, "radius_authorization_profiles", is_mysql):
                logger.info("Creating radius_authorization_profiles table...")
                
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
                        CREATE TABLE radius_authorization_profiles (
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
                logger.info("  ✅ Created radius_authorization_profiles table")
                columns_added += 1
            
            # Commit all changes
            session.commit()
            
            if columns_added > 0:
                logger.info("=" * 60)
                logger.info(f"✅ Migration completed! Added {columns_added} columns/tables")
                logger.info("=" * 60)
            else:
                logger.info("=" * 60)
                logger.info("✅ Migration complete - no changes needed (already up to date)")
                logger.info("=" * 60)
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    run_migration()
