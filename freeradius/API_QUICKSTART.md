# FreeRADIUS Server with Full CRUD API - Quick Start Guide

## 🚀 Overview

This is a complete FreeRADIUS server with a full-featured REST API for managing RADIUS clients and UDN (User Defined Network) assignments. Perfect for Meraki WPN deployments.

## ✨ Features

- ✅ **Full CRUD API** for RADIUS clients and UDN assignments
- ✅ **Swagger UI** at `/docs` for interactive API testing
- ✅ **OpenAPI specification** downloadable at `/openapi.json`
- ✅ **Automatic configuration sync** - Changes reflect in FreeRADIUS within 5 seconds
- ✅ **MAC address normalization** - Accepts any format (AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF)
- ✅ **Auto-assign UDN IDs** - Automatically finds next available ID
- ✅ **Monitoring & Statistics** - View stats, logs, and config files
- ✅ **Security** - Bearer token authentication on all protected endpoints
- ✅ **Database shared with portal** - Single source of truth

## 🏁 Quick Start

### 1. Start the Services

```bash
cd meraki-wpn-portal
docker-compose up --build
```

This starts:
- **MariaDB** on port 3306 (shared database)
- **FreeRADIUS** on ports 1812/udp, 1813/udp, 2083/tcp, 8000/tcp
- **Portal** on port 8080

### 2. Access the API

- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### 3. Authenticate

All API endpoints (except `/health` and `/`) require Bearer token authentication.

**Default Token** (from docker-compose.yml):
```
DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk
```

**In Swagger UI:**
1. Click the 🔒 **Authorize** button at the top
2. Enter: `Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk`
3. Click **Authorize**

**Using curl:**
```bash
curl -H "Authorization: Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk" \
     http://localhost:8000/api/clients
```

## 📚 API Endpoints

### RADIUS Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/clients` | List all clients (with pagination, filtering) |
| GET | `/api/clients/{id}` | Get single client |
| POST | `/api/clients` | Create new client |
| PUT | `/api/clients/{id}` | Update client |
| DELETE | `/api/clients/{id}` | Delete client (soft delete by default) |
| POST | `/api/clients/{id}/test` | Test client with radtest |

### UDN Assignments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/udn-assignments` | List all assignments (with pagination, filtering) |
| GET | `/api/udn-assignments/{id}` | Get single assignment |
| GET | `/api/udn-assignments/by-mac/{mac}` | Lookup by MAC address |
| GET | `/api/udn-assignments/available-udn` | Get next available UDN ID |
| POST | `/api/udn-assignments` | Create new assignment |
| PUT | `/api/udn-assignments/{id}` | Update assignment |
| DELETE | `/api/udn-assignments/{id}` | Delete assignment |

### Monitoring & Statistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Overall statistics |
| GET | `/api/stats/clients` | Client usage statistics |
| GET | `/api/logs/recent` | Recent FreeRADIUS logs |
| GET | `/api/config/files` | View generated config files |
| GET | `/api/config/status` | Configuration status |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reload` | Manually trigger config reload |
| GET | `/health` | Health check (no auth required) |

## 💡 Usage Examples

### Create a RADIUS Client

```bash
curl -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "office-network",
    "ipaddr": "192.168.1.0/24",
    "secret": "SecureRandomSecret123!",
    "nas_type": "meraki",
    "shortname": "office",
    "network_id": "L_123456789",
    "network_name": "Office Network",
    "require_message_authenticator": true
  }'
```

### Create a UDN Assignment (Auto-assign UDN ID)

```bash
curl -X POST http://localhost:8000/api/udn-assignments \
  -H "Authorization: Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk" \
  -H "Content-Type: application/json" \
  -d '{
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "user_name": "John Doe",
    "user_email": "john@example.com",
    "unit": "101",
    "network_id": "L_123456789",
    "ssid_number": 1
  }'
```

### Get Statistics

```bash
curl -X GET http://localhost:8000/api/stats \
  -H "Authorization: Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk"
```

### Download OpenAPI Specification

```bash
curl -o openapi.json http://localhost:8000/openapi.json
```

## 🔍 Monitoring

### Check FreeRADIUS Status

```bash
# Check if radiusd is running
docker exec freeradius-server pgrep radiusd

# View FreeRADIUS logs
docker logs freeradius-server

