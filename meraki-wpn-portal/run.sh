#!/usr/bin/with-contenv bashio
# Meraki WPN Portal startup script
# Unified logic for both Home Assistant add-on and standalone Docker modes

set -e

cd /app

# ============================================================================
# Common Functions
# ============================================================================

generate_password() {
    openssl rand -base64 24 | tr -d '/+=' | head -c 16
}

generate_secret_key() {
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
    export RUN_MODE="homeassistant"
    CONFIG_DIR="/config"
    log_info "Running in Home Assistant Add-on mode"
else
    HA_MODE="false"
    export RUN_MODE="${RUN_MODE:-standalone}"
    CONFIG_DIR="${CONFIG_DIR:-/data}"
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
    ADMIN_USERNAME_CONFIG=$(bashio::config 'admin_username')
    ADMIN_PASSWORD_CONFIG=$(bashio::config 'admin_password')
    WEB_PORT=$(bashio::config 'web_port')
else
    # Load from environment variables with defaults
    DB_TYPE="${DB_TYPE:-sqlite}"
    DB_HOST="${DB_HOST:-}"
    DB_PORT="${DB_PORT:-3306}"
    DB_NAME="${DB_NAME:-meraki_wpn_portal}"
    DB_USER="${DB_USER:-}"
    DB_PASSWORD="${DB_PASSWORD:-}"
    ADMIN_USERNAME_CONFIG="${ADMIN_USERNAME:-}"
    ADMIN_PASSWORD_CONFIG="${ADMIN_PASSWORD:-}"
    WEB_PORT="${WEB_PORT:-8080}"
fi

# ============================================================================
# Admin Credentials (same logic for both modes)
# ============================================================================

CREDENTIALS_FILE="${CONFIG_DIR}/.admin_credentials"

if [ -z "${ADMIN_USERNAME_CONFIG}" ] || [ -z "${ADMIN_PASSWORD_CONFIG}" ]; then
    if [ -f "${CREDENTIALS_FILE}" ]; then
        log_info "Loading previously generated admin credentials"
        source "${CREDENTIALS_FILE}"
    else
        export ADMIN_USERNAME="admin"
        export ADMIN_PASSWORD=$(generate_password)
        
        mkdir -p "${CONFIG_DIR}"
        echo "export ADMIN_USERNAME=\"${ADMIN_USERNAME}\"" > "${CREDENTIALS_FILE}"
        echo "export ADMIN_PASSWORD=\"${ADMIN_PASSWORD}\"" >> "${CREDENTIALS_FILE}"
        chmod 600 "${CREDENTIALS_FILE}"
        
        log_warning "=============================================="
        log_warning "AUTO-GENERATED ADMIN CREDENTIALS"
        log_warning "=============================================="
        log_warning "Username: ${ADMIN_USERNAME}"
        log_warning "Password: ${ADMIN_PASSWORD}"
        log_warning "=============================================="
        log_warning "SAVE THESE CREDENTIALS NOW!"
        log_warning "=============================================="
    fi
else
    export ADMIN_USERNAME="${ADMIN_USERNAME_CONFIG}"
    export ADMIN_PASSWORD="${ADMIN_PASSWORD_CONFIG}"
    log_info "Using configured admin credentials"
fi

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
        export DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
        log_info "Using SQLite: ${CONFIG_DIR}/${DB_NAME}.db"
        ;;
    mysql)
        if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
            export DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            log_info "Using MySQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
        else
            log_error "MySQL selected but no credentials available"
            export DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
            log_warning "Falling back to SQLite"
        fi
        ;;
    postgresql)
        if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
            export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
            log_info "Using PostgreSQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
        else
            log_error "PostgreSQL selected but no credentials"
            export DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
            log_warning "Falling back to SQLite"
        fi
        ;;
    *)
        export DATABASE_URL="sqlite:///${CONFIG_DIR}/${DB_NAME}.db"
        log_info "Using SQLite (default)"
        ;;
esac

# ============================================================================
# Signing Key (same logic for both modes)
# ============================================================================

SIGNING_KEY_FILE="${CONFIG_DIR}/.signing_key"

if [ -f "${SIGNING_KEY_FILE}" ]; then
    export APP_SIGNING_KEY=$(cat "${SIGNING_KEY_FILE}")
else
    export APP_SIGNING_KEY=$(generate_secret_key)
    mkdir -p "${CONFIG_DIR}"
    echo "${APP_SIGNING_KEY}" > "${SIGNING_KEY_FILE}"
    chmod 600 "${SIGNING_KEY_FILE}"
    log_info "Generated new APP_SIGNING_KEY"
fi

# ============================================================================
# FreeRADIUS Discovery (HA-only via shared file)
# ============================================================================

if [ "${HA_MODE}" = "true" ]; then
    DISCOVERY_FILE="${CONFIG_DIR}/.freeradius_discovery"
    
    if [ -f "${DISCOVERY_FILE}" ]; then
        log_info "FreeRADIUS add-on discovered via ${DISCOVERY_FILE}"
        source "${DISCOVERY_FILE}"
        export FREERADIUS_API_URL="${FREERADIUS_API_URL}"
        export FREERADIUS_API_TOKEN="${FREERADIUS_API_TOKEN}"
        
        # Test connection
        if curl -sf -H "Authorization: Bearer ${FREERADIUS_API_TOKEN}" \
            "${FREERADIUS_API_URL}/health" > /dev/null 2>&1; then
            log_info "FreeRADIUS API connection verified"
        else
            log_warning "FreeRADIUS API not responding - add-on may not be running"
        fi
    else
        log_info "FreeRADIUS discovery file not found (add-on not installed or not started)"
    fi
    
    # Get supervisor token
    if bashio::var.has_value "$(bashio::addon.token)"; then
        export SUPERVISOR_TOKEN="$(bashio::addon.token)"
        log_info "Supervisor token configured"
    fi
fi

# ============================================================================
# Start Application
# ============================================================================

log_info "Configuration complete"
log_info "  Database: ${DATABASE_URL%%@*}@..."
log_info "  Admin user: ${ADMIN_USERNAME}"

# Activate virtual environment
source /opt/venv/bin/activate

# Run database initialization
echo "Initializing database..."
python -c "from app.db.database import init_db; init_db()"

# Start the FastAPI application
echo "Starting FastAPI server on port ${WEB_PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${WEB_PORT}
