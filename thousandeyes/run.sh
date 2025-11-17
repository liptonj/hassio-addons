#!/usr/bin/with-contenv bashio

set -e

# =============================================================================
# ThousandEyes Enterprise Agent - Home Assistant Add-on Startup Script
# =============================================================================

bashio::log.info "Starting ThousandEyes Enterprise Agent..."

# =============================================================================
# Configuration Validation
# =============================================================================

# Check for required account token
if ! bashio::config.has_value 'account_token'; then
    bashio::log.fatal "Account token is required! Please configure your ThousandEyes account token."
    bashio::exit.nok "Missing required configuration: account_token"
fi

ACCOUNT_TOKEN=$(bashio::config 'account_token')
bashio::log.info "Account token configured"

# =============================================================================
# Essential Settings
# =============================================================================

export TEAGENT_ACCOUNT_TOKEN="${ACCOUNT_TOKEN}"

# Agent hostname (optional)
if bashio::config.has_value 'agent_hostname'; then
    AGENT_HOSTNAME=$(bashio::config 'agent_hostname')
    export TEAGENT_AGENT_HOSTNAME="${AGENT_HOSTNAME}"
    bashio::log.info "Agent hostname: ${AGENT_HOSTNAME}"
else
    bashio::log.info "Using default agent hostname"
fi

# IPv4/IPv6 mode
if bashio::config.has_value 'inet_mode'; then
    INET_MODE=$(bashio::config 'inet_mode')
    export TEAGENT_INET="${INET_MODE}"
    bashio::log.info "Network mode: ${INET_MODE}"
fi

# =============================================================================
# Resource Limits
# =============================================================================

if bashio::config.has_value 'memory_limit'; then
    MEMORY_LIMIT=$(bashio::config 'memory_limit')
    export TEAGENT_MEMORY_LIMIT="${MEMORY_LIMIT}M"
    bashio::log.info "Memory limit: ${MEMORY_LIMIT}MB"
fi

if bashio::config.has_value 'cpu_shares'; then
    CPU_SHARES=$(bashio::config 'cpu_shares')
    export TEAGENT_CPU_SHARES="${CPU_SHARES}"
    bashio::log.debug "CPU shares: ${CPU_SHARES}"
fi

# =============================================================================
# Logging Configuration
# =============================================================================

if bashio::config.has_value 'log_level'; then
    LOG_LEVEL=$(bashio::config 'log_level')
    export TEAGENT_LOG_LEVEL="${LOG_LEVEL}"
    bashio::log.info "Log level: ${LOG_LEVEL}"
fi

if bashio::config.has_value 'log_file_size'; then
    LOG_FILE_SIZE=$(bashio::config 'log_file_size')
    export TEAGENT_LOG_FILE_SIZE="${LOG_FILE_SIZE}"
    bashio::log.debug "Log file size: ${LOG_FILE_SIZE}MB"
fi

# =============================================================================
# Proxy Configuration (Conditional)
# =============================================================================

if bashio::config.true 'proxy_enabled'; then
    bashio::log.info "Proxy is enabled, configuring proxy settings..."
    
    if bashio::config.has_value 'proxy_host' && bashio::config.has_value 'proxy_port'; then
        PROXY_TYPE=$(bashio::config 'proxy_type')
        PROXY_HOST=$(bashio::config 'proxy_host')
        PROXY_PORT=$(bashio::config 'proxy_port')
        
        # Build proxy URL
        PROXY_URL=""
        if [ "${PROXY_TYPE}" = "SOCKS5" ]; then
            PROXY_PROTOCOL="socks5"
        else
            PROXY_PROTOCOL=$(echo "${PROXY_TYPE}" | tr '[:upper:]' '[:lower:]')
        fi
        
        # Add authentication if provided
        if bashio::config.has_value 'proxy_user' && bashio::config.has_value 'proxy_pass'; then
            PROXY_USER=$(bashio::config 'proxy_user')
            PROXY_PASS=$(bashio::config 'proxy_pass')
            PROXY_URL="${PROXY_PROTOCOL}://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}"
            bashio::log.info "Proxy configured with authentication: ${PROXY_PROTOCOL}://${PROXY_USER}:***@${PROXY_HOST}:${PROXY_PORT}"
        else
            PROXY_URL="${PROXY_PROTOCOL}://${PROXY_HOST}:${PROXY_PORT}"
            bashio::log.info "Proxy configured: ${PROXY_URL}"
        fi
        
        export HTTP_PROXY="${PROXY_URL}"
        export HTTPS_PROXY="${PROXY_URL}"
        export http_proxy="${PROXY_URL}"
        export https_proxy="${PROXY_URL}"
        
        # Proxy bypass list (no_proxy)
        if bashio::config.has_value 'proxy_bypass_list'; then
            PROXY_BYPASS=$(bashio::config 'proxy_bypass_list')
            export NO_PROXY="${PROXY_BYPASS}"
            export no_proxy="${PROXY_BYPASS}"
            bashio::log.debug "Proxy bypass list: ${PROXY_BYPASS}"
        fi
    else
        bashio::log.warning "Proxy enabled but host or port not configured, skipping proxy setup"
    fi
