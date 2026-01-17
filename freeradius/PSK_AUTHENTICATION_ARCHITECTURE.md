# PSK Authentication Architecture

## Current Situation

We have **two approaches** for PSK authentication, which is redundant:

### Approach 1: Static Files (Legacy) ❌
- **Generator**: `PskConfigGenerator.generate_psk_users_file()`
- **Output**: `/config/raddb/users-psk` static file
- **How it works**: Writes PSK passphrases to a users file
- **Problems**:
  - Requires config regeneration when PSK changes
  - Needs passphrase decryption (not implemented)
  - Static file becomes stale
  - Doesn't scale well

### Approach 2: SQL Module (Recommended) ✅
- **Generator**: `SqlConfigGenerator.sync_psk_to_radcheck()`
- **Output**: `radcheck`/`radreply` database tables
- **How it works**: FreeRADIUS queries database at runtime
- **Benefits**:
  - Real-time updates (no config regeneration)
  - No passphrase decryption needed (stored in radcheck)
  - Scales to thousands of users
  - Already integrated in virtual server

## Recommendation: Use SQL Module Only

### Why SQL Module is Better

1. **Real-time Updates**: PSK changes in portal database are immediately available
2. **No Config Regeneration**: No need to regenerate files when PSK changes
3. **No Decryption Needed**: Passphrases stored directly in `radcheck` table
4. **Scalability**: Handles large numbers of users efficiently
5. **Already Implemented**: `sync_psk_to_radcheck()` method exists and works

### How It Works

1. **PSK Sync**: Portal syncs PSK data to `radcheck`/`radreply` tables:
   ```sql
   INSERT INTO radcheck (username, attribute, op, value)
   VALUES ('ipsk-12345', 'Cleartext-Password', ':=', 'my-secret-psk');
   
   INSERT INTO radreply (username, attribute, op, value)
   VALUES ('ipsk-12345', 'Cisco-AVPair', ':=', 'udn:private-group-id=100');
   ```

2. **FreeRADIUS Query**: When user authenticates:
   - FreeRADIUS queries `radcheck` for username (PSK ID)
   - Evaluates `Cleartext-Password := "passphrase"`
   - Queries `radreply` for reply attributes (UDN, group policy, etc.)

3. **Virtual Server**: SQL module already included:
   ```unlang
   authorize {
       files          # Static files (for MAC bypass, etc.)
       sql {          # Dynamic PSK lookups
           ok = return
           notfound = noop
       }
   }
   ```

## Action Items

### 1. Deprecate PSK File Generation When SQL Enabled

Modify `config_generator.py` to skip PSK file generation if SQL module is enabled:

```python
def generate_all(self, db: Session) -> dict[str, Path]:
    configs = {
        "clients": self.generate_clients_conf(db),
        "users": self.generate_users_file(db),
    }
    
    # Check if SQL module is enabled
    sql_module_enabled = (Path(self.settings.radius_config_path) / "mods-enabled" / "sql").exists()
    
    if not sql_module_enabled:
        # Only generate PSK file if SQL module not enabled (fallback)
        psk_generator = PskConfigGenerator()
        configs["users-psk"] = psk_generator.generate_psk_users_file(db)
    else:
        logger.info("SQL module enabled - skipping PSK file generation (using radcheck/radreply)")
    
    # MAC bypass still needed (not PSK-related)
    psk_generator = PskConfigGenerator()
    configs["users-mac-bypass"] = psk_generator.generate_mac_bypass_file(db)
    
    # ... rest of generation
```

### 2. Update Documentation

- Mark `PskConfigGenerator.generate_psk_users_file()` as deprecated
- Document that SQL module is the recommended approach
- Keep PSK generator for fallback scenarios (SQL module disabled)

### 3. Ensure PSK Sync is Called

Make sure `sync_psk_to_radcheck()` is called:
- On initial setup
- When PSK data changes in portal
- Via API endpoint: `POST /api/v1/sql/sync-psk`

## MAC Bypass File (Still Needed)

**Note**: `generate_mac_bypass_file()` is still useful because:
- MAC bypass is not PSK-related
- It's a simple whitelist/blacklist mechanism
- Can be kept as static file (rarely changes)
- Or could also be moved to SQL if needed

## Migration Path

1. ✅ SQL module already configured and enabled
2. ✅ `sync_psk_to_radcheck()` method exists
3. ⏭️ Skip PSK file generation when SQL enabled
4. ⏭️ Update documentation
5. ⏭️ Remove PSK file generation from default flow

## Conclusion

**You're absolutely right** - we should use SQL for PSK calls instead of generating static files. The PSK file generator is redundant when SQL module is enabled and should be deprecated or only used as a fallback.
