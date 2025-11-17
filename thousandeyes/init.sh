#!/bin/bash
set -e

# Read configuration from Home Assistant
CONFIG_PATH="/data/options.json"

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Configuration file not found at $CONFIG_PATH"
    exit 1
fi

# Create persistent data directories in /data (Home Assistant persistent storage)
mkdir -p /data/te-agent /data/te-browserbot /data/te-logs

# Create symlinks from ThousandEyes expected paths to persistent storage
# This ensures data persists across container restarts
if [ ! -L "/var/lib/te-agent" ]; then
    rm -rf /var/lib/te-agent
    ln -sf /data/te-agent /var/lib/te-agent
fi

if [ ! -L "/var/lib/te-browserbot" ]; then
    rm -rf /var/lib/te-browserbot
    ln -sf /data/te-browserbot /var/lib/te-browserbot
fi

if [ ! -L "/var/log/agent" ]; then
    rm -rf /var/log/agent
    ln -sf /data/te-logs /var/log/agent
fi

echo "Persistent storage configured:"
echo "  /var/lib/te-agent -> /data/te-agent"
echo "  /var/lib/te-browserbot -> /data/te-browserbot"
echo "  /var/log/agent -> /data/te-logs"

# Extract essential configuration
export TEAGENT_ACCOUNT_TOKEN=$(jq -r '.account_token // empty' "$CONFIG_PATH")
export TEAGENT_AGENT_HOSTNAME=$(jq -r '.agent_hostname // empty' "$CONFIG_PATH")

# Convert inet_mode to ThousandEyes format (4=IPv4, 6=IPv6, 46=dual)
INET_MODE=$(jq -r '.inet_mode // "ipv4"' "$CONFIG_PATH")
case "$INET_MODE" in
  "ipv4") export TEAGENT_INET=4 ;;
  "ipv6") export TEAGENT_INET=6 ;;
  "dual") export TEAGENT_INET=46 ;;
  *) export TEAGENT_INET=4 ;;
esac

export TEAGENT_LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$CONFIG_PATH")

# Validate required configuration
if [ -z "$TEAGENT_ACCOUNT_TOKEN" ]; then
    echo "ERROR: account_token is required!"
    exit 1
fi

echo "Starting ThousandEyes Enterprise Agent..."
echo "Account token: configured"
echo "Agent hostname: ${TEAGENT_AGENT_HOSTNAME:-default}"
echo "Network mode: IPv${TEAGENT_INET}"
echo "Log level: ${TEAGENT_LOG_LEVEL}"

# Execute the native ThousandEyes entrypoint
# Official ThousandEyes docker command uses /sbin/my_init
exec /sbin/my_init

