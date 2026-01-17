# FreeRADIUS v2.0.0 - Production Deployment Guide

## Table of Contents
1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Modes](#deployment-modes)
3. [HA Addon Deployment](#ha-addon-deployment)
4. [Standalone Deployment](#standalone-deployment)
5. [Post-Deployment Validation](#post-deployment-validation)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Rollback Procedures](#rollback-procedures)

---

## Pre-Deployment Checklist

### ✅ Prerequisites

**All Deployments:**
- [ ] Python 3.11+ installed
- [ ] FreeRADIUS 3.x installed
- [ ] Sufficient disk space (minimum 1GB recommended)
- [ ] Network ports available (1812/udp, 1813/udp, 2083/tcp, 8000/tcp)

**Shared Database:**
- [ ] PostgreSQL 13+ OR MariaDB 10.6+ OR MySQL 8.0+ available
- [ ] Database user created with appropriate permissions
- [ ] Database connection tested from deployment host
- [ ] Backup of existing data (if migrating from v1.x)

**Security:**
- [ ] API authentication token generated (min 32 characters, cryptographically random)
- [ ] Certificate password generated (if using RadSec)
- [ ] Secrets stored in secure secrets management system

### ✅ Configuration Validation

**Before Deployment:**
1. **Test Database Connection:**
   ```bash
   # PostgreSQL
   psql -h <host> -U <user> -d <database> -c "SELECT 1"
   
   # MariaDB/MySQL
   mysql -h <host> -u <user> -p<password> <database> -e "SELECT 1"
   ```

2. **Verify Secrets:**
   ```bash
   # Ensure tokens are strong
   echo $API_AUTH_TOKEN | wc -c  # Should be >= 32
   ```

3. **Check Port Availability:**
   ```bash
   ss -tuln | grep -E '1812|1813|2083|8000'
   # Should return no results (ports free)
   ```

---

## Deployment Modes

### Mode 1: Home Assistant Addon (Recommended for HA Users)
- **Use Case:** Running inside Home Assistant OS
- **Database:** MariaDB addon (core-mariadb)
- **Auto-Detection:** Automatic via SUPERVISOR_TOKEN
- **Complexity:** Low

### Mode 2: Standalone (Recommended for Docker/Production)
- **Use Case:** Docker Compose, Kubernetes, or bare metal
- **Database:** PostgreSQL (recommended) or MariaDB
- **Auto-Detection:** Requires `DEPLOYMENT_MODE=standalone`
- **Complexity:** Medium

---

## HA Addon Deployment

### Step 1: Install MariaDB Addon

1. **Install MariaDB addon** from Home Assistant Add-on Store
2. **Configure MariaDB:**
   ```yaml
   # MariaDB addon config
   databases:
     - wpn_radius
   logins:
     - username: wpn_user
       password: !secret mariadb_password
   rights:
     - username: wpn_user
       database: wpn_radius
   ```

3. **Start MariaDB addon** and verify it's running

### Step 2: Create Secrets

Create `/config/secrets.yaml`:
```yaml
# IMPORTANT: This file should be protected (chmod 600)
mariadb_password: "YOUR_STRONG_DB_PASSWORD_HERE"
radius_api_token: "YOUR_STRONG_API_TOKEN_HERE"
radius_cert_password: "YOUR_CERT_PASSWORD_HERE"
```

**Generate secure passwords:**
```bash
# Database password
openssl rand -base64 32

# API token
openssl rand -base64 48

# Certificate password
openssl rand -base64 24
```

### Step 3: Initialize Database Schema

**Option A: Via Portal (Recommended)**
If Meraki WPN Portal addon is installed, it will create the schema automatically.

**Option B: Manual SQL**
```sql
-- Connect to MariaDB
mysql -h core-mariadb -u wpn_user -p wpn_radius

-- Verify portal created tables
SHOW TABLES;
-- Expected: radius_clients, udn_assignments, users, etc.
```

### Step 4: Configure FreeRADIUS Addon

Edit addon configuration:
```yaml
# FreeRADIUS Server Configuration
server_name: "freeradius-server"
max_requests: 16384
max_request_time: 30
cleanup_delay: 5
max_servers: 32
min_spare_servers: 3
max_spare_servers: 10

# RadSec Configuration
radsec_enabled: true
radsec_port: 2083

# Logging
log_level: "info"
log_auth: true
log_auth_badpass: true
log_auth_goodpass: false

# Database Configuration
database_url: "mysql+pymysql://wpn_user:!secret mariadb_password@core-mariadb:3306/wpn_radius"
run_mode: "auto"  # Auto-detects HA addon mode

# Database pool settings
db_pool_size: 5
db_max_overflow: 10
db_pool_recycle: 3600

# API Configuration
api_enabled: true
api_port: 8000
api_auth_token: "!secret radius_api_token"

# Certificate password
cert_password: "!secret radius_cert_password"
```

### Step 5: Start FreeRADIUS Addon

1. **Start addon** via Home Assistant UI
2. **Monitor logs** for startup errors
3. **Check health endpoint:**
   ```bash
   curl http://homeassistant.local:8000/health
   ```

Expected output:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-13T...",
  "radius_running": true,
  "portal_db_connected": true,
  "config_files_exist": true
}
```

### Step 6: Validate Deployment

See [Post-Deployment Validation](#post-deployment-validation) section below.

---

## Standalone Deployment

### Step 1: Prepare Database

**PostgreSQL (Recommended):**
```bash
# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE wpn_radius;
CREATE USER wpn_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE wpn_radius TO wpn_user;
\c wpn_radius
GRANT ALL ON SCHEMA public TO wpn_user;
EOF
```

**MariaDB:**
```bash
# Create database and user
mysql -u root -p <<EOF
CREATE DATABASE wpn_radius CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wpn_user'@'%' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON wpn_radius.* TO 'wpn_user'@'%';
FLUSH PRIVILEGES;
EOF
```

### Step 2: Prepare Environment

Create `.env` file:
```bash
# Database Configuration
DATABASE_URL=postgresql://wpn_user:your_secure_password@postgres:5432/wpn_radius

# Deployment Mode
DEPLOYMENT_MODE=standalone
RUN_MODE=standalone

# API Configuration
API_ENABLED=true
API_PORT=8000
API_AUTH_TOKEN=your_api_token_here

# RADIUS Configuration
RADSEC_ENABLED=true
LOG_LEVEL=INFO

# Certificates
CERT_PASSWORD=your_cert_password

# Optional: Data directory
DATA_DIR=/data
```

**Security Note:** Set proper file permissions:
```bash
chmod 600 .env
```

### Step 3: Deploy with Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  # Database (PostgreSQL)
  postgres:
    image: postgres:15-alpine
    container_name: wpn-postgres
    environment:
      POSTGRES_DB: wpn_radius
      POSTGRES_USER: wpn_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U wpn_user"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "5432:5432"
    networks:
      - wpn_network
    restart: unless-stopped

  # FreeRADIUS Server
  freeradius:
    build: .
    container_name: wpn-freeradius
    environment:
      DATABASE_URL: postgresql://wpn_user:${DB_PASSWORD}@postgres:5432/wpn_radius
      DEPLOYMENT_MODE: standalone
      API_ENABLED: "true"
      API_PORT: 8000
      API_AUTH_TOKEN: ${RADIUS_API_TOKEN}
      LOG_LEVEL: INFO
      RADSEC_ENABLED: "true"
      CERT_PASSWORD: ${CERT_PASSWORD}
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "1812:1812/udp"  # RADIUS Auth
      - "1813:1813/udp"  # RADIUS Accounting
      - "2083:2083/tcp"  # RadSec
      - "8000:8000/tcp"  # API
    volumes:
      - ./data:/data
      - ./config:/config
      - ./certs:/config/certs
      - ./logs:/var/log/radius
    networks:
      - wpn_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
    driver: local

networks:
  wpn_network:
    driver: bridge
```

Create `.env.example` for reference:
```bash
DB_PASSWORD=change_me
RADIUS_API_TOKEN=change_me
CERT_PASSWORD=change_me
```

### Step 4: Deploy

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f freeradius

# Check health
curl http://localhost:8000/health
```

### Step 5: Initialize Schema

**If using portal, skip this step** (portal creates schema).

**Manual schema creation:**
```bash
docker-compose exec freeradius python3 <<EOF
from radius_app.db.database import get_engine
from radius_app.db.models import Base

engine = get_engine()
Base.metadata.create_all(engine)
print("✅ Schema created successfully")
EOF
```

### Step 6: Validate Deployment

See [Post-Deployment Validation](#post-deployment-validation) section below.

---

## Post-Deployment Validation

### ✅ Validation Checklist

**1. Health Check**
```bash
# Check API health
curl http://localhost:8000/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2026-01-13T...",
  "radius_running": true,
  "portal_db_connected": true,
  "config_files_exist": true
}
```

**2. Database Connectivity**
```bash
# Test database connection
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/config/status

# Expected response
{
  "clients_count": 0,  # Or >0 if data exists
  "assignments_count": 0,
  "status": "no_clients" # Or "active"
}
```

**3. Configuration Files**
```bash
# Check generated config files exist
ls -lh /config/clients/clients.conf
ls -lh /etc/raddb/users

# Verify they're readable
cat /config/clients/clients.conf | head -20
```

**4. RADIUS Daemon**
```bash
# Check RADIUS is running
pgrep -x radiusd

# Check RADIUS logs for errors
tail -f /var/log/radius/radius.log
```

**5. Test Authentication**
```bash
# Test with radtest (requires test client in config)
radtest testuser testpass localhost 0 testing123

# Expected for successful auth:
# Received Access-Accept packet
```

**6. API Authentication**
```bash
# Test auth required
curl http://localhost:8000/api/reload
# Should return 401 Unauthorized

# Test valid token
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/reload \
     -H "Content-Type: application/json" \
     -d '{"force": true}'
# Should return {"success": true, ...}
```

**7. Config Regeneration**
```bash
# Add test data via portal or direct DB
# Then trigger regeneration
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/reload \
     -H "Content-Type: application/json" \
     -d '{"force": true}'

# Verify config was regenerated (check timestamps)
ls -l /config/clients/clients.conf
```

### ✅ Smoke Tests

Run the included smoke tests:
```bash
# Run basic unit tests
cd /path/to/freeradius
pytest tests/unit/ -v

# Run integration tests (requires DB)
pytest tests/integration/ -v -m integration

# Run E2E tests (requires full stack)
pytest tests/e2e/ -v -m e2e
```

---

## Monitoring & Maintenance

### Monitoring Strategy

**1. Health Endpoint**
- **URL:** `http://localhost:8000/health`
- **Frequency:** Every 30 seconds
- **Alert on:** `status != "healthy"` for > 2 minutes

**2. Log Monitoring**
```bash
# Monitor for errors
tail -f /var/log/radius/radius.log | grep -i error

# Monitor for failed auth
tail -f /var/log/radius/radius.log | grep "Login incorrect"
```

**3. Database Connection**
```bash
# Check database connectivity
curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/config/status
```

**4. Process Monitoring**
```bash
# Ensure radiusd is running
pgrep -x radiusd || systemctl restart freeradius
```

### Maintenance Tasks

**Daily:**
- [ ] Check health endpoint
- [ ] Review error logs
- [ ] Monitor disk space

**Weekly:**
- [ ] Review authentication logs for anomalies
- [ ] Check database performance
- [ ] Verify config synchronization

**Monthly:**
- [ ] Update certificates (if expiring soon)
- [ ] Review and rotate logs
- [ ] Database maintenance (vacuum, optimize)
- [ ] Security audit

**Quarterly:**
- [ ] Update FreeRADIUS addon
- [ ] Review and update secrets/passwords
- [ ] Performance testing
- [ ] Disaster recovery drill

---

## Troubleshooting

### Issue 1: Database Connection Failed

**Symptoms:**
- Health check shows `portal_db_connected: false`
- Logs show: `Failed to connect to database`

**Diagnosis:**
```bash
# Test database connection manually
# PostgreSQL
psql -h <host> -U <user> -d <database> -c "SELECT 1"

# MariaDB
mysql -h <host> -u <user> -p<password> <database> -e "SELECT 1"
```

**Solutions:**
1. **Check credentials:** Verify `database_url` in config
2. **Check network:** Ensure database host is reachable
3. **Check permissions:** Verify user has correct grants
4. **Check database:** Ensure database exists and is running

### Issue 2: Config Files Not Generated

**Symptoms:**
- Health check shows `config_files_exist: false`
- Files missing: `/config/clients/clients.conf` or `/etc/raddb/users`

**Diagnosis:**
```bash
# Check directory permissions
ls -ld /config/clients/
ls -ld /etc/raddb/

# Check database watcher logs
docker logs freeradius | grep "database watcher"
```

**Solutions:**
1. **Check permissions:** Ensure directories are writable
2. **Manual trigger:** Force config regeneration via API
3. **Check database:** Ensure tables exist and have data

```bash
# Force regeneration
curl -X POST -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/reload \
     -H "Content-Type: application/json" \
     -d '{"force": true}'
```

### Issue 3: RADIUS Daemon Not Running

**Symptoms:**
- Health check shows `radius_running: false`
- No response on ports 1812/1813

**Diagnosis:**
```bash
# Check if radiusd is running
pgrep -x radiusd

# Check radiusd logs
tail -100 /var/log/radius/radius.log

# Test radiusd config
radiusd -C -X
```

**Solutions:**
1. **Config error:** Check logs for syntax errors in config files
2. **Port conflict:** Ensure ports 1812/1813 are not in use
3. **Certificate error:** Check cert password and cert files exist

### Issue 4: Authentication Fails

**Symptoms:**
- radtest returns `Access-Reject`
- Logs show: `Login incorrect`

**Diagnosis:**
```bash
# Check RADIUS logs
tail -f /var/log/radius/radius.log

# Verify client exists in config
grep -A5 "client testclient" /config/clients/clients.conf

# Verify user exists
grep "test-mac" /etc/raddb/users
```

**Solutions:**
1. **Client mismatch:** Ensure client IP and secret match
2. **User not found:** Verify MAC address in UDN assignments
3. **Inactive record:** Check `is_active` flag in database

### Issue 5: API Returns 401 Unauthorized

**Symptoms:**
- API calls fail with 401
- Even with correct token

**Diagnosis:**
```bash
# Check API token is set
echo $API_AUTH_TOKEN

# Test with explicit token
curl -H "Authorization: Bearer $API_AUTH_TOKEN" \
     http://localhost:8000/api/config/status
```

**Solutions:**
1. **Token mismatch:** Verify token in config matches request
2. **Token not set:** Check `API_AUTH_TOKEN` environment variable
3. **Format error:** Ensure using `Bearer <token>` format

---

## Rollback Procedures

### Quick Rollback (< 5 minutes)

**If deployment fails during startup:**

1. **Stop FreeRADIUS addon/container:**
   ```bash
   # HA Addon
   # Stop via Home Assistant UI
   
   # Docker Compose
   docker-compose down freeradius
   ```

2. **Restore previous configuration:**
   ```bash
   # Restore config from backup
   cp /config/freeradius.backup/config.yaml /config/freeradius/
   ```

3. **Restart with previous version:**
   ```bash
   # HA Addon: Downgrade via addon store
   # Docker: Use previous image tag
   docker-compose up -d freeradius
   ```

### Full Rollback (Migration from v1.x)

**If v2.0 doesn't work and must revert to v1.x:**

1. **Backup v2.0 database (for later retry):**
   ```bash
   # PostgreSQL
   pg_dump -h <host> -U <user> wpn_radius > wpn_radius_v2_backup.sql
   
   # MariaDB
   mysqldump -h <host> -u <user> -p wpn_radius > wpn_radius_v2_backup.sql
   ```

2. **Restore v1.x SQLite database:**
   ```bash
   cp /config/freeradius.db.backup /config/freeradius.db
   ```

3. **Revert to v1.x addon/container:**
   ```bash
   # Change image tag to v1.x
   docker pull ghcr.io/your-org/freeradius:1.0.0
   ```

4. **Update configuration to v1.x format:**
   ```yaml
   # Remove v2.0 specific options
   # database_url
   # run_mode
   # db_pool_*
   ```

5. **Restart:**
   ```bash
   docker-compose up -d freeradius
   ```

6. **Verify v1.x working:**
   ```bash
   curl http://localhost:8000/health
   radtest testuser testpass localhost 0 testing123
   ```

### Post-Rollback Actions

- [ ] Document what failed and why
- [ ] Open GitHub issue with details
- [ ] Plan remediation for next attempt
- [ ] Keep v2.0 backup for later migration

---

## Migration from v1.x to v2.0

**See separate guide:** `MIGRATION_GUIDE.md`

Key differences:
- v1.x: SQLite per addon
- v2.0: Shared database (MariaDB/PostgreSQL)
- v1.x: Sync API for data transfer
- v2.0: Direct database access, no sync

---

## Security Hardening

### Production Security Checklist

- [ ] Strong API token (>= 48 characters, random)
- [ ] Strong database password (>= 32 characters)
- [ ] Certificate password set (>= 24 characters)
- [ ] Secrets stored in secrets management system
- [ ] File permissions correct (config files 644, secrets 600)
- [ ] TLS 1.2+ enforced (no TLS 1.0/1.1)
- [ ] Weak ciphers disabled
- [ ] API accessible only from trusted networks
- [ ] Database accessible only from app network
- [ ] Regular security updates applied
- [ ] Logs reviewed for suspicious activity

---

## Support & Resources

**Documentation:**
- README.md - Overview and quick start
- DATABASE_OPTIONS.md - Database configuration reference
- AGENT_HANDOFF.md - Developer guide
- IMPLEMENTATION_COMPLETE.md - Technical details

**Getting Help:**
- GitHub Issues: https://github.com/your-org/hassio-addons/issues
- Community Forum: https://community.home-assistant.io
- Discord: #freeradius channel

**Reporting Bugs:**
Include:
1. Deployment mode (HA addon or standalone)
2. Database type and version
3. FreeRADIUS version
4. Full logs (with secrets redacted)
5. Steps to reproduce

---

## Appendix A: Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | Auto | Database connection string |
| `DEPLOYMENT_MODE` | No | Auto-detect | `ha_addon` or `standalone` |
| `API_AUTH_TOKEN` | Yes | None | API authentication token |
| `API_PORT` | No | 8000 | API HTTP port |
| `LOG_LEVEL` | No | INFO | Log level (DEBUG, INFO, WARNING, ERROR) |
| `RADSEC_ENABLED` | No | true | Enable RadSec (RADIUS over TLS) |
| `CERT_PASSWORD` | No | Empty | Certificate private key password |
| `DB_POOL_SIZE` | No | 5 | Database connection pool size |
| `DB_MAX_OVERFLOW` | No | 10 | Max overflow connections |
| `DB_POOL_RECYCLE` | No | 3600 | Connection recycle time (seconds) |

---

## Appendix B: Port Reference

| Port | Protocol | Purpose | Firewall |
|------|----------|---------|----------|
| 1812 | UDP | RADIUS Authentication | Allow from NAS only |
| 1813 | UDP | RADIUS Accounting | Allow from NAS only |
| 2083 | TCP | RadSec (RADIUS over TLS) | Allow from NAS only |
| 8000 | TCP | Configuration API | Allow from admin network only |

---

## Changelog

**v2.0.0 (2026-01-13):**
- Initial production deployment guide
- Added validation checklists
- Added troubleshooting section
- Added rollback procedures

---

**Document Version:** 1.0.0  
**Last Updated:** 2026-01-13  
**Maintained By:** FreeRADIUS Addon Team
