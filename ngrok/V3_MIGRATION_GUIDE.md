# ngrok v3 Migration Guide

This add-on now uses **ngrok v3** with the official Docker image. This guide explains the new features, changes, and how to migrate your configuration.

## What's New in v3

### 🚀 Key Improvements

1. **Official Docker Image**: Uses `ngrok/ngrok:latest` for automatic updates
2. **Enhanced Configuration**: New `version: 3` config format with more features
3. **Traffic Policy Engine**: Modern, flexible traffic management
4. **Better Authentication**: OAuth, OIDC, and mutual TLS support
5. **Hostname Support**: Full support for `hostname:port` addresses (e.g., `core-mariadb:3306`)

### 📋 New Configuration Options

#### Authentication & Security
- **OAuth Providers**: Google, GitHub, Microsoft, Facebook, GitLab, LinkedIn, Bitbucket, Amazon
- **OIDC**: Custom OpenID Connect providers
- **Mutual TLS**: Client certificate authentication
- **Circuit Breaker**: Automatic endpoint disabling on high error rates

#### Performance & Features
- **Compression**: Built-in gzip compression
- **WebSocket TCP Converter**: Convert WebSocket to TCP
- **Traffic Policy**: Inline policy configuration
- **Labeled Tunnels**: For service meshes and edge configurations

## Configuration Changes

### v2 vs v3 Format

**Old (v2):**
```yaml
tunnels:
  - name: hass
    proto: http
    addr: 8123
    auth: user:password
    subdomain: my-home
```

**New (v3 - What the add-on generates):**
```yaml
version: 3
endpoints:
  - name: hass
    upstream:
      url: http://172.30.32.1:8123
    url: https://my-home.ngrok.app
    traffic_policy:
      on_http_request:
        - actions:
            - type: basic-auth
              config:
                credentials:
                  - user:password
```

**Your Config (Still uses familiar format):**
```json
{
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "auth": "user:password",
      "hostname": "my-home.ngrok.app"
    }
  ]
}
```

The add-on automatically converts your familiar configuration to v3 format!

## New Options Reference

### Core Options (Required)

| Option   | Type   | Description                                                    |
| -------- | ------ | -------------------------------------------------------------- |
| `name`   | string | Unique tunnel name (a-z, 0-9, -, _)                           |
| `proto`  | string | Protocol: `http`, `https`, `tls`, `tcp`, `labeled`            |
| `addr`   | string | Port, IP:port, or **hostname:port** (e.g., `core-mariadb:3306`) |

### URL Options

| Option     | Type   | Description                                              |
| ---------- | ------ | -------------------------------------------------------- |
| `hostname` | string | Custom domain (requires reservation)                     |
| `domain`   | string | Alternative to hostname                                  |
| `schemes`  | array  | `["http"]`, `["https"]`, or `["http", "https"]`         |

### Authentication Options

#### Basic Auth
```json
{
  "auth": "username:password"
}
```

#### OAuth
```json
{
  "oauth_provider": "google",
  "oauth_allow_domains": ["example.com"],
  "oauth_allow_emails": ["user@example.com"],
  "oauth_scopes": ["openid", "email", "profile"]
}
```

#### OIDC
```json
{
  "oidc_issuer_url": "https://auth.example.com",
  "oidc_client_id": "your-client-id",
  "oidc_client_secret": "your-client-secret",
  "oidc_scopes": ["openid", "email"]
}
```

#### Mutual TLS
```json
{
  "mutual_tls_cas": "/ssl/client-ca.pem"
}
```

### Performance Options

| Option                      | Type    | Default | Description                               |
| --------------------------- | ------- | ------- | ----------------------------------------- |
| `compression`               | boolean | false   | Enable gzip compression                   |
| `websocket_tcp_converter`   | boolean | false   | Convert WebSocket to TCP                  |
| `circuit_breaker`           | float   | null    | Error threshold (0.0-1.0) to disable      |
| `verify_upstream_tls`       | boolean | true    | Verify upstream TLS certificates          |

### TLS Options

