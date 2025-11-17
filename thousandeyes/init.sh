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

# Bind mount persistent storage to ThousandEyes expected paths
# Using --bind option to ensure proper mounting
mount --bind /data/te-agent /var/lib/te-agent
mount --bind /data/te-browserbot /var/lib/te-browserbot

# Set log path via environment variable (officially supported by ThousandEyes)
export TEAGENT_LOG_PATH="/data/te-logs"

echo "Persistent storage configured:"
echo "  /var/lib/te-agent <- /data/te-agent (bind mount)"
echo "  /var/lib/te-browserbot <- /data/te-browserbot (bind mount)"
echo "  /var/log/agent -> /data/te-logs (env var)"

# Extract essential configuration
export TEAGENT_ACCOUNT_TOKEN=$(jq -r '.account_token // empty' "$CONFIG_PATH")

# Agent hostname (optional, uses container hostname if not set)
AGENT_HOSTNAME=$(jq -r '.agent_hostname // empty' "$CONFIG_PATH")
if [ -n "$AGENT_HOSTNAME" ]; then
    export TEAGENT_AGENT_HOSTNAME="$AGENT_HOSTNAME"
    export TEAGENT_HOSTNAME="$AGENT_HOSTNAME"
fi

# Convert inet_mode to ThousandEyes format (4=IPv4, 6=IPv6, 46=dual)
INET_MODE=$(jq -r '.inet_mode // "ipv4"' "$CONFIG_PATH")
case "$INET_MODE" in
  "ipv4") export TEAGENT_INET=4 ;;
  "ipv6") export TEAGENT_INET=6 ;;
  "dual") export TEAGENT_INET=46 ;;
  *) export TEAGENT_INET=4 ;;
esac

# Log level - convert to lowercase for ThousandEyes
LOG_LEVEL=$(jq -r '.log_level // "INFO"' "$CONFIG_PATH")
export TEAGENT_LOG_LEVEL=$(echo "$LOG_LEVEL" | tr '[:upper:]' '[:lower:]')

# BrowserBot configuration (requires privileged mode for container-in-container)
BROWSERBOT_ENABLED=$(jq -r '.browserbot_enabled // true' "$CONFIG_PATH")
if [ "$BROWSERBOT_ENABLED" = "false" ]; then
    export TEAGENT_BROWSERBOT_DISABLED=1
    echo "BrowserBot: DISABLED (saves resources, no web page tests)"
else
    echo "BrowserBot: ENABLED (supports web page tests, requires privileged mode)"
fi

# Validate required configuration
if [ -z "$TEAGENT_ACCOUNT_TOKEN" ]; then
    echo "ERROR: account_token is required!"
    exit 1
fi

echo "========================================"
echo "ThousandEyes Enterprise Agent Starting"
echo "========================================"
echo "Account token: configured"
echo "Agent hostname: ${TEAGENT_HOSTNAME:-$(hostname)}"
echo "Network mode: IPv${TEAGENT_INET}"
echo "Log level: ${TEAGENT_LOG_LEVEL}"
echo "Config file: /etc/te-agent.cfg"
echo "========================================"

# Debug: Show all TEAGENT_ environment variables
echo "Environment variables set:"
env | grep TEAGENT_ | grep -v TOKEN | sort
echo "========================================"

# Execute the native ThousandEyes entrypoint
# Official ThousandEyes docker command uses /sbin/my_init
exec /sbin/my_init