# View recent RADIUS logs via API
curl -X GET http://localhost:8000/api/logs/recent?lines=50 \
  -H "Authorization: Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk"
```

### View Generated Config Files

```bash
# Via API
curl -X GET http://localhost:8000/api/config/files \
  -H "Authorization: Bearer DesbwRck6Gn8PM85I51Txg77d2yKzS3lkQOPXBSIJsk"

# Direct file access
docker exec freeradius-server cat /config/clients/clients.conf
docker exec freeradius-server cat /etc/raddb/users
```

### Test RADIUS Authentication

```bash
# Test localhost client
docker exec freeradius-server radtest test test localhost 1812 testing123

# Test specific client
docker exec freeradius-server radtest username password <client-ip> 1812 <shared-secret>
```

## 🛠️ Configuration

### Environment Variables

Set in `docker-compose.yml` under the `freeradius` service:

| Variable | Description | Default |
|----------|-------------|---------|
| `API_AUTH_TOKEN` | Bearer token for API authentication | (required) |
| `DATABASE_URL` | Database connection string | `mysql+pymysql://wpn-user:...@mariadb:3306/wpn_radius` |
| `LOG_LEVEL` | Logging level | `info` |
| `API_PORT` | API port | `8000` |
| `RADSEC_ENABLED` | Enable RadSec support | `true` |

### Security Best Practices

1. **Change the API token** in production:
   ```bash
   # Generate a secure token
   openssl rand -base64 32
   ```

2. **Use strong RADIUS secrets** (minimum 16 characters)

3. **Enable TLS** for API access in production

4. **Restrict network access** to RADIUS ports (1812/1813)

## 🧪 Running Tests

```bash
# Run unit tests
docker exec freeradius-server pytest tests/unit/ -v

# Run integration tests
docker exec freeradius-server pytest tests/integration/ -v

# Run all tests with coverage
docker exec freeradius-server pytest tests/ -v --cov=radius_app
```

## 🐛 Troubleshooting

### FreeRADIUS won't start

```bash
# Check logs
docker logs freeradius-server

# Test configuration
docker exec freeradius-server radiusd -C

# Check if config files exist
docker exec freeradius-server ls -la /config/clients/
docker exec freeradius-server ls -la /etc/raddb/users
```

### Database connection issues

```bash
# Check database connectivity
docker exec freeradius-server ping -c 3 mariadb

# Test database connection
docker exec freeradius-server mysql -h mariadb -u wpn-user -p wpn_radius
```

### API not responding

```bash
# Check if API is running
docker exec freeradius-server pgrep -f "radius_app.main"

# Check API logs
docker logs freeradius-server | grep "Configuration API"

# Test API health endpoint (no auth required)
curl http://localhost:8000/health
```

### Configuration not updating

```bash
# Manually trigger reload
curl -X POST http://localhost:8000/api/reload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Check database watcher logs
docker logs freeradius-server | grep "Database watcher"
```

## 📖 Additional Documentation

- **Full Deployment Guide**: See `DEPLOYMENT_GUIDE.md`
- **Database Schema**: See `DATABASE_OPTIONS.md`
- **Phase 1 Fixes**: See `PHASE1_FIXES_COMPLETE.md`
- **Implementation Status**: See `IMPLEMENTATION_COMPLETE.md`

## 🎯 What's Next?

1. **Test the API** - Try creating clients and assignments via Swagger UI
2. **Download OpenAPI spec** - Import into Postman or other API clients
3. **Monitor logs** - Watch the database watcher sync changes to FreeRADIUS
4. **Test authentication** - Use radtest to verify RADIUS is working
5. **Integrate with portal** - The portal can now use the API to manage RADIUS

## 📝 Notes

- **Automatic sync**: Changes via API are automatically synced to FreeRADIUS within 5 seconds
- **Shared database**: The FreeRADIUS API and Meraki WPN Portal share the same database
- **Soft deletes**: By default, DELETE operations set `is_active=False` instead of permanent deletion
- **MAC normalization**: MAC addresses are automatically normalized to lowercase with colons
- **UDN auto-assign**: If you don't provide a UDN ID, the system finds the next available one

---

**Built with ❤️ using FastAPI, SQLAlchemy, and FreeRADIUS**
