## Changes

### Version 3.3.0 (2026-01-13)

#### Architecture
- **Follows official ngrok Docker patterns** - Config file mounting approach per [official docs](https://ngrok.com/docs/using-ngrok-with/docker)
- **Switched to official ngrok Docker image** - Now uses `ngrok/ngrok:latest` via multi-stage build
- **Simplified execution flow** - Config generation separate from ngrok execution
- **Always runs latest ngrok version** - Automatically gets the most recent official ngrok release

#### Configuration
- **Upgraded to ngrok v3 configuration format** - Migrated from v2 to v3 config schema
- **Added hostname support for addr field** - Now supports hostnames with ports (e.g., `core-mariadb:3306`)
- **TCP protocol fully supported** - Proper handling of TCP-specific options (remote_addr, proxy_proto)
- **TLS protocol improvements** - TLS termination and mutual TLS support
- **Updated config generation** - Now uses `endpoints` instead of `tunnels` (v3 format)

#### Features
- **OAuth authentication** - Google, GitHub, Microsoft, Facebook, GitLab, LinkedIn, Bitbucket, Amazon
- **OIDC support** - Custom OpenID Connect providers
- **Compression** - Built-in gzip compression option
- **Circuit breaker** - Auto-disable on high error rates
- **WebSocket TCP converter** - Convert WebSocket to TCP
- **PROXY protocol** - Support for PROXY protocol v1 and v2
- **Mutual TLS** - Client certificate authentication
- **Better logging** - More informative messages during startup

#### Documentation
- **V3_MIGRATION_GUIDE.md** - Comprehensive migration guide
- **EXAMPLE_CONFIGS.md** - Real-world configuration examples
- **Updated DOCS.md** - Added v3 information and breaking changes

### Breaking Changes in v3.3.0
- Configuration format updated to ngrok v3 - existing configs should still work but will be auto-converted
- `subdomain` option is deprecated - use `hostname` instead
- Some advanced options (host_header, crt, key, client_cas) now require Traffic Policy configuration
- Config file location changed from `/ngrok-config/ngrok.yml` to `/etc/ngrok.yml`

### Previous Versions
**Note**: You will need to uninstall and reinstall to go to v3.2
- migrating to the new s6-overlay 
- added init: false to config file
- Latest NGROK version
- permission fix moved to docker file since fix-aattrs.d does not work
- changed schema for remote addr
- added +x to the ngrok.sh
- added init: false to config.json