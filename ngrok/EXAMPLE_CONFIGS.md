# ngrok Add-on Example Configurations

This document provides real-world configuration examples for the ngrok Home Assistant add-on.

## Basic Configurations

### Simple HTTP Tunnel

Expose Home Assistant on a secure HTTPS URL:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "schemes": ["https"]
    }
  ]
}
```

### HTTP with Custom Domain

Use your own reserved domain:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "home",
      "proto": "http",
      "addr": 8123,
      "hostname": "home.yourdomain.com",
      "schemes": ["https"]
    }
  ]
}
```

## TCP Tunnels

### Database Tunnel (MariaDB)

Expose your Home Assistant database to external tools:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "mariadb",
      "proto": "tcp",
      "addr": "core-mariadb:3306",
      "inspect": false
    }
  ]
}
```

### SSH Tunnel

Expose SSH for remote access:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "ssh",
      "proto": "tcp",
      "addr": 22,
      "inspect": false
    }
  ]
}
```

### MQTT Tunnel

Expose MQTT broker externally:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "mqtt",
      "proto": "tcp",
      "addr": "core-mosquitto:1883",
      "inspect": false
    }
  ]
}
```

## Authentication Examples

### Basic Authentication

Protect your Home Assistant with username/password:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "auth": "admin:supersecretpassword",
      "schemes": ["https"]
    }
  ]
}
```

### Google OAuth

Only allow specific Google accounts:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "oauth_provider": "google",
      "oauth_allow_emails": [
        "you@gmail.com",
        "spouse@gmail.com"
      ],
      "schemes": ["https"]
    }
  ]
}
```

### OAuth with Domain Whitelist

Allow any user from your organization:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "oauth_provider": "google",
      "oauth_allow_domains": ["yourcompany.com"],
      "schemes": ["https"]
    }
  ]
}
```

### GitHub OAuth

Authenticate with GitHub:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "oauth_provider": "github",
      "oauth_allow_emails": ["your-github-email@example.com"],
      "schemes": ["https"]
    }
  ]
}
```

## Multi-Tunnel Configurations

### Let's Encrypt with Home Assistant

Run both HTTP (for Let's Encrypt challenges) and HTTPS:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "letsencrypt",
      "proto": "http",
      "addr": 80,
      "hostname": "home.yourdomain.com",
      "schemes": ["http"]
    },
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "hostname": "home.yourdomain.com",
      "schemes": ["https"]
    }
  ]
}
```

### Complete Stack Exposure

Expose multiple services:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "hostname": "home.yourdomain.com",
      "schemes": ["https"]
    },
    {
      "name": "db",
      "proto": "tcp",
      "addr": "core-mariadb:3306",
      "inspect": false
    },
    {
      "name": "mqtt",
      "proto": "tcp",
      "addr": "core-mosquitto:1883",
      "inspect": false
    }
  ]
}
```

## Advanced Configurations

### With Compression

Enable gzip compression for better performance:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "compression": true,
      "schemes": ["https"]
    }
  ]
}
```

### Circuit Breaker

Auto-disable endpoint if error rate exceeds 50%:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "circuit_breaker": 0.5,
      "schemes": ["https"]
    }
  ]
}
```

### With Metadata

Add custom metadata for tracking:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "metadata": "Home Assistant Production Instance",
      "schemes": ["https"]
    }
  ]
}
```

### TCP with PROXY Protocol

Enable PROXY protocol for TCP tunnel:

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "ssh",
      "proto": "tcp",
      "addr": 22,
      "proxy_proto": "2",
      "inspect": false
    }
  ]
}
```

### Reserved TCP Address

Use a reserved TCP address (requires ngrok paid plan):

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "db",
      "proto": "tcp",
      "addr": "core-mariadb:3306",
      "remote_addr": "1.tcp.ngrok.io:12345",
      "inspect": false
    }
  ]
}
```

## Regional Configurations

### Europe Region

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "eu",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "schemes": ["https"]
    }
  ]
}
```

### Asia Pacific Region

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "ap",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "schemes": ["https"]
    }
  ]
}
```

## Debugging Configurations

### Maximum Verbosity

Enable trace logging for troubleshooting:

```json
{
  "log_level": "trace",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "inspect": true,
      "schemes": ["https"]
    }
  ]
}
```

## Tips

1. **Get your auth token**: https://dashboard.ngrok.com/get-started/your-authtoken
2. **Reserve domains**: Go to https://dashboard.ngrok.com/cloud-edge/domains
3. **Monitor tunnels**: Check the ngrok dashboard or use the web inspection interface at `http://homeassistant.local:4040`
4. **TCP addresses**: Reserved TCP addresses require a paid ngrok plan
5. **OAuth providers**: Some OAuth providers require additional configuration in their respective dashboards

## Common Patterns

### Home Lab Complete Setup

```json
{
  "log_level": "info",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "hostname": "home.yourdomain.com",
      "oauth_provider": "google",
      "oauth_allow_domains": ["yourdomain.com"],
      "compression": true,
      "schemes": ["https"]
    },
    {
      "name": "mariadb",
      "proto": "tcp",
      "addr": "core-mariadb:3306",
      "inspect": false
    }
  ]
}
```

### Production with Circuit Breaker

```json
{
  "log_level": "warn",
  "auth_token": "your_ngrok_authtoken",
  "region": "us",
  "tunnels": [
    {
      "name": "hass",
      "proto": "http",
      "addr": 8123,
      "hostname": "home.yourdomain.com",
      "auth": "admin:strongpassword",
      "compression": true,
      "circuit_breaker": 0.3,
      "schemes": ["https"]
    }
  ]
}
```

## Resources

- [ngrok Documentation](https://ngrok.com/docs)
- [Traffic Policy Reference](https://ngrok.com/docs/traffic-policy)
- [ngrok Dashboard](https://dashboard.ngrok.com)
- [OAuth Setup Guide](https://ngrok.com/docs/http/oauth)
