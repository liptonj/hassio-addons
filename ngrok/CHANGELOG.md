## Changes

### Version 3.35.2 (2026-01-13)

#### Critical Fixes
- **Fixed Docker build** - Corrected ngrok binary path from `/usr/local/bin/ngrok` to `/bin/ngrok`
- **Fixed ARG placement** - Moved `ARG BUILD_FROM` before first FROM statement
- **Fixed v3 config format** - Now follows [official ngrok v3 specification](https://ngrok.com/docs/agent/config/v3)
- **Fixed TCP endpoint handling** - TCP tunnels no longer incorrectly use HTTPS URLs
- **Removed schemes option** - Not supported in ngrok v3, was causing validation errors

#### Architecture
- **Uses official ngrok Docker image** - Multi-stage build with `ngrok/ngrok:latest` 
- **Follows official patterns** - Config file mounting per [ngrok Docker docs](https://ngrok.com/docs/using-ngrok-with/docker)
- **Simplified execution** - Separate config generation from ngrok execution
- **Always latest ngrok** - Currently running ngrok version 3.35.0

#### Configuration Format (v3)
Based on official [ngrok v3 config](https://ngrok.com/docs/agent/config/v3):
```yaml
version: 3
agent:
  authtoken: xxx
  api_key: xxx  # NEW: optional API key support
  log_level: info
  log_format: term
  log: stdout
  web_addr: 0.0.0.0:4040
endpoints:
  - name: example
    url: https://example.ngrok.app  # optional
    upstream:
      url: 8080  # port shorthand for HTTP
      protocol: http1  # only for HTTP/HTTPS
      proxy_protocol: 2  # optional
```

#### TCP Support
- **Random TCP address** - Omit hostname to get auto-assigned address (e.g., `3.tcp.ngrok.io:12345`)
- **Reserved TCP address** - Use `hostname: "3.tcp.ngrok.io:12345"` for reserved addresses
- **Named services** - Full support for `addr: "core-mariadb:3306"`
- **Proper URL handling** - TCP endpoints don't use `https://` scheme
- **PROXY protocol** - Optional v1 and v2 support

#### Features Added
- **api_key support** - Configure ngrok API key in agent section
- **Hostname:port addresses** - Works for all protocols: `core-mariadb:3306`, `172.30.32.1:8080`
- **PROXY protocol** - v1 and v2 support via `upstream.proxy_protocol`
- **WebSocket TCP converter** - Note in logs (requires Traffic Policy in v3)
- **Metadata** - Custom metadata per endpoint
- **Better logging** - Informative messages during config generation

#### What Was Removed
- **schemes option** - Not supported in v3 (use endpoint type instead)
- **OAuth/OIDC options** - Removed from schema (requires Traffic Policy in v3)
- **region field** - v3 uses connect_url instead
- **Complex TLS options** - Simplified for v3 compatibility

#### Documentation
- **V3_MIGRATION_GUIDE.md** - Complete migration guide with examples
- **EXAMPLE_CONFIGS.md** - 20+ real-world configuration examples
- **VALIDATION_CHECKLIST.md** - Comprehensive validation checklist
- **Updated DOCS.md** - v3 changes and TCP examples

### Breaking Changes in 3.35.x
- **Configuration format** - Uses ngrok v3 YAML format with `agent:` and `endpoints:` sections
- **schemes removed** - Not supported in v3, configure via endpoint type
- **subdomain deprecated** - Use `hostname` instead
- **Config location** - Changed from `/ngrok-config/ngrok.yml` to `/etc/ngrok.yml`
- **Requires auth_token** - Always required in v3

### Migration from Previous Versions
Your existing Home Assistant add-on configuration will work, but:
1. Remove `schemes` from your config (will cause validation error)
2. For TCP tunnels, don't set hostname unless you have a reserved TCP address
3. auth_token is now required (was optional in v2)

### Previous Versions (3.2.2p and earlier)
- migrating to the new s6-overlay 
- added init: false to config file
- permission fix moved to docker file
- changed schema for remote addr
- added +x to the ngrok.sh