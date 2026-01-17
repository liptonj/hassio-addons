# Certificate Management for FreeRADIUS

This document describes the certificate management options for FreeRADIUS, including recommendations for EAP authentication and RadSec transport.

## Port Configuration & Security

**Important Security Note:** The FreeRADIUS API and Let's Encrypt use separate ports:

| Port | Service | Default Exposure | Purpose |
|------|---------|------------------|---------|
| 8000 | Configuration API | localhost only | Internal management |
| 80 | Let's Encrypt HTTP | Not exposed | ACME HTTP-01 challenge |
| 1812 | RADIUS Auth | Exposed | Authentication |
| 1813 | RADIUS Acct | Exposed | Accounting |
| 2083 | RadSec | Exposed | Secure RADIUS |
| 3799 | CoA/DM | Exposed | Session control |

The **API is bound to localhost (127.0.0.1) by default** for security. Access it via:
- Home Assistant Ingress
- Local network only
- Set `api_host: "0.0.0.0"` to expose externally (requires `api_auth_token`)

## Overview

FreeRADIUS uses TLS certificates in two main contexts:

1. **EAP Authentication** (EAP-TLS, PEAP, TTLS) - Authenticating users via TLS
2. **RadSec Transport** - RADIUS over TLS for secure communication between servers

Each context has different certificate requirements and recommendations.

## Certificate Options

### Self-Signed CA (Recommended for EAP)

For EAP authentication, **self-signed certificates with your own CA are strongly recommended**.

**Why self-signed for EAP?**
- Clients MUST trust the CA certificate
- You control the entire certificate chain
- No dependency on external CAs
- Certificates can have longer validity periods
- No renewal disruption to clients

**How it works:**
1. Generate a CA certificate (10 year validity)
2. Generate server certificate signed by your CA
3. Distribute CA certificate to all EAP clients
4. Clients configure their supplicants to trust your CA

**API Endpoint:**
```bash
POST /api/radsec/certificates/eap/generate
?common_name=radius.example.com
&organization=MyCompany
&country=US
&key_size=4096
```

**Certificate Location:**
- CA: `/config/certs/eap/ca.pem`
- Server: `/config/certs/eap/server.pem`
- Server Key: `/config/certs/eap/server-key.pem`
- DH Params: `/config/certs/eap/dh`

### Let's Encrypt (Recommended for RadSec)

For RadSec transport, **Let's Encrypt certificates are a good option** when connecting to external systems that trust public CAs.

**Why Let's Encrypt for RadSec?**
- Uses standard TLS trust chain
- Clients don't need to install additional CA certificates
- Automatic certificate issuance
- Widely trusted

**Limitations:**
- Certificates expire every 90 days (auto-renewal recommended)
- Not suitable for EAP (clients would need to update CA regularly)
- Requires publicly resolvable domain name

**Prerequisites:**
1. Let's Encrypt certificates must be configured (e.g., via Home Assistant SSL add-on)
2. SSL directory must be mapped to the add-on (already configured: `ssl:ro`)
3. Domain must be publicly accessible for certificate issuance

**Two Options for Let's Encrypt:**

**Option 1: Use Home Assistant Let's Encrypt Addon (Recommended)**
- Install the HA Let's Encrypt addon
- It manages certificate renewal automatically
- Certs are stored in `/ssl`
- Our addon reads from `/ssl` - no port 80 needed

**Option 2: Cloudflare DNS-01 Challenge (Recommended if you use Cloudflare)**

This uses Cloudflare DNS for domain validation - **no port 80 needed**.

The WPN Portal already has Cloudflare configured? Great! The RADIUS addon can use those credentials.

**From the Portal (Automatic Flow):**

The portal can provision everything for you in one step:

```bash
# From the Portal - configures DNS and triggers certificate provisioning
POST /api/admin/radius/configure-hostname
?hostname=radius.example.com
&ip_address=1.2.3.4
&create_dns=true
&obtain_certificate=true
&cert_email=admin@example.com
```

This will:
1. Create DNS A record: `radius.example.com -> 1.2.3.4`
2. Save RADIUS hostname to settings
3. Sync Cloudflare credentials to RADIUS addon
4. Trigger Let's Encrypt certificate via DNS-01

**Manual Flow (Direct to RADIUS API):**

```bash
# 1. Sync Cloudflare config from portal
POST /api/cloudflare/sync
{
  "portal_api_url": "http://portal:8080/api",
  "portal_token": "your-portal-admin-token"
}

# 2. Create DNS record for RADIUS server
POST /api/cloudflare/dns/create
{
  "hostname": "radius.example.com",
  "ip_address": "1.2.3.4",
  "proxied": false
}

# 3. Obtain certificate via DNS-01
POST /api/cloudflare/certificates/obtain
{
  "domain": "radius.example.com",
  "email": "admin@example.com",
  "staging": false
}
```

**Benefits of Cloudflare DNS-01:**
- ✅ No port 80 exposure required
- ✅ Reuses portal's existing Cloudflare credentials (unmasked via `/api/admin/radius/cloudflare-credentials`)
- ✅ Automatic DNS record management
- ✅ Works behind NAT/firewalls
- ✅ Works with any hosting setup
- ✅ Portal and RADIUS share one Cloudflare configuration

