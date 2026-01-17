#!/usr/bin/with-contenv bashio
# FreeRADIUS Server startup script
# Unified logic for both Home Assistant add-on and standalone Docker modes

set -e

# ============================================================================
# Common Functions
# ============================================================================

generate_api_token() {
    openssl rand -hex 32
}

log_info() {
    if [ "${HA_MODE}" = "true" ]; then
        bashio::log.info "$1"
    else
        echo "[INFO] $1"
    fi
}

log_warning() {
    if [ "${HA_MODE}" = "true" ]; then
        bashio::log.warning "$1"
    else
        echo "[WARNING] $1"
    fi
}

log_error() {
    if [ "${HA_MODE}" = "true" ]; then
        bashio::log.error "$1"
    else
        echo "[ERROR] $1"
    fi
}

# ============================================================================
# Detect Run Mode
# ============================================================================

if bashio::supervisor.ping 2>/dev/null; then
    HA_MODE="true"
    CONFIG_DIR="/config"
    log_info "Running in Home Assistant Add-on mode"
else
    HA_MODE="false"
    CONFIG_DIR="${CONFIG_DIR:-/config}"
    echo "[INFO] Running in Standalone Docker mode"
fi

# ============================================================================
# Load Configuration
# ============================================================================

if [ "${HA_MODE}" = "true" ]; then
    # Load from HA add-on config
    DB_TYPE=$(bashio::config 'db_type')
    DB_HOST=$(bashio::config 'db_host')
    DB_PORT=$(bashio::config 'db_port')
    DB_NAME=$(bashio::config 'db_name')
    DB_USER=$(bashio::config 'db_user')
    DB_PASSWORD=$(bashio::config 'db_password')
    API_AUTH_TOKEN_CONFIG=$(bashio::config 'api_auth_token')
    LOG_LEVEL=$(bashio::config 'log_level')
else
    # Load from environment variables with defaults
    DB_TYPE="${DB_TYPE:-sqlite}"
    DB_HOST="${DB_HOST:-}"
    DB_PORT="${DB_PORT:-3306}"
    DB_NAME="${DB_NAME:-freeradius}"
    DB_USER="${DB_USER:-}"
    DB_PASSWORD="${DB_PASSWORD:-}"
    API_AUTH_TOKEN_CONFIG="${API_AUTH_TOKEN:-}"
    LOG_LEVEL="${LOG_LEVEL:-info}"
fi

# Server defaults (same for both modes)
SERVER_NAME="${SERVER_NAME:-freeradius-server}"
RADSEC_ENABLED="${RADSEC_ENABLED:-true}"
RADSEC_PORT="${RADSEC_PORT:-2083}"
COA_ENABLED="${COA_ENABLED:-true}"
COA_PORT="${COA_PORT:-3799}"
CERT_SOURCE="${CERT_SOURCE:-selfsigned}"
API_ENABLED="${API_ENABLED:-true}"
API_PORT="${API_PORT:-8000}"
API_HOST="${API_HOST:-127.0.0.1}"

# ============================================================================
# API Auth Token (same logic for both modes)
# ============================================================================

API_TOKEN_FILE="${CONFIG_DIR}/.freeradius_api_token"
DISCOVERY_FILE="${CONFIG_DIR}/.freeradius_discovery"

if [ -z "${API_AUTH_TOKEN_CONFIG}" ]; then
    if [ -f "${API_TOKEN_FILE}" ]; then
        API_AUTH_TOKEN=$(cat "${API_TOKEN_FILE}")
        log_info "Loaded API auth token from ${API_TOKEN_FILE}"
    else
        API_AUTH_TOKEN=$(generate_api_token)
        mkdir -p "${CONFIG_DIR}"
        echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
        chmod 600 "${API_TOKEN_FILE}"
        
        log_warning "=============================================="
        log_warning "AUTO-GENERATED API AUTH TOKEN"
        log_warning "=============================================="
        log_warning "Token: ${API_AUTH_TOKEN}"
        log_warning "=============================================="
        log_warning "SAVE THIS TOKEN for API access!"
        log_warning "=============================================="
    fi
else
    API_AUTH_TOKEN="${API_AUTH_TOKEN_CONFIG}"
    echo "${API_AUTH_TOKEN}" > "${API_TOKEN_FILE}"
    chmod 600 "${API_TOKEN_FILE}"
    log_info "Using configured API auth token"
fi

export API_AUTH_TOKEN

