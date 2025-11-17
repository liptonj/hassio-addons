# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-17

### Added
- Initial release of ThousandEyes Enterprise Agent Home Assistant Add-on
- Support for all major ThousandEyes configuration options
- Essential settings: Account token, agent hostname, IPv4/IPv6 mode
- Resource limits: Memory and CPU configuration
- Logging configuration with multiple log levels
- Conditional proxy configuration with support for HTTP, HTTPS, and SOCKS5
- Proxy authentication support
- Proxy bypass list configuration
- Conditional custom DNS configuration
- Security options: BrowserBot toggle, self-signed certificate acceptance
- Advanced options: Crash reports, auto-update controls
- Custom volume path configuration
- Comprehensive error handling and validation
- Detailed logging with appropriate log levels
- Security-first approach with hard-coded NET_ADMIN and SYS_ADMIN capabilities
- Based on official `thousandeyes/enterprise-agent:latest` Docker image
- Bashio integration for Home Assistant configuration management
- Comprehensive documentation with troubleshooting guide
- Environment variable reference file for local testing

### Security
- Password fields properly protected in configuration schema
- Required capabilities (NET_ADMIN, SYS_ADMIN) hard-coded for security
- AppArmor disabled as required by ThousandEyes agent
- Proper file permissions in startup script
- Secure handling of credentials in proxy configuration

## [Unreleased]

### Planned Features
- Health check integration
- Statistics reporting to Home Assistant
- Network test result integration as sensors
- Auto-discovery of optimal configuration
- Multi-agent support for large deployments

