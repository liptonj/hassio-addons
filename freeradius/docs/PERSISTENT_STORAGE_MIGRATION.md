# Persistent Storage Migration

## Overview

All FreeRADIUS configurations are now stored in persistent storage (`/config/raddb`) instead of ephemeral container storage (`/etc/raddb`).

## Changes Made

### 1. Configuration Path Update

**Before:**
- Config path: `/etc/raddb` (ephemeral, lost on restart)
- Default in `config.py`: `radius_config_path: str = "/etc/raddb"`

**After:**
- Config path: `/config/raddb` (persistent, survives restarts)
- Default in `config.py`: `radius_config_path: str = "/config/raddb"`

### 2. Symlink for FreeRADIUS Compatibility

FreeRADIUS expects configs in `/etc/raddb` by default. To maintain compatibility while using persistent storage:

```bash
/etc/raddb -> /config/raddb  # Symlink
```

This allows:
- FreeRADIUS to use standard paths (`/etc/raddb`)
- Configs to be stored persistently (`/config/raddb`)
- No changes needed to FreeRADIUS configuration

### 3. Directory Structure

All configs are now in `/config/raddb/`:

```
/config/
├── raddb/                    # Persistent FreeRADIUS configs
│   ├── mods-available/       # Module configs (EAP, SQL, SQL Counter)
│   ├── mods-enabled/         # Enabled module symlinks
│   ├── sites-available/      # Virtual server configs
│   ├── sites-enabled/        # Enabled site symlinks
│   ├── policy.d/            # Policy files
│   ├── users                 # Users file
│   ├── users-psk             # PSK users file
│   ├── users-mac-bypass      # MAC bypass file
│   └── policies              # Policy file
├── clients/                  # RADIUS clients config
│   └── clients.conf
└── certs/                    # Certificates
    ├── ca.pem
    ├── server.pem
    └── server-key.pem
```

## Migration Process

The `run.sh` script automatically handles migration:

1. **Creates persistent directories** in `/config/raddb/`
2. **Creates symlink** `/etc/raddb -> /config/raddb`
3. **Migrates existing configs** if `/etc/raddb` exists (first run only)
4. **Initializes configs** from templates if needed

## Benefits

### ✅ Persistent Storage
- All configs survive container restarts
- No regeneration delay on startup
- Faster startup time

### ✅ Data Safety
- Configs are backed up with `/config` volume
- No data loss on container updates
- Easy to backup/restore

### ✅ Compatibility
- FreeRADIUS still uses standard paths (`/etc/raddb`)
- No changes needed to FreeRADIUS config files
- Works with existing FreeRADIUS tools

## Updated Components

### Config Generators
All config generators now use persistent storage:

- `ConfigGenerator` → `/config/raddb/users`
- `EapConfigGenerator` → `/config/raddb/mods-available/eap`
- `SqlConfigGenerator` → `/config/raddb/mods-available/sql`
- `SqlCounterGenerator` → `/config/raddb/mods-available/sqlcounter`
- `PolicyGenerator` → `/config/raddb/policies`
- `PskConfigGenerator` → `/config/raddb/users-psk`, `/config/raddb/users-mac-bypass`
- `VirtualServerGenerator` → `/config/raddb/sites-available/*`

### Environment Variables

Updated in `run.sh`:
```bash
export RADIUS_CONFIG_PATH="/config/raddb"  # Changed from /etc/raddb
```

### Settings Default

Updated in `config.py`:
```python
radius_config_path: str = "/config/raddb"  # Changed from /etc/raddb
```

## Verification

To verify persistent storage is working:

```bash
# Check symlink exists
ls -la /etc/raddb

# Check configs are in persistent storage
ls -la /config/raddb/

# Restart container and verify configs persist
docker restart freeradius-server
ls -la /config/raddb/  # Should still exist
```

## Rollback

If needed, you can rollback by:

1. Setting environment variable:
   ```bash
   export RADIUS_CONFIG_PATH="/etc/raddb"
   ```

2. Removing symlink:
   ```bash
   rm /etc/raddb
   mkdir /etc/raddb
   ```

3. Copying configs back:
   ```bash
   cp -r /config/raddb/* /etc/raddb/
   ```

However, this is not recommended as it loses persistence benefits.

## Notes

- The symlink approach ensures FreeRADIUS compatibility
- All configs are still database-driven (can be regenerated)
- Persistent storage provides faster startup and data safety
- No manual intervention needed - migration is automatic
