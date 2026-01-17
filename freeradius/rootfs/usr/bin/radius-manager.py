#!/usr/bin/env python3
"""
FreeRADIUS Configuration Management API

This service provides a RESTful API for managing FreeRADIUS configuration,
including clients, users, and certificates. It's designed to be called by
the Meraki WPN Portal for dynamic RADIUS configuration.
"""

import argparse
import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Header, status
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

# Try to import PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("PostgreSQL support not available")

# Try to import MySQL/MariaDB support
try:
    import pymysql
    pymysql.install_as_MySQLdb()  # Makes it work with MySQLdb-compatible code
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("MySQL/MariaDB support not available")

if not POSTGRES_AVAILABLE and not MYSQL_AVAILABLE:
    logger_temp.warning("No database drivers available, using SQLite only")

# Configuration from environment
CONFIG_PATH = os.getenv("RADIUS_CONFIG_PATH", "/etc/raddb")
CERTS_PATH = os.getenv("RADIUS_CERTS_PATH", "/config/certs")
CLIENTS_PATH = os.getenv("RADIUS_CLIENTS_PATH", "/config/clients")
DATABASE_TYPE = os.getenv("RADIUS_DATABASE_TYPE", "sqlite")
DATABASE_PATH = os.getenv("RADIUS_DATABASE_PATH", "/config/freeradius.db")
LOG_LEVEL = os.getenv("RADIUS_LOG_LEVEL", "info").upper()

# Portal database connection
PORTAL_DB_TYPE = os.getenv("PORTAL_DB_TYPE", "mysql")  # mysql, postgresql, or sqlite
PORTAL_DB_HOST = os.getenv("PORTAL_DB_HOST", "core-mariadb")
PORTAL_DB_PORT = int(os.getenv("PORTAL_DB_PORT", "3306"))  # Default MySQL port
PORTAL_DB_NAME = os.getenv("PORTAL_DB_NAME", "wpn_radius")
PORTAL_DB_USER = os.getenv("PORTAL_DB_USER", "wpn-user")
PORTAL_DB_PASSWORD = os.getenv("PORTAL_DB_PASSWORD", "C1sco5150!")

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="FreeRADIUS Configuration API",
    description="API for managing FreeRADIUS configuration",
    version="1.0.0"
)


# Pydantic models
class RadiusClient(BaseModel):
    """RADIUS client configuration."""
    name: str = Field(..., description="Client name/identifier")
    ipaddr: str = Field(..., description="Client IP address or CIDR")
    secret: str = Field(..., description="Shared secret")
    nas_type: str = Field(default="other", description="NAS type")
    shortname: Optional[str] = Field(None, description="Short name")
    require_message_authenticator: bool = Field(default=True)


class RadiusUser(BaseModel):
    """RADIUS user/MAC authorization."""
    username: str = Field(..., description="Username or MAC address")
    password: Optional[str] = Field(None, description="Password (if applicable)")
    reply_attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Reply attributes (e.g., Cisco-AVPair)"
    )


class UdnAssignment(BaseModel):
    """UDN ID assignment for MAC address."""
    mac_address: str = Field(..., description="MAC address (normalized)")
    udn_id: int = Field(..., description="UDN ID (2-16777200)")
    user_email: Optional[str] = Field(None, description="Associated user email")
    unit_number: Optional[str] = Field(None, description="Associated unit")
    is_active: bool = Field(default=True, description="Is assignment active")


class SyncRequest(BaseModel):
    """Request to sync configuration from portal database."""
    sync_clients: bool = Field(default=True, description="Sync RADIUS clients")
    sync_users: bool = Field(default=True, description="Sync UDN assignments")
    reload_radius: bool = Field(default=True, description="Reload RADIUS after sync")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    radius_running: bool
    portal_db_connected: bool
    config_files_exist: bool


