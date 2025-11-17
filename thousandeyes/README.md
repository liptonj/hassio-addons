# ThousandEyes Enterprise Agent - Home Assistant Add-on

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg

## About

This Home Assistant add-on runs the ThousandEyes Enterprise Agent Docker container, enabling network monitoring and testing capabilities directly from your Home Assistant instance.

ThousandEyes provides comprehensive network visibility, monitoring internet performance, cloud services, and application delivery from the perspective of your network.

## Prerequisites

- A ThousandEyes account with an active subscription
- Account Group Token from your ThousandEyes portal

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "ThousandEyes Enterprise Agent" add-on
3. Configure the add-on with your ThousandEyes account token
4. Start the add-on

## Configuration

### Required Configuration

#### `account_token` (Required)

Your ThousandEyes Account Group Token. You can obtain this from:
1. Log in to ThousandEyes portal
2. Navigate to Settings > Agents > Enterprise Agents
3. Click "Add New Enterprise Agent"
4. Copy the Account Group Token

**Example:**
```yaml
account_token: "your-account-group-token-here"
```

### Essential Settings

#### `agent_hostname` (Optional)

The hostname for this agent as it will appear in ThousandEyes portal. If not specified, a default hostname will be used.

**Default:** Auto-generated
**Example:**
```yaml
agent_hostname: "homeassistant-agent-01"
```

#### `inet_mode` (Optional)

Network mode for the agent. Controls whether the agent uses IPv4, IPv6, or both.

**Options:**
- `ipv4` - IPv4 only (default)
- `ipv6` - IPv6 only
- `dual` - Both IPv4 and IPv6

**Default:** `ipv4`
**Example:**
```yaml
inet_mode: "ipv4"
```

### Resource Limits

#### `memory_limit` (Optional)

Memory limit for the agent in megabytes. ThousandEyes recommends at least 2GB for optimal performance.

**Default:** `2048` (2GB)
**Example:**
```yaml
memory_limit: "2048"
```

#### `cpu_shares` (Optional)

CPU shares for the agent container. Higher values give more CPU priority.

**Default:** `1024`
**Example:**
```yaml
cpu_shares: "1024"
```

### Logging Configuration

#### `log_level` (Optional)

Logging level for the agent.

**Options:**
- `DEBUG` - Detailed debugging information
- `INFO` - General informational messages (default)
- `WARNING` - Warning messages only
- `ERROR` - Error messages only

**Default:** `INFO`
**Example:**
```yaml
log_level: "INFO"
```

#### `log_file_size` (Optional)

Maximum size of individual log files in megabytes before rotation.

**Default:** `10`
**Example:**
```yaml
log_file_size: "10"
```

### Proxy Configuration

Enable and configure proxy settings if your network requires a proxy for internet access.

#### `proxy_enabled` (Required for Proxy)

Enable or disable proxy configuration.

**Default:** `false`
**Example:**
```yaml
proxy_enabled: true
```

When `proxy_enabled` is `true`, the following options become available:

#### `proxy_type` (Optional)

Type of proxy server.

**Options:**
- `HTTP` - HTTP proxy (default)
- `HTTPS` - HTTPS proxy
- `SOCKS5` - SOCKS5 proxy

**Default:** `HTTP`

#### `proxy_host` (Required when proxy enabled)

Hostname or IP address of your proxy server.

**Example:**
```yaml
proxy_host: "proxy.example.com"
```

#### `proxy_port` (Required when proxy enabled)

Port number of your proxy server.

**Default:** `3128`
**Example:**
```yaml
proxy_port: 3128
```

#### `proxy_user` (Optional)

Username for proxy authentication (if required).

**Example:**
```yaml
proxy_user: "proxy_username"
```

#### `proxy_pass` (Optional)

Password for proxy authentication (if required).

**Example:**
```yaml
proxy_pass: "proxy_password"
```

#### `proxy_bypass_list` (Optional)

Comma-separated list of hostnames or IP addresses that should bypass the proxy.

**Example:**
```yaml
proxy_bypass_list: "localhost,127.0.0.1,.local"
```

### Complete Proxy Example

```yaml
proxy_enabled: true
proxy_type: "HTTP"
proxy_host: "proxy.example.com"
proxy_port: 8080
proxy_user: "myusername"
proxy_pass: "mypassword"
proxy_bypass_list: "localhost,127.0.0.1"
```

### Custom DNS Configuration

Configure custom DNS servers if needed.

#### `custom_dns_enabled` (Required for Custom DNS)

Enable or disable custom DNS configuration.

**Default:** `false`
**Example:**
```yaml
custom_dns_enabled: true
```

#### `custom_dns_servers` (Required when custom DNS enabled)

List of DNS server IP addresses to use.

**Example:**
```yaml
custom_dns_enabled: true
custom_dns_servers:
  - "8.8.8.8"
  - "8.8.4.4"
```

### Security Options

#### `browserbot_enabled` (Optional)

Enable or disable BrowserBot for web-based testing. BrowserBot allows the agent to perform page load and transaction tests.

**Default:** `true`
**Example:**
```yaml
browserbot_enabled: true
```

#### `accept_self_signed_certs` (Optional)

