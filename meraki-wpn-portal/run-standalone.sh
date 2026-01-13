#!/bin/bash
# Standalone Docker mode entrypoint
# Use this when running outside of Home Assistant

set -e

cd /app

# Set required environment variables only
# Note: PROPERTY_NAME, PRIMARY_COLOR, etc. come from DATABASE in standalone mode
export RUN_MODE="${RUN_MODE:-standalone}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////data/meraki_wpn_portal.db}"
export SECRET_KEY="${SECRET_KEY:-change-this-in-production}"
# Allow editable settings to be loaded from database (don't set defaults here)

# Generate or load encryption key for settings
if [ -z "${SETTINGS_ENCRYPTION_KEY}" ]; then
    # Check if key file exists
    if [ -f "/data/.encryption_key" ]; then
        export SETTINGS_ENCRYPTION_KEY=$(cat /data/.encryption_key)
        echo "Loaded encryption key from /data/.encryption_key"
    else
        # Generate new key and save it
        export SETTINGS_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
        echo "$SETTINGS_ENCRYPTION_KEY" > /data/.encryption_key
        chmod 600 /data/.encryption_key
        echo "Generated new encryption key and saved to /data/.encryption_key"
    fi
fi

echo "=============================================="
echo "Meraki WPN Portal - Standalone Mode"
echo "=============================================="
echo "Run mode: ${RUN_MODE}"
echo "Database: ${DATABASE_URL}"
echo "Settings: Loaded from database"
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