# Authentication
def verify_token(authorization: str = Header(None)) -> bool:
    """Verify API token from header.
    
    Security: API_AUTH_TOKEN MUST be configured. No bypass allowed.
    This enforces authentication for all API endpoints.
    
    Raises
    ------
    HTTPException
        - 500: If API_AUTH_TOKEN is not configured (server misconfigured)
        - 401: If authorization header is missing or invalid
    """
    api_token = os.getenv("API_AUTH_TOKEN", "")
    if not api_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_AUTH_TOKEN not configured - server misconfigured. "
                   "Administrator must set API_AUTH_TOKEN environment variable."
        )
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = authorization.replace("Bearer ", "")
    if token != api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    return True


# Database helpers
def get_db_connection():
    """Get database connection."""
    if DATABASE_TYPE == "sqlite":
        return sqlite3.connect(DATABASE_PATH)
    
    raise NotImplementedError(f"Database type {DATABASE_TYPE} not yet implemented")


def get_portal_db_connection():
    """Get connection to portal database (MySQL/MariaDB or PostgreSQL)."""
    
    if PORTAL_DB_TYPE == "mysql" or PORTAL_DB_TYPE == "mariadb":
        if not MYSQL_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MySQL/MariaDB support not available (pip install pymysql)"
            )
        
        try:
            conn = pymysql.connect(
                host=PORTAL_DB_HOST,
                port=PORTAL_DB_PORT,
                database=PORTAL_DB_NAME,
                user=PORTAL_DB_USER,
                password=PORTAL_DB_PASSWORD,
                cursorclass=pymysql.cursors.DictCursor,
                charset='utf8mb4'
            )
            logger.debug(f"Connected to MySQL database: {PORTAL_DB_NAME} at {PORTAL_DB_HOST}:{PORTAL_DB_PORT}")
            return conn
        except pymysql.Error as e:
            logger.error(f"Failed to connect to MySQL/MariaDB database: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MySQL/MariaDB database unavailable: {str(e)}"
            )
    
    elif PORTAL_DB_TYPE == "postgresql":
        if not POSTGRES_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PostgreSQL support not available (pip install psycopg2-binary)"
            )
        
        try:
            conn = psycopg2.connect(
                host=PORTAL_DB_HOST,
                port=PORTAL_DB_PORT,
                database=PORTAL_DB_NAME,
                user=PORTAL_DB_USER,
                password=PORTAL_DB_PASSWORD,
                cursor_factory=RealDictCursor
            )
            logger.debug(f"Connected to PostgreSQL database: {PORTAL_DB_NAME} at {PORTAL_DB_HOST}:{PORTAL_DB_PORT}")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL database: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"PostgreSQL database unavailable: {str(e)}"
            )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported database type: {PORTAL_DB_TYPE}. Use 'mysql', 'mariadb', or 'postgresql'"
        )


def test_portal_db_connection() -> bool:
    """Test connection to portal database."""
    if PORTAL_DB_TYPE == "mysql" or PORTAL_DB_TYPE == "mariadb":
        if not MYSQL_AVAILABLE:
            return False
    elif PORTAL_DB_TYPE == "postgresql":
        if not POSTGRES_AVAILABLE:
            return False
    
    try:
        conn = get_portal_db_connection()
        conn.close()
        logger.info(f"✅ Portal database connection test successful ({PORTAL_DB_TYPE})")
        return True
    except Exception as e:
        logger.warning(f"Portal database connection test failed: {e}")
        return False


def normalize_mac_address(mac: str) -> str:
    """Normalize MAC address to FreeRADIUS format (lowercase, colon-separated)."""
    # Remove all non-hex characters
    mac_clean = re.sub(r'[^0-9a-fA-F]', '', mac)
    
    if len(mac_clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    
    # Convert to lowercase and add colons
    return ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2)).lower()


def init_database():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radius_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            ipaddr TEXT NOT NULL,
            secret TEXT NOT NULL,
            nas_type TEXT DEFAULT 'other',
            shortname TEXT,
            require_message_authenticator INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radius_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Reply attributes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS radius_reply_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            attribute TEXT NOT NULL,
            value TEXT NOT NULL,
            op TEXT DEFAULT ':=',
            FOREIGN KEY (username) REFERENCES radius_users(username)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


