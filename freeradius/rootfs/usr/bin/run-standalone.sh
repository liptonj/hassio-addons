#!/bin/bash
# ==============================================================================
# FreeRADIUS Server - Standalone Docker Mode
# Runs without s6-overlay for use in docker-compose standalone deployments
# ==============================================================================

set -e

# Function to generate secure random token
generate_api_token() {
    openssl rand -hex 32
}

echo "Running in Standalone Docker mode"

# Load configuration from environment variables with defaults
SERVER_NAME="${SERVER_NAME:-freeradius-server}"
RADSEC_ENABLED="${RADSEC_ENABLED:-true}"
COA_ENABLED="${COA_ENABLED:-true}"
COA_PORT="${COA_PORT:-3799}"
CERT_SOURCE="${CERT_SOURCE:-selfsigned}"
LOG_LEVEL="${LOG_LEVEL:-info}"
API_ENABLED="${API_ENABLED:-true}"
API_PORT="${API_PORT:-8000}"

# Database configuration from environment variables
DB_TYPE="${DB_TYPE:-sqlite}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-freeradius}"
DB_USER="${DB_USER:-}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Build DATABASE_URL based on type (if not already set)
if [ -z "${DATABASE_URL}" ]; then
    case "${DB_TYPE}" in
        sqlite)
            DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="/config/${DB_NAME}.db"
            echo "Using SQLite database: /config/${DB_NAME}.db"
            ;;
        mysql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                DATABASE_URL="mysql+pymysql://${DB_HOST}:${DB_PORT}/${DB_NAME}"
            fi
            DATABASE_TYPE="mysql"
            DATABASE_PATH=""
            echo "Using MySQL database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            ;;
        postgresql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                DATABASE_URL="postgresql://${DB_HOST}:${DB_PORT}/${DB_NAME}"
            fi
            DATABASE_TYPE="postgresql"
            DATABASE_PATH=""
            echo "Using PostgreSQL database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            ;;
        *)
            echo "Unknown database type: ${DB_TYPE}, defaulting to SQLite"
            DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="/config/${DB_NAME}.db"
            ;;
    esac
fi

export DATABASE_URL DATABASE_TYPE DATABASE_PATH

# Generate API auth token if not set
API_TOKEN_FILE="/config/.freeradius_api_token"
DISCOVERY_FILE="/config/.freeradius_discovery"

if [ -z "${API_AUTH_TOKEN}" ]; then
    if [ -f "${API_TOKEN_FILE}" ]; then
        export API_AUTH_TOKEN=$(cat "${API_TOKEN_FILE}")
        echo "Loaded API auth token from ${API_TOKEN_FILE}"
    else
        export API_AUTH_TOKEN=$(generate_api_token)
        mkdir -p /config
        echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
        chmod 600 "${API_TOKEN_FILE}"
        echo "=============================================="
        echo "AUTO-GENERATED API AUTH TOKEN"
        echo "=============================================="
        echo "Token: ${API_AUTH_TOKEN}"
        echo "=============================================="
        echo "SAVE THIS TOKEN for API access!"
        echo "Or set API_AUTH_TOKEN environment variable."
        echo "=============================================="
    fi
fi

echo "Server name: ${SERVER_NAME}"
echo "RadSec enabled: ${RADSEC_ENABLED}"
echo "Log level: ${LOG_LEVEL}"
echo "API auth: ${API_AUTH_TOKEN:+enabled}"

echo "Starting FreeRADIUS Server..."

# Alpine Linux paths
RADDB_PATH="/etc/raddb"
RADIUS_USER="radius"
RADIUS_GROUP="radius"

echo "Server name: ${SERVER_NAME}"
echo "RadSec enabled: ${RADSEC_ENABLED}"
echo "CoA enabled: ${COA_ENABLED}"
echo "Certificate source: ${CERT_SOURCE}"
echo "Log level: ${LOG_LEVEL}"
echo "Database: ${DATABASE_TYPE}"

# Create necessary directories
mkdir -p /config/certs
mkdir -p /config/clients
mkdir -p /config/raddb/mods-available
mkdir -p /config/raddb/mods-enabled
mkdir -p /config/raddb/mods-config/preprocess
mkdir -p /config/raddb/sites-available
mkdir -p /config/raddb/sites-enabled
mkdir -p /config/raddb/policy.d
mkdir -p /config/raddb/certs
mkdir -p /var/log/radius
mkdir -p /var/run/radiusd
mkdir -p /usr/var/log
mkdir -p /tmp/radiusd  # Required for EAP TLS certificate verification

# Set permissions for radiusd temp directory
chown -R ${RADIUS_USER}:${RADIUS_GROUP} /tmp/radiusd 2>/dev/null || true
chmod 700 /tmp/radiusd

