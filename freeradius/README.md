# FreeRADIUS Server Add-on

![FreeRADIUS](https://img.shields.io/badge/FreeRADIUS-3.2+-blue?style=flat-square)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5?style=flat-square&logo=home-assistant)
![Version](https://img.shields.io/badge/version-2.0.0-green?style=flat-square)

A FreeRADIUS server add-on with RadSec support and **shared database architecture** for Meraki Wi-Fi Personal Network (WPN) deployments.

## ✨ What's New in v2.0.0

- 🗄️ **Shared Database**: Reads from same database as Portal (real-time updates!)
- 🔄 **Auto-Detection**: Automatically detects HA addon vs standalone mode
- 🐘 **Multi-Database**: PostgreSQL, MySQL/MariaDB, or SQLite support
- 🔒 **Enhanced Security**: No hardcoded credentials, required API authentication
- 🧩 **Modular Architecture**: Clean, testable, maintainable code
- ⚡ **Real-time Config**: Updates within 5 seconds of database changes

## Features

- 🔐 **RadSec Support**: Secure RADIUS over TLS on port 2083
- 📡 **Traditional RADIUS**: UDP authentication (1812) and accounting (1813)
- 🗄️ **Flexible Database**: PostgreSQL, MySQL/MariaDB, or SQLite
- 🔧 **Configuration API**: RESTful API for management
- 🎫 **WPN Integration**: UDN ID assignment via Cisco VSA
- 📝 **Comprehensive Logging**: Track authentication attempts
- 🏥 **Health Checks**: Monitor service status

## Quick Start

### HA Addon Mode (Recommended)

1. Install MariaDB addon from HA store
2. Create database:
   ```sql
   CREATE DATABASE wpn_radius CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'wpn_user'@'%' IDENTIFIED BY 'your-password';
   GRANT ALL PRIVILEGES ON wpn_radius.* TO 'wpn_user'@'%';
   ```
3. Configure both Portal and FreeRADIUS addons:
   ```yaml
   database_url: "mysql+pymysql://wpn_user:!secret wpn_db_password@core-mariadb:3306/wpn_radius"
   api_auth_token: "your-secure-token"
   ```
4. Start the addon

### Standalone Mode (Docker Compose)

1. Copy `docker-compose.yml`
2. Create `.env` file:
   ```bash
   DB_PASSWORD=your-secure-password
   API_AUTH_TOKEN=your-secure-token
   ```
3. Start services:
   ```bash
   docker-compose up -d
   ```

## Configuration

### Basic (HA Addon)

```yaml
database_url: "mysql+pymysql://wpn_user:!secret wpn_db_password@core-mariadb:3306/wpn_radius"
api_auth_token: "your-secure-token"
run_mode: "auto"  # auto-detects HA addon mode
```

### Advanced

```yaml
# Database pool settings
db_pool_size: 5
db_max_overflow: 10
db_pool_recycle: 3600

# Certificate password (optional)
cert_password: ""

# RadSec configuration
radsec_enabled: true
radsec_port: 2083

# Logging
log_level: "info"
```

See [DATABASE_OPTIONS.md](DATABASE_OPTIONS.md) for all configuration options.

## Ports

- **1812/udp**: RADIUS Authentication
- **1813/udp**: RADIUS Accounting  
- **2083/tcp**: RadSec (RADIUS over TLS)
- **8000/tcp**: Configuration API

## API Endpoints

- `GET /health` - Health check (no auth)
- `GET /` - API information
- `POST /api/config/regenerate` - Manual config regeneration (auth required)

## Architecture

```
┌────────────────────────────────────┐
│  Shared Database (wpn_radius)     │
│  - MariaDB / PostgreSQL / MySQL   │
└─────────┬──────────────────────────┘
          │
    ┌─────┴─────┐
    ↓           ↓
 Portal      FreeRADIUS
(writes)     (reads, generates config)
```

**Benefits:**
- Real-time updates (no sync delays)
- Single source of truth
- Simpler architecture
- Better performance

## Documentation

- [Full Documentation](DOCS.md)
- [Database Configuration Options](DATABASE_OPTIONS.md)
- [Agent Handoff Guide](AGENT_HANDOFF.md)
- [Implementation Complete](IMPLEMENTATION_COMPLETE.md)
- [Changelog](CHANGELOG.md)

## Upgrade from v1.0.0

See [Migration Guide](DATABASE_OPTIONS.md#migration-checklist) for upgrade instructions.

**Key Changes:**
- Shared database required (MariaDB addon or PostgreSQL)
- API authentication token now required
- Configuration regenerates automatically from database

## Support

Report issues on GitHub or the Home Assistant Community forum.

## License

MIT License - See [LICENSE](../LICENSE) for details.
