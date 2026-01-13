#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Generating ngrok v3 configuration..."
configPath="/etc/ngrok.yml"

# Start with version (required)
echo "version: 3" > $configPath
echo "" >> $configPath

# Agent configuration section (required)
echo "agent:" >> $configPath

# Configure auth token (required)
if bashio::var.has_value "$(bashio::config 'auth_token')"; then
  echo "  authtoken: $(bashio::config 'auth_token')" >> $configPath
else
  bashio::log.error "authtoken is required!"
fi

# Configure API key (optional)
if bashio::var.has_value "$(bashio::config 'api_key')"; then
  echo "  api_key: $(bashio::config 'api_key')" >> $configPath
fi

# Configure log format (optional)
if bashio::var.has_value "$(bashio::config 'log_level')"; then
  echo "  log_level: $(bashio::config 'log_level')" >> $configPath
fi

echo "  log_format: term" >> $configPath
echo "  log: stdout" >> $configPath

# Configure web interface (optional)
if bashio::var.has_value "$(bashio::addon.port 4040)"; then
  echo "  web_addr: 0.0.0.0:$(bashio::addon.port 4040)" >> $configPath
fi

# Build endpoints section
echo "" >> $configPath
echo "endpoints:" >> $configPath

for id in $(bashio::config "tunnels|keys"); do
  name=$(bashio::config "tunnels[${id}].name")
  proto=$(bashio::config "tunnels[${id}].proto")
  addr=$(bashio::config "tunnels[${id}].addr")
  
  bashio::log.info "Configuring endpoint: ${name} (${proto})"
  
  echo "  - name: $name" >> $configPath
  
  # Add endpoint URL if hostname is specified
  hostname=$(bashio::config "tunnels[${id}].hostname")
  if [[ $hostname != "null" ]]; then
    echo "    url: https://${hostname}" >> $configPath
  fi
  
  # Add metadata if specified
  metadata=$(bashio::config "tunnels[${id}].metadata")
  if [[ $metadata != "null" ]]; then
    echo "    metadata: '${metadata}'" >> $configPath
  fi
  
  # Upstream section (required)
  echo "    upstream:" >> $configPath
  
  # Handle address - check if it's just a port number
  if [[ $addr =~ ^([1-9]|[1-5]?[0-9]{2,4}|6[1-4][0-9]{3}|65[1-4][0-9]{2}|655[1-2][0-9]|6553[1-5])$ ]]; then
    # Just a port number - use localhost
    echo "      url: ${addr}" >> $configPath
  else
    # Full address (hostname:port or IP:port) - need to prepend with scheme for non-TCP
    if [[ $proto == "tcp" ]]; then
      echo "      url: ${addr}" >> $configPath
    else
      # For HTTP/HTTPS, add http:// prefix if not present
      if [[ $addr =~ ^https?:// ]]; then
        echo "      url: ${addr}" >> $configPath
      else
        echo "      url: http://${addr}" >> $configPath
      fi
    fi
  fi
  
  # Protocol for HTTP endpoints (optional)
  if [[ $proto == "http" ]] || [[ $proto == "https" ]]; then
    echo "      protocol: http1" >> $configPath
    
    # WebSocket TCP converter
    websocket_tcp_converter=$(bashio::config "tunnels[${id}].websocket_tcp_converter")
    if [[ $websocket_tcp_converter == "true" ]]; then
      bashio::log.info "Note: websocket_tcp_converter must be configured via Traffic Policy in v3"
    fi
  fi
  
  # PROXY protocol (optional)
  proxy_proto=$(bashio::config "tunnels[${id}].proxy_proto")
  if [[ $proxy_proto != "null" ]]; then
    bashio::log.info "Enabling PROXY protocol version: ${proxy_proto}"
    echo "      proxy_protocol: ${proxy_proto}" >> $configPath
  fi
  
done

echo "" >> $configPath

# Log the generated config
bashio::log.info "Generated ngrok v3 configuration:"
cat $configPath | while IFS= read -r line; do
  bashio::log.info "  ${line}"
done

bashio::log.info "Configuration generation complete. Config saved to: ${configPath}"
