#!/usr/bin/with-contenv bashio
# ==============================================================================
# FreeRADIUS Server for Home Assistant
# Runs the FreeRADIUS server with RadSec support
# Supports both Home Assistant add-on mode and standalone Docker mode
# ==============================================================================

set -e

# Function to generate secure random token
generate_api_token() {
    openssl rand -hex 32
}

# Check if we're running in Home Assistant add-on mode
if bashio::supervisor.ping 2>/dev/null; then
    # HOME ASSISTANT ADD-ON MODE
    bashio::log.info "Running in Home Assistant Add-on mode"
    
    # Load configuration from bashio
    SERVER_NAME=$(bashio::config 'server_name')
    RADSEC_ENABLED=$(bashio::config 'radsec_enabled')
    RADSEC_PORT=$(bashio::config 'radsec_port')
    COA_ENABLED=$(bashio::config 'coa_enabled')
    COA_PORT=$(bashio::config 'coa_port')
    CERT_SOURCE=$(bashio::config 'cert_source')
    LOG_LEVEL=$(bashio::config 'log_level')
    LOG_AUTH=$(bashio::config 'log_auth')
    LOG_AUTH_BADPASS=$(bashio::config 'log_auth_badpass')
    LOG_AUTH_GOODPASS=$(bashio::config 'log_auth_goodpass')
    API_ENABLED=$(bashio::config 'api_enabled')
    API_PORT=$(bashio::config 'api_port')
    API_HOST=$(bashio::config 'api_host')
    API_AUTH_TOKEN_CONFIG=$(bashio::config 'api_auth_token')
    CERT_PASSWORD=$(bashio::config 'cert_password')
    
    # Database configuration
    DB_TYPE=$(bashio::config 'db_type')
    DB_HOST=$(bashio::config 'db_host')
    DB_PORT=$(bashio::config 'db_port')
    DB_NAME=$(bashio::config 'db_name')
    DB_USER=$(bashio::config 'db_user')
    DB_PASSWORD=$(bashio::config 'db_password')
    DB_POOL_SIZE=$(bashio::config 'db_pool_size')
    DB_MAX_OVERFLOW=$(bashio::config 'db_max_overflow')
    DB_POOL_RECYCLE=$(bashio::config 'db_pool_recycle')
    
    # Wait for MariaDB if MySQL is configured
    if [ "${DB_TYPE}" = "mysql" ]; then
        bashio::log.info "MySQL database configured - waiting for MariaDB service..."
        
        # Wait for the MariaDB service to become available (max 120 seconds)
        WAIT_TIMEOUT=120
        WAIT_COUNT=0
        while [ ${WAIT_COUNT} -lt ${WAIT_TIMEOUT} ]; do
            if bashio::services.available "mysql"; then
                bashio::log.info "MariaDB service is available"
                break
            fi
            
            if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
                bashio::log.info "Waiting for MariaDB service... (${WAIT_COUNT}/${WAIT_TIMEOUT}s)"
            fi
            
            sleep 1
            WAIT_COUNT=$((WAIT_COUNT + 1))
        done
        
        if [ ${WAIT_COUNT} -ge ${WAIT_TIMEOUT} ]; then
            bashio::log.warning "MariaDB service not available after ${WAIT_TIMEOUT}s"
            bashio::log.warning "Make sure the MariaDB add-on is installed and running"
        fi
    fi
    
    # Auto-discover MariaDB add-on if db_type is mysql and no credentials provided
    if [ "${DB_TYPE}" = "mysql" ] && [ -z "${DB_USER}" ]; then
        bashio::log.info "Attempting to auto-discover MariaDB add-on..."
        
        # Check if MariaDB add-on is installed and running
        if bashio::services.available "mysql"; then
            bashio::log.info "MariaDB service discovered via Supervisor"
            
            # Get connection details from the service
            DB_HOST=$(bashio::services "mysql" "host")
            DB_PORT=$(bashio::services "mysql" "port")
            DB_USER=$(bashio::services "mysql" "username")
            DB_PASSWORD=$(bashio::services "mysql" "password")
            
            bashio::log.info "Auto-configured MariaDB connection:"
            bashio::log.info "  Host: ${DB_HOST}"
            bashio::log.info "  Port: ${DB_PORT}"
            bashio::log.info "  User: ${DB_USER}"
            
            # Wait for MariaDB to be ready to accept connections
            bashio::log.info "Testing MariaDB connection..."
            DB_READY=false
            for i in $(seq 1 30); do
                if mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" \
                    -e "SELECT 1;" > /dev/null 2>&1; then
                    DB_READY=true
                    bashio::log.info "MariaDB connection successful"
                    break
                fi
                bashio::log.info "Waiting for MariaDB to accept connections... (${i}/30)"
                sleep 2
            done
            
            if [ "${DB_READY}" = "true" ]; then
                # Create database if it doesn't exist
                bashio::log.info "Ensuring database '${DB_NAME}' exists..."
                mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" \
                    -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null && \
                    bashio::log.info "Database '${DB_NAME}' is ready" || \
                    bashio::log.warning "Could not auto-create database. Please create it manually."
            else
                bashio::log.error "Could not connect to MariaDB after 60 seconds"
                bashio::log.warning "Falling back to SQLite"
                DB_TYPE="sqlite"
            fi
        else
            bashio::log.warning "MariaDB service not found. Please install the MariaDB add-on or configure database manually."
        fi
    fi
    
    # Build DATABASE_URL based on type
    case "${DB_TYPE}" in
        sqlite)
            DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="/config/${DB_NAME}.db"
            bashio::log.info "Using SQLite database: /config/${DB_NAME}.db"
            ;;
        mysql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                DATABASE_TYPE="mysql"
                DATABASE_PATH=""
                bashio::log.info "Using MySQL database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "MySQL selected but no credentials available. Set db_user/db_password or install MariaDB add-on."
                DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                DATABASE_TYPE="sqlite"
                DATABASE_PATH="/config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        postgresql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                DATABASE_TYPE="postgresql"
                DATABASE_PATH=""
                bashio::log.info "Using PostgreSQL database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "PostgreSQL selected but no credentials configured."
                DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                DATABASE_TYPE="sqlite"
                DATABASE_PATH="/config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        *)
            bashio::log.warning "Unknown database type: ${DB_TYPE}, defaulting to SQLite"
            DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="/config/${DB_NAME}.db"
            ;;
    esac
    
    # Generate API auth token if not set
    API_TOKEN_FILE="/config/.freeradius_api_token"
    DISCOVERY_FILE="/config/.freeradius_discovery"
    
    if [ -z "${API_AUTH_TOKEN_CONFIG}" ]; then
        if [ -f "${API_TOKEN_FILE}" ]; then
            API_AUTH_TOKEN=$(cat "${API_TOKEN_FILE}")
            bashio::log.info "Loaded API auth token from ${API_TOKEN_FILE}"
        else
            API_AUTH_TOKEN=$(generate_api_token)
            echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
            chmod 600 "${API_TOKEN_FILE}"
            bashio::log.warning "=============================================="
            bashio::log.warning "AUTO-GENERATED API AUTH TOKEN"
            bashio::log.warning "=============================================="
            bashio::log.warning "Token: ${API_AUTH_TOKEN}"
            bashio::log.warning "=============================================="
            bashio::log.warning "SAVE THIS TOKEN for API access!"
            bashio::log.warning "Or set api_auth_token in add-on configuration."
            bashio::log.warning "Token saved to ${API_TOKEN_FILE}"
            bashio::log.warning "=============================================="
        fi
    else
        API_AUTH_TOKEN="${API_AUTH_TOKEN_CONFIG}"
        # Save configured token for discovery by other add-ons
        echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
        chmod 600 "${API_TOKEN_FILE}"
        bashio::log.info "Using configured API auth token"
    fi
    
    # Write discovery file for other add-ons (Meraki WPN Portal)
    # This allows auto-discovery of FreeRADIUS API endpoint
    API_HOST_INTERNAL="${API_HOST:-127.0.0.1}"
    # For add-on to add-on communication, use the container hostname
    FREERADIUS_HOST="freeradius-server"
    
    bashio::log.info "Writing FreeRADIUS discovery file for other add-ons..."
    cat > "${DISCOVERY_FILE}" << EOF