# API endpoints
@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting FreeRADIUS Configuration API")
    init_database()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    radius_running = Path("/var/run/radiusd/radiusd.pid").exists()
    portal_db_connected = test_portal_db_connection()
    
    clients_conf = Path(CLIENTS_PATH) / "clients.conf"
    users_file = Path(CONFIG_PATH) / "users"
    config_files_exist = clients_conf.exists() and users_file.exists()
    
    overall_status = "healthy"
    if not radius_running:
        overall_status = "degraded"
    elif not portal_db_connected:
        overall_status = "warning"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        radius_running=radius_running,
        portal_db_connected=portal_db_connected,
        config_files_exist=config_files_exist
    )


@app.get("/api/clients")
async def list_clients(authorization: str = Header(None)):
    """List all RADIUS clients."""
    verify_token(authorization)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, ipaddr, nas_type, shortname FROM radius_clients")
    
    clients = []
    for row in cursor.fetchall():
        clients.append({
            "id": row[0],
            "name": row[1],
            "ipaddr": row[2],
            "nas_type": row[3],
            "shortname": row[4]
        })
    
    conn.close()
    return {"clients": clients}


@app.post("/api/clients", status_code=status.HTTP_201_CREATED)
async def add_client(client: RadiusClient, authorization: str = Header(None)):
    """Add a new RADIUS client."""
    verify_token(authorization)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO radius_clients 
            (name, ipaddr, secret, nas_type, shortname, require_message_authenticator, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client.name,
            client.ipaddr,
            client.secret,
            client.nas_type,
            client.shortname or client.name,
            1 if client.require_message_authenticator else 0,
            now,
            now
        ))
        conn.commit()
        client_id = cursor.lastrowid
        
        # Generate clients.conf
        regenerate_clients_conf()
        
        logger.info(f"Added RADIUS client: {client.name}")
        return {"id": client_id, "message": "Client added successfully"}
        
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Client {client.name} already exists"
        )
    finally:
        conn.close()


@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: int, authorization: str = Header(None)):
    """Delete a RADIUS client."""
    verify_token(authorization)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM radius_clients WHERE id = ?", (client_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    conn.commit()
    conn.close()
    
    # Regenerate clients.conf
    regenerate_clients_conf()
    
    logger.info(f"Deleted RADIUS client ID: {client_id}")
    return {"message": "Client deleted successfully"}


