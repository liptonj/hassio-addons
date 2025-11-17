#!/bin/bash
set -e

# Read configuration from Home Assistant
CONFIG_PATH="/data/options.json"

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Configuration file not found at $CONFIG_PATH"
    exit 1
fi

# Extract essential configuration
export TEAGENT_ACCOUNT_TOKEN=$(jq -r '.account_token // empty' "$CONFIG_PATH")
export TEAGENT_AGENT_HOSTNAME=$(jq -r '.agent_hostname // empty' "$CONFIG_PATH")
export TEAGENT_INET=$(jq -r '.inet_mode // "ipv4"' "$CONFIG_PATH")
export TEAGENT_LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$CONFIG_PATH")
export TEAGENT_LIB_PATH="/data/te-agent-lib"
export TEAGENT_LOG_PATH="/data/te-agent-logs"

# Validate required configuration
if [ -z "$TEAGENT_ACCOUNT_TOKEN" ]; then
    echo "ERROR: account_token is required!"
    exit 1
fi

echo "Starting ThousandEyes Enterprise Agent..."
echo "Account token: configured"
echo "Agent hostname: ${TEAGENT_AGENT_HOSTNAME:-default}"
echo "Network mode: ${TEAGENT_INET}"
echo "Log level: ${TEAGENT_LOG_LEVEL}"

# Execute the native ThousandEyes entrypoint
# The container uses: /sbin/tini -- /etc/init
exec /sbin/tini -- /etc/init

