#!/bin/bash
set -e

# Read configuration from Home Assistant
CONFIG_PATH="/data/options.json"

# Check if config file exists
if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Configuration file not found at $CONFIG_PATH"
    exit 1
fi

# Load required kernel modules for BrowserBot (iptables support)
# BrowserBot requires iptables with comment extension for container networking
echo "Loading kernel modules for BrowserBot..."
if modprobe xt_comment 2>/dev/null; then
    echo "✓ xt_comment module loaded successfully"
else
    echo "⚠ WARNING: Could not load xt_comment module - BrowserBot may not work"
    echo "  This requires kernel_modules: true and SYS_MODULE capability"
fi

# Load other iptables modules that may be needed
for module in xt_nat xt_conntrack nf_nat nf_conntrack ip_tables iptable_nat iptable_filter; do
    if modprobe "$module" 2>/dev/null; then
        echo "✓ $module loaded"
    fi
done

echo "Kernel modules status:"
lsmod | grep -E "xt_|nf_|ip_tables" || echo "  (no iptables modules visible)"

# Create persistent data directories in /data (Home Assistant persistent storage)
mkdir -p /data/te-agent /data/te-browserbot /data/te-logs

# Create mount point for logs (matching official Docker command)
mkdir -p /var/log/agent

# Bind mount persistent storage to ThousandEyes expected paths
# Using --bind option to ensure proper mounting (matches official docker run command)
mount --bind /data/te-agent /var/lib/te-agent
mount --bind /data/te-browserbot /var/lib/te-browserbot
mount --bind /data/te-logs /var/log/agent

echo "Persistent storage configured (matching official ThousandEyes Docker command):"
echo "  /var/lib/te-agent <- /data/te-agent (bind mount)"
echo "  /var/lib/te-browserbot <- /data/te-browserbot (bind mount)"
echo "  /var/log/agent <- /data/te-logs (bind mount)"

# Extract and configure ThousandEyes environment variables
# Official documentation: https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/docker-agent-config-options
#
# OFFICIALLY DOCUMENTED VARIABLES:
#   - TEAGENT_ACCOUNT_TOKEN (required)
#   - TEAGENT_PROXY_TYPE, TEAGENT_PROXY_LOCATION, TEAGENT_PROXY_AUTH_TYPE
#   - TEAGENT_PROXY_USER, TEAGENT_PROXY_PASS, TEAGENT_PROXY_BYPASS_LIST
#   - TEAGENT_AUTO_UPDATES (note: plural 'S')
#   - HOSTNAME (set via Docker --hostname flag, not env var)
#
# UNDOCUMENTED BUT WORKING VARIABLES (from Docker image inspection):
#   - TEAGENT_INET, TEAGENT_LOG_LEVEL, TEAGENT_LOG_FILE_SIZE
#   - TEAGENT_HOSTNAME, TEAGENT_AGENT_HOSTNAME (alternative to --hostname)
#   - TEAGENT_BROWSERBOT_DISABLED, TEAGENT_CRASH_REPORTS
#   - TEAGENT_ACCEPT_SELF_SIGNED_CERTS

# Required: Account token for agent registration
export TEAGENT_ACCOUNT_TOKEN=$(jq -r '.account_token // empty' "$CONFIG_PATH")

# Agent hostname (optional, defaults to "HA-TE-01" if not set)
# NOTE: Official docs use Docker's --hostname flag, but Home Assistant doesn't
# expose this. Using TEAGENT_HOSTNAME env var as fallback (undocumented but works)
AGENT_HOSTNAME=$(jq -r '.agent_hostname // ""' "$CONFIG_PATH")
if [ -n "$AGENT_HOSTNAME" ] && [ "$AGENT_HOSTNAME" != "null" ]; then
    export TEAGENT_AGENT_HOSTNAME="$AGENT_HOSTNAME"
    export TEAGENT_HOSTNAME="$AGENT_HOSTNAME"
    export HOSTNAME="$AGENT_HOSTNAME"
    echo "Agent hostname set to: $AGENT_HOSTNAME"
else
    export TEAGENT_AGENT_HOSTNAME="HA-TE-01"
    export TEAGENT_HOSTNAME="HA-TE-01"
    export HOSTNAME="HA-TE-01"
    echo "Agent hostname: using default (HA-TE-01)"
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

# Log file size (in MB)
LOG_FILE_SIZE=$(jq -r '.log_file_size // "10"' "$CONFIG_PATH")
export TEAGENT_LOG_FILE_SIZE="$LOG_FILE_SIZE"