@app.get("/api/users")
async def list_users(authorization: str = Header(None)):
    """List all RADIUS users."""
    verify_token(authorization)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, 
               GROUP_CONCAT(ra.attribute || '=' || ra.value, ', ') as attributes
        FROM radius_users u
        LEFT JOIN radius_reply_attributes ra ON u.username = ra.username
        GROUP BY u.id, u.username
    """)
    
    users = []
    for row in cursor.fetchall():
        users.append({
            "id": row[0],
            "username": row[1],
            "attributes": row[2] or ""
        })
    
    conn.close()
    return {"users": users}


@app.post("/api/users", status_code=status.HTTP_201_CREATED)
async def add_user(user: RadiusUser, authorization: str = Header(None)):
    """Add a new RADIUS user."""
    verify_token(authorization)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO radius_users (username, password, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (user.username, user.password, now, now))
        
        # Add reply attributes
        for attr, value in user.reply_attributes.items():
            cursor.execute("""
                INSERT INTO radius_reply_attributes (username, attribute, value, op)
                VALUES (?, ?, ?, ':=')
            """, (user.username, attr, value))
        
        conn.commit()
        user_id = cursor.lastrowid
        
        # Regenerate users file
        regenerate_users_file()
        
        logger.info(f"Added RADIUS user: {user.username}")
        return {"id": user_id, "message": "User added successfully"}
        
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {user.username} already exists"
        )
    finally:
        conn.close()


@app.post("/api/reload")
async def reload_config(authorization: str = Header(None)):
    """Reload FreeRADIUS configuration."""
    verify_token(authorization)
    
    # Send HUP signal to radiusd
    import subprocess
    try:
        subprocess.run(["killall", "-HUP", "radiusd"], check=True)
        logger.info("FreeRADIUS configuration reloaded")
        return {"message": "Configuration reloaded successfully"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to reload configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reload configuration"
        )


@app.post("/api/sync")
async def sync_from_portal(
    sync_request: SyncRequest,
    authorization: str = Header(None)
):
    """Sync configuration from portal database.
    
    This endpoint pulls RADIUS clients and UDN assignments from the portal's
    PostgreSQL database and regenerates FreeRADIUS configuration files.
    """
    verify_token(authorization)
    
    result = {
        "clients_synced": 0,
        "users_synced": 0,
        "errors": [],
        "reloaded": False
    }
    
    try:
        conn = get_portal_db_connection()
        cursor = conn.cursor()
        
        # Sync RADIUS clients
        if sync_request.sync_clients:
            try:
                cursor.execute("""
                    SELECT id, name, ipaddr, secret, nas_type, 
                           network_name, require_message_authenticator
                    FROM radius_clients
                    WHERE is_active = true
                """)
                
                clients = cursor.fetchall()
                result["clients_synced"] = len(clients)
                
                # Generate clients.conf directly from portal data
                clients_file = Path(CLIENTS_PATH) / "clients.conf"
                clients_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(clients_file, "w") as f:
                    f.write("# Auto-generated RADIUS clients from portal\n")
                    f.write(f"# Generated: {datetime.utcnow().isoformat()}\n")
                    f.write("# Do not edit manually\n\n")
                    
                    for client in clients:
                        name = client['name'].replace(' ', '_')
                        f.write(f"client {name} {{\n")
                        f.write(f"    ipaddr = {client['ipaddr']}\n")
                        f.write(f"    secret = {client['secret']}\n")
                        f.write(f"    nas_type = {client['nas_type'] or 'other'}\n")
                        
                        if client['network_name']:
                            f.write(f"    shortname = {client['network_name']}\n")
                        
                        if client['require_message_authenticator']:
                            f.write(f"    require_message_authenticator = yes\n")
                        
                        f.write("}\n\n")
                
                logger.info(f"Synced {len(clients)} RADIUS clients from portal")
                
            except Exception as e:
                error_msg = f"Failed to sync clients: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        # Sync UDN assignments (users)
        # Note: UDN is assigned to USER (not MAC). MAC is optional.
        if sync_request.sync_users:
            try:
                cursor.execute("""
                    SELECT user_id, mac_address, udn_id, user_email, unit, ipsk_id
                    FROM udn_assignments
                    WHERE is_active = true
                    ORDER BY user_id
                """)
                
                assignments = cursor.fetchall()
                result["users_synced"] = len(assignments)
                
                # Generate users file with UDN IDs
                # For PSK authentication, UDN is looked up via USER->PSK relationship
                users_file = Path(CONFIG_PATH) / "users"
                users_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(users_file, "w") as f:
                    f.write("# Auto-generated RADIUS users from portal\n")
                    f.write(f"# Generated: {datetime.utcnow().isoformat()}\n")
                    f.write("# Do not edit manually\n\n")
                    f.write("# UDN assignments: USER -> PSK -> UDN\n")
                    f.write("# MAC address is optional (for tracking only)\n")
                    f.write("# Format: MAC Auth-Type := Accept, Cisco-AVPair := \"udn:private-group-id=<UDN_ID>\"\n\n")
                    
                    for assignment in assignments:
                        user_id = assignment['user_id']
                        mac = assignment['mac_address']
                        udn_id = assignment['udn_id']
                        
                        # Comment with user info
                        f.write(f"# User ID: {user_id}")
                        if assignment['user_email']:
                            f.write(f", Email: {assignment['user_email']}")
                        if assignment['unit']:
                            f.write(f", Unit: {assignment['unit']}")
                        f.write(f"\n")
                        
                        if mac:
                            # MAC-based authentication entry (if MAC provided)
                            mac_normalized = normalize_mac_address(mac)
                            f.write(f"{mac_normalized} Auth-Type := Accept\n")
                            f.write(f"    Cisco-AVPair := \"udn:private-group-id={udn_id}\"\n\n")
                        else:
                            # User entry without MAC - PSK authentication will handle UDN lookup
                            f.write(f"# User {user_id} - UDN {udn_id} (PSK authentication)\n")
                            f.write(f"# PSK entries are generated separately\n\n")
                
                logger.info(f"Synced {len(assignments)} UDN assignments from portal")
                
            except Exception as e:
                error_msg = f"Failed to sync users: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        conn.close()
        
        # Reload RADIUS if requested and no errors
        if sync_request.reload_radius and not result["errors"]:
            try:
                import subprocess
                subprocess.run(["killall", "-HUP", "radiusd"], check=True)
                result["reloaded"] = True
                logger.info("FreeRADIUS reloaded after sync")
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to reload RADIUS: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        return result
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


def regenerate_clients_conf():
    """Regenerate clients.conf from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, ipaddr, secret, nas_type, shortname FROM radius_clients")
    
    clients_file = Path(CLIENTS_PATH) / "clients.conf"
    clients_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(clients_file, "w") as f:
        f.write("# Auto-generated RADIUS clients configuration\n")
        f.write("# Do not edit manually - managed by radius-manager API\n\n")
        
        for row in cursor.fetchall():
            name, ipaddr, secret, nas_type, shortname = row
            f.write(f"client {name} {{\n")
            f.write(f"    ipaddr = {ipaddr}\n")
            f.write(f"    secret = {secret}\n")
            f.write(f"    nas_type = {nas_type}\n")
            if shortname:
                f.write(f"    shortname = {shortname}\n")
            f.write(f"    require_message_authenticator = yes\n")
            f.write("}\n\n")
    
    conn.close()
    logger.info(f"Regenerated clients configuration: {clients_file}")