# Copy default FreeRADIUS config to persistent storage if not present
if [ -d "${RADDB_PATH}" ] && [ ! -L "${RADDB_PATH}" ]; then
    if [ ! -f /config/raddb/radiusd.conf ] || [ ! -s /config/raddb/radiusd.conf ]; then
        echo "Copying default FreeRADIUS configuration to persistent storage..."
        cp -r ${RADDB_PATH}/* /config/raddb/ 2>/dev/null || true
        echo "Default configuration copied"
        
        # Apply our secure fallback configs over Alpine's defaults
        if [ -f ${RADDB_PATH}/mods-available/eap.fallback ]; then
            echo "Applying secure EAP fallback configuration..."
            cp ${RADDB_PATH}/mods-available/eap.fallback /config/raddb/mods-available/eap
            echo "Secure EAP configuration applied"
        fi
        
        if [ -d ${RADDB_PATH}/sites-available.fallback ]; then
            echo "Applying secure virtual server fallback configurations..."
            cp ${RADDB_PATH}/sites-available.fallback/* /config/raddb/sites-available/ 2>/dev/null || true
            echo "Secure virtual server configurations applied"
        fi
    fi
    
    # Create symlink from /etc/raddb to /config/raddb
    echo "Creating symlink ${RADDB_PATH} -> /config/raddb"
    rm -rf ${RADDB_PATH}
    ln -s /config/raddb ${RADDB_PATH}
    echo "Symlink created"
elif [ ! -L "${RADDB_PATH}" ]; then
    echo "Creating symlink ${RADDB_PATH} -> /config/raddb"
    ln -s /config/raddb ${RADDB_PATH}
fi

# Initialize config files from templates if they don't exist
if [ ! -f /config/clients/clients.conf ]; then
    echo "Creating initial clients.conf from template..."
    if [ -f /etc/raddb/clients.conf.template ]; then
        cp /etc/raddb/clients.conf.template /config/clients/clients.conf
    else
        touch /config/clients/clients.conf
        echo "# RADIUS Clients - dynamically generated" > /config/clients/clients.conf
    fi
    chmod 644 /config/clients/clients.conf
    echo "clients.conf created"
fi

# Initialize users file in persistent storage
if [ ! -f /config/raddb/users ]; then
    echo "Creating initial users file from template..."
    if [ -f /etc/raddb/users.template ]; then
        cp /etc/raddb/users.template /config/raddb/users
    else
        touch /config/raddb/users
        echo "# FreeRADIUS users file" > /config/raddb/users
        echo "# Auto-generated from database" >> /config/raddb/users
    fi
    chmod 644 /config/raddb/users
    echo "users file created in persistent storage"
fi

# Create required preprocess files if they don't exist
if [ ! -f /config/raddb/mods-config/preprocess/huntgroups ]; then
    mkdir -p /config/raddb/mods-config/preprocess
    touch /config/raddb/mods-config/preprocess/huntgroups
    chmod 644 /config/raddb/mods-config/preprocess/huntgroups
    echo "# Huntgroups file" > /config/raddb/mods-config/preprocess/huntgroups
fi

# Set permissions
chown -R ${RADIUS_USER}:${RADIUS_GROUP} /var/log/radius /var/run/radiusd 2>/dev/null || true
chown -R ${RADIUS_USER}:${RADIUS_GROUP} /config/raddb/mods-config 2>/dev/null || true

# Copy Meraki dictionary if it exists
if [ -f /etc/raddb/dictionary.meraki ]; then
    echo "Installing Meraki vendor dictionary..."
    cp /etc/raddb/dictionary.meraki /config/raddb/dictionary.meraki
    chmod 644 /config/raddb/dictionary.meraki
    
    # Add to dictionary if not already included
    if ! grep -q "dictionary.meraki" /config/raddb/dictionary 2>/dev/null; then
        echo "" >> /config/raddb/dictionary
        echo "# Meraki vendor-specific attributes for IPSK" >> /config/raddb/dictionary
        echo "\$INCLUDE dictionary.meraki" >> /config/raddb/dictionary
        echo "Meraki dictionary added"
    fi
fi

# Configure radiusd.conf to include our dynamic clients file
echo "Configuring radiusd.conf..."

# First, comment out the stock clients.conf include to avoid duplicate client errors
if grep -q '^\$INCLUDE clients.conf' /config/raddb/radiusd.conf 2>/dev/null; then
    echo "Commenting out stock clients.conf include (using dynamic clients instead)..."
    sed -i 's/^\$INCLUDE clients\.conf/#DISABLED: $INCLUDE clients.conf/g' /config/raddb/radiusd.conf
    echo "Stock clients.conf include commented out"
fi

if ! grep -q "/config/clients/clients.conf" /config/raddb/radiusd.conf 2>/dev/null; then
    echo "" >> /config/raddb/radiusd.conf
    echo "# Include dynamic clients from portal" >> /config/raddb/radiusd.conf
    echo "\$INCLUDE /config/clients/clients.conf" >> /config/raddb/radiusd.conf
    echo "Added clients.conf include to radiusd.conf"
fi

# Ensure sites-enabled directory is included
if ! grep -q "sites-enabled" /config/raddb/radiusd.conf 2>/dev/null; then
    echo "" >> /config/raddb/radiusd.conf
    echo "# Include virtual servers from sites-enabled" >> /config/raddb/radiusd.conf
    echo "\$INCLUDE sites-enabled/" >> /config/raddb/radiusd.conf
    echo "Added sites-enabled include to radiusd.conf"
fi

# Ensure policy.d directory is included for custom unlang policies
if ! grep -q "policy.d" /config/raddb/radiusd.conf 2>/dev/null; then
    echo "" >> /config/raddb/radiusd.conf
    echo "# Include custom policies from policy.d" >> /config/raddb/radiusd.conf
    echo "\$INCLUDE policy.d/" >> /config/raddb/radiusd.conf
    echo "Added policy.d include to radiusd.conf"
fi

# Create empty policy files if they don't exist (prevents include errors)
touch /config/raddb/policy.d/mac_bypass 2>/dev/null || true
touch /config/raddb/policy.d/authorize_custom 2>/dev/null || true

# Configure files module
if [ -f /config/raddb/mods-enabled/files ]; then
    sed -i 's|usersfile = ${confdir}/users|usersfile = ${confdir}/users|g' /config/raddb/mods-enabled/files
    echo "Files module configured"
fi

# Disable REST module if not configured
if [ -f /config/raddb/mods-enabled/rest ]; then
    rm -f /config/raddb/mods-enabled/rest
    echo "Disabled REST module (not configured)"
fi

# Initialize database if needed
if [ "${DATABASE_TYPE}" = "sqlite" ]; then
    if [ ! -f "${DATABASE_PATH}" ]; then
        echo "Initializing SQLite database..."
        touch "${DATABASE_PATH}"
        chown ${RADIUS_USER}:${RADIUS_GROUP} "${DATABASE_PATH}" 2>/dev/null || true
    fi
fi

# Export environment variables for radius-app
export RADIUS_CONFIG_PATH="/config/raddb"
export RADIUS_CERTS_PATH="/config/certs"
export RADIUS_CLIENTS_PATH="/config/clients"
export RADIUS_DATABASE_TYPE="${DATABASE_TYPE}"
export RADIUS_DATABASE_PATH="${DATABASE_PATH}"
export RADIUS_LOG_LEVEL="${LOG_LEVEL}"
export RADIUS_CERT_PASSWORD="${CERT_PASSWORD:-}"

# Test secret for localhost health checks
export RADIUS_TEST_SECRET="${RADIUS_TEST_SECRET:-$(openssl rand -base64 32)}"

# API authentication token
if [ -n "${API_AUTH_TOKEN}" ]; then
    export API_AUTH_TOKEN="${API_AUTH_TOKEN}"
fi

# Start configuration API in background if enabled
if [ "${API_ENABLED}" = "true" ]; then
    API_HOST="${API_HOST:-0.0.0.0}"
    export API_HOST="${API_HOST}"
    
    echo "Starting configuration API on ${API_HOST}:${API_PORT}..."
    cd /usr/bin
    python3 -m radius_app.main &
    API_PID=$!
    echo "Configuration API started (PID: ${API_PID})"
    
    # Wait for API to be ready
    echo "Waiting for API to be ready..."
    TIMEOUT=30
    COUNT=0
    while [ $COUNT -lt $TIMEOUT ]; do
        if curl -s -f http://localhost:${API_PORT}/health > /dev/null 2>&1; then
            echo "✅ Configuration API is ready"
            break
        fi
        sleep 1
        COUNT=$((COUNT + 1))
        if [ $((COUNT % 5)) -eq 0 ]; then
            echo "Still waiting for API... ($COUNT/${TIMEOUT}s)"
        fi
    done
    
    if [ $COUNT -ge $TIMEOUT ]; then
        echo "⚠️  WARNING: API health check timeout after ${TIMEOUT}s"
        echo "⚠️  Continuing anyway - API may still be starting..."
    fi
    
    # Wait for config files to be generated
    echo "Waiting for config files to be generated..."
    TIMEOUT=15
    COUNT=0
    while [ $COUNT -lt $TIMEOUT ]; do
        if [ -f "/config/clients/clients.conf" ] && [ -f "/config/raddb/users" ] && [ -f "/config/raddb/sites-enabled/default" ]; then
            echo "✅ Config files generated successfully"
            break
        fi
        sleep 1
        COUNT=$((COUNT + 1))
    done
    
    if [ ! -f "/config/clients/clients.conf" ] || [ ! -f "/config/raddb/users" ]; then
        echo "⚠️  WARNING: Config files not found, using templates as fallback"
        if [ ! -f "/config/clients/clients.conf" ]; then
            touch /config/clients/clients.conf
        fi
        if [ ! -f "/config/raddb/users" ]; then
            touch /config/raddb/users
            echo "# FreeRADIUS users file" > /config/raddb/users
        fi
    fi
    
    # Apply fallback configs if API didn't generate them
    if [ ! -f "/config/raddb/sites-enabled/default" ]; then
        echo "⚠️  Default virtual server not generated, applying fallback..."
        if [ -d /etc/raddb/sites-available.fallback ]; then
            cp /etc/raddb/sites-available.fallback/default /config/raddb/sites-available/default 2>/dev/null || true
            ln -sf ../sites-available/default /config/raddb/sites-enabled/default
            echo "✅ Fallback default virtual server applied"
        fi
    fi
    
    if [ ! -f "/config/raddb/mods-enabled/eap" ] && [ -f /etc/raddb/mods-available/eap.fallback ]; then
        echo "⚠️  EAP module not configured, applying secure fallback..."
        cp /etc/raddb/mods-available/eap.fallback /config/raddb/mods-available/eap 2>/dev/null || true
        ln -sf ../mods-available/eap /config/raddb/mods-enabled/eap
        echo "✅ Fallback EAP configuration applied"
    fi
fi

# Check if certificates exist for RadSec
if [ "${RADSEC_ENABLED}" = "true" ]; then
    if [ ! -f "/config/certs/ca.pem" ] || [ ! -f "/config/certs/server.pem" ] || [ ! -f "/config/certs/server-key.pem" ]; then
        echo "RadSec certificates not found. Generating self-signed certificates..."
        
        cd /config/certs || exit 1
        
        # Generate CA key and certificate (397 days)
        openssl genrsa -out ca-key.pem 4096
        openssl req -new -x509 -days 397 -key ca-key.pem -out ca.pem \
            -subj "/C=US/ST=State/L=City/O=Home Assistant/OU=FreeRADIUS/CN=RADIUS CA"
        
        # Generate server key and CSR
        openssl genrsa -out server-key.pem 4096
        openssl req -new -key server-key.pem -out server.csr \
            -subj "/C=US/ST=State/L=City/O=Home Assistant/OU=FreeRADIUS/CN=${SERVER_NAME}"
        
        # Sign server certificate with CA (397 days)
        openssl x509 -req -days 397 -in server.csr -CA ca.pem -CAkey ca-key.pem \
            -CAcreateserial -out server.pem -sha256
        
        # Set permissions
        chmod 600 ca-key.pem server-key.pem
        chmod 644 ca.pem server.pem
        chown ${RADIUS_USER}:${RADIUS_GROUP} *.pem 2>/dev/null || true
        
        rm -f server.csr ca.srl
        
        echo "RadSec certificates generated successfully"
    else
        echo "Using existing RadSec certificates"
    fi
fi

# Start FreeRADIUS in foreground
echo "Starting FreeRADIUS daemon..."
echo "============================================================"
echo "Configuration Summary:"
echo "  - FreeRADIUS version: 3.x (stable)"
echo "  - Clients config: /config/clients/clients.conf"
echo "  - Users file: /config/raddb/users (persistent)"
echo "  - RadSec enabled: ${RADSEC_ENABLED}"
echo "  - Log level: ${LOG_LEVEL}"
echo "============================================================"

# Verify config files exist
if [ ! -f "/config/clients/clients.conf" ]; then
    echo "❌ ERROR: /config/clients/clients.conf not found!"
    touch /config/clients/clients.conf
fi

if [ ! -f "/config/raddb/users" ]; then
    echo "❌ ERROR: /config/raddb/users not found!"
    touch /config/raddb/users
    echo "# FreeRADIUS users file" > /config/raddb/users
fi

# Test configuration before starting
echo "Testing FreeRADIUS configuration..."
if radiusd -XC -d /config/raddb > /dev/null 2>&1; then
    echo "✅ Configuration test passed"
    echo "Starting radiusd in foreground with debug output..."
    exec radiusd -f -X -l stdout -d /config/raddb
else
    echo "❌ ERROR: Configuration test failed!"
    echo ""
    echo "FreeRADIUS configuration validation failed. Please check:"
    echo "  - Configuration files in /config/raddb/"
    echo "  - Check logs for specific validation errors"
    echo ""
    echo "Running validation with verbose output to show errors:"
    radiusd -XC -d /config/raddb
    echo ""
    echo "FreeRADIUS will NOT start with invalid configuration."
    exit 1
fi
