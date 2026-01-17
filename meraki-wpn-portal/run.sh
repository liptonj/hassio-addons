#!/usr/bin/with-contenv bashio
# Meraki WPN Portal startup script
# Supports both Home Assistant add-on mode and standalone Docker mode

set -e

cd /app

# Function to generate secure random password
generate_password() {
    openssl rand -base64 24 | tr -d '/+=' | head -c 16
}

# Function to generate secure random secret key
generate_secret_key() {
    openssl rand -hex 32
}

# Check if we're running in Home Assistant add-on mode
if bashio::config.exists 'db_type' 2>/dev/null; then
    # HOME ASSISTANT ADD-ON MODE
    bashio::log.info "Running in Home Assistant Add-on mode"
    
    export RUN_MODE="homeassistant"
    
    # Admin credentials - load from config or generate if not set
    ADMIN_USERNAME_CONFIG=$(bashio::config 'admin_username')
    ADMIN_PASSWORD_CONFIG=$(bashio::config 'admin_password')
    
    CREDENTIALS_FILE="/config/.admin_credentials"
    
    if [ -z "${ADMIN_USERNAME_CONFIG}" ] || [ -z "${ADMIN_PASSWORD_CONFIG}" ]; then
        if [ -f "${CREDENTIALS_FILE}" ]; then
            bashio::log.info "Loading previously generated admin credentials"
            source "${CREDENTIALS_FILE}"
        else
            export ADMIN_USERNAME="admin"
            export ADMIN_PASSWORD=$(generate_password)
            
            echo "export ADMIN_USERNAME=\"${ADMIN_USERNAME}\"" > "${CREDENTIALS_FILE}"
            echo "export ADMIN_PASSWORD=\"${ADMIN_PASSWORD}\"" >> "${CREDENTIALS_FILE}"
            chmod 600 "${CREDENTIALS_FILE}"
            
            bashio::log.warning "=============================================="
            bashio::log.warning "AUTO-GENERATED ADMIN CREDENTIALS"
            bashio::log.warning "=============================================="
            bashio::log.warning "Username: ${ADMIN_USERNAME}"
            bashio::log.warning "Password: ${ADMIN_PASSWORD}"
            bashio::log.warning "=============================================="
            bashio::log.warning "SAVE THESE CREDENTIALS NOW!"
            bashio::log.warning "Credentials saved to ${CREDENTIALS_FILE}"
            bashio::log.warning "=============================================="
        fi
    else
        export ADMIN_USERNAME="${ADMIN_USERNAME_CONFIG}"
        export ADMIN_PASSWORD="${ADMIN_PASSWORD_CONFIG}"
        bashio::log.info "Using configured admin credentials"
    fi

    # Database configuration
    DB_TYPE=$(bashio::config 'db_type')
    DB_HOST=$(bashio::config 'db_host')
    DB_PORT=$(bashio::config 'db_port')
    DB_NAME=$(bashio::config 'db_name')
    DB_USER=$(bashio::config 'db_user')
    DB_PASSWORD=$(bashio::config 'db_password')
    
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
            export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            bashio::log.info "Using SQLite: /config/${DB_NAME}.db"
            ;;
        mysql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                export DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                bashio::log.info "Using MySQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "MySQL selected but no credentials available"
                export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        postgresql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                bashio::log.info "Using PostgreSQL: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "PostgreSQL selected but no credentials"
                export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        *)
            bashio::log.warning "Unknown database type: ${DB_TYPE}, using SQLite"
            export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            ;;
    esac
    
    # Generate or load APP_SIGNING_KEY for JWT tokens
    SIGNING_KEY_FILE="/config/.signing_key"
    if [ -f "${SIGNING_KEY_FILE}" ]; then
        export APP_SIGNING_KEY=$(cat "${SIGNING_KEY_FILE}")
    else
        export APP_SIGNING_KEY=$(generate_secret_key)
        echo "${APP_SIGNING_KEY}" > "${SIGNING_KEY_FILE}"
        chmod 600 "${SIGNING_KEY_FILE}"
        bashio::log.info "Generated new APP_SIGNING_KEY"
    fi

    # Get supervisor token for HA API access
    if bashio::var.has_value "$(bashio::addon.token)"; then
        export SUPERVISOR_TOKEN="$(bashio::addon.token)"
        bashio::log.info "Supervisor token configured"
    fi

    bashio::log.info "Configuration loaded - all other settings managed via admin UI"
else
    # STANDALONE DOCKER MODE
    echo "Running in Standalone Docker mode"
    
    export RUN_MODE="${RUN_MODE:-standalone}"
    export DATABASE_URL="${DATABASE_URL:-sqlite:///./meraki_wpn_portal.db}"
    
    # Generate APP_SIGNING_KEY if not set
    if [ -z "${APP_SIGNING_KEY}" ] || [ "${APP_SIGNING_KEY}" = "change-this-in-production" ]; then
        SIGNING_KEY_FILE="/data/.signing_key"
        if [ -f "${SIGNING_KEY_FILE}" ]; then
            export APP_SIGNING_KEY=$(cat "${SIGNING_KEY_FILE}")
        else
            export APP_SIGNING_KEY=$(generate_secret_key)
            mkdir -p /data
            echo "${APP_SIGNING_KEY}" > "${SIGNING_KEY_FILE}"
            chmod 600 "${SIGNING_KEY_FILE}"
            echo "Generated new APP_SIGNING_KEY"
        fi
    fi
    
    # Generate admin credentials if not set
    if [ -z "${ADMIN_USERNAME}" ] || [ -z "${ADMIN_PASSWORD}" ]; then
        CREDENTIALS_FILE="/data/.admin_credentials"
        if [ -f "${CREDENTIALS_FILE}" ]; then
            echo "Loading previously generated admin credentials"
            source "${CREDENTIALS_FILE}"
        else
            export ADMIN_USERNAME="admin"
            export ADMIN_PASSWORD=$(generate_password)
            mkdir -p /data
            echo "export ADMIN_USERNAME=\"${ADMIN_USERNAME}\"" > "${CREDENTIALS_FILE}"
            echo "export ADMIN_PASSWORD=\"${ADMIN_PASSWORD}\"" >> "${CREDENTIALS_FILE}"
            chmod 600 "${CREDENTIALS_FILE}"
            echo "=============================================="
            echo "AUTO-GENERATED ADMIN CREDENTIALS"
            echo "=============================================="
            echo "Username: ${ADMIN_USERNAME}"
            echo "Password: ${ADMIN_PASSWORD}"
            echo "=============================================="
            echo "SAVE THESE CREDENTIALS NOW!"
            echo "=============================================="
        fi
    fi
fi

# Activate virtual environment
source /opt/venv/bin/activate

# Run database initialization
echo "Initializing database..."
python -c "from app.db.database import init_db; init_db()"

# Start the FastAPI application
echo "Starting FastAPI server on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