def regenerate_users_file():
    """Regenerate users file from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.username, u.password, ra.attribute, ra.value, ra.op
        FROM radius_users u
        LEFT JOIN radius_reply_attributes ra ON u.username = ra.username
        ORDER BY u.username
    """)
    
    users_file = Path(CONFIG_PATH) / "users"
    users_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(users_file, "w") as f:
        f.write("# Auto-generated RADIUS users authorization\n")
        f.write("# Do not edit manually - managed by radius-manager API\n")
        f.write(f"# Generated: {datetime.utcnow().isoformat()}\n\n")
        
        current_user = None
        attributes = []
        current_password = None
        
        for row in cursor.fetchall():
            username, password, attribute, value, op = row
            
            if current_user and current_user != username:
                # Write previous user
                # Check if this looks like a MAC address (for MAC-based auth)
                is_mac_auth = bool(re.match(r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$', current_user))
                
                if is_mac_auth:
                    # MAC-based authentication - no password check
                    f.write(f"{current_user} Auth-Type := Accept\n")
                else:
                    # Regular user with password
                    pwd = current_password or "N/A"
                    f.write(f"{current_user} Cleartext-Password := \"{pwd}\"\n")
                
                # Write reply attributes
                for attr, val, operation in attributes:
                    f.write(f"    {attr} {operation} \"{val}\"\n")
                f.write("\n")
                
                attributes = []
            
            current_user = username
            current_password = password
            if attribute and value:
                attributes.append((attribute, value, op or ':='))
        
        # Write last user
        if current_user:
            is_mac_auth = bool(re.match(r'^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$', current_user))
            
            if is_mac_auth:
                f.write(f"{current_user} Auth-Type := Accept\n")
            else:
                pwd = current_password or "N/A"
                f.write(f"{current_user} Cleartext-Password := \"{pwd}\"\n")
            
            for attr, val, operation in attributes:
                f.write(f"    {attr} {operation} \"{val}\"\n")
            f.write("\n")
    
    conn.close()
    logger.info(f"Regenerated users file: {users_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="FreeRADIUS Configuration API")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()
    
    logger.info(f"Starting API server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level=LOG_LEVEL.lower())


if __name__ == "__main__":
    main()
