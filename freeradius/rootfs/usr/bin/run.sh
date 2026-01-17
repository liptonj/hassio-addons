#!/usr/bin/with-contenv bashio
# ==============================================================================
# FreeRADIUS Server for Home Assistant
# Runs the FreeRADIUS server with RadSec support
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
    
    # Load configuration from bashio (simplified config)
    DB_TYPE=$(bashio::config 'db_type')
    DB_HOST=$(bashio::config 'db_host')
    DB_PORT=$(bashio::config 'db_port')
    DB_NAME=$(bashio::config 'db_name')
    DB_USER=$(bashio::config 'db_user')
    DB_PASSWORD=$(bashio::config 'db_password')
    API_AUTH_TOKEN_CONFIG=$(bashio::config 'api_auth_token')
    LOG_LEVEL=$(bashio::config 'log_level')
    
    # Use sensible defaults for settings not in config
    SERVER_NAME="freeradius-server"
    RADSEC_ENABLED="true"
    RADSEC_PORT="2083"
    COA_ENABLED="true"
    COA_PORT="3799"
    CERT_SOURCE="selfsigned"
    LOG_AUTH="true"
    LOG_AUTH_BADPASS="true"
    LOG_AUTH_GOODPASS="false"
    API_ENABLED="true"
    API_PORT="8000"
    API_HOST="127.0.0.1"
    
    # Wait for MariaDB if MySQL is configured
    if [ "${DB_TYPE}" = "mysql" ]; then
        bashio::log.info "MySQL database configured - waiting for MariaDB service..."
        
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
        fi
    fi
    
    # Auto-discover MariaDB if configured and no credentials provided
    if [ "${DB_TYPE}" = "mysql" ] && [ -z "${DB_USER}" ]; then
        bashio::log.info "Attempting to auto-discover MariaDB add-on..."
        
        if bashio::services.available "mysql"; then
            bashio::log.info "MariaDB service discovered via Supervisor"
            
            DB_HOST=$(bashio::services "mysql" "host")
            DB_PORT=$(bashio::services "mysql" "port")
            DB_USER=$(bashio::services "mysql" "username")
            DB_PASSWORD=$(bashio::services "mysql" "password")
            
            bashio::log.info "Auto-configured MariaDB: ${DB_HOST}:${DB_PORT}"
            
            # Wait for MariaDB to accept connections
            bashio::log.info "Testing MariaDB connection..."
            DB_READY=false
            for i in $(seq 1 30); do
                if mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" \
                    -e "SELECT 1;" > /dev/null 2>&1; then
                    DB_READY=true
                    bashio::log.info "MariaDB connection successful"
                    break
                fi
                bashio::log.info "Waiting for MariaDB... (${i}/30)"
                sleep 2
            done
            
            if [ "${DB_READY}" = "true" ]; then
                bashio::log.info "Ensuring database '${DB_NAME}' exists..."
                mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" \
                    -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null && \
                    bashio::log.info "Database '${DB_NAME}' is ready" || \
                    bashio::log.warning "Could not auto-create database"
            else
                bashio::log.error "Could not connect to MariaDB"
                bashio::log.warning "Falling back to SQLite"
                DB_TYPE="sqlite"
            fi
        else
            bashio::log.warning "MariaDB service not found"
        fi
    fi
    
    # Build DATABASE_URL
    case "${DB_TYPE}" in
        sqlite)
            DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="/config/${DB_NAME}.db"
            bashio::log.info "Using SQLite: /config/${DB_NAME}.db"
            ;;
        mysql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                DATABASE_TYPE="mysql"
                DATABASE_PATH=""
                bashio::log.info "Using MySQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "MySQL selected but no credentials available"
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
                bashio::log.info "Using PostgreSQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "PostgreSQL selected but no credentials"
                DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                DATABASE_TYPE="sqlite"
                DATABASE_PATH="/config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        *)
            bashio::log.warning "Unknown database type: ${DB_TYPE}, using SQLite"
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
            bashio::log.warning "Token saved to ${API_TOKEN_FILE}"
            bashio::log.warning "=============================================="
        fi
    else
        API_AUTH_TOKEN="${API_AUTH_TOKEN_CONFIG}"
        echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
        chmod 600 "${API_TOKEN_FILE}"
        bashio::log.info "Using configured API auth token"
    fi
    
    # Write discovery file for other add-ons
    FREERADIUS_HOST="freeradius-server"
    bashio::log.info "Writing FreeRADIUS discovery file..."
    cat > "${DISCOVERY_FILE}" << EOF