# FreeRADIUS API Discovery File
# Auto-generated - do not edit manually
FREERADIUS_API_HOST=${FREERADIUS_HOST}
FREERADIUS_API_PORT=${API_PORT}
FREERADIUS_API_TOKEN=${API_AUTH_TOKEN}
FREERADIUS_API_URL=http://${FREERADIUS_HOST}:${API_PORT}
EOF
    chmod 600 "${DISCOVERY_FILE}"
    bashio::log.info "Discovery file written to ${DISCOVERY_FILE}"
    
    # Export all config as environment variables
    export SERVER_NAME RADSEC_ENABLED RADSEC_PORT COA_ENABLED COA_PORT
    export CERT_SOURCE LOG_LEVEL LOG_AUTH LOG_AUTH_BADPASS LOG_AUTH_GOODPASS
    export API_ENABLED API_PORT API_HOST API_AUTH_TOKEN
    export DATABASE_URL DATABASE_TYPE DATABASE_PATH
    export DB_TYPE DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
    export DB_POOL_SIZE DB_MAX_OVERFLOW DB_POOL_RECYCLE
    export CERT_PASSWORD
    
    bashio::log.info "Server name: ${SERVER_NAME}"
    bashio::log.info "RadSec enabled: ${RADSEC_ENABLED}"
    bashio::log.info "Log level: ${LOG_LEVEL}"
    bashio::log.info "API auth: ${API_AUTH_TOKEN:+enabled}"
else
    # STANDALONE DOCKER MODE
    echo "Running in Standalone Docker mode"
    
    # Source s6-overlay container environment if available
    if [ -d /run/s6/container_environment ]; then
        echo "Loading container environment from s6-overlay..."
        for envfile in /run/s6/container_environment/*; do
            if [ -f "$envfile" ]; then
                varname=$(basename "$envfile")
                # Skip special s6 variables
                if [[ "$varname" != S6_* ]] && [[ "$varname" != s6* ]]; then
                    value=$(cat "$envfile")
                    export "$varname"="$value"
                fi
            fi
        done
    fi
    
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
fi

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
# The stock clients.conf has localhost defined, and our dynamic one also has it
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
# Note: Database migrations are now run inside the Python app startup (main.py)
if [ "${API_ENABLED}" = "true" ]; then
    API_HOST="${API_HOST:-127.0.0.1}"
    export API_HOST="${API_HOST}"
    
    echo "Starting configuration API on ${API_HOST}:${API_PORT}..."
    echo "⚠️  API is bound to ${API_HOST} for security - use Ingress or local access"
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