# Write discovery file for Meraki WPN Portal to find us
FREERADIUS_HOST="${FREERADIUS_HOST:-freeradius-server}"
log_info "Writing FreeRADIUS discovery file..."
cat > "${DISCOVERY_FILE}" << EOF
# FreeRADIUS API Discovery File - auto-generated
FREERADIUS_API_HOST=${FREERADIUS_HOST}
FREERADIUS_API_PORT=${API_PORT}
FREERADIUS_API_TOKEN=${API_AUTH_TOKEN}
FREERADIUS_API_URL=http://${FREERADIUS_HOST}:${API_PORT}
EOF
chmod 600 "${DISCOVERY_FILE}"
log_info "Discovery file written to ${DISCOVERY_FILE}"

# ============================================================================
# Database Configuration
# ============================================================================

# HA-only: MariaDB auto-discovery
if [ "${HA_MODE}" = "true" ] && [ "${DB_TYPE}" = "mysql" ]; then
    log_info "MySQL configured - checking for MariaDB service..."
    
    # Wait for MariaDB service
    WAIT_TIMEOUT=120
    WAIT_COUNT=0
    while [ ${WAIT_COUNT} -lt ${WAIT_TIMEOUT} ]; do
        if bashio::services.available "mysql"; then
            log_info "MariaDB service is available"
            break
        fi
        [ $((WAIT_COUNT % 10)) -eq 0 ] && log_info "Waiting for MariaDB... (${WAIT_COUNT}/${WAIT_TIMEOUT}s)"
        sleep 1
        WAIT_COUNT=$((WAIT_COUNT + 1))
    done
    
    # Auto-discover credentials if not provided
    if [ -z "${DB_USER}" ] && bashio::services.available "mysql"; then
        log_info "Auto-discovering MariaDB credentials..."
        DB_HOST=$(bashio::services "mysql" "host")
        DB_PORT=$(bashio::services "mysql" "port")
        DB_USER=$(bashio::services "mysql" "username")
        DB_PASSWORD=$(bashio::services "mysql" "password")
        log_info "MariaDB auto-configured: ${DB_HOST}:${DB_PORT}"
        
        # Test connection and create database
        log_info "Testing MariaDB connection..."
        for i in $(seq 1 30); do
            if mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" \
                -e "SELECT 1;" > /dev/null 2>&1; then
                log_info "MariaDB connection successful"
                mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" \
                    -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null && \
                    log_info "Database '${DB_NAME}' is ready"
                break
            fi
            sleep 2
        done
    fi
fi

# Build DATABASE_URL (same logic for both modes)
case "${DB_TYPE}" in
    sqlite)
        DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
        DATABASE_TYPE="sqlite"
        DATABASE_PATH="${CONFIG_DIR}/${DB_NAME}.db"
        log_info "Using SQLite: ${CONFIG_DIR}/${DB_NAME}.db"
        ;;
    mysql)
        if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
            DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            DATABASE_TYPE="mysql"
            DATABASE_PATH=""
            log_info "Using MySQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
        else
            log_error "MySQL selected but no credentials available"
            DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="${CONFIG_DIR}/${DB_NAME}.db"
            log_warning "Falling back to SQLite"
        fi
        ;;
    postgresql)
        if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
            DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            DATABASE_TYPE="postgresql"
            DATABASE_PATH=""
            log_info "Using PostgreSQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
        else
            log_error "PostgreSQL selected but no credentials"
            DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
            DATABASE_TYPE="sqlite"
            DATABASE_PATH="${CONFIG_DIR}/${DB_NAME}.db"
            log_warning "Falling back to SQLite"
        fi
        ;;
    *)
        DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
        DATABASE_TYPE="sqlite"
        DATABASE_PATH="${CONFIG_DIR}/${DB_NAME}.db"
        log_info "Using SQLite (default)"
        ;;
esac

export DATABASE_URL DATABASE_TYPE DATABASE_PATH

# ============================================================================
# FreeRADIUS Setup (same for both modes)
# ============================================================================

log_info "Starting FreeRADIUS Server..."

RADDB_PATH="/etc/raddb"
RADIUS_USER="radius"
RADIUS_GROUP="radius"

