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
                        ("mac_matching_enabled", "BOOLEAN DEFAULT TRUE"),
                        ("mac_validation_mode", "VARCHAR(20) DEFAULT NULL"),
                        ("match_on_psk_only", "BOOLEAN DEFAULT FALSE"),
                        ("splash_url", "VARCHAR(500) DEFAULT NULL"),
                        ("url_redirect_acl", "VARCHAR(100) DEFAULT NULL"),
                        ("unregistered_group_policy", "VARCHAR(255) DEFAULT NULL"),
                        ("registered_group_policy", "VARCHAR(255) DEFAULT NULL"),
                        ("group_policy_vendor", "VARCHAR(50) DEFAULT 'meraki' NOT NULL"),
                        ("filter_id", "VARCHAR(255) DEFAULT NULL"),
                        ("downloadable_acl", "VARCHAR(255) DEFAULT NULL"),
                        ("sgt_value", "INTEGER DEFAULT NULL"),
                        ("sgt_name", "VARCHAR(100) DEFAULT NULL"),
                        ("include_udn", "BOOLEAN DEFAULT TRUE"),
                    ]
                else:
                    policy_columns = [
                        ("psk_validation_required", "BOOLEAN DEFAULT 0"),
                        ("mac_matching_enabled", "BOOLEAN DEFAULT 1"),
                        ("mac_validation_mode", "VARCHAR(20) DEFAULT NULL"),
                        ("match_on_psk_only", "BOOLEAN DEFAULT 0"),
                        ("splash_url", "VARCHAR(500) DEFAULT NULL"),
                        ("url_redirect_acl", "VARCHAR(100) DEFAULT NULL"),
                        ("unregistered_group_policy", "VARCHAR(255) DEFAULT NULL"),
                        ("registered_group_policy", "VARCHAR(255) DEFAULT NULL"),
                        ("group_policy_vendor", "VARCHAR(50) DEFAULT 'meraki' NOT NULL"),
                        ("filter_id", "VARCHAR(255) DEFAULT NULL"),
                        ("downloadable_acl", "VARCHAR(255) DEFAULT NULL"),
                        ("sgt_value", "INTEGER DEFAULT NULL"),
                        ("sgt_name", "VARCHAR(100) DEFAULT NULL"),
                        ("include_udn", "BOOLEAN DEFAULT 1"),
                    ]
                
                for col_name, col_def in policy_columns:
                    if add_column_if_not_exists(session, "radius_policies", col_name, col_def, is_mysql):
                        changes_made += 1
            
            # Migration 2: Create radius_mac_bypass_configs table if not exists
            if not table_exists(session, "radius_mac_bypass_configs", is_mysql):
                if is_mysql:
                    session.execute(text("""
                        CREATE TABLE radius_mac_bypass_configs (
                            id INTEGER PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            mac_addresses JSON,
                            bypass_mode VARCHAR(20) DEFAULT 'whitelist' NOT NULL,
                            require_registration BOOLEAN DEFAULT FALSE NOT NULL,
                            registered_policy_id INTEGER,
                            unregistered_policy_id INTEGER,
                            is_active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            created_by VARCHAR(255),
                            FOREIGN KEY (registered_policy_id) REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            FOREIGN KEY (unregistered_policy_id) REFERENCES radius_unlang_policies(id) ON DELETE SET NULL
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_mac_bypass_configs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            mac_addresses TEXT,
                            bypass_mode VARCHAR(20) DEFAULT 'whitelist' NOT NULL,
                            require_registration BOOLEAN DEFAULT 0 NOT NULL,
                            registered_policy_id INTEGER REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            unregistered_policy_id INTEGER REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_by VARCHAR(255)
                        )
                    """))
                logger.info("  ✅ Created table radius_mac_bypass_configs")
                changes_made += 1
            
            # Migration 2b: Add policy reference columns to radius_mac_bypass_configs (if table exists but missing columns)
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
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            psk_type VARCHAR(20) DEFAULT 'user' NOT NULL,
                            generic_passphrase VARCHAR(255) DEFAULT NULL,
                            auth_policy_id INTEGER,
                            default_group_policy VARCHAR(255) DEFAULT NULL,
                            is_active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            FOREIGN KEY (auth_policy_id) REFERENCES radius_unlang_policies(id) ON DELETE SET NULL
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_psk_configs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            psk_type VARCHAR(20) DEFAULT 'user' NOT NULL,
                            generic_passphrase VARCHAR(255) DEFAULT NULL,
                            auth_policy_id INTEGER REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            default_group_policy VARCHAR(255) DEFAULT NULL,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                logger.info("  ✅ Created table radius_psk_configs")
                changes_made += 1
            
            # Migration 6: Create radius_eap_configs table
            if not table_exists(session, "radius_eap_configs", is_mysql):
                if is_mysql:
                    session.execute(text("""
                        CREATE TABLE radius_eap_configs (
                            id INTEGER PRIMARY KEY AUTO_INCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            default_eap_type VARCHAR(20) DEFAULT 'tls' NOT NULL,
                            timer_expire INTEGER DEFAULT 60,
                            ignore_unknown_eap_types BOOLEAN DEFAULT FALSE,
                            cisco_accounting_username_bug BOOLEAN DEFAULT FALSE,
                            max_sessions INTEGER DEFAULT 4096,
                            enabled_methods JSON,
                            tls_min_version VARCHAR(10) DEFAULT '1.2' NOT NULL,
                            tls_max_version VARCHAR(10) DEFAULT '1.3' NOT NULL,
                            cipher_list TEXT,
                            cipher_server_preference BOOLEAN DEFAULT TRUE,
                            private_key_file VARCHAR(500) DEFAULT '${certdir}/server-key.pem',
                            certificate_file VARCHAR(500) DEFAULT '${certdir}/server.pem',
                            ca_file VARCHAR(500) DEFAULT '${certdir}/ca.pem',
                            dh_file VARCHAR(500) DEFAULT '${certdir}/dh',
                            check_cert_cn BOOLEAN DEFAULT TRUE,
                            check_crl BOOLEAN DEFAULT FALSE,
                            cache_enable BOOLEAN DEFAULT TRUE,
                            cache_lifetime INTEGER DEFAULT 24,
                            cache_max_entries INTEGER DEFAULT 255,
                            ttls_default_eap_type VARCHAR(20) DEFAULT 'mschapv2',
                            ttls_copy_request_to_tunnel BOOLEAN DEFAULT FALSE,
                            ttls_use_tunneled_reply BOOLEAN DEFAULT FALSE,
                            ttls_virtual_server VARCHAR(100),
                            peap_default_eap_type VARCHAR(20) DEFAULT 'mschapv2',
                            peap_copy_request_to_tunnel BOOLEAN DEFAULT FALSE,
                            peap_use_tunneled_reply BOOLEAN DEFAULT FALSE,
                            peap_virtual_server VARCHAR(100),
                            fast_tls_auto_chain BOOLEAN DEFAULT TRUE,
                            is_active BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_eap_configs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) NOT NULL UNIQUE,
                            description TEXT,
                            default_eap_type VARCHAR(20) DEFAULT 'tls' NOT NULL,
                            timer_expire INTEGER DEFAULT 60,
                            ignore_unknown_eap_types BOOLEAN DEFAULT 0,
                            cisco_accounting_username_bug BOOLEAN DEFAULT 0,
                            max_sessions INTEGER DEFAULT 4096,
                            enabled_methods TEXT,
                            tls_min_version VARCHAR(10) DEFAULT '1.2' NOT NULL,
                            tls_max_version VARCHAR(10) DEFAULT '1.3' NOT NULL,
                            cipher_list TEXT,
                            cipher_server_preference BOOLEAN DEFAULT 1,
                            private_key_file VARCHAR(500),
                            certificate_file VARCHAR(500),
                            ca_file VARCHAR(500),
                            dh_file VARCHAR(500),
                            check_cert_cn BOOLEAN DEFAULT 1,
                            check_crl BOOLEAN DEFAULT 0,
                            cache_enable BOOLEAN DEFAULT 1,
                            cache_lifetime INTEGER DEFAULT 24,
                            cache_max_entries INTEGER DEFAULT 255,
                            ttls_default_eap_type VARCHAR(20) DEFAULT 'mschapv2',
                            ttls_copy_request_to_tunnel BOOLEAN DEFAULT 0,
                            ttls_use_tunneled_reply BOOLEAN DEFAULT 0,
                            ttls_virtual_server VARCHAR(100),
                            peap_default_eap_type VARCHAR(20) DEFAULT 'mschapv2',
                            peap_copy_request_to_tunnel BOOLEAN DEFAULT 0,
                            peap_use_tunneled_reply BOOLEAN DEFAULT 0,
                            peap_virtual_server VARCHAR(100),
                            fast_tls_auto_chain BOOLEAN DEFAULT 1,
                            is_active BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                logger.info("  ✅ Created table radius_eap_configs")
                changes_made += 1
            
            # Migration 7: Create radius_eap_methods table
            if not table_exists(session, "radius_eap_methods", is_mysql):
                if is_mysql:
                    session.execute(text("""
                        CREATE TABLE radius_eap_methods (
                            id INTEGER PRIMARY KEY AUTO_INCREMENT,
                            eap_config_id INTEGER NOT NULL,
                            method_name VARCHAR(20) NOT NULL,
                            settings JSON,
                            success_policy_id INTEGER,
                            failure_policy_id INTEGER,
                            is_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                            auth_attempts INTEGER DEFAULT 0,
                            auth_successes INTEGER DEFAULT 0,
                            auth_failures INTEGER DEFAULT 0,
                            last_used TIMESTAMP NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            FOREIGN KEY (eap_config_id) REFERENCES radius_eap_configs(id) ON DELETE CASCADE,
                            FOREIGN KEY (success_policy_id) REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            FOREIGN KEY (failure_policy_id) REFERENCES radius_unlang_policies(id) ON DELETE SET NULL
                        )
                    """))
                else:
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS radius_eap_methods (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            eap_config_id INTEGER NOT NULL REFERENCES radius_eap_configs(id) ON DELETE CASCADE,
                            method_name VARCHAR(20) NOT NULL,
                            settings TEXT,
                            success_policy_id INTEGER REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            failure_policy_id INTEGER REFERENCES radius_unlang_policies(id) ON DELETE SET NULL,
                            is_enabled BOOLEAN DEFAULT 1 NOT NULL,
                            auth_attempts INTEGER DEFAULT 0,
                            auth_successes INTEGER DEFAULT 0,
                            auth_failures INTEGER DEFAULT 0,
                            last_used TIMESTAMP NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                logger.info("  ✅ Created table radius_eap_methods")
                changes_made += 1
            
            # Migration 8: Create radius_authorization_profiles table
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
