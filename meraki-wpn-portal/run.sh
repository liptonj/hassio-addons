#!/usr/bin/with-contenv bashio
# Meraki WPN Portal startup script
# Supports both Home Assistant add-on mode and standalone Docker mode

set -e

cd /app

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
    export ADMIN_USERNAME=$(bashio::config 'admin_username')
    export ADMIN_PASSWORD=$(bashio::config 'admin_password')
    
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

    # Set database path in HA config directory
    export DATABASE_URL="sqlite:////config/meraki_wpn_portal.db"

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
fi

# Activate virtual environment
source /opt/venv/bin/activate

# Run database initialization
echo "Initializing database..."
python -c "from app.db.database import init_db; init_db()"

# Start the FastAPI application
echo "Starting FastAPI server on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