# FreeRADIUS API Discovery File
FREERADIUS_API_HOST=${FREERADIUS_HOST}
FREERADIUS_API_PORT=${API_PORT}
FREERADIUS_API_TOKEN=${API_AUTH_TOKEN}
FREERADIUS_API_URL=http://${FREERADIUS_HOST}:${API_PORT}
EOF
    chmod 600 "${DISCOVERY_FILE}"
    
    # Export environment variables
    export SERVER_NAME RADSEC_ENABLED RADSEC_PORT COA_ENABLED COA_PORT
    export CERT_SOURCE LOG_LEVEL LOG_AUTH LOG_AUTH_BADPASS LOG_AUTH_GOODPASS
    export API_ENABLED API_PORT API_HOST API_AUTH_TOKEN
    export DATABASE_URL DATABASE_TYPE DATABASE_PATH
    export DB_TYPE DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
    
    bashio::log.info "Log level: ${LOG_LEVEL}"
    bashio::log.info "RadSec enabled: ${RADSEC_ENABLED}"
else
    # STANDALONE DOCKER MODE
    echo "Running in Standalone Docker mode"
    
    # Load from environment with defaults
    SERVER_NAME="${SERVER_NAME:-freeradius-server}"
    RADSEC_ENABLED="${RADSEC_ENABLED:-true}"
    COA_ENABLED="${COA_ENABLED:-true}"
    COA_PORT="${COA_PORT:-3799}"
    CERT_SOURCE="${CERT_SOURCE:-selfsigned}"
    LOG_LEVEL="${LOG_LEVEL:-info}"
    API_ENABLED="${API_ENABLED:-true}"
    API_PORT="${API_PORT:-8000}"
    
    DB_TYPE="${DB_TYPE:-sqlite}"
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-3306}"
    DB_NAME="${DB_NAME:-freeradius}"
    
    # Build DATABASE_URL
    if [ -z "${DATABASE_URL}" ]; then
        case "${DB_TYPE}" in
            sqlite)
                DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                DATABASE_TYPE="sqlite"
                DATABASE_PATH="/config/${DB_NAME}.db"
                ;;
            mysql)
                DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                DATABASE_TYPE="mysql"
                DATABASE_PATH=""
                ;;
            postgresql)
                DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                DATABASE_TYPE="postgresql"
                DATABASE_PATH=""
                ;;
        esac
    fi
    
    export DATABASE_URL DATABASE_TYPE DATABASE_PATH
    
    # Generate API auth token if not set
    API_TOKEN_FILE="/config/.freeradius_api_token"
    if [ -z "${API_AUTH_TOKEN}" ]; then
        if [ -f "${API_TOKEN_FILE}" ]; then
            export API_AUTH_TOKEN=$(cat "${API_TOKEN_FILE}")
        else
            export API_AUTH_TOKEN=$(generate_api_token)
            mkdir -p /config
            echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
            chmod 600 "${API_TOKEN_FILE}"
            echo "=============================================="
            echo "AUTO-GENERATED API AUTH TOKEN"
            echo "Token: ${API_AUTH_TOKEN}"
            echo "=============================================="
        fi
    fi
    
    echo "Log level: ${LOG_LEVEL}"
    echo "RadSec enabled: ${RADSEC_ENABLED}"
fi

echo "Starting FreeRADIUS Server..."

# Alpine Linux paths
RADDB_PATH="/etc/raddb"
RADIUS_USER="radius"
RADIUS_GROUP="radius"

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
mkdir -p /tmp/radiusd

chown -R ${RADIUS_USER}:${RADIUS_GROUP} /tmp/radiusd 2>/dev/null || true
chmod 700 /tmp/radiusd

