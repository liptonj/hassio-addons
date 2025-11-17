# ThousandEyes Enterprise Agent Add-on Documentation

This add-on allows you to run the ThousandEyes Enterprise Agent directly from your Home Assistant installation.

## What is ThousandEyes?

ThousandEyes is a network intelligence platform that provides visibility into the performance of applications, networks, and internet services. The Enterprise Agent allows you to monitor from your own network perspective.

## Quick Start

1. **Get your Account Token**
   - Log in to [ThousandEyes](https://app.thousandeyes.com)
   - Navigate to: Cloud & Enterprise Agents > Agent Settings
   - Click "Add New Agent"
   - Copy the Account Group Token

2. **Install the Add-on**
   - Add this repository to your Home Assistant Add-on Store
   - Click "Install" on the ThousandEyes Enterprise Agent add-on
   - Wait for installation to complete

3. **Configure the Add-on**
   - Click on "Configuration" tab
   - Paste your Account Token in the `account_token` field
   - (Optional) Set an `agent_hostname` to identify this agent
   - Click "Save"

4. **Start the Add-on**
   - Click "Start"
   - Monitor the logs to ensure successful startup
   - Wait 2-5 minutes for the agent to appear in ThousandEyes portal

## Configuration

### Minimal Configuration

The only required field is `account_token`:

```yaml
account_token: "your-token-here"
```

### Common Configuration

For most users, this configuration is recommended:

```yaml
account_token: "your-token-here"
agent_hostname: "home-network"
memory_limit: "2048"
log_level: "INFO"
```

### Behind a Proxy?

If your network requires a proxy:

```yaml
account_token: "your-token-here"
proxy_enabled: true
proxy_host: "proxy.example.com"
proxy_port: 8080
```

With authentication:

```yaml
proxy_enabled: true
proxy_host: "proxy.example.com"
proxy_port: 8080
proxy_user: "username"
proxy_pass: "password"
```

### Need Custom DNS?

```yaml
account_token: "your-token-here"
custom_dns_enabled: true
custom_dns_servers:
  - "8.8.8.8"
  - "8.8.4.4"
```

## Understanding the Options

### Essential Settings

- **account_token**: Your ThousandEyes Account Group Token (required)
- **agent_hostname**: Friendly name for this agent in the portal
- **inet_mode**: Network protocol (ipv4, ipv6, or dual)

### Resource Settings

- **memory_limit**: RAM in MB (default: 2048, minimum recommended: 2048)
- **cpu_shares**: CPU priority (default: 1024)

### Logging

- **log_level**: Amount of detail in logs (DEBUG, INFO, WARNING, ERROR)
- **log_file_size**: Size in MB before log rotation (default: 10)

### Proxy Settings

Enable `proxy_enabled: true` first, then configure:
- **proxy_type**: HTTP, HTTPS, or SOCKS5
- **proxy_host**: Proxy server address
- **proxy_port**: Proxy server port
- **proxy_user**: Username for authentication (optional)
- **proxy_pass**: Password for authentication (optional)
- **proxy_bypass_list**: Comma-separated hosts to bypass (optional)

### DNS Settings

Enable `custom_dns_enabled: true` first, then configure:
- **custom_dns_servers**: List of DNS server IPs

### Security Settings

- **browserbot_enabled**: Enable web page testing (default: true)
- **accept_self_signed_certs**: Accept self-signed SSL certs (default: false)

### Advanced Settings

- **crash_reports**: Send crash reports to ThousandEyes (default: true)
- **auto_update**: Auto-update the agent (default: true)
- **use_custom_paths**: Use custom storage paths (default: false)

## Troubleshooting

### Agent won't start

Check the logs (click "Log" tab):
- **"Account token is required"**: Add your token in configuration
- **"Connection refused"**: Check internet connectivity
- **"Out of memory"**: Increase `memory_limit`

### Agent not in portal

- Wait 5 minutes - registration takes time
- Check logs for errors
- Verify your account token is correct
- Ensure firewall allows HTTPS (port 443) outbound

### Behind a proxy?

If tests aren't running:
1. Enable `proxy_enabled: true`
2. Set `proxy_host` and `proxy_port`
3. Add credentials if needed
4. Restart the add-on

### DNS issues?

Try enabling custom DNS:
```yaml
custom_dns_enabled: true
custom_dns_servers:
  - "8.8.8.8"
  - "1.1.1.1"
```

### High resource usage?

- Disable BrowserBot if not needed: `browserbot_enabled: false`
- Check which tests are assigned to this agent in portal
- Consider reducing `memory_limit` (but keep above 1024)

## Advanced Usage

### Custom Storage Paths

```yaml
use_custom_paths: true
custom_lib_path: "/data/custom/lib"
custom_log_path: "/data/custom/logs"
```

### IPv6 Only Network

```yaml
inet_mode: "ipv6"
```

### Dual Stack Network

```yaml
inet_mode: "dual"
```

## Logs

Access logs via:
1. Add-on page → "Log" tab (real-time)
2. Settings → System → Logs → Supervisor (system-wide)

Log levels:
- **DEBUG**: Detailed troubleshooting information
- **INFO**: Normal operation (default)
- **WARNING**: Important notices
- **ERROR**: Problems that need attention

## Updates

The add-on uses the official ThousandEyes Docker image with the `latest` tag, which means:
- Set `auto_update: true` for automatic agent updates
- Rebuild the add-on to get the latest image
- Check CHANGELOG.md for add-on updates

## Security

This add-on:
- Requires NET_ADMIN and SYS_ADMIN capabilities (needed by ThousandEyes)
- Stores credentials securely in Home Assistant
- Uses AppArmor disabled mode (required by agent)
- Runs in bridge network mode (not host network)

## Support Resources

- [ThousandEyes Documentation](https://docs.thousandeyes.com/)
- [Enterprise Agent Installation Guide](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing)
- Home Assistant Forum: [Community Add-ons](https://community.home-assistant.io/)

## Performance Expectations

- **Memory**: 1-2 GB typical usage
- **CPU**: Low usage when idle, spikes during tests
- **Network**: Varies by test frequency (typically < 1 Mbps)
- **Storage**: ~100-500 MB for logs and data

## Known Limitations

- Requires Home Assistant Supervisor (add-ons not supported in Container or Core installations)
- Requires internet connectivity to ThousandEyes cloud
- Some advanced agent features may not be exposed in configuration
- Agent updates require add-on rebuild or `auto_update: true`

## FAQ

**Q: Do I need a ThousandEyes subscription?**  
A: Yes, a valid ThousandEyes account with an active subscription is required.

**Q: Can I run multiple agents?**  
A: Currently, this add-on runs one agent per installation. For multiple agents, deploy additional instances.

**Q: Will this affect my Home Assistant performance?**  
A: The agent is lightweight and typically uses 1-2 GB RAM. Ensure your system has adequate resources.

**Q: How do I update the agent?**  
A: The agent auto-updates if `auto_update: true`. For the add-on itself, update through the Home Assistant UI.

**Q: Can I use this for IPv6-only networks?**  
A: Yes, set `inet_mode: "ipv6"` in the configuration.

**Q: What tests can I run?**  
A: All tests supported by Enterprise Agents, configured through the ThousandEyes portal.

**Q: Is this official from ThousandEyes?**  
A: No, this is a community add-on using the official ThousandEyes Docker image.

