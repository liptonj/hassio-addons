"""Database initialization and migration script.

This module handles automatic database schema creation and migrations
on first run or upgrade. It ensures all tables exist with the latest structure.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Base
from app.db.database import get_engine, get_session_local

logger = logging.getLogger(__name__)


def init_db(db_url: str | None = None) -> None:
    """Initialize database schema on first run.
    
    Creates all tables if they don't exist, and applies migrations
    for existing databases to add new columns.
    
    Args:
        db_url: Database URL (uses settings default if not provided)
    """
    logger.info("Initializing database schema...")
    engine = get_engine() if db_url is None else create_engine(db_url)
    inspector = inspect(engine)
    
    # Check if this is a fresh install
    existing_tables = inspector.get_table_names()
    is_fresh_install = len(existing_tables) == 0
    
    if is_fresh_install:
        logger.info("Fresh install detected - creating all tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully")
        
        # Seed default settings on fresh install
        SessionLocal = get_session_local()
        with SessionLocal() as session:
            seed_default_settings(session)
    else:
        logger.info(f"Existing database detected with {len(existing_tables)} tables")
        # Create any missing tables
        Base.metadata.create_all(bind=engine)
        
        # Apply incremental migrations for existing tables
        apply_migrations(engine, inspector)
    
    logger.info("Database initialization complete")


def apply_migrations(engine, inspector) -> None:
    """Apply incremental schema migrations for existing databases.
    
    Args:
        engine: SQLAlchemy engine
        inspector: SQLAlchemy inspector
    """
    logger.info("Checking for required schema migrations...")
    
    with Session(engine) as session:
        # Migration 1: Add AUP fields to users table
        if 'users' in inspector.get_table_names():
            columns = {col['name'] for col in inspector.get_columns('users')}
            migrations = []
            
            if 'accept_aup_at' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN accept_aup_at TIMESTAMP"
                )
            if 'aup_version' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN aup_version INTEGER"
                )
            if 'custom_fields' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN custom_fields TEXT"  # JSON as TEXT
                )
            if 'ipsk_status' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN ipsk_status VARCHAR(20) DEFAULT 'active'"
                )
            if 'ipsk_expires_at' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN ipsk_expires_at TIMESTAMP"
                )
            if 'expired_at' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN expired_at TIMESTAMP"
                )
            if 'expiration_notified_at' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN expiration_notified_at TIMESTAMP"
                )
            if 'oauth_provider' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50)"
                )
            if 'eap_enabled' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN eap_enabled BOOLEAN DEFAULT FALSE"
                )
            if 'cert_auto_renew' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN cert_auto_renew BOOLEAN DEFAULT TRUE"
                )
            if 'preferred_auth_method' not in columns:
                migrations.append(
                    "ALTER TABLE users ADD COLUMN preferred_auth_method VARCHAR(20)"
                )
            
            for migration in migrations:
                try:
                    session.execute(text(migration))
                    logger.info(f"Applied migration: {migration}")
                except Exception as e:
                    logger.warning(f"Migration may have already been applied: {e}")
            
            if migrations:
                session.commit()
        
        # Migration 2: Create device_registrations table if it doesn't exist
        if 'device_registrations' not in inspector.get_table_names():
            logger.info("Creating device_registrations table...")
            session.execute(text("""
                CREATE TABLE device_registrations (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    mac_address VARCHAR(50) NOT NULL,
                    device_type VARCHAR(50),
                    device_os VARCHAR(50),
                    device_os_version VARCHAR(100),
                    browser_name VARCHAR(100),
                    browser_version VARCHAR(50),
                    device_vendor VARCHAR(100),
                    device_model VARCHAR(100),
                    user_agent TEXT,
                    device_name VARCHAR(255),
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP,
                    last_ip_address VARCHAR(50),
                    udn_id INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    UNIQUE(user_id, mac_address)
                )
            """))
            session.execute(text("CREATE INDEX idx_device_mac ON device_registrations(mac_address)"))
            session.execute(text("CREATE INDEX idx_device_user ON device_registrations(user_id)"))
            session.execute(text("CREATE INDEX idx_device_active ON device_registrations(is_active)"))
            session.commit()
            logger.info("device_registrations table created")
        
        # Migration 3: Create ipsk_expiration_log table
        if 'ipsk_expiration_log' not in inspector.get_table_names():
            logger.info("Creating ipsk_expiration_log table...")
            session.execute(text("""
                CREATE TABLE ipsk_expiration_log (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    ipsk_id VARCHAR(100),
                    action VARCHAR(50),
                    details TEXT,
                    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    performed_by VARCHAR(255)
                )
            """))
            session.execute(text("CREATE INDEX idx_ipsk_exp_log_user ON ipsk_expiration_log(user_id)"))
            session.execute(text("CREATE INDEX idx_ipsk_exp_log_action ON ipsk_expiration_log(action)"))
            session.commit()
            logger.info("ipsk_expiration_log table created")
        
        # Migration 4: Create wifi_qr_tokens table
        if 'wifi_qr_tokens' not in inspector.get_table_names():
            logger.info("Creating wifi_qr_tokens table...")
            session.execute(text("""
                CREATE TABLE wifi_qr_tokens (
                    token VARCHAR(64) PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    ipsk_id VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            """))
            session.execute(text("CREATE INDEX idx_qr_token_user ON wifi_qr_tokens(user_id)"))
            session.execute(text("CREATE INDEX idx_qr_token_expires ON wifi_qr_tokens(expires_at)"))
            session.commit()
            logger.info("wifi_qr_tokens table created")
        
        # Migration 5: Update device_registrations table with EAP fields
        if 'device_registrations' in inspector.get_table_names():
            columns = {col['name'] for col in inspector.get_columns('device_registrations')}
            migrations = []
            
            if 'auth_method' not in columns:
                migrations.append(
                    "ALTER TABLE device_registrations ADD COLUMN auth_method VARCHAR(20)"
                )
            if 'certificate_id' not in columns:
                migrations.append(
                    "ALTER TABLE device_registrations ADD COLUMN certificate_id INTEGER"
                )
            if 'supports_eap' not in columns:
                migrations.append(
                    "ALTER TABLE device_registrations ADD COLUMN supports_eap BOOLEAN DEFAULT FALSE"
                )
            
            for migration in migrations:
                try:
                    session.execute(text(migration))
                    logger.info(f"Applied migration: {migration}")
                except Exception as e:
                    logger.warning(f"Migration may have already been applied: {e}")
            
            if migrations:
                session.commit()

        # Migration 5b: Update users table with certificate_id
        if 'users' in inspector.get_table_names():
            user_columns = {col['name'] for col in inspector.get_columns('users')}
            if 'certificate_id' not in user_columns:
                try:
                    session.execute(
                        text("ALTER TABLE users ADD COLUMN certificate_id INTEGER")
                    )
                    session.commit()
                    logger.info("Applied migration: ALTER TABLE users ADD COLUMN certificate_id INTEGER")
                except Exception as e:
                    logger.warning(f"Migration may have already been applied: {e}")
        
        # Migration 5c: Add approval workflow fields to users table
        if 'users' in inspector.get_table_names():
            user_columns = {col['name'] for col in inspector.get_columns('users')}
            approval_migrations = []
            
            if 'approval_status' not in user_columns:
                approval_migrations.append(
                    "ALTER TABLE users ADD COLUMN approval_status VARCHAR(20) DEFAULT 'approved'"
                )
            if 'approval_notes' not in user_columns:
                approval_migrations.append(
                    "ALTER TABLE users ADD COLUMN approval_notes TEXT"
                )
            if 'approved_at' not in user_columns:
                approval_migrations.append(
                    "ALTER TABLE users ADD COLUMN approved_at TIMESTAMP"
                )
            if 'approved_by' not in user_columns:
                approval_migrations.append(
                    "ALTER TABLE users ADD COLUMN approved_by VARCHAR(255)"
                )
            
            for migration in approval_migrations:
                try:
                    session.execute(text(migration))
                    logger.info(f"Applied migration: {migration}")
                except Exception as e:
                    logger.warning(f"Migration may have already been applied: {e}")
            
            if approval_migrations:
                session.commit()
        
        # Migration 6: Create certificate_authorities table
        if 'certificate_authorities' not in inspector.get_table_names():
            logger.info("Creating certificate_authorities table...")
            session.execute(text("""
                CREATE TABLE certificate_authorities (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    ca_type VARCHAR(20) NOT NULL,
                    root_certificate TEXT NOT NULL,
                    root_certificate_fingerprint VARCHAR(100) NOT NULL,
                    private_key_encrypted TEXT,
                    certificate_chain TEXT,
                    valid_from TIMESTAMP NOT NULL,
                    valid_until TIMESTAMP NOT NULL,
                    key_algorithm VARCHAR(20) DEFAULT 'RSA',
                    key_size INTEGER DEFAULT 4096,
                    signature_algorithm VARCHAR(50) DEFAULT 'sha256WithRSAEncryption',
                    default_validity_days INTEGER DEFAULT 365,
                    auto_renewal_enabled BOOLEAN DEFAULT TRUE,
                    renewal_threshold_days INTEGER DEFAULT 30,
                    crl_url VARCHAR(500),
                    crl_distribution_point VARCHAR(500),
                    is_active BOOLEAN DEFAULT TRUE,
                    is_primary BOOLEAN DEFAULT FALSE,
                    certificates_issued INTEGER DEFAULT 0,
                    certificates_revoked INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255)
                )
            """))
            session.execute(text("CREATE INDEX idx_ca_name ON certificate_authorities(name)"))
            session.execute(text("CREATE INDEX idx_ca_type ON certificate_authorities(ca_type)"))
            session.execute(text("CREATE INDEX idx_ca_fingerprint ON certificate_authorities(root_certificate_fingerprint)"))
            session.commit()
            logger.info("certificate_authorities table created")
        
        # Migration 7: Create user_certificates table
        if 'user_certificates' not in inspector.get_table_names():
            logger.info("Creating user_certificates table...")
            session.execute(text("""
                CREATE TABLE user_certificates (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    ca_id INTEGER NOT NULL,
                    device_registration_id INTEGER,
                    certificate TEXT NOT NULL,
                    certificate_fingerprint VARCHAR(100) NOT NULL UNIQUE,
                    private_key_encrypted TEXT NOT NULL,
                    pkcs12_encrypted TEXT,
                    pkcs12_password_encrypted VARCHAR(255),
                    subject_common_name VARCHAR(255) NOT NULL,
                    subject_email VARCHAR(255),
                    subject_distinguished_name VARCHAR(500) NOT NULL,
                    valid_from TIMESTAMP NOT NULL,
                    valid_until TIMESTAMP NOT NULL,
                    key_algorithm VARCHAR(20) DEFAULT 'RSA',
                    key_size INTEGER DEFAULT 2048,
                    serial_number VARCHAR(100) NOT NULL UNIQUE,
                    status VARCHAR(20) DEFAULT 'active' NOT NULL,
                    renewed_by_certificate_id INTEGER,
                    renewal_requested_at TIMESTAMP,
                    auto_renew BOOLEAN DEFAULT TRUE,
                    revoked_at TIMESTAMP,
                    revocation_reason VARCHAR(100),
                    last_authenticated_at TIMESTAMP,
                    authentication_count INTEGER DEFAULT 0,
                    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    downloaded_at TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(ca_id) REFERENCES certificate_authorities(id)
                )
            """))
            session.execute(text("CREATE INDEX idx_user_cert_user ON user_certificates(user_id)"))
            session.execute(text("CREATE INDEX idx_user_cert_ca ON user_certificates(ca_id)"))
            session.execute(text("CREATE INDEX idx_user_cert_fingerprint ON user_certificates(certificate_fingerprint)"))
            session.execute(text("CREATE INDEX idx_user_cert_serial ON user_certificates(serial_number)"))
            session.execute(text("CREATE INDEX idx_user_cert_cn ON user_certificates(subject_common_name)"))
            session.execute(text("CREATE INDEX idx_user_cert_status ON user_certificates(status)"))
            session.execute(text("CREATE INDEX idx_user_cert_valid_until ON user_certificates(valid_until)"))
            session.commit()
            logger.info("user_certificates table created")
        
        # Migration 8: Create certificate_revocations table
        if 'certificate_revocations' not in inspector.get_table_names():
            logger.info("Creating certificate_revocations table...")
            session.execute(text("""
                CREATE TABLE certificate_revocations (
                    id INTEGER PRIMARY KEY,
                    certificate_id INTEGER NOT NULL,
                    ca_id INTEGER NOT NULL,
                    serial_number VARCHAR(100) NOT NULL,
                    revocation_reason VARCHAR(50) NOT NULL,
                    revoked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    revoked_by VARCHAR(255) NOT NULL,
                    published_to_crl BOOLEAN DEFAULT FALSE,
                    crl_published_at TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY(certificate_id) REFERENCES user_certificates(id),
                    FOREIGN KEY(ca_id) REFERENCES certificate_authorities(id)
                )
            """))
            session.execute(text("CREATE INDEX idx_cert_rev_cert ON certificate_revocations(certificate_id)"))
            session.execute(text("CREATE INDEX idx_cert_rev_ca ON certificate_revocations(ca_id)"))
            session.execute(text("CREATE INDEX idx_cert_rev_serial ON certificate_revocations(serial_number)"))
            session.execute(text("CREATE INDEX idx_cert_rev_revoked_at ON certificate_revocations(revoked_at)"))
            session.commit()
            logger.info("certificate_revocations table created")
        
        # Migration 9: Create auth_method_preferences table
        if 'auth_method_preferences' not in inspector.get_table_names():
            logger.info("Creating auth_method_preferences table...")
            session.execute(text("""
                CREATE TABLE auth_method_preferences (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    device_registration_id INTEGER,
                    auth_method VARCHAR(20) NOT NULL,
                    preference_reason VARCHAR(100),
                    set_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(device_registration_id) REFERENCES device_registrations(id)
                )
            """))
            session.execute(text("CREATE INDEX idx_auth_pref_user ON auth_method_preferences(user_id)"))
            session.execute(text("CREATE INDEX idx_auth_pref_device ON auth_method_preferences(device_registration_id)"))
            session.commit()
            logger.info("auth_method_preferences table created")
        
        # Migration 10: Add new EAP settings to portal_settings
        # Settings will be created on first use via seed_default_settings
        
        logger.info("All migrations completed successfully")


def seed_default_settings(session: Session) -> None:
    """Seed default portal settings on first run.
    
    Args:
        session: Database session
    """
    from app.db.models import PortalSetting
    
    default_settings = [
        # AUP Settings
        ('aup_enabled', 'false', 'bool', 'Enable Acceptable Use Policy', 'auth'),
        ('aup_text', '', 'string', 'AUP text content', 'auth'),
        ('aup_url', '', 'string', 'AUP external URL', 'auth'),
        ('aup_version', '1', 'int', 'AUP version number', 'auth'),
        
        # Custom Fields
        ('custom_registration_fields', '[]', 'json', 'Custom registration form fields', 'registration'),
        
        # PSK Settings
        ('allow_custom_psk', 'true', 'bool', 'Allow users to set custom PSK', 'network'),
        ('psk_min_length', '8', 'int', 'Minimum PSK length', 'network'),
        ('psk_max_length', '63', 'int', 'Maximum PSK length', 'network'),
        
        # Invite Code Settings
        ('invite_code_email_restriction', 'false', 'bool', 'Restrict invite codes to email', 'auth'),
        ('invite_code_single_use', 'false', 'bool', 'Single use invite codes', 'auth'),
        
        # Authentication Methods
        ('auth_method_local', 'true', 'bool', 'Enable local email/password auth', 'auth'),
        ('auth_method_oauth', 'false', 'bool', 'Enable OAuth/SAML SSO', 'auth'),
        ('auth_method_invite_code', 'true', 'bool', 'Enable invite code registration', 'auth'),
        ('auth_method_self_registration', 'true', 'bool', 'Enable open self-registration', 'auth'),
        
        # Registration Mode (open, invite_only, approval_required)
        ('registration_mode', 'open', 'string', 'Registration mode: open, invite_only, or approval_required', 'auth'),
        ('approval_notification_email', '', 'string', 'Email to notify on new pending registrations', 'auth'),
        
        # Universal Login
        ('universal_login_enabled', 'true', 'bool', 'Enable universal email lookup login', 'auth'),
        ('show_login_method_selector', 'false', 'bool', 'Show auth method selector', 'auth'),
        
        # iPSK Expiration Management
        ('ipsk_expiration_check_enabled', 'true', 'bool', 'Enable automated expiration checks', 'ipsk'),
        ('ipsk_expiration_check_interval_hours', '1', 'int', 'Check interval in hours', 'ipsk'),
        ('ipsk_cleanup_action', 'soft_delete', 'string', 'Cleanup action (soft_delete, revoke_meraki, full_cleanup)', 'ipsk'),
        ('ipsk_expiration_warning_days', '7,3,1', 'string', 'Warning notification days', 'ipsk'),
        ('ipsk_expiration_email_enabled', 'false', 'bool', 'Enable expiration email notifications', 'ipsk'),
        
        # EAP-TLS / Certificate Authentication
        ('eap_tls_enabled', 'false', 'bool', 'Enable EAP-TLS certificate authentication', 'auth'),
        ('ipsk_enabled', 'true', 'bool', 'Enable IPSK authentication', 'auth'),
        ('allow_user_auth_choice', 'true', 'bool', 'Allow users to choose auth method', 'auth'),
        ('ca_provider', 'internal', 'string', 'Certificate Authority provider (internal, letsencrypt, external, meraki)', 'certificates'),
        ('cert_validity_days', '365', 'int', 'Default certificate validity in days', 'certificates'),
        ('cert_auto_renewal_enabled', 'true', 'bool', 'Enable automatic certificate renewal', 'certificates'),
        ('cert_renewal_threshold_days', '30', 'int', 'Days before expiry to trigger renewal', 'certificates'),
        ('cert_key_size', '2048', 'int', 'Certificate key size (2048, 3072, 4096)', 'certificates'),
        ('cert_signature_algorithm', 'sha256', 'string', 'Certificate signature algorithm', 'certificates'),
    ]
    
    for key, value, value_type, description, category in default_settings:
        # Check if setting already exists
        existing = session.query(PortalSetting).filter_by(key=key).first()
        if not existing:
            setting = PortalSetting(
                key=key,
                value=value,
                value_type=value_type,
                description=description,
                category=category,
                updated_by='system'
            )
            session.add(setting)
    
    session.commit()
    logger.info("Default settings seeded")
    
    # Seed default admin user if not exists
    seed_default_admin_user(session)


def seed_default_admin_user(session: Session) -> None:
    """Seed default admin user on first run.
    
    Creates an admin user with email admin@example.com and password admin123.
    This allows login via the Universal Login with an email address.
    
    Args:
        session: Database session
    """
    from app.db.models import User
    
    # Import hash_password with fallback for testing environments
    try:
        from app.core.security import hash_password
    except ImportError:
        import bcrypt
        def hash_password(password: str) -> str:
            return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Check if admin user already exists
    existing_admin = session.query(User).filter(
        (User.email == "admin@example.com") | (User.is_admin == True)
    ).first()
    
    if existing_admin:
        logger.info(f"Admin user already exists: {existing_admin.email}")
        return
    
    # Create default admin user
    admin_user = User(
        name="Administrator",
        email="admin@example.com",
        username="admin",
        password_hash=hash_password("admin123"),
        is_admin=True,
        is_active=True,
        auth_type="local",
    )
    
    session.add(admin_user)
    session.commit()
    logger.info("Default admin user created: admin@example.com / admin123")