Accept self-signed SSL certificates during tests. Only enable if you need to test internal services with self-signed certificates.

**Default:** `false`
**Example:**
```yaml
accept_self_signed_certs: false
```

### Advanced Options

#### `crash_reports` (Optional)

Enable or disable automatic crash report submission to ThousandEyes.

**Default:** `true`
**Example:**
```yaml
crash_reports: true
```

#### `auto_update` (Optional)

Enable or disable automatic agent updates.

**Default:** `true`
**Example:**
```yaml
auto_update: true
```

### Volume Path Configuration

#### `use_custom_paths` (Optional)

Use custom paths for agent data and logs instead of the default Home Assistant data directory.

**Default:** `false`
**Example:**
```yaml
use_custom_paths: false
```

When `use_custom_paths` is `true`, the following options become available:

#### `custom_lib_path` (Optional)

Custom path for agent library data.

**Default:** `/data/te-agent-lib`
**Example:**
```yaml
custom_lib_path: "/data/te-agent-lib"
```

#### `custom_log_path` (Optional)

Custom path for agent logs.

**Default:** `/data/te-agent-logs`
**Example:**
```yaml
custom_log_path: "/data/te-agent-logs"
```

## Complete Configuration Example

### Minimal Configuration

```yaml
account_token: "your-account-group-token-here"
```

### Full Configuration Example

```yaml
# Essential settings
account_token: "your-account-group-token-here"
agent_hostname: "homeassistant-agent-01"
inet_mode: "ipv4"

# Resource limits
memory_limit: "2048"
cpu_shares: "1024"

# Logging
log_level: "INFO"
log_file_size: "10"

# Proxy (disabled by default)
proxy_enabled: true
proxy_type: "HTTP"
proxy_host: "proxy.example.com"
proxy_port: 8080
proxy_user: "username"
proxy_pass: "password"
proxy_bypass_list: "localhost,127.0.0.1"

# Custom DNS (disabled by default)
custom_dns_enabled: true
custom_dns_servers:
  - "8.8.8.8"
  - "8.8.4.4"

# Security options
browserbot_enabled: true
accept_self_signed_certs: false

# Advanced options
crash_reports: true
auto_update: true

# Volume paths
use_custom_paths: false
```

## Troubleshooting

### Agent not starting

1. **Check your account token**: Ensure you've entered the correct ThousandEyes Account Group Token
2. **Review logs**: Go to the Add-on page and click on the "Log" tab to see detailed error messages
3. **Memory limits**: Ensure your system has enough memory allocated (minimum 2GB recommended)

### Agent not appearing in ThousandEyes portal

1. **Wait a few minutes**: It can take 2-5 minutes for the agent to register with ThousandEyes
2. **Check network connectivity**: Ensure your Home Assistant instance can reach the internet
3. **Verify proxy settings**: If using a proxy, verify the configuration is correct

### Connection issues

1. **Check proxy configuration**: If you're behind a proxy, ensure `proxy_enabled` is `true` and all proxy settings are correct
2. **Verify firewall rules**: Ensure outbound HTTPS (port 443) is allowed
3. **Check DNS**: If experiencing DNS issues, try enabling custom DNS with public DNS servers like `8.8.8.8`

### High resource usage

1. **Reduce BrowserBot tests**: If not needed, disable BrowserBot by setting `browserbot_enabled: false`
2. **Adjust memory limits**: Lower the `memory_limit` if needed, but maintain at least 1GB for basic functionality
3. **Review test configuration**: In ThousandEyes portal, review which tests are assigned to this agent

### Logs show permission errors

The add-on is configured with the necessary capabilities (`NET_ADMIN`, `SYS_ADMIN`) for ThousandEyes. If you see permission errors:

1. Restart the add-on
2. Ensure Home Assistant Supervisor is up to date
3. Check Home Assistant system logs for any supervisor-level errors

## Support

### ThousandEyes Documentation

For more information about ThousandEyes Enterprise Agents:
- [Installing Enterprise Agents with Docker](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/docker-agents/installing-enterprise-agents-with-docker)
- [ThousandEyes Support Portal](https://docs.thousandeyes.com/)

### Add-on Issues

For issues specific to this Home Assistant add-on, please check:
1. Add-on logs (Configuration > Add-ons > ThousandEyes Enterprise Agent > Log)
2. Home Assistant Supervisor logs (Settings > System > Logs > Supervisor)

## Technical Details

- **Base Image**: `thousandeyes/enterprise-agent:latest`
- **Required Capabilities**: NET_ADMIN, SYS_ADMIN
- **Persistent Storage**: `/data/te-agent-lib`, `/data/te-agent-logs`
- **Network Mode**: Bridge (not host network mode)

## Version History

### 1.0.0
- Initial release
- Support for all major ThousandEyes configuration options
- Conditional proxy and custom DNS configuration
- Comprehensive logging and error handling
- Security-first approach with proper capability management

## License

This add-on uses the official ThousandEyes Enterprise Agent Docker image, which is subject to ThousandEyes' license terms.

## Credits

- ThousandEyes for providing the Enterprise Agent Docker image
- Home Assistant community for the add-on framework