# Proxy configuration (per official ThousandEyes documentation)
PROXY_ENABLED=$(jq -r '.proxy_enabled // false' "$CONFIG_PATH")
if [ "$PROXY_ENABLED" = "true" ]; then
    PROXY_TYPE=$(jq -r '.proxy_type // "STATIC"' "$CONFIG_PATH")
    PROXY_LOCATION=$(jq -r '.proxy_location // ""' "$CONFIG_PATH")
    
    # Set proxy type (DIRECT, STATIC, or PAC)
    export TEAGENT_PROXY_TYPE="$PROXY_TYPE"
    
    if [ "$PROXY_TYPE" != "DIRECT" ] && [ -n "$PROXY_LOCATION" ] && [ "$PROXY_LOCATION" != "null" ]; then
        # For STATIC: hostname:port (e.g., proxy.example.com:3128)
        # For PAC: URL to PAC file (e.g., https://example.com/proxy.pac)
        export TEAGENT_PROXY_LOCATION="$PROXY_LOCATION"
        
        # Proxy authentication type (NONE, BASIC, NTLM, KERBEROS)
        PROXY_AUTH_TYPE=$(jq -r '.proxy_auth_type // "NONE"' "$CONFIG_PATH")
        if [ "$PROXY_AUTH_TYPE" != "NONE" ]; then
            export TEAGENT_PROXY_AUTH_TYPE="$PROXY_AUTH_TYPE"
            
            # Username and password for BASIC/NTLM authentication
            PROXY_USER=$(jq -r '.proxy_user // ""' "$CONFIG_PATH")
            PROXY_PASS=$(jq -r '.proxy_pass // ""' "$CONFIG_PATH")
            if [ -n "$PROXY_USER" ] && [ "$PROXY_USER" != "null" ]; then
                export TEAGENT_PROXY_USER="$PROXY_USER"
                if [ -n "$PROXY_PASS" ] && [ "$PROXY_PASS" != "null" ]; then
                    export TEAGENT_PROXY_PASS="$PROXY_PASS"
                fi
            fi
            
            echo "Proxy: ENABLED ($PROXY_TYPE at $PROXY_LOCATION with $PROXY_AUTH_TYPE auth)"
        else
            echo "Proxy: ENABLED ($PROXY_TYPE at $PROXY_LOCATION, no auth)"
        fi
        
        # Proxy bypass list (for STATIC proxies only)
        if [ "$PROXY_TYPE" = "STATIC" ]; then
            PROXY_BYPASS=$(jq -r '.proxy_bypass_list // ""' "$CONFIG_PATH")
            if [ -n "$PROXY_BYPASS" ] && [ "$PROXY_BYPASS" != "null" ]; then
                export TEAGENT_PROXY_BYPASS_LIST="$PROXY_BYPASS"
                echo "Proxy bypass list: $PROXY_BYPASS"
            fi
        fi
    else
        echo "Proxy: Type set to $PROXY_TYPE (no proxy location needed)"
    fi
else
    echo "Proxy: DISABLED"
fi

# Custom DNS configuration
CUSTOM_DNS_ENABLED=$(jq -r '.custom_dns_enabled // false' "$CONFIG_PATH")
if [ "$CUSTOM_DNS_ENABLED" = "true" ]; then
    DNS_SERVERS=$(jq -r '.custom_dns_servers[]? // empty' "$CONFIG_PATH" | tr '\n' ',' | sed 's/,$//')
    if [ -n "$DNS_SERVERS" ]; then
        # Create custom resolv.conf with DNS servers
        echo "# Custom DNS servers from Home Assistant config" > /etc/resolv.conf
        jq -r '.custom_dns_servers[]? // empty' "$CONFIG_PATH" | while read -r dns; do
            echo "nameserver $dns" >> /etc/resolv.conf
        done
        echo "Custom DNS: ENABLED ($DNS_SERVERS)"
    else
        echo "Custom DNS: ENABLED but no servers specified, using defaults"
    fi
else
    echo "Custom DNS: DISABLED (using Home Assistant defaults)"
fi

# SSL/TLS configuration
ACCEPT_SELF_SIGNED=$(jq -r '.accept_self_signed_certs // false' "$CONFIG_PATH")
if [ "$ACCEPT_SELF_SIGNED" = "true" ]; then
    export TEAGENT_ACCEPT_SELF_SIGNED_CERTS=1
    echo "SSL: Accept self-signed certificates ENABLED"
fi

# Crash reports
CRASH_REPORTS=$(jq -r '.crash_reports // true' "$CONFIG_PATH")
if [ "$CRASH_REPORTS" = "false" ]; then
    export TEAGENT_CRASH_REPORTS=0
    echo "Crash reports: DISABLED"
fi

# Auto-update (per official ThousandEyes documentation: TEAGENT_AUTO_UPDATES with 'S')
AUTO_UPDATE=$(jq -r '.auto_update // true' "$CONFIG_PATH")
if [ "$AUTO_UPDATE" = "false" ]; then
    export TEAGENT_AUTO_UPDATES=0
    echo "Auto-update: DISABLED"
fi

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

