"""Database migration for enterprise features.

This migration adds support for:
- NAD Management (extended client info, health monitoring)
- Policy Management (authorization policies)
- RadSec Configuration (secure RADIUS over TLS)
- Session Tracking (accounting, authentication logs)

Run this migration to add enterprise tables to an existing database.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment or use default."""
    import os
    return os.getenv("DATABASE_URL", "sqlite:///./radius.db")


def run_migration():
    """Run the enterprise features migration."""
    logger.info("=" * 60)
    logger.info("Starting Enterprise Features Migration")
    logger.info("=" * 60)
    
    # Create engine
    database_url = get_database_url()
    logger.info(f"Database: {database_url}")
    engine = create_engine(database_url)
    
    with Session(engine) as session:
        try:
            # Check if tables already exist
            result = session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='radius_nad_extended'"
            ))
            if result.fetchone():
                logger.warning("⚠️  Migration already applied - tables exist")
                return
            
            logger.info("Creating enterprise tables...")
            
            # Create NAD extended table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_nad_extended (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    radius_client_id INTEGER NOT NULL UNIQUE,
                    vendor VARCHAR(100),
                    model VARCHAR(100),
                    location VARCHAR(255),
                    description VARCHAR(500),
                    radsec_enabled BOOLEAN DEFAULT 0,
                    radsec_port INTEGER,
                    require_tls_cert BOOLEAN DEFAULT 0,
                    coa_enabled BOOLEAN DEFAULT 0,
                    coa_port INTEGER,
                    virtual_server VARCHAR(100),
                    capabilities TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (radius_client_id) REFERENCES radius_clients(id) ON DELETE CASCADE
                )
            """))
            logger.info("✅ Created radius_nad_extended table")
            
            # Create NAD health table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_nad_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nad_id INTEGER NOT NULL UNIQUE,
                    is_reachable BOOLEAN DEFAULT 0,
                    last_seen TIMESTAMP,
                    request_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    avg_response_time_ms REAL,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (nad_id) REFERENCES radius_nad_extended(id) ON DELETE CASCADE
                )
            """))
            logger.info("✅ Created radius_nad_health table")
            
            # Create policies table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    priority INTEGER DEFAULT 100 NOT NULL,
                    group_name VARCHAR(100),
                    policy_type VARCHAR(50) DEFAULT 'user' NOT NULL,
                    match_username VARCHAR(255),
                    match_mac_address VARCHAR(50),
                    match_calling_station VARCHAR(100),
                    match_nas_identifier VARCHAR(100),
                    match_nas_ip VARCHAR(100),
                    reply_attributes TEXT,
                    check_attributes TEXT,
                    time_restrictions TEXT,
                    vlan_id INTEGER,
                    vlan_name VARCHAR(100),
                    bandwidth_limit_up INTEGER,
                    bandwidth_limit_down INTEGER,
                    session_timeout INTEGER,
                    idle_timeout INTEGER,
                    max_concurrent_sessions INTEGER,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255)
                )
            """))
            logger.info("✅ Created radius_policies table")
            
            # Create RadSec configs table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_radsec_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    listen_address VARCHAR(100) DEFAULT '0.0.0.0' NOT NULL,
                    listen_port INTEGER DEFAULT 2083 NOT NULL,
                    tls_min_version VARCHAR(10) DEFAULT '1.2' NOT NULL,
                    tls_max_version VARCHAR(10) DEFAULT '1.3' NOT NULL,
                    cipher_list TEXT NOT NULL,
                    certificate_file VARCHAR(255) NOT NULL,
                    private_key_file VARCHAR(255) NOT NULL,
                    ca_certificate_file VARCHAR(255) NOT NULL,
                    require_client_cert BOOLEAN DEFAULT 1 NOT NULL,
                    verify_client_cert BOOLEAN DEFAULT 1 NOT NULL,
                    verify_depth INTEGER DEFAULT 2 NOT NULL,
                    crl_file VARCHAR(255),
                    check_crl BOOLEAN DEFAULT 0 NOT NULL,
                    ocsp_enable BOOLEAN DEFAULT 0 NOT NULL,
                    ocsp_url VARCHAR(255),
                    max_connections INTEGER DEFAULT 100 NOT NULL,
                    connection_timeout INTEGER DEFAULT 30 NOT NULL,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255)
                )
            """))
            logger.info("✅ Created radius_radsec_configs table")
            
            # Create RadSec clients table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_radsec_clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    certificate_subject VARCHAR(500) NOT NULL,
                    certificate_fingerprint VARCHAR(100),
                    client_id VARCHAR(100),
                    radius_client_id INTEGER,
                    connection_count INTEGER DEFAULT 0,
                    last_connected TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255),
                    FOREIGN KEY (radius_client_id) REFERENCES radius_clients(id) ON DELETE SET NULL
                )
            """))
            logger.info("✅ Created radius_radsec_clients table")
            
            # Create sessions table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(255) NOT NULL UNIQUE,
                    username VARCHAR(255) NOT NULL,
                    nas_ip VARCHAR(100) NOT NULL,
                    nas_port INTEGER,
                    calling_station_id VARCHAR(50),
                    called_station_id VARCHAR(50),
                    framed_ip VARCHAR(100),
                    session_start TIMESTAMP NOT NULL,
                    session_time INTEGER DEFAULT 0,
                    input_octets INTEGER DEFAULT 0,
                    output_octets INTEGER DEFAULT 0,
                    terminate_cause VARCHAR(100),
                    is_active BOOLEAN DEFAULT 1 NOT NULL
                )
            """))
            logger.info("✅ Created radius_sessions table")
            
            # Create auth log table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS radius_auth_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    mac_address VARCHAR(50),
                    nas_ip VARCHAR(100) NOT NULL,
                    nas_identifier VARCHAR(100),
                    auth_result VARCHAR(20) NOT NULL,
                    reject_reason VARCHAR(255),
                    policy_id INTEGER,
                    FOREIGN KEY (policy_id) REFERENCES radius_policies(id) ON DELETE SET NULL
                )
            """))
            logger.info("✅ Created radius_auth_log table")
            
            # Create indexes for better performance
            logger.info("Creating indexes...")
            
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_nad_extended_client ON radius_nad_extended(radius_client_id)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_nad_health_nad ON radius_nad_health(nad_id)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_policies_priority ON radius_policies(priority, is_active)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_policies_group ON radius_policies(group_name)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_radsec_clients_radius ON radius_radsec_clients(radius_client_id)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_sessions_username ON radius_sessions(username)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_sessions_active ON radius_sessions(is_active)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_auth_log_timestamp ON radius_auth_log(timestamp)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_auth_log_username ON radius_auth_log(username)"
            ))
            session.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_auth_log_result ON radius_auth_log(auth_result)"
            ))
            
            logger.info("✅ Created indexes")
            
            # Create default policies
            logger.info("Creating default policies...")
            
            default_policies = [
                {
                    "name": "default-guest-network",
                    "description": "Default policy for guest users with limited access",
                    "priority": 100,
                    "group_name": "guests",
                    "policy_type": "user",
                    "match_username": "guest.*",
                    "vlan_id": 100,
                    "bandwidth_limit_down": 10000,
                    "bandwidth_limit_up": 5000,
                    "session_timeout": 3600,
                    "idle_timeout": 600,
                    "is_active": 1,
                    "created_by": "migration",
                },
                {
                    "name": "default-employee-network",
                    "description": "Default policy for employees with full access",
                    "priority": 50,
                    "group_name": "employees",
                    "policy_type": "user",
                    "vlan_id": 200,
                    "session_timeout": 28800,
                    "is_active": 1,
                    "created_by": "migration",
                },
                {
                    "name": "default-iot-devices",
                    "description": "Default policy for IoT devices with restricted access",
                    "priority": 150,
                    "group_name": "iot",
                    "policy_type": "device",
                    "vlan_id": 300,
                    "max_concurrent_sessions": 1,
                    "is_active": 1,
                    "created_by": "migration",
                },
            ]
            
            for policy in default_policies:
                session.execute(text("""
                    INSERT INTO radius_policies 
                    (name, description, priority, group_name, policy_type, match_username, 
                     vlan_id, bandwidth_limit_down, bandwidth_limit_up, session_timeout, 
                     idle_timeout, max_concurrent_sessions, is_active, created_by)
                    VALUES 
                    (:name, :description, :priority, :group_name, :policy_type, :match_username,
                     :vlan_id, :bandwidth_limit_down, :bandwidth_limit_up, :session_timeout,
                     :idle_timeout, :max_concurrent_sessions, :is_active, :created_by)
                """), policy)
            
            logger.info("✅ Created 3 default policies")
            
            # Commit all changes
            session.commit()
            
            logger.info("=" * 60)
            logger.info("✅ Migration completed successfully!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Next steps:")
            logger.info("1. Restart the FreeRADIUS API service")
            logger.info("2. Access the API docs at http://your-server:port/docs")
            logger.info("3. Start using the new enterprise endpoints!")
            logger.info("")
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            raise


def rollback_migration():
    """Rollback the migration (drop all enterprise tables)."""
    logger.warning("=" * 60)
    logger.warning("Rolling back Enterprise Features Migration")
    logger.warning("=" * 60)
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    with Session(engine) as session:
        try:
            tables = [
                "radius_auth_log",
                "radius_sessions",
                "radius_radsec_clients",
                "radius_radsec_configs",
                "radius_policies",
                "radius_nad_health",
                "radius_nad_extended",
            ]
            
            for table in tables:
                session.execute(text(f"DROP TABLE IF EXISTS {table}"))
                logger.info(f"✅ Dropped {table}")
            
            session.commit()
            logger.warning("✅ Rollback completed")
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Rollback failed: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()
