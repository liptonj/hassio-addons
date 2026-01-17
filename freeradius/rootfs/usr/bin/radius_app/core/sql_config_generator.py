"""SQL module configuration generator for FreeRADIUS.

Per FreeRADIUS SQL documentation:
https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/index.html

The SQL module allows FreeRADIUS to query user data directly from the database
at runtime, rather than using static users files. This is more dynamic and
allows for real-time updates without regenerating config files.

Uses Jinja2 templates for clean, maintainable configuration generation.
"""

import logging
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from sqlalchemy.orm import Session

from radius_app.config import get_settings

logger = logging.getLogger(__name__)


class SqlConfigGenerator:
    """Generate FreeRADIUS SQL module configuration.
    
    Per FreeRADIUS SQL documentation, the SQL module uses:
    - radcheck/radreply tables for user-specific attributes
    - radusergroup/radgroupcheck/radgroupreply for group-based attributes
    - Proper operators (:=, ==, +=, etc.) for check and reply items
    """
    
    def __init__(self):
        """Initialize SQL config generator."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.radius_config_path)
        self.mods_available = self.config_path / "mods-available"
        self.mods_enabled = self.config_path / "mods-enabled"
        
        # Ensure directories exist
        self.mods_available.mkdir(parents=True, exist_ok=True)
        self.mods_enabled.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        
        logger.info(f"SQL config generator initialized: {self.config_path}")
    
    def write_sql_module_config(self, db: Session) -> Path:
        """Generate and write SQL module configuration, then enable it.
        
        Per FreeRADIUS modules documentation:
        - Modules are enabled by creating symlinks from mods-enabled/ to mods-available/
        - This method writes the config and creates the symlink
        
        Args:
            db: Database session
            
        Returns:
            Path to generated SQL module config file
        """
        logger.info("Generating and enabling SQL module configuration")
        
        # Ensure directories exist
        self.mods_available.mkdir(parents=True, exist_ok=True)
        self.mods_enabled.mkdir(parents=True, exist_ok=True)
        
        # Generate config
        config = self.generate_sql_module_config(db)
        
        # Write to mods-available
        sql_file = self.mods_available / "sql"
        sql_file.write_text(config)
        logger.info(f"✅ Wrote SQL module config: {sql_file}")
        
        # Create symlink in mods-enabled (enable module)
        sql_enabled = self.mods_enabled / "sql"
        if sql_enabled.exists() or sql_enabled.is_symlink():
            sql_enabled.unlink()
        sql_enabled.symlink_to(sql_file)
        logger.info(f"✅ Enabled SQL module: {sql_enabled} -> {sql_file}")
        
        return sql_file
    
    def _parse_database_url(self, db_url: str) -> dict:
        """Parse database URL to extract connection parameters.
        
        Args:
            db_url: Database URL (mysql+pymysql://, postgresql://, sqlite:///)
            
        Returns:
            Dictionary with driver, host, port, user, password, dbname
        """
        if db_url.startswith("mysql") or db_url.startswith("mariadb"):
            driver = "mysql"
            # Extract connection details: mysql+pymysql://user:pass@host:port/dbname
            parts = db_url.replace("mysql+pymysql://", "").replace("mariadb+pymysql://", "").split("@")
            if len(parts) == 2:
                user_pass = parts[0].split(":")
                user = user_pass[0]
                password = ":".join(user_pass[1:]) if len(user_pass) > 1 else ""
                host_db = parts[1].split("/")
                host_port = host_db[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 3306
                dbname = host_db[1] if len(host_db) > 1 else "radius"
            else:
                host, port, user, password, dbname = "localhost", 3306, "radius", "", "radius"
                
        elif db_url.startswith("postgresql"):
            driver = "postgresql"
            parts = db_url.replace("postgresql://", "").replace("postgresql+psycopg2://", "").split("@")
            if len(parts) == 2:
                user_pass = parts[0].split(":")
                user = user_pass[0]
                password = ":".join(user_pass[1:]) if len(user_pass) > 1 else ""
                host_db = parts[1].split("/")
                host_port = host_db[0].split(":")
                host = host_port[0]
                port = int(host_port[1]) if len(host_port) > 1 else 5432
                dbname = host_db[1] if len(host_db) > 1 else "radius"
            else:
                host, port, user, password, dbname = "localhost", 5432, "radius", "", "radius"
                
        elif db_url.startswith("sqlite"):
            driver = "sqlite"
            dbname = db_url.replace("sqlite:///", "")
            host, port, user, password = "", 0, "", ""
            
        else:
            return None
        
        return {
            "driver": driver,
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "dbname": dbname,
        }
    
    def generate_sql_module_config(self, db: Session) -> str:
        """Generate SQL module configuration.
        
        Per FreeRADIUS SQL documentation:
        - SQL module connects to database for runtime lookups
        - Uses radcheck/radreply tables for user attributes
        - Uses radusergroup/radgroupcheck/radgroupreply for group attributes
        
        Args:
            db: Database session (for connection string extraction)
            
        Returns:
            SQL module configuration as string
        """
        logger.info("Generating SQL module configuration")
        
        # Parse database URL
        db_url = self.settings.database_url
        db_config = self._parse_database_url(db_url)
        
        if not db_config:
            logger.warning(f"Unknown database type in URL: {db_url}")
            return self._generate_default_sql_config()
        
        # Build template context
        context = {
            "driver": db_config["driver"],
            "host": db_config["host"],
            "port": db_config["port"],
            "user": db_config["user"],
            "password": db_config["password"],
            "dbname": db_config["dbname"],
            "pool": {
                "start": 5,
                "min": 4,
                "max": 10,
                "spare": 3,
                "uses": 0,
                "retry_delay": 30,
                "lifetime": 0,
                "idle_timeout": 60,
                "connect_timeout": 3.0,
            },
            "tables": {
                "radcheck": "radcheck",
                "radreply": "radreply",
                "radusergroup": "radusergroup",
                "radgroupcheck": "radgroupcheck",
                "radgroupreply": "radgroupreply",
                "radacct": "radacct",
                "radpostauth": "radpostauth",
            },
            "read_groups": True,
            "remove_stale_sessions": True,
            "query_timeout": 5,
            "connect_failure_retry_delay": 60,
        }
        
        try:
            template = self.jinja_env.get_template("sql_module.j2")
            config_content = template.render(**context)
            return config_content
        except TemplateNotFound:
            logger.error("SQL module template not found - falling back to code generation")
            return self._generate_fallback_sql_config(db_config)
        except Exception as e:
            logger.error(f"Error rendering SQL module template: {e}", exc_info=True)
            return self._generate_fallback_sql_config(db_config)
    
    def _generate_fallback_sql_config(self, db_config: dict) -> str:
        """Fallback SQL config generation if template fails.
        
        Args:
            db_config: Database configuration dictionary
            
        Returns:
            SQL module configuration as string
        """
        logger.warning("Using fallback code-based SQL configuration generation")
        
        driver = db_config["driver"]
        host = db_config["host"]
        port = db_config["port"]
        user = db_config["user"]
        password = db_config["password"]
        dbname = db_config["dbname"]
        
        config_lines = [
            "# SQL module configuration - Generated (fallback mode)",
            "sql {",
        ]
        
        if driver in ("mysql", "mariadb"):
            config_lines.extend([
                '    driver = "rlm_sql_mysql"',
                f'    server = "{host}"',
                f'    port = {port}',
                f'    login = "{user}"',
                f'    password = "{password}"',
                f'    radius_db = "{dbname}"',
            ])
        elif driver == "postgresql":
            config_lines.extend([
                '    driver = "rlm_sql_postgresql"',
                f'    server = "{host}"',
                f'    port = {port}',
                f'    login = "{user}"',
                f'    password = "{password}"',
                f'    radius_db = "{dbname}"',
            ])
        elif driver == "sqlite":
            config_lines.extend([
                '    driver = "rlm_sql_sqlite"',
                '    sqlite {',
                f'        filename = "{dbname}"',
                '    }',
            ])
        
        config_lines.extend([
            '    read_groups = yes',
            '    query_timeout = 5',
            '}',
        ])
        
        return "\n".join(config_lines)
    
    def _generate_default_sql_config(self) -> str:
        """Generate default SQL module configuration.
        
        Returns:
            Default SQL configuration as string
        """
        logger.warning("Generating default SQL configuration (no database URL)")
        
        return """# SQL module configuration - Default (no database config)
# This is a placeholder - configure database connection in settings

sql {
    # Default SQLite configuration
    driver = "rlm_sql_sqlite"
    
    sqlite {
        filename = "/config/freeradius.db"
        busy_timeout = 200
        bootstrap = "${modconfdir}/../sql/main/sqlite/schema.sql"
    }
    
    # Note: Configure proper database connection in portal settings
    # See FreeRADIUS SQL documentation for details
}
"""
    
    def generate_sql_schema_script(self) -> str:
        """Generate SQL schema creation script for radcheck/radreply tables.
        
        Per FreeRADIUS SQL documentation, these tables are required:
        - radcheck: User check attributes (operators: :=, ==, +=, etc.)
        - radreply: User reply attributes (operators: :=, +=)
        - radusergroup: User group membership with priority
        - radgroupcheck: Group check attributes
        - radgroupreply: Group reply attributes
        
        Returns:
            SQL schema creation script
        """
        logger.info("Generating SQL schema script")
        
        schema = """-- FreeRADIUS SQL Schema
-- Per FreeRADIUS SQL documentation:
-- https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/index.html
--
-- These tables are used by the SQL module for runtime user lookups

-- User check attributes (radcheck table)
-- Used for authentication and authorization checks
CREATE TABLE IF NOT EXISTS radcheck (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL DEFAULT '',
    attribute VARCHAR(64) NOT NULL DEFAULT '',
    op CHAR(2) NOT NULL DEFAULT '==',
    value VARCHAR(253) NOT NULL DEFAULT '',
    INDEX username (username(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User reply attributes (radreply table)
-- Used for authorization reply attributes
CREATE TABLE IF NOT EXISTS radreply (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL DEFAULT '',
    attribute VARCHAR(64) NOT NULL DEFAULT '',
    op CHAR(2) NOT NULL DEFAULT '=',
    value VARCHAR(253) NOT NULL DEFAULT '',
    INDEX username (username(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User group membership (radusergroup table)
-- Links users to groups with priority for ordering
CREATE TABLE IF NOT EXISTS radusergroup (
    username VARCHAR(64) NOT NULL DEFAULT '',
    groupname VARCHAR(64) NOT NULL DEFAULT '',
    priority INT NOT NULL DEFAULT 1,
    PRIMARY KEY (username, groupname),
    INDEX groupname (groupname(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Group check attributes (radgroupcheck table)
-- Check attributes applied to group members
CREATE TABLE IF NOT EXISTS radgroupcheck (
    id INT PRIMARY KEY AUTO_INCREMENT,
    groupname VARCHAR(64) NOT NULL DEFAULT '',
    attribute VARCHAR(64) NOT NULL DEFAULT '',
    op CHAR(2) NOT NULL DEFAULT '==',
    value VARCHAR(253) NOT NULL DEFAULT '',
    INDEX groupname (groupname(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Group reply attributes (radgroupreply table)
-- Reply attributes applied to group members
CREATE TABLE IF NOT EXISTS radgroupreply (
    id INT PRIMARY KEY AUTO_INCREMENT,
    groupname VARCHAR(64) NOT NULL DEFAULT '',
    attribute VARCHAR(64) NOT NULL DEFAULT '',
    op CHAR(2) NOT NULL DEFAULT '=',
    value VARCHAR(253) NOT NULL DEFAULT '',
    INDEX groupname (groupname(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Accounting table (radacct)
CREATE TABLE IF NOT EXISTS radacct (
    radacctid BIGINT PRIMARY KEY AUTO_INCREMENT,
    acctuniqueid VARCHAR(32) NOT NULL DEFAULT '',
    acctsessionid VARCHAR(64) NOT NULL DEFAULT '',
    username VARCHAR(64) NOT NULL DEFAULT '',
    realm VARCHAR(64) DEFAULT '',
    nasipaddress VARCHAR(15) NOT NULL DEFAULT '',
    nasportid VARCHAR(15) DEFAULT NULL,
    nasporttype VARCHAR(32) DEFAULT NULL,
    acctstarttime DATETIME DEFAULT NULL,
    acctstoptime DATETIME DEFAULT NULL,
    acctsessiontime INT DEFAULT NULL,
    acctauthentic VARCHAR(32) DEFAULT NULL,
    connectinfo_start VARCHAR(50) DEFAULT NULL,
    connectinfo_stop VARCHAR(50) DEFAULT NULL,
    acctinputoctets BIGINT DEFAULT NULL,
    acctoutputoctets BIGINT DEFAULT NULL,
    calledstationid VARCHAR(50) NOT NULL DEFAULT '',
    callingstationid VARCHAR(50) NOT NULL DEFAULT '',
    acctterminatecause VARCHAR(32) NOT NULL DEFAULT '',
    servicetype VARCHAR(32) DEFAULT NULL,
    framedprotocol VARCHAR(32) DEFAULT NULL,
    framedipaddress VARCHAR(15) NOT NULL DEFAULT '',
    INDEX acctuniqueid (acctuniqueid),
    INDEX username (username),
    INDEX framedipaddress (framedipaddress),
    INDEX acctsessionid (acctsessionid),
    INDEX acctsessiontime (acctsessiontime),
    INDEX acctstarttime (acctstarttime),
    INDEX acctstoptime (acctstoptime),
    INDEX nasipaddress (nasipaddress)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Post-authentication logging (radpostauth)
CREATE TABLE IF NOT EXISTS radpostauth (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL DEFAULT '',
    pass VARCHAR(64) NOT NULL DEFAULT '',
    reply VARCHAR(32) NOT NULL DEFAULT '',
    authdate TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX username (username(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
        
        return schema
    
    def sync_psk_to_radcheck(self, db: Session, portal_db_url: Optional[str] = None) -> dict:
        """Sync PSK data from portal database to radcheck/radreply tables.
        
        Per FreeRADIUS SQL documentation:
        - radcheck: Check attributes (e.g., Cleartext-Password := "passphrase")
        - radreply: Reply attributes (e.g., Cisco-AVPair := "udn:private-group-id=100")
        
        This allows FreeRADIUS to query PSK data directly from SQL at runtime.
        
        Args:
            db: FreeRADIUS database session
            portal_db_url: Portal database URL (if different)
            
        Returns:
            Dictionary with sync statistics
        """
        logger.info("Syncing PSK data to radcheck/radreply tables")
        
        stats = {
            "users_synced": 0,
            "radcheck_entries": 0,
            "radreply_entries": 0,
            "errors": [],
        }
        
        try:
            # Check if radcheck/radreply tables exist
            from sqlalchemy import inspect, text
            inspector = inspect(db.bind)
            tables = inspector.get_table_names()
            
            if "radcheck" not in tables or "radreply" not in tables:
                logger.warning("radcheck/radreply tables not found - creating schema")
                schema = self.generate_sql_schema_script()
                # Execute schema creation
                for statement in schema.split(";"):
                    statement = statement.strip()
                    if statement and not statement.startswith("--"):
                        try:
                            db.execute(text(statement))
                        except Exception as e:
                            logger.warning(f"Schema creation warning: {e}")
                db.commit()
            
            # Query users with PSK from portal database
            if portal_db_url:
                from sqlalchemy import create_engine
                portal_engine = create_engine(portal_db_url)
                with portal_engine.connect() as portal_conn:
                    result = portal_conn.execute(text("""
                        SELECT 
                            id,
                            email,
                            ipsk_id,
                            ipsk_passphrase_encrypted,
                            ipsk_name,
                            ssid_name,
                            unit
                        FROM users
                        WHERE ipsk_passphrase_encrypted IS NOT NULL
                          AND ipsk_passphrase_encrypted != ''
                          AND is_active = true
                        ORDER BY email
                    """))
                    
                    users = result.fetchall()
                    logger.info(f"Found {len(users)} users with PSK")
                    
                    for user in users:
                        user_id = user[0]
                        email = user[1]
                        ipsk_id = user[2]
                        encrypted_passphrase = user[3]
                        ipsk_name = user[4]
                        ssid_name = user[5]
                        unit = user[6]
                        
                        # Decrypt passphrase
                        passphrase = self._decrypt_passphrase(encrypted_passphrase, portal_db_url)
                        if not passphrase:
                            logger.warning(f"Could not decrypt passphrase for user {email}")
                            stats["errors"].append(f"User {email}: Could not decrypt passphrase")
                            continue
                        
                        # Username for RADIUS (use ipsk_id or email)
                        username = ipsk_id or email
                        
                        # Look up UDN ID for this user
                        from sqlalchemy import select
                        from radius_app.db.models import UdnAssignment
                        udn_stmt = select(UdnAssignment).where(
                            UdnAssignment.user_id == user_id,
                            UdnAssignment.is_active == True
                        )
                        udn_assignment = db.execute(udn_stmt).scalar_one_or_none()
                        
                        # Insert into radcheck (authentication)
                        # Per FreeRADIUS SQL docs: operator := means "always matches and replaces"
                        try:
                            # Delete existing entries for this username
                            db.execute(text("""
                                DELETE FROM radcheck WHERE username = :username
                            """), {"username": username})
                            db.execute(text("""
                                DELETE FROM radreply WHERE username = :username
                            """), {"username": username})
                            
                            # Insert Cleartext-Password check attribute
                            # Operator := means "always matches"
                            db.execute(text("""
                                INSERT INTO radcheck (username, attribute, op, value)
                                VALUES (:username, 'Cleartext-Password', ':=', :password)
                            """), {"username": username, "password": passphrase})
                            stats["radcheck_entries"] += 1
                            
                            # Insert reply attributes into radreply
                            # Operator := means "add to reply list"
                            reply_attrs = []
                            
                            # UDN ID reply attribute
                            if udn_assignment:
                                reply_attrs.append((
                                    username,
                                    "Cisco-AVPair",
                                    ":=",
                                    f"udn:private-group-id={udn_assignment.udn_id}"
                                ))
                            
                            # SSID name reply attribute
                            if ssid_name:
                                reply_attrs.append((
                                    username,
                                    "Reply-Message",
                                    ":=",
                                    f"SSID: {ssid_name}"
                                ))
                            
                            # Insert reply attributes
                            for attr_username, attr_name, attr_op, attr_value in reply_attrs:
                                db.execute(text("""
                                    INSERT INTO radreply (username, attribute, op, value)
                                    VALUES (:username, :attribute, :op, :value)
                                """), {
                                    "username": attr_username,
                                    "attribute": attr_name,
                                    "op": attr_op,
                                    "value": attr_value
                                })
                                stats["radreply_entries"] += 1
                            
                            stats["users_synced"] += 1
                            
                        except Exception as e:
                            logger.error(f"Failed to sync user {email}: {e}")
                            stats["errors"].append(f"User {email}: {str(e)}")
                            db.rollback()
                            continue
                    
                    db.commit()
                    logger.info(f"✅ Synced {stats['users_synced']} users to radcheck/radreply")
            
        except Exception as e:
            logger.error(f"Failed to sync PSK to radcheck: {e}", exc_info=True)
            stats["errors"].append(f"Sync failed: {str(e)}")
        
        return stats
    
    def _decrypt_passphrase(self, encrypted_passphrase: str, portal_db_url: Optional[str] = None) -> Optional[str]:
        """Decrypt PSK passphrase for SQL storage.
        
        Args:
            encrypted_passphrase: Encrypted passphrase from database
            portal_db_url: Portal database URL (for decryption if needed)
            
        Returns:
            Decrypted passphrase or None if decryption fails
        """
        # TODO: Implement proper passphrase decryption
        # This should use the same encryption key as the portal
        logger.warning("Passphrase decryption not yet implemented - PSK entries will need manual configuration")
        return None
