#!/bin/bash
# Standalone Docker mode entrypoint
# Use this when running outside of Home Assistant

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

# Set required environment variables only
# Note: PROPERTY_NAME, PRIMARY_COLOR, etc. come from DATABASE in standalone mode
export RUN_MODE="${RUN_MODE:-standalone}"

# DATABASE_URL should come from environment (docker-compose or .env)
# Only set default if completely unset
if [ -z "${DATABASE_URL}" ]; then
    export DATABASE_URL="sqlite:////data/meraki_wpn_portal.db"
fi

# Generate or load SECRET_KEY for JWT tokens
SECRET_KEY_FILE="/data/.secret_key"
if [ -z "${SECRET_KEY}" ] || [ "${SECRET_KEY}" = "change-this-in-production" ]; then
    if [ -f "${SECRET_KEY_FILE}" ]; then
        export SECRET_KEY=$(cat "${SECRET_KEY_FILE}")
        echo "Loaded SECRET_KEY from ${SECRET_KEY_FILE}"
    else
        export SECRET_KEY=$(generate_secret_key)
        mkdir -p /data
        echo "${SECRET_KEY}" > "${SECRET_KEY_FILE}"
        chmod 600 "${SECRET_KEY_FILE}"
        echo "Generated new SECRET_KEY and saved to ${SECRET_KEY_FILE}"
    fi
fi

# Generate or load encryption key for settings
if [ -z "${SETTINGS_ENCRYPTION_KEY}" ]; then
    # Check if key file exists
    if [ -f "/data/.encryption_key" ]; then
        export SETTINGS_ENCRYPTION_KEY=$(cat /data/.encryption_key)
        echo "Loaded encryption key from /data/.encryption_key"
    else
        # Generate new key and save it
        export SETTINGS_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
        mkdir -p /data
        echo "$SETTINGS_ENCRYPTION_KEY" > /data/.encryption_key
        chmod 600 /data/.encryption_key
        echo "Generated new encryption key and saved to /data/.encryption_key"
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
        echo "Credentials saved to ${CREDENTIALS_FILE}"
        echo "=============================================="
    fi
fi

echo "=============================================="
echo "Meraki WPN Portal - Standalone Mode"
echo "=============================================="
echo "Run mode: ${RUN_MODE}"
echo "Database: ${DATABASE_URL}"
echo "Settings: Loaded from database"
echo "Admin: ${ADMIN_USERNAME}"
if [ -n "${MERAKI_API_KEY}" ]; then
    echo "Meraki API: Configured"
else
    echo "Meraki API: Demo mode (no API key)"
fi
echo "=============================================="

# Activate virtual environment
source /opt/venv/bin/activate

# Initialize database
echo "Initializing database..."
python -c "from app.db.database import init_db; init_db()"

# Start the FastAPI application
echo "Starting FastAPI server on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