# Create directories
mkdir -p ${CONFIG_DIR}/certs
mkdir -p ${CONFIG_DIR}/clients
mkdir -p ${CONFIG_DIR}/raddb/mods-available
mkdir -p ${CONFIG_DIR}/raddb/mods-enabled
mkdir -p ${CONFIG_DIR}/raddb/mods-config/preprocess
mkdir -p ${CONFIG_DIR}/raddb/sites-available
mkdir -p ${CONFIG_DIR}/raddb/sites-enabled
mkdir -p ${CONFIG_DIR}/raddb/policy.d
mkdir -p ${CONFIG_DIR}/raddb/certs
mkdir -p /var/log/radius
mkdir -p /var/run/radiusd
mkdir -p /tmp/radiusd

chown -R ${RADIUS_USER}:${RADIUS_GROUP} /tmp/radiusd 2>/dev/null || true
chmod 700 /tmp/radiusd

# Copy default config if not present
if [ -d "${RADDB_PATH}" ] && [ ! -L "${RADDB_PATH}" ]; then
    if [ ! -f ${CONFIG_DIR}/raddb/radiusd.conf ] || [ ! -s ${CONFIG_DIR}/raddb/radiusd.conf ]; then
        log_info "Copying default FreeRADIUS configuration..."
        cp -r ${RADDB_PATH}/* ${CONFIG_DIR}/raddb/ 2>/dev/null || true
        
        [ -f ${RADDB_PATH}/mods-available/eap.fallback ] && \
            cp ${RADDB_PATH}/mods-available/eap.fallback ${CONFIG_DIR}/raddb/mods-available/eap
        
        [ -d ${RADDB_PATH}/sites-available.fallback ] && \
            cp ${RADDB_PATH}/sites-available.fallback/* ${CONFIG_DIR}/raddb/sites-available/ 2>/dev/null || true
    fi
    
    rm -rf ${RADDB_PATH}
    ln -s ${CONFIG_DIR}/raddb ${RADDB_PATH}
elif [ ! -L "${RADDB_PATH}" ]; then
    ln -s ${CONFIG_DIR}/raddb ${RADDB_PATH}
fi

# Initialize config files
[ ! -f ${CONFIG_DIR}/clients/clients.conf ] && \
    echo "# RADIUS Clients - dynamically generated" > ${CONFIG_DIR}/clients/clients.conf && \
    chmod 644 ${CONFIG_DIR}/clients/clients.conf

[ ! -f ${CONFIG_DIR}/raddb/users ] && \
    echo "# FreeRADIUS users file" > ${CONFIG_DIR}/raddb/users && \
    chmod 644 ${CONFIG_DIR}/raddb/users

[ ! -f ${CONFIG_DIR}/raddb/mods-config/preprocess/huntgroups ] && \
    echo "# Huntgroups file" > ${CONFIG_DIR}/raddb/mods-config/preprocess/huntgroups

chown -R ${RADIUS_USER}:${RADIUS_GROUP} /var/log/radius /var/run/radiusd 2>/dev/null || true
chown -R ${RADIUS_USER}:${RADIUS_GROUP} ${CONFIG_DIR}/raddb/mods-config 2>/dev/null || true

# Install Meraki dictionary
if [ -f /etc/raddb/dictionary.meraki ]; then
    cp /etc/raddb/dictionary.meraki ${CONFIG_DIR}/raddb/dictionary.meraki
    chmod 644 ${CONFIG_DIR}/raddb/dictionary.meraki
    grep -q "dictionary.meraki" ${CONFIG_DIR}/raddb/dictionary 2>/dev/null || \
        echo "\$INCLUDE dictionary.meraki" >> ${CONFIG_DIR}/raddb/dictionary
fi

# Configure radiusd.conf
if grep -q '^\$INCLUDE clients.conf' ${CONFIG_DIR}/raddb/radiusd.conf 2>/dev/null; then
    sed -i 's/^\$INCLUDE clients\.conf/#DISABLED: $INCLUDE clients.conf/g' ${CONFIG_DIR}/raddb/radiusd.conf
fi

grep -q "${CONFIG_DIR}/clients/clients.conf" ${CONFIG_DIR}/raddb/radiusd.conf 2>/dev/null || \
    echo "\$INCLUDE ${CONFIG_DIR}/clients/clients.conf" >> ${CONFIG_DIR}/raddb/radiusd.conf

grep -q "sites-enabled" ${CONFIG_DIR}/raddb/radiusd.conf 2>/dev/null || \
    echo "\$INCLUDE sites-enabled/" >> ${CONFIG_DIR}/raddb/radiusd.conf

grep -q "policy.d" ${CONFIG_DIR}/raddb/radiusd.conf 2>/dev/null || \
    echo "\$INCLUDE policy.d/" >> ${CONFIG_DIR}/raddb/radiusd.conf

touch ${CONFIG_DIR}/raddb/policy.d/mac_bypass 2>/dev/null || true
touch ${CONFIG_DIR}/raddb/policy.d/authorize_custom 2>/dev/null || true

# Disable REST module
[ -f ${CONFIG_DIR}/raddb/mods-enabled/rest ] && rm -f ${CONFIG_DIR}/raddb/mods-enabled/rest

# Initialize SQLite database if needed
if [ "${DATABASE_TYPE}" = "sqlite" ] && [ ! -f "${DATABASE_PATH}" ]; then
    touch "${DATABASE_PATH}"
    chown ${RADIUS_USER}:${RADIUS_GROUP} "${DATABASE_PATH}" 2>/dev/null || true
fi

# Export for radius-app
export RADIUS_CONFIG_PATH="${CONFIG_DIR}/raddb"
export RADIUS_CERTS_PATH="${CONFIG_DIR}/certs"
export RADIUS_CLIENTS_PATH="${CONFIG_DIR}/clients"
export RADIUS_DATABASE_TYPE="${DATABASE_TYPE}"
export RADIUS_DATABASE_PATH="${DATABASE_PATH}"
export RADIUS_LOG_LEVEL="${LOG_LEVEL}"
export RADIUS_TEST_SECRET="${RADIUS_TEST_SECRET:-$(openssl rand -base64 32)}"
export SERVER_NAME RADSEC_ENABLED RADSEC_PORT COA_ENABLED COA_PORT
export API_ENABLED API_PORT API_HOST

# Start configuration API
if [ "${API_ENABLED}" = "true" ]; then
    log_info "Starting configuration API on ${API_HOST}:${API_PORT}..."
    cd /usr/bin
    python3 -m radius_app.main &
    
    # Wait for API
    for i in $(seq 1 30); do
        curl -sf http://localhost:${API_PORT}/health > /dev/null 2>&1 && break
        sleep 1
    done
    
    # Wait for config files
    for i in $(seq 1 15); do
        [ -f "${CONFIG_DIR}/clients/clients.conf" ] && \
        [ -f "${CONFIG_DIR}/raddb/users" ] && \
        [ -f "${CONFIG_DIR}/raddb/sites-enabled/default" ] && break
        sleep 1
    done
    
    # Apply fallbacks if needed
    if [ ! -f "${CONFIG_DIR}/raddb/sites-enabled/default" ] && [ -d /etc/raddb/sites-available.fallback ]; then
        cp /etc/raddb/sites-available.fallback/default ${CONFIG_DIR}/raddb/sites-available/default 2>/dev/null || true
        ln -sf ../sites-available/default ${CONFIG_DIR}/raddb/sites-enabled/default
    fi
    
    if [ ! -f "${CONFIG_DIR}/raddb/mods-enabled/eap" ] && [ -f /etc/raddb/mods-available/eap.fallback ]; then
        cp /etc/raddb/mods-available/eap.fallback ${CONFIG_DIR}/raddb/mods-available/eap 2>/dev/null || true
        ln -sf ../mods-available/eap ${CONFIG_DIR}/raddb/mods-enabled/eap
    fi
fi

# Generate RadSec certificates if needed
if [ "${RADSEC_ENABLED}" = "true" ]; then
    if [ ! -f "${CONFIG_DIR}/certs/ca.pem" ] || [ ! -f "${CONFIG_DIR}/certs/server.pem" ]; then
        log_info "Generating self-signed RadSec certificates..."
        cd ${CONFIG_DIR}/certs
        
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
        
        log_info "RadSec certificates generated"
    fi
fi

# Start FreeRADIUS
log_info "Starting FreeRADIUS daemon..."
log_info "  Database: ${DATABASE_TYPE}"
log_info "  RadSec: ${RADSEC_ENABLED}"
log_info "  Log level: ${LOG_LEVEL}"

if radiusd -XC -d ${CONFIG_DIR}/raddb > /dev/null 2>&1; then
    log_info "Configuration test passed"
    exec radiusd -f -X -l stdout -d ${CONFIG_DIR}/raddb
else
    log_error "Configuration test failed!"
    radiusd -XC -d ${CONFIG_DIR}/raddb
    exit 1
fi
