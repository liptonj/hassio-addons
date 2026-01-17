# Changelog

## [2.0.0] - 2026-01-13

### 🎉 Major Refactor - Shared Database Architecture

#### Added
- **Multi-Database Support**: PostgreSQL, MySQL/MariaDB, and SQLite
- **Auto-Detection**: Automatically detects HA addon vs standalone deployment mode
- **Modular Architecture**: Complete code restructure with separated concerns
  - `radius-app/config.py`: Settings with validation
  - `radius-app/db/`: Database models and connection
  - `radius-app/api/`: API routers (health, config)
  - `radius-app/core/`: Business logic (config generation)
  - `radius-app/schemas/`: Pydantic models
- **Database Watcher**: Automatically regenerates config when database changes
- **Comprehensive Tests**: Unit tests with pytest and fixtures
- **Docker Compose**: Standalone deployment with PostgreSQL

#### Changed
- **Shared Database**: FreeRADIUS now reads from same database as Portal (no more sync API)
- **Real-time Updates**: Config regenerates within 5 seconds of database changes
- **Configuration**: New `database_url` option for flexible database configuration
- **API v2**: Cleaner endpoints with proper error handling and logging
- **Dependencies**: Added pymysql, psycopg2-binary for multi-database support

#### Security
- **Fixed**: Removed hardcoded certificate password (now uses `RADIUS_CERT_PASSWORD` env var)
- **Fixed**: Removed "allow all" authentication fallback - API token now required
- **Improved**: Better logging of authentication attempts with IP addresses
- **Enhanced**: Proper error handling without exposing internal details

#### Removed
- **Deprecated**: Old `/api/sync` endpoint (replaced by database watcher)
- **Deprecated**: Manual client/user management endpoints (managed by Portal)
- **Cleaned**: ~300 lines of sync-related code removed

#### Migration Notes
- **Breaking**: Requires shared database setup (MariaDB addon or PostgreSQL)
- **Action Required**: Set `database_url` in config for HA addon mode
- **Action Required**: Set `API_AUTH_TOKEN` for security
- See `DATABASE_OPTIONS.md` for setup instructions

---

## [1.0.0] - 2026-01-12

### Added
- Initial release of FreeRADIUS Server add-on
- RadSec (RADIUS over TLS) support on port 2083
- Traditional RADIUS authentication (UDP 1812) and accounting (UDP 1813)
- SQLite and PostgreSQL backend support
- Configuration management API
- Auto-generated RadSec certificates
- Integration with Meraki WPN Portal
- MAC-based authentication for WPN with UDN ID assignment
- Cisco VSA (Vendor-Specific Attributes) support
- Authentication logging and monitoring
- Health check endpoints