else
    bashio::log.debug "Proxy is disabled"
fi

# =============================================================================
# Custom DNS Configuration (Conditional)
# =============================================================================

if bashio::config.true 'custom_dns_enabled'; then
    bashio::log.info "Custom DNS is enabled, configuring DNS servers..."
    
    if bashio::config.has_value 'custom_dns_servers'; then
        # Read DNS servers as JSON array
        DNS_SERVERS=$(bashio::config 'custom_dns_servers')
        
        # Convert JSON array to comma-separated string
        DNS_LIST=$(echo "${DNS_SERVERS}" | jq -r 'join(",")')
        
        if [ -n "${DNS_LIST}" ] && [ "${DNS_LIST}" != "null" ]; then
            export TEAGENT_DNS_SERVERS="${DNS_LIST}"
            bashio::log.info "Custom DNS servers: ${DNS_LIST}"
        else
            bashio::log.warning "Custom DNS enabled but no servers configured"
        fi
    else
        bashio::log.warning "Custom DNS enabled but no servers configured"
    fi
else
    bashio::log.debug "Custom DNS is disabled"
fi

# =============================================================================
# Security Options
# =============================================================================

if bashio::config.false 'browserbot_enabled'; then
    export TEAGENT_BROWSERBOT_DISABLED="1"
    bashio::log.info "BrowserBot is disabled"
fi

if bashio::config.true 'accept_self_signed_certs'; then
    export TEAGENT_ACCEPT_SELF_SIGNED_CERTS="1"
    bashio::log.warning "Accepting self-signed certificates (security warning)"
fi

# =============================================================================
# Advanced Options
# =============================================================================

if bashio::config.false 'crash_reports'; then
    export TEAGENT_CRASH_REPORTS_DISABLED="1"
    bashio::log.info "Crash reports disabled"
fi

if bashio::config.false 'auto_update'; then
    export TEAGENT_AUTO_UPDATE_DISABLED="1"
    bashio::log.info "Auto-update disabled"
fi

# =============================================================================
# Volume Path Configuration
# =============================================================================

if bashio::config.true 'use_custom_paths'; then
    bashio::log.info "Using custom volume paths..."
    
    if bashio::config.has_value 'custom_lib_path'; then
        CUSTOM_LIB_PATH=$(bashio::config 'custom_lib_path')
        mkdir -p "${CUSTOM_LIB_PATH}"
        export TEAGENT_LIB_PATH="${CUSTOM_LIB_PATH}"
        bashio::log.info "Custom lib path: ${CUSTOM_LIB_PATH}"
    fi
    
    if bashio::config.has_value 'custom_log_path'; then
        CUSTOM_LOG_PATH=$(bashio::config 'custom_log_path')
        mkdir -p "${CUSTOM_LOG_PATH}"
        export TEAGENT_LOG_PATH="${CUSTOM_LOG_PATH}"
        bashio::log.info "Custom log path: ${CUSTOM_LOG_PATH}"
    fi
else
    # Use default Home Assistant data directory
    bashio::log.info "Using default data directory paths"
    mkdir -p /data/te-agent-lib
    mkdir -p /data/te-agent-logs
    export TEAGENT_LIB_PATH="/data/te-agent-lib"
    export TEAGENT_LOG_PATH="/data/te-agent-logs"
fi

# =============================================================================
# Start ThousandEyes Agent
# =============================================================================

bashio::log.info "==================================================================="
bashio::log.info "Starting ThousandEyes Enterprise Agent with configured settings"
bashio::log.info "==================================================================="

# Check if the original entrypoint exists
if [ -f "/sbin/my_init" ]; then
    bashio::log.info "Starting agent using /sbin/my_init..."
    exec /sbin/my_init
elif [ -f "/usr/local/bin/te-agent" ]; then
    bashio::log.info "Starting agent using /usr/local/bin/te-agent..."
    exec /usr/local/bin/te-agent
else
    bashio::log.error "Could not find ThousandEyes agent executable"
    bashio::log.info "Searching for agent executable..."
    find / -name "te-agent" -o -name "my_init" 2>/dev/null || true
    bashio::exit.nok "ThousandEyes agent executable not found"
fi

