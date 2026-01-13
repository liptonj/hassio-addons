#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Generating ngrok v3 configuration..."
configPath="/etc/ngrok.yml"

# Start with basic config structure (v3 format)
echo "version: 3" > $configPath
echo "log: stdout" >> $configPath

# Configure log level
if bashio::var.has_value "$(bashio::config 'log_level')"; then
  echo "log_level: $(bashio::config 'log_level')" >> $configPath
fi

# Configure auth token
if bashio::var.has_value "$(bashio::config 'auth_token')"; then
  echo "authtoken: $(bashio::config 'auth_token')" >> $configPath
fi

# Configure region
if bashio::var.has_value "$(bashio::config 'region')"; then
  echo "region: $(bashio::config 'region')" >> $configPath
else
  bashio::log.info "No region defined, using default region (US)."
fi

# Configure web interface
bashio::log.debug "Web interface port: $(bashio::addon.port 4040)"
if bashio::var.has_value "$(bashio::addon.port 4040)"; then
  echo "web_addr: 0.0.0.0:$(bashio::addon.port 4040)" >> $configPath
fi

# Build endpoints section (v3 uses 'endpoints' instead of 'tunnels')
echo "endpoints:" >> $configPath

for id in $(bashio::config "tunnels|keys"); do
  name=$(bashio::config "tunnels[${id}].name")
  proto=$(bashio::config "tunnels[${id}].proto")
  addr=$(bashio::config "tunnels[${id}].addr")
  
  bashio::log.info "Configuring endpoint: ${name} (${proto})"
  
  echo "  - name: $name" >> $configPath
  
  # Handle address - check if it's just a port number
  if [[ $addr =~ ^([1-9]|[1-5]?[0-9]{2,4}|6[1-4][0-9]{3}|65[1-4][0-9]{2}|655[1-2][0-9]|6553[1-5])$ ]]; then
    # Just a port number - prepend with Home Assistant gateway IP
    echo "    upstream:" >> $configPath
    echo "      url: ${proto}://172.30.32.1:${addr}" >> $configPath
  else
    # Full address (hostname:port or IP:port)
    echo "    upstream:" >> $configPath
    echo "      url: ${proto}://${addr}" >> $configPath
  fi
  
  # Add URL/hostname if specified (protocol-specific)
  hostname=$(bashio::config "tunnels[${id}].hostname")
  if [[ $hostname != "null" ]]; then
    if [[ $proto == "tcp" ]]; then
      # TCP uses tcp:// scheme
      echo "    url: tcp://${hostname}" >> $configPath
    elif [[ $proto == "tls" ]]; then
      # TLS uses tls:// scheme
      echo "    url: tls://${hostname}" >> $configPath
    else
      # HTTP/HTTPS use https:// by default
      echo "    url: https://${hostname}" >> $configPath
    fi
  fi
  
  # Handle domain (alternative to hostname)
  domain=$(bashio::config "tunnels[${id}].domain")
  if [[ $domain != "null" ]]; then
    if [[ $proto == "tcp" ]]; then
      echo "    url: tcp://${domain}" >> $configPath
    elif [[ $proto == "tls" ]]; then
      echo "    url: tls://${domain}" >> $configPath
    else
      echo "    url: https://${domain}" >> $configPath
    fi
  fi
  
  # Warn about deprecated subdomain
  subdomain=$(bashio::config "tunnels[${id}].subdomain")
  if [[ $subdomain != "null" ]]; then
    bashio::log.warning "Subdomain option is deprecated in ngrok v3. Use hostname instead."
  fi
  
  # Handle schemes for HTTP endpoints only
  if [[ $proto == "http" ]] || [[ $proto == "https" ]]; then
    schemes=$(bashio::config "tunnels[${id}].schemes")
    if [[ $schemes != "null" ]]; then
      echo "    schemes:" >> $configPath
      for scheme in $(bashio::config "tunnels[${id}].schemes"); do
        if [[ $scheme == "http" ]]; then
          echo "      - HTTP" >> $configPath
        elif [[ $scheme == "https" ]]; then
          echo "      - HTTPS" >> $configPath
        fi
      done
    fi
    
    # Handle legacy bind_tls option for HTTP
    bind_tls=$(bashio::config "tunnels[${id}].bind_tls")
    if [[ $bind_tls != "null" ]]; then
      if [[ $bind_tls == "false" ]]; then
        echo "    schemes:" >> $configPath
        echo "      - HTTP" >> $configPath
      elif [[ $bind_tls == "true" ]]; then
        echo "    schemes:" >> $configPath
        echo "      - HTTPS" >> $configPath
      fi
    fi
  fi
  
  # TCP-specific options
  if [[ $proto == "tcp" ]]; then
    # Remote address (requires reserved TCP address)
    remote_addr=$(bashio::config "tunnels[${id}].remote_addr")
    if [[ $remote_addr != "null" ]]; then
      bashio::log.info "Using reserved TCP address: ${remote_addr}"
      echo "    remote_addr: ${remote_addr}" >> $configPath
    fi
    
    # PROXY protocol support
    proxy_proto=$(bashio::config "tunnels[${id}].proxy_proto")
    if [[ $proxy_proto != "null" ]]; then
      bashio::log.info "Enabling PROXY protocol version: ${proxy_proto}"
      echo "    proxy_protocol:" >> $configPath
      echo "      version: ${proxy_proto}" >> $configPath
    fi
  fi
  
  # TLS-specific options
  if [[ $proto == "tls" ]]; then
    # TLS termination certificate
    crt=$(bashio::config "tunnels[${id}].crt")
    key=$(bashio::config "tunnels[${id}].key")
    if [[ $crt != "null" ]] && [[ $key != "null" ]]; then
      bashio::log.info "TLS termination enabled with custom certificate"
      echo "    tls_terminate:" >> $configPath
      echo "      cert_pem: |" >> $configPath
      cat "$crt" | sed 's/^/        /' >> $configPath
      echo "      key_pem: |" >> $configPath
      cat "$key" | sed 's/^/        /' >> $configPath
    fi
    
    # Mutual TLS
    client_cas=$(bashio::config "tunnels[${id}].client_cas")
    mutual_tls_cas=$(bashio::config "tunnels[${id}].mutual_tls_cas")
    if [[ $client_cas != "null" ]]; then
      bashio::log.info "Mutual TLS enabled with client CA"
      echo "    mutual_tls:" >> $configPath
      echo "      ca_pem: |" >> $configPath
      cat "$client_cas" | sed 's/^/        /' >> $configPath
    elif [[ $mutual_tls_cas != "null" ]]; then
      bashio::log.info "Mutual TLS enabled"
      echo "    mutual_tls:" >> $configPath
      echo "      ca_pem: |" >> $configPath
      cat "$mutual_tls_cas" | sed 's/^/        /' >> $configPath
    fi
  fi
  
  # HTTP/HTTPS-specific options
  if [[ $proto == "http" ]] || [[ $proto == "https" ]]; then
    # Basic authentication via Traffic Policy
    auth=$(bashio::config "tunnels[${id}].auth")
    if [[ $auth != "null" ]]; then
      bashio::log.info "Adding basic auth to endpoint: ${name}"
      echo "    traffic_policy:" >> $configPath
      echo "      on_http_request:" >> $configPath
      echo "        - actions:" >> $configPath
      echo "            - type: basic-auth" >> $configPath
      echo "              config:" >> $configPath
      echo "                credentials:" >> $configPath
      echo "                  - ${auth}" >> $configPath
    fi
    
    # OAuth configuration
    oauth_provider=$(bashio::config "tunnels[${id}].oauth_provider")
    if [[ $oauth_provider != "null" ]]; then
      bashio::log.info "Configuring OAuth with provider: ${oauth_provider}"
      echo "    oauth:" >> $configPath
      echo "      provider: ${oauth_provider}" >> $configPath
      
      oauth_allow_domains=$(bashio::config "tunnels[${id}].oauth_allow_domains")
      if [[ $oauth_allow_domains != "null" ]]; then
        echo "      allow_domains:" >> $configPath
        for domain in $(bashio::config "tunnels[${id}].oauth_allow_domains"); do
          echo "        - ${domain}" >> $configPath
        done
      fi
      
      oauth_allow_emails=$(bashio::config "tunnels[${id}].oauth_allow_emails")
      if [[ $oauth_allow_emails != "null" ]]; then
        echo "      allow_emails:" >> $configPath
        for email in $(bashio::config "tunnels[${id}].oauth_allow_emails"); do
          echo "        - ${email}" >> $configPath
        done
      fi
      
      oauth_scopes=$(bashio::config "tunnels[${id}].oauth_scopes")
      if [[ $oauth_scopes != "null" ]]; then
        echo "      scopes:" >> $configPath
        for scope in $(bashio::config "tunnels[${id}].oauth_scopes"); do
          echo "        - ${scope}" >> $configPath
        done
      fi
    fi
    
    # OIDC configuration
    oidc_issuer_url=$(bashio::config "tunnels[${id}].oidc_issuer_url")
    if [[ $oidc_issuer_url != "null" ]]; then
      bashio::log.info "Configuring OIDC authentication"
      echo "    oidc:" >> $configPath
      echo "      issuer_url: ${oidc_issuer_url}" >> $configPath
      
      oidc_client_id=$(bashio::config "tunnels[${id}].oidc_client_id")
      if [[ $oidc_client_id != "null" ]]; then
        echo "      client_id: ${oidc_client_id}" >> $configPath
      fi
      
      oidc_client_secret=$(bashio::config "tunnels[${id}].oidc_client_secret")
      if [[ $oidc_client_secret != "null" ]]; then
        echo "      client_secret: ${oidc_client_secret}" >> $configPath
      fi
      
      oidc_scopes=$(bashio::config "tunnels[${id}].oidc_scopes")
      if [[ $oidc_scopes != "null" ]]; then
        echo "      scopes:" >> $configPath
        for scope in $(bashio::config "tunnels[${id}].oidc_scopes"); do
          echo "        - ${scope}" >> $configPath
        done
      fi
    fi
    
    # Compression
    compression=$(bashio::config "tunnels[${id}].compression")
    if [[ $compression == "true" ]]; then
      bashio::log.info "Enabling compression for endpoint: ${name}"
      echo "    compression: true" >> $configPath
    fi
    
    # WebSocket TCP converter
    websocket_tcp_converter=$(bashio::config "tunnels[${id}].websocket_tcp_converter")
    if [[ $websocket_tcp_converter == "true" ]]; then
      bashio::log.info "Enabling WebSocket TCP converter for endpoint: ${name}"
      echo "    websocket_tcp_converter: true" >> $configPath
    fi
    
    # Circuit breaker
    circuit_breaker=$(bashio::config "tunnels[${id}].circuit_breaker")
    if [[ $circuit_breaker != "null" ]]; then
      bashio::log.info "Configuring circuit breaker with threshold: ${circuit_breaker}"
      echo "    circuit_breaker: ${circuit_breaker}" >> $configPath
    fi
    
    # Host header rewrite
    host_header=$(bashio::config "tunnels[${id}].host_header")
    if [[ $host_header != "null" ]]; then
      bashio::log.info "Setting host header: ${host_header}"
      echo "    host_header: ${host_header}" >> $configPath
    fi
  fi
  
  # Common options for all protocols
  
  # Verify upstream TLS
  verify_upstream_tls=$(bashio::config "tunnels[${id}].verify_upstream_tls")
  if [[ $verify_upstream_tls == "false" ]]; then
    bashio::log.warning "Disabling upstream TLS verification (not recommended for production)"
    echo "    verify_upstream_tls: false" >> $configPath
  fi
  
  # Add metadata if specified
  metadata=$(bashio::config "tunnels[${id}].metadata")
  if [[ $metadata != "null" ]]; then
    echo "    metadata: $metadata" >> $configPath
  fi
  
  # Handle inspect option (web inspection interface)
  inspect=$(bashio::config "tunnels[${id}].inspect")
  if [[ $inspect == "false" ]]; then
    bashio::log.debug "Inspection disabled for endpoint: ${name}"
  fi
  
  # Note: Some v2 options are not directly supported in v3 and would require traffic policies
  # host_header, crt, key, client_cas, remote_addr are advanced options
  host_header=$(bashio::config "tunnels[${id}].host_header")
  if [[ $host_header != "null" ]]; then
    bashio::log.warning "host_header requires Traffic Policy in ngrok v3 - not yet implemented"
  fi
  
done

# Log the generated config
bashio::log.info "Generated ngrok v3 configuration:"
cat $configPath | while IFS= read -r line; do
  bashio::log.info "  ${line}"
done

bashio::log.info "Configuration generation complete. Config saved to: ${configPath}"