# Copy default FreeRADIUS config if not present
if [ -d "${RADDB_PATH}" ] && [ ! -L "${RADDB_PATH}" ]; then
    if [ ! -f /config/raddb/radiusd.conf ] || [ ! -s /config/raddb/radiusd.conf ]; then
        echo "Copying default FreeRADIUS configuration..."
        cp -r ${RADDB_PATH}/* /config/raddb/ 2>/dev/null || true
        
        if [ -f ${RADDB_PATH}/mods-available/eap.fallback ]; then
            cp ${RADDB_PATH}/mods-available/eap.fallback /config/raddb/mods-available/eap
        fi
        
        if [ -d ${RADDB_PATH}/sites-available.fallback ]; then
            cp ${RADDB_PATH}/sites-available.fallback/* /config/raddb/sites-available/ 2>/dev/null || true
        fi
    fi
    
    rm -rf ${RADDB_PATH}
    ln -s /config/raddb ${RADDB_PATH}
elif [ ! -L "${RADDB_PATH}" ]; then
    ln -s /config/raddb ${RADDB_PATH}
fi

# Initialize config files
if [ ! -f /config/clients/clients.conf ]; then
    touch /config/clients/clients.conf
    echo "# RADIUS Clients - dynamically generated" > /config/clients/clients.conf
    chmod 644 /config/clients/clients.conf
fi

if [ ! -f /config/raddb/users ]; then
    touch /config/raddb/users
    echo "# FreeRADIUS users file" > /config/raddb/users
    chmod 644 /config/raddb/users
fi

if [ ! -f /config/raddb/mods-config/preprocess/huntgroups ]; then
    mkdir -p /config/raddb/mods-config/preprocess
    echo "# Huntgroups file" > /config/raddb/mods-config/preprocess/huntgroups
    chmod 644 /config/raddb/mods-config/preprocess/huntgroups
fi

chown -R ${RADIUS_USER}:${RADIUS_GROUP} /var/log/radius /var/run/radiusd 2>/dev/null || true
chown -R ${RADIUS_USER}:${RADIUS_GROUP} /config/raddb/mods-config 2>/dev/null || true

# Install Meraki dictionary
if [ -f /etc/raddb/dictionary.meraki ]; then
    cp /etc/raddb/dictionary.meraki /config/raddb/dictionary.meraki
    chmod 644 /config/raddb/dictionary.meraki
    
    if ! grep -q "dictionary.meraki" /config/raddb/dictionary 2>/dev/null; then
        echo "" >> /config/raddb/dictionary
        echo "\$INCLUDE dictionary.meraki" >> /config/raddb/dictionary
    fi
fi

# Configure radiusd.conf
if grep -q '^\$INCLUDE clients.conf' /config/raddb/radiusd.conf 2>/dev/null; then
    sed -i 's/^\$INCLUDE clients\.conf/#DISABLED: $INCLUDE clients.conf/g' /config/raddb/radiusd.conf
fi

if ! grep -q "/config/clients/clients.conf" /config/raddb/radiusd.conf 2>/dev/null; then
    echo "" >> /config/raddb/radiusd.conf
    echo "\$INCLUDE /config/clients/clients.conf" >> /config/raddb/radiusd.conf
fi

if ! grep -q "sites-enabled" /config/raddb/radiusd.conf 2>/dev/null; then
    echo "\$INCLUDE sites-enabled/" >> /config/raddb/radiusd.conf
fi

if ! grep -q "policy.d" /config/raddb/radiusd.conf 2>/dev/null; then
    echo "\$INCLUDE policy.d/" >> /config/raddb/radiusd.conf
fi

touch /config/raddb/policy.d/mac_bypass 2>/dev/null || true
touch /config/raddb/policy.d/authorize_custom 2>/dev/null || true

# Disable REST module
if [ -f /config/raddb/mods-enabled/rest ]; then
    rm -f /config/raddb/mods-enabled/rest
fi

# Initialize SQLite database if needed
if [ "${DATABASE_TYPE}" = "sqlite" ]; then
    if [ ! -f "${DATABASE_PATH}" ]; then
        touch "${DATABASE_PATH}"
        chown ${RADIUS_USER}:${RADIUS_GROUP} "${DATABASE_PATH}" 2>/dev/null || true
    fi
fi

# Export for radius-app
export RADIUS_CONFIG_PATH="/config/raddb"
export RADIUS_CERTS_PATH="/config/certs"
export RADIUS_CLIENTS_PATH="/config/clients"
export RADIUS_DATABASE_TYPE="${DATABASE_TYPE}"
export RADIUS_DATABASE_PATH="${DATABASE_PATH}"
export RADIUS_LOG_LEVEL="${LOG_LEVEL}"
export RADIUS_TEST_SECRET="${RADIUS_TEST_SECRET:-$(openssl rand -base64 32)}"

# Start configuration API
if [ "${API_ENABLED}" = "true" ]; then
    API_HOST="${API_HOST:-127.0.0.1}"
    export API_HOST
    
    echo "Starting configuration API on ${API_HOST}:${API_PORT}..."
    cd /usr/bin
    python3 -m radius_app.main &
    API_PID=$!
    
    # Wait for API
    TIMEOUT=30
    COUNT=0
    while [ $COUNT -lt $TIMEOUT ]; do
        if curl -s -f http://localhost:${API_PORT}/health > /dev/null 2>&1; then
            echo "Configuration API is ready"
            break
        fi
        sleep 1
        COUNT=$((COUNT + 1))
    done
    
    # Wait for config files
    TIMEOUT=15
    COUNT=0
    while [ $COUNT -lt $TIMEOUT ]; do
        if [ -f "/config/clients/clients.conf" ] && [ -f "/config/raddb/users" ] && [ -f "/config/raddb/sites-enabled/default" ]; then
            break
        fi
        sleep 1
        COUNT=$((COUNT + 1))
    done
    
    # Apply fallbacks if needed
    if [ ! -f "/config/raddb/sites-enabled/default" ]; then
        if [ -d /etc/raddb/sites-available.fallback ]; then
            cp /etc/raddb/sites-available.fallback/default /config/raddb/sites-available/default 2>/dev/null || true
            ln -sf ../sites-available/default /config/raddb/sites-enabled/default
        fi
    fi
    
    if [ ! -f "/config/raddb/mods-enabled/eap" ] && [ -f /etc/raddb/mods-available/eap.fallback ]; then
        cp /etc/raddb/mods-available/eap.fallback /config/raddb/mods-available/eap 2>/dev/null || true
        ln -sf ../mods-available/eap /config/raddb/mods-enabled/eap
    fi
fi

# Generate RadSec certificates if needed
if [ "${RADSEC_ENABLED}" = "true" ]; then
    if [ ! -f "/config/certs/ca.pem" ] || [ ! -f "/config/certs/server.pem" ]; then
        echo "Generating self-signed RadSec certificates..."
        cd /config/certs
        
        openssl genrsa -out ca-key.pem 4096
        openssl req -new -x509 -days 397 -key ca-key.pem -out ca.pem \
            -subj "/C=US/ST=State/L=City/O=Home Assistant/OU=FreeRADIUS/CN=RADIUS CA"
        
        openssl genrsa -out server-key.pem 4096
        openssl req -new -key server-key.pem -out server.csr \
            -subj "/C=US/ST=State/L=City/O=Home Assistant/OU=FreeRADIUS/CN=${SERVER_NAME}"
        
        openssl x509 -req -days 397 -in server.csr -CA ca.pem -CAkey ca-key.pem \
            -CAcreateserial -out server.pem -sha256
        
        chmod 600 ca-key.pem server-key.pem
        chmod 644 ca.pem server.pem
        chown ${RADIUS_USER}:${RADIUS_GROUP} *.pem 2>/dev/null || true
        rm -f server.csr ca.srl
        
        echo "RadSec certificates generated"
    fi
fi

# Start FreeRADIUS
echo "Starting FreeRADIUS daemon..."
echo "  Database: ${DATABASE_TYPE}"
echo "  RadSec: ${RADSEC_ENABLED}"
echo "  Log level: ${LOG_LEVEL}"

if radiusd -XC -d /config/raddb > /dev/null 2>&1; then
    echo "Configuration test passed"
    exec radiusd -f -X -l stdout -d /config/raddb
else
    echo "Configuration test failed!"
    radiusd -XC -d /config/raddb
    exit 1
fi
