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
# (bashio functions will fail in standalone mode)
if bashio::config.exists 'ha_url' 2>/dev/null; then
    # HOME ASSISTANT ADD-ON MODE
    bashio::log.info "Running in Home Assistant Add-on mode"
    
    export RUN_MODE="homeassistant"
    export HA_URL=$(bashio::config 'ha_url')
    export HA_TOKEN=$(bashio::config 'ha_token')
    export PROPERTY_NAME=$(bashio::config 'property_name')
    export LOGO_URL=$(bashio::config 'logo_url')
    export PRIMARY_COLOR=$(bashio::config 'primary_color')
    export DEFAULT_NETWORK_ID=$(bashio::config 'default_network_id')
    export DEFAULT_SSID_NUMBER=$(bashio::config 'default_ssid_number')
    export DEFAULT_GROUP_POLICY_ID=$(bashio::config 'default_group_policy_id')
    export AUTH_SELF_REGISTRATION=$(bashio::config 'auth_self_registration')
    export AUTH_INVITE_CODES=$(bashio::config 'auth_invite_codes')
    export AUTH_EMAIL_VERIFICATION=$(bashio::config 'auth_email_verification')
    export AUTH_SMS_VERIFICATION=$(bashio::config 'auth_sms_verification')
    export REQUIRE_UNIT_NUMBER=$(bashio::config 'require_unit_number')
    export UNIT_SOURCE=$(bashio::config 'unit_source')
    export MANUAL_UNITS=$(bashio::config 'manual_units')
    export DEFAULT_IPSK_DURATION_HOURS=$(bashio::config 'default_ipsk_duration_hours')
    export PASSPHRASE_LENGTH=$(bashio::config 'passphrase_length')
    export ADMIN_NOTIFICATION_EMAIL=$(bashio::config 'admin_notification_email')
    
    # Admin credentials - load from config or generate if not set
    ADMIN_USERNAME_CONFIG=$(bashio::config 'admin_username')
    ADMIN_PASSWORD_CONFIG=$(bashio::config 'admin_password')
    
    # Generate credentials file path
    CREDENTIALS_FILE="/config/.admin_credentials"
    
    if [ -z "${ADMIN_USERNAME_CONFIG}" ] || [ -z "${ADMIN_PASSWORD_CONFIG}" ]; then
        # Check if we have previously generated credentials
        if [ -f "${CREDENTIALS_FILE}" ]; then
            bashio::log.info "Loading previously generated admin credentials"
            source "${CREDENTIALS_FILE}"
        else
            # Generate new credentials
            export ADMIN_USERNAME="admin"
            export ADMIN_PASSWORD=$(generate_password)
            
            # Save to file for persistence
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
            bashio::log.warning "Or set them in the add-on configuration."
            bashio::log.warning "Credentials saved to ${CREDENTIALS_FILE}"
            bashio::log.warning "=============================================="
        fi
    else
        export ADMIN_USERNAME="${ADMIN_USERNAME_CONFIG}"
        export ADMIN_PASSWORD="${ADMIN_PASSWORD_CONFIG}"
        bashio::log.info "Using configured admin credentials"
    fi
    
    # OAuth/SSO Settings
    export ENABLE_OAUTH=$(bashio::config 'enable_oauth')
    export OAUTH_PROVIDER=$(bashio::config 'oauth_provider')
    export OAUTH_ADMIN_ONLY=$(bashio::config 'oauth_admin_only')
    export DUO_CLIENT_ID=$(bashio::config 'duo_client_id')
    export DUO_CLIENT_SECRET=$(bashio::config 'duo_client_secret')
    export DUO_API_HOSTNAME=$(bashio::config 'duo_api_hostname')
    export ENTRA_CLIENT_ID=$(bashio::config 'entra_client_id')
    export ENTRA_CLIENT_SECRET=$(bashio::config 'entra_client_secret')
    export ENTRA_TENANT_ID=$(bashio::config 'entra_tenant_id')
    export OAUTH_CALLBACK_URL=$(bashio::config 'oauth_callback_url')

    # Database configuration - build URL from components
    DB_TYPE=$(bashio::config 'db_type')
    DB_HOST=$(bashio::config 'db_host')
    DB_PORT=$(bashio::config 'db_port')
    DB_NAME=$(bashio::config 'db_name')
    DB_USER=$(bashio::config 'db_user')
    DB_PASSWORD=$(bashio::config 'db_password')
    
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
            export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
            bashio::log.info "Using SQLite database: /config/${DB_NAME}.db"
            ;;
        mysql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                export DATABASE_URL="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                bashio::log.info "Using MySQL database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "MySQL selected but no credentials available. Set db_user/db_password or install MariaDB add-on."
                export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        postgresql)
            if [ -n "${DB_USER}" ] && [ -n "${DB_PASSWORD}" ]; then
                export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
                bashio::log.info "Using PostgreSQL database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
            else
                bashio::log.error "PostgreSQL selected but no credentials configured."
                export DATABASE_URL="sqlite:////config/${DB_NAME}.db"
                bashio::log.warning "Falling back to SQLite"
            fi
            ;;
        *)
            bashio::log.warning "Unknown database type: ${DB_TYPE}, defaulting to SQLite"
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
    
    # FreeRADIUS Integration
    FREERADIUS_ENABLED=$(bashio::config 'freeradius_enabled')
    FREERADIUS_API_URL=$(bashio::config 'freeradius_api_url')
    FREERADIUS_API_TOKEN=$(bashio::config 'freeradius_api_token')
    
    if [ "${FREERADIUS_ENABLED}" = "true" ]; then
        bashio::log.info "FreeRADIUS integration enabled"
        
        # Auto-discover FreeRADIUS if no URL/token configured
        if [ -z "${FREERADIUS_API_URL}" ] || [ -z "${FREERADIUS_API_TOKEN}" ]; then
            DISCOVERY_FILE="/config/.freeradius_discovery"
            
            if [ -f "${DISCOVERY_FILE}" ]; then
                bashio::log.info "Auto-discovering FreeRADIUS from ${DISCOVERY_FILE}..."
                source "${DISCOVERY_FILE}"
                
                export FREERADIUS_API_URL="${FREERADIUS_API_URL:-${FREERADIUS_API_URL}}"
                export FREERADIUS_API_TOKEN="${FREERADIUS_API_TOKEN:-${FREERADIUS_API_TOKEN}}"
                export FREERADIUS_API_HOST="${FREERADIUS_API_HOST}"
                export FREERADIUS_API_PORT="${FREERADIUS_API_PORT}"
                
                bashio::log.info "FreeRADIUS auto-discovered:"
                bashio::log.info "  URL: ${FREERADIUS_API_URL}"
                bashio::log.info "  Token: [configured]"
                
                # Test connection to FreeRADIUS
                bashio::log.info "Testing FreeRADIUS API connection..."
                if curl -sf -H "Authorization: Bearer ${FREERADIUS_API_TOKEN}" \
                    "${FREERADIUS_API_URL}/health" > /dev/null 2>&1; then
                    bashio::log.info "FreeRADIUS API connection successful"
                else
                    bashio::log.warning "Could not connect to FreeRADIUS API"
                    bashio::log.warning "Make sure the FreeRADIUS add-on is running"
                fi
            else
                bashio::log.warning "FreeRADIUS discovery file not found at ${DISCOVERY_FILE}"
                bashio::log.warning "Make sure the FreeRADIUS add-on is installed and has been started at least once"
            fi
        else
            export FREERADIUS_API_URL="${FREERADIUS_API_URL}"
            export FREERADIUS_API_TOKEN="${FREERADIUS_API_TOKEN}"
            bashio::log.info "Using manually configured FreeRADIUS API: ${FREERADIUS_API_URL}"
        fi
    else
        bashio::log.info "FreeRADIUS integration disabled"
    fi

    # Get supervisor token for HA API access
    if bashio::var.has_value "$(bashio::addon.token)"; then
        export SUPERVISOR_TOKEN="$(bashio::addon.token)"
        bashio::log.info "Supervisor token configured"
    fi

    bashio::log.info "Property: ${PROPERTY_NAME}"
    bashio::log.info "Home Assistant URL: ${HA_URL}"
else
    # STANDALONE DOCKER MODE
    # Environment variables should already be set via -e flags
    echo "Running in Standalone Docker mode"
    echo "Run mode: ${RUN_MODE:-standalone}"
    echo "Property: ${PROPERTY_NAME:-My Property}"
    
    # Use defaults if not set
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
            echo "Or set ADMIN_USERNAME and ADMIN_PASSWORD env vars."
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
