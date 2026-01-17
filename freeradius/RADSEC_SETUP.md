# RadSec Setup Guide

## Overview

RadSec (RADIUS over TLS) provides secure, encrypted RADIUS transport using TLS 1.2/1.3. This guide covers certificate generation, RadSec configuration, and client setup.

## Table of Contents

1. [What is RadSec?](#what-is-radsec)
2. [Benefits](#benefits)
3. [Requirements](#requirements)
4. [Quick Start](#quick-start)
5. [Certificate Management](#certificate-management)
6. [RadSec Server Configuration](#radsec-server-configuration)
7. [RadSec Client Setup](#radsec-client-setup)
8. [Security Best Practices](#security-best-practices)
9. [Troubleshooting](#troubleshooting)
10. [Examples](#examples)

---

## What is RadSec?

**RadSec** is RADIUS over TLS - a secure transport protocol that encrypts RADIUS traffic using TLS. Unlike traditional RADIUS (which uses shared secrets and UDP), RadSec provides:

- **Strong Encryption**: TLS 1.2/1.3 with modern cipher suites
- **Certificate-Based Authentication**: Mutual TLS (mTLS) for client verification
- **TCP Transport**: Reliable delivery over TCP (not UDP)
- **Standard Port**: 2083 (IANA registered)

---

## Benefits

### Security
- ✅ End-to-end encryption
- ✅ Protection against replay attacks
- ✅ Certificate-based mutual authentication
- ✅ No shared secret transmission

### Reliability
- ✅ TCP provides reliable delivery
- ✅ Connection-oriented protocol
- ✅ Built-in error detection

### Compliance
- ✅ Meets modern security standards
- ✅ Suitable for PCI-DSS environments
- ✅ Supports compliance auditing

---

## Requirements

### Server Requirements
- FreeRADIUS 3.0.20+ with TLS support
- OpenSSL 1.1.1+ or compatible TLS library
- Valid TLS certificates (CA, server, optionally client)

### Client Requirements
- RadSec-capable NAS or proxy
- Client certificate (if mutual TLS required)
- Network connectivity on port 2083

### API Requirements
- Python 3.9+
- `cryptography` library (for certificate operations)

---

## Quick Start

### 1. Generate Certificates

```bash
curl -X POST http://localhost:8000/api/radsec/certificates/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "common_name": "radius.example.com",
    "organization": "My Company",
    "country": "US",
    "validity_days": 397,
    "key_size": 4096
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Certificate generated successfully",
  "certificate_path": "/etc/raddb/certs/server.pem",
  "key_path": "/etc/raddb/certs/server-key.pem",
  "certificate_info": {
    "subject": "CN=radius.example.com, O=My Company, C=US",
    "valid_until": "2027-02-15T12:00:00Z",
    "fingerprint_sha256": "aa:bb:cc:...",
    "key_size": 4096
  }
}
```

### 2. Create RadSec Configuration

```bash
curl -X POST http://localhost:8000/api/radsec/configs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "primary-radsec",
    "description": "Primary RadSec listener",
    "listen_address": "0.0.0.0",
    "listen_port": 2083,
    "certificate_file": "/etc/raddb/certs/server.pem",
    "private_key_file": "/etc/raddb/certs/server-key.pem",
    "ca_certificate_file": "/etc/raddb/certs/ca.pem",
    "require_client_cert": true,
    "verify_client_cert": true,
    "is_active": true
  }'
```

### 3. Restart FreeRADIUS

The database watcher will automatically regenerate RadSec configuration and reload FreeRADIUS within 5 seconds.

---

## Certificate Management

### Certificate Hierarchy

```
CA Certificate (ca.pem)
├── Server Certificate (server.pem)
│   └── Server Private Key (server-key.pem)
└── Client Certificates (optional)
    └── Client Private Keys
```

### Generating Certificates

#### Auto-Generation (Recommended)

The API handles certificate generation automatically:

```http
POST /api/radsec/certificates/generate
Authorization: Bearer YOUR_TOKEN

{
  "common_name": "radius.example.com",
  "organization": "My Company",
  "country": "US",
  "validity_days": 397,  // Max 825 days
  "key_size": 4096       // 2048 or 4096
}
```

This generates:
1. **CA Certificate** (if not exists): `/etc/raddb/certs/ca.pem`
2. **Server Certificate**: `/etc/raddb/certs/server.pem`
3. **Server Key**: `/etc/raddb/certs/server-key.pem`

#### Security Compliance

All generated certificates comply with security best practices:
- ✅ RSA keys: 2048 bits minimum (4096 recommended)
- ✅ Signature: SHA-256 or stronger (no MD5/SHA-1)
- ✅ Validity: Maximum 825 days (Apple/Chrome requirement)
- ✅ TLS: Compatible with TLS 1.2 and 1.3

### Certificate Verification

#### List All Certificates

```http
GET /api/radsec/certificates
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "certificates": [
    {
      "file_name": "ca.pem",
      "subject": "CN=My Company CA",
      "valid_until": "2036-01-14T12:00:00Z",
      "is_expired": false,
      "days_until_expiry": 3650,
      "key_size": 4096,
      "warnings": []
    },
    {
      "file_name": "server.pem",
      "subject": "CN=radius.example.com",
      "valid_until": "2027-02-15T12:00:00Z",
      "is_expired": false,
      "days_until_expiry": 397,
      "key_size": 4096,
      "warnings": []
    }
  ]
}
```

#### Verify Certificate Chain

```http
GET /api/radsec/certificates/verify?certificate_path=/etc/raddb/certs/server.pem&ca_path=/etc/raddb/certs/ca.pem
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "certificate_info": {
    "subject": "CN=radius.example.com",
    "issuer": "CN=My Company CA",
    "valid_until": "2027-02-15T12:00:00Z",
    "is_expired": false
  },
  "chain_valid": true,
  "chain_error": null
}
```

### Certificate Warnings

The API automatically detects security issues:

#### Weak Keys
```json
{
  "warnings": ["WEAK KEY: RSA key size 1024 bits is insufficient (minimum 2048)"]
}
```

#### Insecure Signatures
```json
{
  "warnings": ["INSECURE SIGNATURE: sha1WithRSAEncryption is cryptographically weak"]
}
```

#### Expiring Soon
```json
{
  "warnings": ["EXPIRING SOON: Certificate expires in 25 days"]
}
```

#### Expired
```json
{
  "warnings": ["EXPIRED: Certificate expired on 2025-12-01T12:00:00Z"]
}
```

---

## RadSec Server Configuration

### Create Configuration

```http
POST /api/radsec/configs
Authorization: Bearer YOUR_TOKEN

{
  "name": "main-radsec",
  "description": "Primary RadSec listener for enterprise",
  "listen_address": "0.0.0.0",
  "listen_port": 2083,
  
  // TLS Settings
  "tls_min_version": "1.2",
  "tls_max_version": "1.3",
  "cipher_list": "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384",
  
  // Certificates
  "certificate_file": "/etc/raddb/certs/server.pem",
  "private_key_file": "/etc/raddb/certs/server-key.pem",
  "ca_certificate_file": "/etc/raddb/certs/ca.pem",
  
  // Client Validation
  "require_client_cert": true,
  "verify_client_cert": true,
  "verify_depth": 2,
  
  // Connection Limits
  "max_connections": 100,
  "connection_timeout": 30,
  
  "is_active": true
}
```

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `listen_address` | `0.0.0.0` | Bind address (0.0.0.0 = all interfaces) |
| `listen_port` | `2083` | TCP port (IANA standard) |
| `tls_min_version` | `1.2` | Minimum TLS version |
| `tls_max_version` | `1.3` | Maximum TLS version |
| `cipher_list` | Modern ciphers | Allowed cipher suites |
| `require_client_cert` | `true` | Require client certificate |
| `verify_client_cert` | `true` | Verify client cert validity |
| `verify_depth` | `2` | Certificate chain depth |
| `max_connections` | `100` | Maximum concurrent connections |
| `connection_timeout` | `30` | Connection timeout (seconds) |

### TLS Configuration

#### Recommended Cipher Suites

```
ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256
```

**Security:**
- ✅ Forward secrecy (ECDHE)
- ✅ Authenticated encryption (GCM)
- ✅ Strong key exchange
- ❌ No MD5, SHA-1, DES, RC4

#### TLS Versions

- **TLS 1.3** (Recommended): Best security, fastest handshake
- **TLS 1.2** (Supported): Widely compatible
- **TLS 1.1/1.0** (Blocked): Insecure, not allowed

### Certificate Revocation

#### CRL (Certificate Revocation List)

```json
{
  "check_crl": true,
  "crl_file": "/etc/raddb/certs/crl.pem"
}
```

#### OCSP (Online Certificate Status Protocol)

```json
{
  "ocsp_enable": true,
  "ocsp_url": "http://ocsp.example.com"
}
```

### List Configurations

```http
GET /api/radsec/configs?page=1&is_active=true
```

### Update Configuration

```http
PUT /api/radsec/configs/{id}
Authorization: Bearer YOUR_TOKEN

{
  "max_connections": 200,
  "connection_timeout": 60
}
```

---

## RadSec Client Setup

### Register Client Certificate

```http
POST /api/radsec/clients
Authorization: Bearer YOUR_TOKEN

{
  "name": "office-proxy",
  "description": "Office location RADIUS proxy",
  "certificate_subject": "CN=office-proxy.example.com",
  "certificate_fingerprint": "aa:bb:cc:dd:ee:ff:...",
  "radius_client_id": 1,  // Optional link to RADIUS client
  "is_active": true
}
```

### Client Certificate Requirements

Clients must present certificates that:
1. Are signed by the trusted CA
2. Are not expired
3. Match the subject pattern (if specified)
4. Have valid fingerprint (if fingerprint pinning enabled)

### Example Client Configuration (FreeRADIUS)

```conf
# radiusd.conf on client/proxy
home_server radsec {
    type = auth+acct
    ipaddr = radius-server.example.com
    port = 2083
    proto = tls
    
    tls {
        certificate_file = /etc/raddb/certs/client.pem
        private_key_file = /etc/raddb/certs/client-key.pem
        ca_file = /etc/raddb/certs/ca.pem
        
        tls_min_version = "1.2"
        tls_max_version = "1.3"
    }
}
```

---

## Security Best Practices

### 1. Certificate Security

✅ **DO:**
- Use 4096-bit RSA keys
- Limit validity to 397 days (Apple/Chrome compliance)
- Use SHA-256 or stronger signatures
- Store private keys with 0600 permissions
- Rotate certificates before expiry

❌ **DON'T:**
- Use keys < 2048 bits
- Use MD5 or SHA-1 signatures
- Set validity > 825 days
- Share private keys
- Ignore expiry warnings

### 2. TLS Configuration

✅ **DO:**
- Require TLS 1.2 minimum
- Use modern cipher suites
- Enable client certificate verification
- Set reasonable connection limits

❌ **DON'T:**
- Allow TLS 1.0/1.1
- Use weak ciphers (RC4, DES, 3DES)
- Disable certificate validation
- Allow unlimited connections

### 3. Monitoring

✅ **Monitor:**
- Certificate expiry dates
- Connection counts
- Authentication failures
- TLS errors

✅ **Alert on:**
- Certificates expiring < 30 days
- Weak key detection
- Failed client authentication
- Connection limit reached

### 4. Access Control

✅ **Implement:**
- Firewall rules (allow only port 2083)
- Client certificate allowlist
- IP-based restrictions (if needed)
- Rate limiting

---

## Troubleshooting

### Connection Refused

**Problem:** Cannot connect to RadSec port

**Solutions:**
1. Check if RadSec listener is configured and active
2. Verify firewall allows port 2083
3. Check `listen_address` (0.0.0.0 vs specific IP)
4. Verify FreeRADIUS is running
5. Check logs: `/var/log/radius/radius.log`

### Certificate Verification Failed

**Problem:** Client certificate rejected

**Solutions:**
1. Verify client cert is signed by trusted CA
2. Check certificate is not expired
3. Verify certificate subject matches
4. Check CA certificate is correct
5. Verify certificate chain: `openssl verify -CAfile ca.pem client.pem`

### TLS Handshake Failed

**Problem:** TLS negotiation fails

**Solutions:**
1. Check TLS version compatibility
2. Verify cipher suites match
3. Ensure certificates are valid
4. Check certificate file permissions
5. Review TLS logs in FreeRADIUS

### Weak Key Warning

**Problem:** API reports weak key

**Solution:**
```bash
# Regenerate with stronger key
curl -X POST http://localhost:8000/api/radsec/certificates/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"common_name": "radius.example.com", "key_size": 4096}'
```

### Certificate Expired

**Problem:** Certificate expired

**Solution:**
1. Generate new certificate
2. Update RadSec configuration with new cert paths
3. Distribute new CA/client certs if needed
4. Restart FreeRADIUS

---

## Examples

### Example 1: Basic RadSec Setup

```bash
# 1. Generate certificates
curl -X POST http://localhost:8000/api/radsec/certificates/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"common_name": "radius.local", "key_size": 4096}'

# 2. Create RadSec config
curl -X POST http://localhost:8000/api/radsec/configs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "basic-radsec",
    "certificate_file": "/etc/raddb/certs/server.pem",
    "private_key_file": "/etc/raddb/certs/server-key.pem",
    "ca_certificate_file": "/etc/raddb/certs/ca.pem",
    "require_client_cert": false
  }'

# 3. Verify
curl http://localhost:8000/api/radsec/configs
```

### Example 2: Enterprise RadSec with Client Certs

```bash
# 1. Generate server certs
curl -X POST http://localhost:8000/api/radsec/certificates/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "common_name": "radius.company.com",
    "organization": "Company Inc",
    "validity_days": 397,
    "key_size": 4096
  }'

# 2. Create secure RadSec config
curl -X POST http://localhost:8000/api/radsec/configs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "enterprise-radsec",
    "description": "Production RadSec with mutual TLS",
    "listen_address": "0.0.0.0",
    "listen_port": 2083,
    "tls_min_version": "1.2",
    "tls_max_version": "1.3",
    "certificate_file": "/etc/raddb/certs/server.pem",
    "private_key_file": "/etc/raddb/certs/server-key.pem",
    "ca_certificate_file": "/etc/raddb/certs/ca.pem",
    "require_client_cert": true,
    "verify_client_cert": true,
    "verify_depth": 2,
    "max_connections": 100,
    "is_active": true
  }'

# 3. Register client
curl -X POST http://localhost:8000/api/radsec/clients \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "branch-office-proxy",
    "certificate_subject": "CN=branch-proxy.company.com",
    "is_active": true
  }'
```

### Example 3: Monitor Certificate Expiry

```bash
# List all certificates
curl http://localhost:8000/api/radsec/certificates \
  -H "Authorization: Bearer $TOKEN" | jq '.certificates[] | {file_name, days_until_expiry, warnings}'

# Output:
# {
#   "file_name": "server.pem",
#   "days_until_expiry": 365,
#   "warnings": []
# }
```

---

## API Reference

### Certificates

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/radsec/certificates` | List all certificates |
| POST | `/api/radsec/certificates/generate` | Generate new certificates |
| GET | `/api/radsec/certificates/verify` | Verify certificate chain |

### Configurations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/radsec/configs` | List RadSec configurations |
| GET | `/api/radsec/configs/{id}` | Get configuration details |
| POST | `/api/radsec/configs` | Create configuration |
| PUT | `/api/radsec/configs/{id}` | Update configuration |
| DELETE | `/api/radsec/configs/{id}` | Delete configuration |

### Clients

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/radsec/clients` | List RadSec clients |
| POST | `/api/radsec/clients` | Register client |
| PUT | `/api/radsec/clients/{id}` | Update client |
| DELETE | `/api/radsec/clients/{id}` | Remove client |

---

## Next Steps

- Review [Policy Guide](POLICY_GUIDE.md)
- Explore [Enterprise Features](ENTERPRISE_FEATURES.md)
- Read [API Documentation](http://localhost:8000/docs)
