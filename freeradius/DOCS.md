# FreeRADIUS Server Add-on Documentation

## Overview

This add-on provides a FreeRADIUS server with RadSec (RADIUS over TLS) support, specifically designed to work with the Meraki WPN Portal for Wi-Fi Personal Network (WPN) deployments.

## Features

- **RadSec Support**: Secure RADIUS over TLS on port 2083
- **Traditional RADIUS**: UDP authentication (1812) and accounting (1813)
- **Database Backends**: SQLite (default) or PostgreSQL
- **Configuration API**: RESTful API for dynamic configuration
- **Certificate Management**: Auto-generated or custom RadSec certificates
- **WPN Integration**: UDN ID assignment via Cisco VSA attributes
- **MAC Authentication**: Support for MAC-based authentication
- **Logging**: Comprehensive authentication and authorization logging

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install "FreeRADIUS Server"
3. Configure the add-on (see Configuration section)
4. Start the add-on
5. Configure the Meraki WPN Portal to use this RADIUS server

## Configuration

### Basic Configuration

```yaml
server_name: "freeradius-server"
max_requests: 16384
max_request_time: 30
radsec_enabled: true
radsec_port: 2083
log_level: "info"
```

### Database Configuration

**SQLite (Default)**:
```yaml
database_type: "sqlite"
database_path: "/config/freeradius.db"
```

**PostgreSQL**:
```yaml
database_type: "postgresql"
database_path: "postgresql://user:pass@host:5432/radius"
```

### API Configuration

```yaml
api_enabled: true
api_port: 8000
api_auth_token: "your-secure-token-here"
```

## Usage with Meraki WPN Portal

1. **Install Both Add-ons**:
   - Install this FreeRADIUS Server add-on
   - Install the Meraki WPN Portal add-on

2. **Configure Portal**:
   - In the WPN Portal admin UI, enable RADIUS
   - Configure RADIUS server: `localhost:2083` (RadSec)
   - Generate RadSec certificates

3. **Configure Meraki Dashboard**:
   - Upload the CA certificate to Meraki Dashboard
   - Configure RADIUS server with your public hostname/IP
   - Set SSID to "Identity PSK with RADIUS"
   - Enable WPN on the SSID

4. **User Registration Flow**:
   - User registers through WPN Portal
   - Portal assigns UDN ID to user's MAC address
   - FreeRADIUS returns UDN ID via Cisco-AVPair
   - Meraki places user in private WPN segment

## Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 1812 | UDP | RADIUS Authentication |
| 1813 | UDP | RADIUS Accounting |
| 2083 | TCP | RadSec (RADIUS over TLS) |
| 8000 | TCP | Configuration API |

## Security

- **RadSec Certificates**: Use auto-generated certificates or upload your own
- **Shared Secrets**: Configure per-client shared secrets
- **TLS Requirements**: TLS 1.2+ with strong cipher suites
- **Key Strength**: RSA 4096-bit keys, SHA-256 signatures
- **No Weak Crypto**: No MD5, SHA-1, DES, 3DES, RC4

## Logs

View logs in Home Assistant:
- Supervisor → FreeRADIUS Server → Logs

Log levels: `debug`, `info`, `warn`, `error`

## API Endpoints

The configuration API (port 8000) provides:

- `GET /health` - Health check
- `GET /api/clients` - List RADIUS clients
- `POST /api/clients` - Add RADIUS client
- `DELETE /api/clients/{id}` - Remove RADIUS client
- `GET /api/users` - List authorized users/MACs
- `POST /api/reload` - Reload configuration

## Troubleshooting

### RADIUS Not Starting

Check logs for errors:
```bash
ha addons logs freeradius-server
```

### RadSec Connection Issues

1. Verify certificates are valid
2. Check Meraki can reach your server on port 2083
3. Verify CA certificate matches server certificate
4. Check firewall rules

### Authentication Failures

1. Check client configuration (shared secret, IP address)
2. Verify user/MAC exists in database
3. Review authentication logs
4. Test with radtest:
   ```bash
   radtest username password localhost 1812 testing123
   ```

### Certificate Errors

Check certificate validity:
```bash
openssl x509 -in /config/certs/server.crt -text -noout
```

## Support

- GitHub Issues: Report bugs and feature requests
- Home Assistant Community: Join the discussion

## License

This add-on is licensed under the MIT License.
