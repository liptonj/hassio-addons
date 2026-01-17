"""Database schema initialization for standalone mode."""

import logging
import os
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from radius_app.db.database import get_engine
from radius_app.db.models import (
    Base,
    RadiusClient,
    RadiusEapConfig,
    RadiusEapMethod,
    RadiusMacBypassConfig,
    RadiusPolicy,
    RadiusUnlangPolicy,
    RadiusPskConfig,
)

logger = logging.getLogger(__name__)


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database.
    
    Args:
        engine: SQLAlchemy engine
        table_name: Name of the table to check
        
    Returns:
        True if table exists, False otherwise
    """
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_schema(engine) -> None:
    """Create database schema if it doesn't exist.
    
    This function creates all tables defined in the models if they don't
    already exist. It's safe to call multiple times.
    
    Args:
        engine: SQLAlchemy engine
    """
    logger.info("🔍 Checking database schema...")
    
    # Check which tables already exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    logger.info(f"Existing tables: {existing_tables}")
    
    # Create tables that don't exist
    tables_to_create = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            tables_to_create.append(table_name)
    
    if tables_to_create:
        logger.info(f"📊 Creating missing tables: {tables_to_create}")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database schema created successfully")
    else:
        logger.info("✅ All required tables already exist")


def init_default_data(engine) -> None:
    """Initialize default data on first run.
    
    Creates default configurations that are needed for the system to work:
    - Default localhost client for health checks
    - Default EAP configuration with enabled methods
    - Default MAC bypass configuration (empty)
    - Default authorization policies
    
    Args:
        engine: SQLAlchemy engine
    """
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timezone
    
    # Create session from the passed engine, not the global cached one
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # 1. Create default localhost client for health checks
        existing_client = db.query(RadiusClient).filter(
            RadiusClient.name == "localhost"
        ).first()
        
        if not existing_client:
            logger.info("📝 Creating default localhost client for health checks...")
            localhost_client = RadiusClient(
                name="localhost",
                ipaddr="127.0.0.1",
                secret="testing123",
                nas_type="other",
                shortname="localhost",
                require_message_authenticator=False,
                is_active=True,
                created_by="system",
            )
            db.add(localhost_client)
            logger.info("✅ Default localhost client created")
        else:
            logger.info("✅ Default localhost client already exists")
        
        # 1b. Create environment-configured client (for Docker networks, etc.)
        env_client_name = os.environ.get("RADIUS_CLIENT_NAME")
        env_client_network = os.environ.get("RADIUS_CLIENT_NETWORK")
        env_client_secret = os.environ.get("RADIUS_CLIENT_SECRET")
        
        if env_client_name and env_client_network and env_client_secret:
            existing_env_client = db.query(RadiusClient).filter(
                RadiusClient.name == env_client_name
            ).first()
            
            if not existing_env_client:
                logger.info(f"📝 Creating environment-configured client '{env_client_name}'...")
                env_client = RadiusClient(
                    name=env_client_name,
                    ipaddr=env_client_network,
                    secret=env_client_secret,
                    nas_type="other",
                    shortname=env_client_name,
                    require_message_authenticator=False,
                    is_active=True,
                    created_by="system",
                )
                db.add(env_client)
                logger.info(f"✅ Environment client '{env_client_name}' created for {env_client_network}")
            else:
                # Update existing client if network or secret changed
                if existing_env_client.ipaddr != env_client_network or existing_env_client.secret != env_client_secret:
                    logger.info(f"📝 Updating environment-configured client '{env_client_name}'...")
                    existing_env_client.ipaddr = env_client_network
                    existing_env_client.secret = env_client_secret
                    logger.info(f"✅ Environment client '{env_client_name}' updated")
                else:
                    logger.info(f"✅ Environment client '{env_client_name}' already exists with correct settings")
        
        # 2. Create default EAP configuration
        existing_eap_config = db.query(RadiusEapConfig).filter(
            RadiusEapConfig.is_active == True
        ).first()
        
        if not existing_eap_config:
            logger.info("📝 Creating default EAP configuration...")
            eap_config = RadiusEapConfig(
                name="default",
                description="Default EAP configuration - created on first run",
                default_eap_type="peap",
                enabled_methods=["peap", "ttls", "tls"],
                tls_min_version="1.2",
                tls_max_version="1.3",
                is_active=True,
                created_by="system",
            )
            db.add(eap_config)
            db.flush()  # Flush to get the ID
            
            # Create EAP method records
            for method_name in ["peap", "ttls", "tls"]:
                eap_method = RadiusEapMethod(
                    eap_config_id=eap_config.id,
                    method_name=method_name,
                    is_enabled=True,
                )
                db.add(eap_method)
            
            logger.info("✅ Default EAP configuration created with PEAP, TTLS, and TLS enabled")
        else:
            logger.info("✅ Default EAP configuration already exists")
        
        # 3. Create default MAC bypass configuration (empty)
        # Note: Policy IDs will be updated after unlang policies are created
        existing_mac_bypass = db.query(RadiusMacBypassConfig).filter(
            RadiusMacBypassConfig.name == "default"
        ).first()
        
        if not existing_mac_bypass:
            logger.info("📝 Creating default MAC bypass configuration...")
            mac_bypass = RadiusMacBypassConfig(
                name="default",
                description="Default MAC bypass configuration - add MAC addresses to bypass authentication",
                mac_addresses=[],
                bypass_mode="whitelist",
                require_registration=False,
                is_active=True,
                created_by="system",
            )
            db.add(mac_bypass)
            logger.info("✅ Default MAC bypass configuration created (policies will be linked later)")
        else:
            logger.info("✅ Default MAC bypass configuration already exists")
        
        # 4. Create default authorization policies
        existing_policy = db.query(RadiusPolicy).filter(
            RadiusPolicy.name == "default-accept"
        ).first()
        
        if not existing_policy:
            logger.info("📝 Creating default authorization policies...")
            
            # Default accept policy (lowest priority - fallback)
            default_policy = RadiusPolicy(
                name="default-accept",
                description="Default policy - accepts all authenticated requests",
                priority=1000,  # Lowest priority
                policy_type="user",
                is_active=True,
                psk_validation_required=False,
                mac_matching_enabled=False,
                match_on_psk_only=False,
                include_udn=True,
                created_by="system",
            )
            db.add(default_policy)
            
            # PSK-based policy for registered users
            psk_policy = RadiusPolicy(
                name="psk-registered-users",
                description="Policy for PSK-authenticated registered users - includes UDN",
                priority=100,
                policy_type="user",
                is_active=True,
                psk_validation_required=True,
                mac_matching_enabled=False,  # PSK-only matching (no MAC required)
                match_on_psk_only=True,
                include_udn=True,
                registered_group_policy="registered",
                created_by="system",
            )
            db.add(psk_policy)
            
            # Unregistered users policy (splash page)
            unregistered_policy = RadiusPolicy(
                name="unregistered-users",
                description="Policy for unregistered users - redirects to splash page",
                priority=50,
                policy_type="user",
                is_active=True,
                psk_validation_required=False,
                mac_matching_enabled=False,
                match_on_psk_only=False,
                include_udn=False,
                splash_url="/splash",
                unregistered_group_policy="unregistered",
                created_by="system",
            )
            db.add(unregistered_policy)
            
            logger.info("✅ Default authorization policies created")
        else:
            logger.info("✅ Default authorization policies already exist")
        
        # 5. Create default unlang policies (authorization policies with conditions)
        # These are what get assigned to EAP methods, MAC Bypass, and PSK configs
        existing_unlang = db.query(RadiusUnlangPolicy).filter(
            RadiusUnlangPolicy.name == "registered-users"
        ).first()
        
        if not existing_unlang:
            logger.info("📝 Creating default unlang (authorization) policies...")
            
            # Get the authorization profiles we just created to link to them
            psk_profile = db.query(RadiusPolicy).filter(
                RadiusPolicy.name == "psk-registered-users"
            ).first()
            unreg_profile = db.query(RadiusPolicy).filter(
                RadiusPolicy.name == "unregistered-users"
            ).first()
            default_profile = db.query(RadiusPolicy).filter(
                RadiusPolicy.name == "default-accept"
            ).first()
            
            # Policy for registered/authenticated users
            registered_policy = RadiusUnlangPolicy(
                name="registered-users",
                description="Apply registered user profile on successful authentication",
                priority=100,
                policy_type="authorization",
                section="authorize",
                condition_type="attribute",
                condition_attribute="User-Name",
                condition_operator="exists",
                action_type="apply_profile",
                authorization_profile_id=psk_profile.id if psk_profile else None,
                is_active=True,
                created_by="system",
            )
            db.add(registered_policy)
            
            # Policy for unregistered/guest users
            guest_policy = RadiusUnlangPolicy(
                name="guest-users",
                description="Apply guest profile for unregistered devices",
                priority=200,
                policy_type="authorization",
                section="authorize",
                condition_type="attribute",
                condition_attribute="User-Name",
                condition_operator="exists",
                action_type="apply_profile",
                authorization_profile_id=unreg_profile.id if unreg_profile else None,
                is_active=True,
                created_by="system",
            )
            db.add(guest_policy)
            
            # Default accept policy (fallback)
            default_unlang = RadiusUnlangPolicy(
                name="default-accept",
                description="Default accept policy - fallback for all users",
                priority=1000,
                policy_type="authorization",
                section="authorize",
                condition_type="attribute",
                condition_attribute="User-Name",
                condition_operator="exists",
                action_type="accept",
                authorization_profile_id=default_profile.id if default_profile else None,
                is_active=True,
                created_by="system",
            )
            db.add(default_unlang)
            
            logger.info("✅ Default unlang policies created (registered-users, guest-users, default-accept)")
            
            # Now link the MAC bypass config to the policies
            mac_bypass_config = db.query(RadiusMacBypassConfig).filter(
                RadiusMacBypassConfig.name == "default"
            ).first()
            
            if mac_bypass_config:
                mac_bypass_config.registered_policy_id = registered_policy.id
                mac_bypass_config.unregistered_policy_id = guest_policy.id
                logger.info("✅ MAC bypass config linked to policies")
            
            # Also link EAP methods to the default policy
            db.flush()  # Ensure policy IDs are available
            eap_methods = db.query(RadiusEapMethod).all()
            for method in eap_methods:
                if method.success_policy_id is None:
                    method.success_policy_id = registered_policy.id
                    logger.info(f"✅ EAP method {method.method_name} linked to registered-users policy")
        else:
            logger.info("✅ Default unlang policies already exist")
        
        # 6. Create default PSK configuration
        existing_psk = db.query(RadiusPskConfig).filter(
            RadiusPskConfig.name == "default"
        ).first()
        
        if not existing_psk:
            logger.info("📝 Creating default PSK configuration...")
            
            # Get the registered users policy
            registered_policy = db.query(RadiusUnlangPolicy).filter(
                RadiusUnlangPolicy.name == "registered-users"
            ).first()
            
            psk_config = RadiusPskConfig(
                name="default",
                description="Default PSK configuration for IPSK authentication",
                psk_type="user",
                auth_policy_id=registered_policy.id if registered_policy else None,
                is_active=True,
                created_by="system",
            )
            db.add(psk_config)
            logger.info("✅ Default PSK configuration created")
        else:
            logger.info("✅ Default PSK configuration already exists")
        
        db.commit()
        logger.info("✅ Default data initialization complete")
        
    except Exception as e:
        logger.error(f"❌ Failed to create default data: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def initialize_database() -> bool:
    """Initialize database schema and default data.
    
    This is the main entry point for database initialization.
    Safe to call multiple times - will only create missing components.
    
    Returns:
        True if initialization successful, False otherwise
    """
    try:
        engine = get_engine()
        
        # Create schema
        create_schema(engine)
        
        # Apply EAP migrations
        apply_eap_migrations(engine)
        
        # Initialize default data
        init_default_data(engine)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        return False


def apply_eap_migrations(engine) -> None:
    """Apply EAP-related migrations to existing database.
    
    Args:
        engine: SQLAlchemy engine
    """
    logger.info("🔄 Checking for EAP module migrations...")
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    # The new EAP tables will be created automatically by Base.metadata.create_all()
    # This function just logs what's being added
    
    new_tables = []
    for table_name in ["radius_eap_configs", "radius_eap_methods", "radius_user_certificates"]:
        if table_name not in existing_tables:
            new_tables.append(table_name)
    
    if new_tables:
        logger.info(f"📊 Creating EAP tables: {new_tables}")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ EAP tables created successfully")
    else:
        logger.info("✅ EAP tables already exist")


def verify_schema() -> dict[str, bool]:
    """Verify that all required tables exist and have correct structure.
    
    Returns:
        Dictionary with verification results
    """
    try:
        engine = get_engine()
        inspector = inspect(engine)
        
        results = {
            "radius_clients_exists": check_table_exists(engine, "radius_clients"),
            "udn_assignments_exists": check_table_exists(engine, "udn_assignments"),
            "radius_eap_configs_exists": check_table_exists(engine, "radius_eap_configs"),
            "radius_eap_methods_exists": check_table_exists(engine, "radius_eap_methods"),
            "radius_user_certificates_exists": check_table_exists(engine, "radius_user_certificates"),
        }
        
        # Check for required columns in radius_clients
        if results["radius_clients_exists"]:
            columns = [col["name"] for col in inspector.get_columns("radius_clients")]
            results["radius_clients_has_created_by"] = "created_by" in columns
            results["radius_clients_columns"] = columns
        
        # Check for required columns in udn_assignments
        if results["udn_assignments_exists"]:
            columns = [col["name"] for col in inspector.get_columns("udn_assignments")]
            results["udn_assignments_columns"] = columns
        
        # Check EAP config table
        if results["radius_eap_configs_exists"]:
            columns = [col["name"] for col in inspector.get_columns("radius_eap_configs")]
            results["radius_eap_configs_columns"] = columns
        
        return results
        
    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        return {"error": str(e)}
