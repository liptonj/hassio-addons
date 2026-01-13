# Changelog

All notable changes to the Meraki WPN Portal add-on will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-12

### Added

- Initial release of Meraki WPN Portal
- Public WiFi registration portal with Cisco Meraki branding
- Self-registration with name, email, and unit selection
- QR code generation for easy device connection
- "My Network" page for credential retrieval
- Admin dashboard with IPSK management
- Invite code system for controlled registration
- Home Assistant integration via WebSocket API
- Support for Home Assistant areas as unit source
- SQLite database for registration and invite code storage
- Comprehensive API documentation
- Unit tests for backend functionality

### Features

- **Registration Portal**: Beautiful, mobile-friendly registration page
- **IPSK Management**: Create, revoke, and delete IPSKs from admin dashboard
- **Invite Codes**: Generate time-limited invite codes with usage limits
- **QR Codes**: Automatic WiFi configuration QR code generation
- **Statistics**: Dashboard with registration and IPSK statistics
- **Branding**: Customizable property name, logo, and colors

### Technical

- FastAPI backend with async/await support
- React 18 frontend with TypeScript
- SQLAlchemy for database operations
- Home Assistant WebSocket client for IPSK management
- Docker multi-stage build for optimized container size

## [Unreleased]

### Planned

- Email verification for registrations
- SMS verification option
- Bulk IPSK creation
- Export/import functionality
- Advanced reporting and analytics
- Guest access expiration reminders
