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
  
  # Strip any protocol prefix from addr (user convenience)
  # tcp://host:port -> host:port
  # http://host:port -> host:port
  addr=$(echo "$addr" | sed -E 's|^[a-z]+://||')
  
  bashio::log.info "Configuring endpoint: ${name} (${proto})"
  
  echo "  - name: $name" >> $configPath
  
  # Handle endpoint URL - different for TCP vs HTTP/HTTPS
  hostname=$(bashio::config "tunnels[${id}].hostname")
  if [[ $hostname != "null" ]]; then
    if [[ $proto == "tcp" ]]; then
      # For TCP, hostname should be the full reserved address (e.g., 3.tcp.ngrok.io:12345)
      if [[ $hostname =~ \.tcp\.ngrok\.io:[0-9]+ ]]; then
        # Full TCP address provided
        echo "    url: tcp://${hostname}" >> $configPath
      else
        bashio::log.warning "TCP hostname should be a reserved TCP address (e.g., 3.tcp.ngrok.io:12345)"
        echo "    url: tcp://${hostname}" >> $configPath
      fi
    elif [[ $proto == "tls" ]]; then
      echo "    url: tls://${hostname}" >> $configPath
    else
      # HTTP/HTTPS
      echo "    url: https://${hostname}" >> $configPath
    fi
  else
    # No hostname specified
    if [[ $proto == "tcp" ]]; then
      bashio::log.info "No hostname specified for TCP - ngrok will assign a random TCP address"
      # Don't add url field for TCP without hostname - ngrok will auto-assign
    elif [[ $proto == "tls" ]]; then
      bashio::log.info "No hostname specified for TLS - ngrok will assign a random TLS address"
      # Don't add url field for TLS without hostname
    else
      # For HTTP/HTTPS without hostname, ngrok will assign random address
      bashio::log.info "No hostname specified - ngrok will assign a random address"
    fi
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
    # Just a port number
    if [[ $proto == "tcp" ]]; then
      # For TCP with just port, forward to Home Assistant gateway
      echo "      url: 172.30.32.1:${addr}" >> $configPath
    else
      # For HTTP/HTTPS, use port shorthand
      echo "      url: ${addr}" >> $configPath
    fi
  else
    # Full address (hostname:port or IP:port)
    if [[ $proto == "tcp" ]]; then
      # For TCP, just use the address as-is
      echo "      url: ${addr}" >> $configPath
    else
      # For HTTP/HTTPS, ensure it has a scheme
      if [[ $addr =~ ^https?:// ]]; then
        echo "      url: ${addr}" >> $configPath
      else
        echo "      url: http://${addr}" >> $configPath
      fi
    fi
  fi
  
  # Protocol field - for all endpoint types
  # Protocol field in upstream - ONLY for HTTP/HTTPS endpoints
  # Per https://ngrok.com/docs/agent/config/v3#upstreamprotocol
  # upstream.protocol is for HTTP endpoints only (http1 or http2)
  # TCP and TLS endpoints should NOT have this field
  if [[ $proto == "http" ]] || [[ $proto == "https" ]]; then
    # HTTP/HTTPS can specify http1 or http2
    echo "      protocol: http1" >> $configPath
    
    # WebSocket TCP converter
    websocket_tcp_converter=$(bashio::config "tunnels[${id}].websocket_tcp_converter")
    if [[ $websocket_tcp_converter == "true" ]]; then
      bashio::log.info "Note: websocket_tcp_converter must be configured via Traffic Policy in v3"
    fi
  fi
  
  # PROXY protocol - available for all protocols
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