**Certificate Renewal:**

```bash
POST /api/cloudflare/certificates/renew
```

Run this periodically (e.g., weekly cron) or set up a renewal timer.

**Option 3: Standalone Certbot HTTP-01 (Legacy)**
```yaml
# config.yaml
letsencrypt_standalone: true
letsencrypt_domain: "radius.example.com"
letsencrypt_email: "admin@example.com"
letsencrypt_http_port: 80
```
- Requires port 80 to be forwarded to the addon
- NOT recommended - use DNS-01 instead

**API Endpoint:**
```bash
POST /api/radsec/certificates/letsencrypt/setup
?domain=radius.example.com
&copy=true
```

**Check Let's Encrypt Status:**
```bash
GET /api/radsec/certificates/letsencrypt/status
```

**Certificate Location (after import):**
- Server: `/config/certs/radsec/radsec-server.pem`
- Server Key: `/config/certs/radsec/radsec-server-key.pem`
- CA Chain: `/config/certs/radsec/radsec-ca.pem`

### Self-Signed for RadSec

If you don't have Let's Encrypt or prefer to use your own CA for RadSec:

```bash
POST /api/radsec/certificates/radsec/generate
?common_name=radius.example.com
&organization=MyCompany
```

**Note:** Connecting systems will need to trust your CA certificate.

## Certificate Usage Recommendations

| Use Case | Recommended Certificate | Why |
|----------|------------------------|-----|
| EAP-TLS | Self-signed CA | Clients must trust CA anyway |
| PEAP | Self-signed CA | Clients must trust CA anyway |
| EAP-TTLS | Self-signed CA | Clients must trust CA anyway |
| RadSec (Meraki) | Let's Encrypt | Standard TLS trust works |
| RadSec (Internal) | Self-signed or LE | Depends on trust requirements |
| API Server (HTTPS) | Let's Encrypt | Browser compatibility |

## FreeRADIUS Certificate References

Per [FreeRADIUS documentation](https://www.freeradius.org/documentation/freeradius-server/4.0.0/reference/raddb/certs/index.html):

> In general, you should use self-signed certificates for 802.1x (EAP) authentication. When you list root CAs from other organisations in the `ca_file`, you permit them to masquerade as you, to authenticate your users, and to issue client certificates for EAP-TLS.

### EAP Certificate Troubleshooting

Common issues ([per FreeRADIUS docs](https://www.freeradius.org/documentation/freeradius-server/4.0.0/trouble-shooting/eap_certificates.html)):

1. **Windows clients**: Require Microsoft XP Extensions in the certificate
2. **Certificate validation loop**: Client starts EAP, gets challenges, then restarts
   - Usually means certificate is missing required OIDs
   - Check that CA is installed on client
3. **Windows XP SP2**: Has issues with intermediate certificates
4. **Windows CE**: Cannot handle 4K RSA certificates
5. **Certificate chains > 64KB**: Will likely fail (too many round trips)

### Let's Encrypt for RADIUS

Per [FreeRADIUS Let's Encrypt howto](https://www.freeradius.org/documentation/freeradius-server/4.0.0/howto/os/letsencrypt.html):

**Can be used for:**
- RadSec (RADIUS over TLS)
- Status-Server over TLS
- API endpoints (HTTPS)

**Should NOT be used for:**
- EAP-TLS, PEAP, TTLS authentication
  - Clients must trust the CA certificate
  - 90-day expiry would require frequent client reconfiguration
  - Let's Encrypt root rotation could break authentication

## API Reference

### Get Certificate Status
```bash
GET /api/radsec/certificates/status
```

Returns status of all certificate types (EAP, RadSec, Let's Encrypt).

### List All Certificates
```bash
GET /api/radsec/certificates
```

Returns all certificates with expiry information and warnings.

### Generate EAP Certificates
```bash
POST /api/radsec/certificates/eap/generate
?common_name=<FQDN>
&organization=<org>
&country=<CC>
&key_size=<2048-8192>
```

### Setup Let's Encrypt for RadSec
```bash
POST /api/radsec/certificates/letsencrypt/setup
?domain=<domain>
&copy=<true|false>
```

### Generate Self-Signed RadSec Certificates
```bash
POST /api/radsec/certificates/radsec/generate
?common_name=<FQDN>
&organization=<org>
```

### Verify Certificate
```bash
GET /api/radsec/certificates/verify
?certificate_path=<path>
&ca_path=<optional_ca_path>
```

## File Permissions

All certificates should have appropriate permissions:

| File Type | Permissions | Owner |
|-----------|-------------|-------|
| CA Certificate | 644 | root |
| Server Certificate | 644 | root |
| Private Keys | 600 | root |
| DH Parameters | 644 | root |

## Security Considerations

1. **Key Size**: Minimum 2048-bit RSA, recommend 4096-bit
2. **Signature Algorithm**: Use SHA-256 or stronger (never MD5 or SHA-1)
3. **Validity Period**: 
   - CA: Up to 10 years
   - Server: Max 397 days (for browser compatibility) or 825 days
4. **Private Key Storage**: Never expose private keys; use 600 permissions
5. **Certificate Renewal**: Monitor expiry; renew before expiration
