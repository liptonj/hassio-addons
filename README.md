# Home Assistant Add-ons by liptonj

## About

This repository contains custom Home Assistant add-ons for network management and WiFi services.

## Add-ons

### Meraki WPN Portal

Self-service WiFi registration portal for Cisco Meraki networks with Identity PSK (IPSK) management.

**Features:**
- Guest WiFi self-registration
- Identity PSK (IPSK) creation and management
- Home Assistant integration
- OAuth/SSO support (Duo, Microsoft Entra ID)
- QR code generation for easy device connection
- Admin dashboard for user management

### FreeRADIUS Server

FreeRADIUS server with RadSec (RADIUS over TLS) support, designed to work with the Meraki WPN Portal.

**Features:**
- RadSec (RADIUS over TLS) on port 2083
- Traditional RADIUS (UDP 1812/1813)
- Change of Authorization (CoA) support
- Database backends: SQLite, PostgreSQL, MySQL/MariaDB
- RESTful configuration API
- TLS 1.2+ with strong cipher suites

### ngrok

Ngrok tunnel for secure remote access to Home Assistant.

## Installation

Add the repository URL below to your Supervisor Add-on Store in Home Assistant:

```txt
https://github.com/liptonj/hassio-addons
```

1. Navigate to **Settings** → **Add-ons** → **Add-on Store**
2. Click the three-dot menu (⋮) → **Repositories**
3. Add the repository URL above
4. Refresh the page and find the add-ons in the store

## Documentation

Each add-on has its own documentation:

- [Meraki WPN Portal Documentation](meraki-wpn-portal/DOCS.md)
- [FreeRADIUS Server Documentation](freeradius/DOCS.md)
- [ngrok Documentation](ngrok/DOCS.md)

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/liptonj/hassio-addons/issues) page.

## License

MIT License

[addons-community]: https://addons.community/
[community-addons-repo]: https://github.com/hassio-addons/repository
