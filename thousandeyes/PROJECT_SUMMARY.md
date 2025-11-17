# ThousandEyes Home Assistant Add-on - Project Summary

## Overview

This project provides a complete Home Assistant add-on for running the ThousandEyes Enterprise Agent. The add-on enables users to monitor network performance and application delivery directly from their Home Assistant installation.

## Project Structure

```
thousand-eyes-plugin/
├── config.yaml              # Add-on configuration and schema
├── Dockerfile              # Container build instructions
├── run.sh                  # Startup script with bashio integration
├── build.yaml              # Build configuration
├── README.md               # User-facing documentation
├── DOCS.md                 # Detailed documentation
├── INSTALL.md              # Installation guide
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # Contribution guidelines
├── LICENSE                 # MIT License
├── PROJECT_SUMMARY.md      # This file
├── repository.yaml         # Repository configuration
├── env.example             # Environment variables reference
├── icon.png.md             # Icon placeholder/instructions
└── .gitignore              # Git ignore rules
```

## Key Features

### Comprehensive Configuration
- **Essential Settings**: Account token, agent hostname, IPv4/IPv6 mode
- **Resource Limits**: Memory and CPU configuration
- **Logging**: Multiple log levels and file size control
- **Proxy Support**: HTTP/HTTPS/SOCKS5 with authentication
- **Custom DNS**: Configurable DNS servers
- **Security Options**: BrowserBot toggle, SSL certificate handling
- **Advanced Options**: Crash reports, auto-updates, custom paths

### Conditional Configuration
- Proxy settings only visible when proxy is enabled
- DNS settings only visible when custom DNS is enabled
- Sensible defaults for all optional settings
- Clear validation and error messages

### Security First
- Password fields properly protected in schema
- Required capabilities (NET_ADMIN, SYS_ADMIN) hard-coded
- Secure credential handling
- No sensitive data in logs

### Professional Documentation
- Comprehensive README with all configuration options
- Detailed DOCS with troubleshooting guide
- Step-by-step INSTALL guide
- CHANGELOG for version tracking
- CONTRIBUTING guide for developers

## Technical Implementation

### Architecture
- **Base Image**: `thousandeyes/enterprise-agent:latest`
- **Integration**: Bashio for Home Assistant configuration management
- **Network**: Bridge mode (not host network)
- **Storage**: Persistent volumes for agent data and logs
- **Capabilities**: NET_ADMIN and SYS_ADMIN (required by ThousandEyes)

### Configuration Flow
1. User configures options in Home Assistant UI
2. Home Assistant stores configuration in `options.json`
3. `run.sh` reads configuration using bashio
4. Script validates required settings
5. Environment variables set based on configuration
6. Conditional settings applied (proxy, DNS)
7. ThousandEyes agent started with configuration

### Error Handling
- Required configuration validation on startup
- Clear error messages for missing settings
- Graceful handling of optional configuration
- Comprehensive logging at appropriate levels
- Proper exit codes for fatal errors

## Configuration Schema

### Required
- `account_token`: ThousandEyes Account Group Token (password type)

### Optional - Essential
- `agent_hostname`: Agent display name
- `inet_mode`: Network protocol (ipv4/ipv6/dual)

### Optional - Resources
- `memory_limit`: RAM allocation (default: 2048 MB)
- `cpu_shares`: CPU priority (default: 1024)

### Optional - Logging
- `log_level`: DEBUG/INFO/WARNING/ERROR (default: INFO)
- `log_file_size`: Log rotation size (default: 10 MB)

### Optional - Proxy (Conditional)
- `proxy_enabled`: Enable/disable proxy (default: false)
- `proxy_type`: HTTP/HTTPS/SOCKS5 (default: HTTP)
- `proxy_host`: Proxy server address
- `proxy_port`: Proxy server port (default: 3128)
- `proxy_user`: Authentication username
- `proxy_pass`: Authentication password
- `proxy_bypass_list`: Comma-separated bypass list

### Optional - DNS (Conditional)
- `custom_dns_enabled`: Enable/disable custom DNS (default: false)
- `custom_dns_servers`: List of DNS server IPs

### Optional - Security
- `browserbot_enabled`: Enable web testing (default: true)
- `accept_self_signed_certs`: Accept self-signed SSL (default: false)

### Optional - Advanced
- `crash_reports`: Enable crash reporting (default: true)
- `auto_update`: Enable auto-updates (default: true)
- `use_custom_paths`: Custom storage paths (default: false)
- `custom_lib_path`: Custom library path
- `custom_log_path`: Custom log path

## Development Guidelines

### Coding Standards
- Follow PEP 8 for Python
- Use shellcheck for bash scripts
- Validate YAML syntax
- Add comments for complex logic
- Include docstrings and documentation

### Testing Checklist
- [ ] Basic startup with minimal config
- [ ] All configuration options
- [ ] Proxy enabled/disabled
- [ ] Custom DNS enabled/disabled
- [ ] Resource limits enforcement
- [ ] Log level changes
- [ ] Agent appears in ThousandEyes portal
- [ ] Tests run successfully
- [ ] Logs are clear and helpful
- [ ] Error messages are actionable

### Release Process
1. Update version in `config.yaml`
2. Add entry to `CHANGELOG.md`
3. Test all features
4. Create git tag
5. Push to repository
6. Update documentation if needed

## Dependencies

### Runtime Dependencies
- Home Assistant Supervisor
- ThousandEyes account and subscription
- Internet connectivity (HTTPS/443 outbound)
- Minimum 2GB RAM available

### Build Dependencies
- `thousandeyes/enterprise-agent:latest` Docker image
- Bashio v0.16.2 (for Home Assistant integration)
- bash, jq, curl (installed in Dockerfile)

## Known Limitations

1. Requires Home Assistant Supervisor (not available in Container or Core installations)
2. Requires internet connectivity to ThousandEyes cloud
3. Some advanced agent features may not be exposed
4. Single agent per add-on instance
5. No direct Home Assistant sensor integration (data visible in ThousandEyes portal only)

## Future Enhancements

Potential features for future versions:
- Health check integration
- Statistics reporting to Home Assistant
- Network test results as Home Assistant sensors
- Auto-discovery of optimal configuration
- Multi-agent support
- Custom test scheduling from Home Assistant
- Integration with Home Assistant notifications
- Dashboard cards for test results

## Resources

### Official Documentation
- [ThousandEyes Documentation](https://docs.thousandeyes.com/)
- [Enterprise Agent Docker Installation](https://docs.thousandeyes.com/product-documentation/global-vantage-points/enterprise-agents/installing/docker-agents/installing-enterprise-agents-with-docker)
- [Home Assistant Add-on Development](https://developers.home-assistant.io/docs/add-ons/tutorial)

### Related Projects
- [ThousandEyes Docker Image](https://hub.docker.com/r/thousandeyes/enterprise-agent)
- [Home Assistant](https://www.home-assistant.io/)
- [Bashio](https://github.com/hassio-addons/bashio)

## Support

For issues and questions:
- **Add-on Issues**: GitHub Issues
- **ThousandEyes Help**: ThousandEyes Support Portal
- **Home Assistant Help**: Home Assistant Community Forum

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

The ThousandEyes Enterprise Agent Docker image is subject to ThousandEyes' own license terms.

## Credits

- ThousandEyes for the Enterprise Agent Docker image
- Home Assistant community for the add-on framework
- Bashio developers for the configuration management library

## Version

Current version: **1.0.0**

Release date: November 17, 2025

## Contributors

See GitHub contributors list and CONTRIBUTING.md for contribution guidelines.

---

**Built with ❤️ for the Home Assistant community**