| Option            | Type   | Description                                    |
| ----------------- | ------ | ---------------------------------------------- |
| `bind_tls`        | mixed  | `true` (HTTPS only), `false` (HTTP), `"both"`  |
| `crt`             | string | Path to TLS certificate                        |
| `key`             | string | Path to TLS private key                        |
| `client_cas`      | string | Path to client CA certificates                 |

### TCP Options

| Option         | Type   | Description                                |
| -------------- | ------ | ------------------------------------------ |
| `remote_addr`  | string | Request specific TCP address (reserved)    |
| `proxy_proto`  | string | PROXY protocol: `"1"`, `"2"`, or `""`     |

### Advanced Options

| Option         | Type   | Description                                    |
| -------------- | ------ | ---------------------------------------------- |
| `metadata`     | string | Arbitrary metadata for API                     |
| `labels`       | array  | Labels for labeled tunnels                     |
| `policy`       | string | Inline Traffic Policy (JSON/YAML)              |
| `host_header`  | string | Rewrite Host header or `"preserve"`            |

## Migration Examples

### Example 1: Simple HTTP with Auth

**Before (v2 style - still works!):**
```json
{
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "auth": "admin:secretpass",
      "hostname": "home.example.com"
    }
  ]
}
```

**What happens in v3:**
- Auth becomes Traffic Policy with basic-auth action
- hostname becomes the URL
- addr becomes upstream.url

### Example 2: Database Tunnel (NEW!)

```json
{
  "tunnels": [
    {
      "name": "db",
      "proto": "tcp",
      "addr": "core-mariadb:3306",
      "inspect": false
    }
  ]
}
```

Now supports hostnames directly!

### Example 3: OAuth Protection

```json
{
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "oauth_provider": "google",
      "oauth_allow_domains": ["yourdomain.com"],
      "hostname": "home.example.com"
    }
  ]
}
```

Only allows Google accounts from your domain!

### Example 4: Multiple Schemes

```json
{
  "tunnels": [
    {
      "name": "web",
      "proto": "http",
      "addr": 80,
      "schemes": ["http", "https"],
      "hostname": "site.example.com"
    }
  ]
}
```

### Example 5: Let's Encrypt Challenge

```json
{
  "tunnels": [
    {
      "name": "lets_encrypt",
      "proto": "http",
      "addr": 80,
      "schemes": ["http"],
      "hostname": "ha.example.com"
    },
    {
      "name": "home",
      "proto": "http",
      "addr": 8123,
      "schemes": ["https"],
      "hostname": "ha.example.com"
    }
  ]
}
```

## Breaking Changes

### Required auth_token

In v3, `auth_token` is **required** for all tunnel types. Get yours at: https://dashboard.ngrok.com/get-started/your-authtoken

### Deprecated Options

| Option      | Status      | Use Instead      |
| ----------- | ----------- | ---------------- |
| `subdomain` | Deprecated  | `hostname`       |

### Changed Behavior

1. **inspect**: Now defaults to `true` (was `false`)
2. **schemes**: Must be lowercase in arrays
3. **bind_tls**: Now accepts `true`, `false`, or `"both"` (string)

## Troubleshooting

### Error: "auth_token is required"

**Solution**: Add your auth token from https://dashboard.ngrok.com/get-started/your-authtoken

```json
{
  "auth_token": "your-token-here",
  "tunnels": [...]
}
```

### Error: "invalid upstream URL"

**Solution**: Check your `addr` format. Valid formats:
- Port: `8123`
- IP:port: `192.168.1.100:8123`
- Hostname:port: `core-mariadb:3306`

### Warning: "subdomain is deprecated"

**Solution**: Change `subdomain` to `hostname`:

```json
// Old
{ "subdomain": "my-home" }

// New
{ "hostname": "my-home.ngrok.app" }
```

## Resources

- [ngrok v3 Documentation](https://ngrok.com/docs)
- [ngrok Docker Guide](https://ngrok.com/docs/using-ngrok-with/docker)
- [Traffic Policy Reference](https://ngrok.com/docs/traffic-policy)
- [ngrok Dashboard](https://dashboard.ngrok.com)

## Support

For issues specific to this Home Assistant add-on, please file an issue on GitHub.

For ngrok-specific questions, see the [ngrok documentation](https://ngrok.com/docs) or [ngrok support](https://ngrok.com/support).
