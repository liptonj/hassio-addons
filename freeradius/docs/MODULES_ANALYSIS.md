# FreeRADIUS Modules Analysis

## Overview

Per [FreeRADIUS Modules Documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/raddb/mods-available/index.html), modules are enabled by creating symlinks from `mods-enabled/` to `mods-available/`. This document analyzes which modules we're using, which we should add, and which we should configure.

## Currently Used Modules

### ✅ Enabled and Configured

1. **EAP Module** (`mods-available/eap`)
   - **Status**: ✅ Configured via `EapConfigGenerator`
   - **Purpose**: EAP authentication (EAP-TLS, EAP-TTLS, PEAP)
   - **Location**: Generated to `mods-available/eap`, symlinked to `mods-enabled/eap`
   - **Usage**: Referenced in `authorize` and `authenticate` sections

2. **Files Module** (`mods-available/files`)
   - **Status**: ✅ Referenced in virtual servers
   - **Purpose**: Reads users file for authorization
   - **Usage**: Used in `authorize` section for PSK/MAC bypass lookups
   - **Note**: Should be configured to use our generated users file

3. **PAP Module** (`mods-available/pap`)
   - **Status**: ✅ Referenced in virtual servers
   - **Purpose**: PAP authentication (used for PSK)
   - **Usage**: Used in `authenticate` section

4. **Detail Module** (`mods-available/detail`)
   - **Status**: ✅ Referenced in virtual servers
   - **Purpose**: Detailed accounting logging
   - **Usage**: Used in `accounting` and `post-auth` sections

5. **Unix Module** (`mods-available/unix`)
   - **Status**: ✅ Referenced in virtual servers
   - **Purpose**: Unix accounting (radutmp)
   - **Usage**: Used in `accounting` section

6. **Attr_Filter Module** (`mods-available/attr_filter`)
   - **Status**: ✅ Referenced in virtual servers
   - **Purpose**: Filters attributes from replies
   - **Usage**: Used in `post-auth` and `accounting` sections

### ⚠️ Referenced but Not Configured

1. **SQL Module** (`mods-available/sql`)
   - **Status**: ⚠️ Config generated but module not enabled
   - **Purpose**: Dynamic user lookups from database (radcheck/radreply)
   - **Action Needed**: 
     - Generate SQL module config via `SqlConfigGenerator`
     - Create symlink: `ln -s ../mods-available/sql mods-enabled/sql`
     - Add to virtual server `authorize` section

2. **SQL Counter Module** (`mods-available/sqlcounter`)
   - **Status**: ⚠️ Config generated but module not enabled
   - **Purpose**: Session time limit tracking (daily/monthly/total)
   - **Action Needed**:
     - Generate SQL Counter config via `SqlCounterGenerator`
     - Create symlink: `ln -s ../mods-available/sqlcounter mods-enabled/sqlcounter`
     - Add counters to virtual server `authorize` section

### 🔧 Built-in Modules (No Configuration Needed)

1. **filter_username** - Filters and normalizes usernames
2. **preprocess** - Preprocesses RADIUS attributes
3. **update** - Updates request/reply attributes (Unlang)

## Recommended Modules to Add

### 🔴 HIGH PRIORITY

1. **SQL Module** (`mods-available/sql`)
   - **Why**: Dynamic PSK lookups, UDN assignment, group policies
   - **Benefits**: Real-time updates without config regeneration
   - **Integration**: Already have `SqlConfigGenerator` - need to enable module

2. **SQL Counter Module** (`mods-available/sqlcounter`)
   - **Why**: Session time limits (daily/monthly/total)
   - **Benefits**: Enforce usage limits per user
   - **Integration**: Already have `SqlCounterGenerator` - need to enable module

3. **Cache Module** (`mods-available/cache`)
   - **Why**: Cache user lookups for performance
   - **Benefits**: Reduces database queries
   - **Use Case**: Cache PSK lookups, MAC bypass rules

4. **Expiration Module** (`mods-available/expiration`)
   - **Why**: Account expiration handling
   - **Benefits**: Automatically expire accounts based on date
   - **Use Case**: Guest account expiration

### 🟡 MEDIUM PRIORITY

5. **Always Module** (`mods-available/always`)
   - **Why**: Always return success (useful for testing)
   - **Use Case**: Development/testing

6. **Date Module** (`mods-available/date`)
   - **Why**: Date/time-based policies
   - **Use Case**: Time-based access restrictions

7. **Linelog Module** (`mods-available/linelog`)
   - **Why**: Custom logging format
   - **Use Case**: Integration with external log systems

8. **Logtee Module** (`mods-available/logtee`)
   - **Why**: Duplicate logs to multiple destinations
   - **Use Case**: Send logs to both file and syslog

### 🟢 LOW PRIORITY

9. **LDAP Module** (`mods-available/ldap`)
   - **Why**: LDAP integration (if needed)
   - **Use Case**: Enterprise directory integration
   - **Note**: Currently using SQL, may not need LDAP

10. **REST Module** (`mods-available/rest`)
    - **Why**: REST API authentication
    - **Note**: Currently disabled in `run.sh` - may enable if needed

11. **Python Module** (`mods-available/python`)
    - **Why**: Python scripting in policies
    - **Use Case**: Complex policy logic
    - **Note**: May be overkill for current use case

## Module Configuration Status

### Modules We Generate Configs For

| Module | Config Generator | Status | Enabled |
|--------|----------------|--------|---------|
| EAP | `EapConfigGenerator` | ✅ Complete | ✅ Yes |
| SQL | `SqlConfigGenerator` | ✅ Complete | ❌ No |
| SQL Counter | `SqlCounterGenerator` | ✅ Complete | ❌ No |
| Files | Manual | ⚠️ Partial | ✅ Yes |
| Virtual Servers | `VirtualServerGenerator` | ✅ Complete | ✅ Yes |

### Modules We Reference But Don't Configure

| Module | Referenced In | Config Needed |
|--------|--------------|---------------|
| PAP | `authenticate` section | ⚠️ Default config |
| Detail | `accounting` section | ⚠️ Default config |
| Unix | `accounting` section | ⚠️ Default config |
| Attr_Filter | `post-auth` section | ⚠️ Default config |

## Action Items

### Immediate (Required for SQL-based PSK)

1. **Enable SQL Module**
   ```bash
   # Generate config
   python -c "from radius_app.core.sql_config_generator import SqlConfigGenerator; ..."
   
   # Enable module
   ln -s ../mods-available/sql /etc/raddb/mods-enabled/sql
   ```

2. **Enable SQL Counter Module**
   ```bash
   # Generate config
   python -c "from radius_app.core.sql_counter_generator import SqlCounterGenerator; ..."
   
   # Enable module
   ln -s ../mods-available/sqlcounter /etc/raddb/mods-enabled/sqlcounter
   ```

3. **Update Virtual Server Generator**
   - Already includes SQL and SQL Counter in `authorize` section
   - Ensure modules are enabled before using

### Short Term (Performance & Features)

4. **Configure Files Module**
   - Ensure it points to our generated users file
   - Already handled in `run.sh`

5. **Add Cache Module**
   - Cache PSK lookups
   - Cache MAC bypass rules
   - Reduce database load

6. **Configure Detail Module**
   - Customize accounting log format
   - Add UDN ID to logs

### Long Term (Advanced Features)

7. **Expiration Module**
   - Guest account expiration
   - Temporary access tokens

8. **Date Module**
   - Time-based access restrictions
   - Business hours only access

## Module Enablement Pattern

Per FreeRADIUS documentation, modules are enabled via symlinks:

```bash
cd /etc/raddb/mods-enabled/
ln -s ../mods-available/module_name .
```

For conditional modules (optional), prefix with `-`:

```unlang
authorize {
    files
    -sql    # Only use if configured
    eap
}
```

## Integration with Config Generators

Our config generators should:

1. **Generate Module Configs**: Write to `mods-available/`
2. **Create Symlinks**: Automatically enable in `mods-enabled/`
3. **Update Virtual Servers**: Reference modules in appropriate sections
4. **Validate**: Check module configs before enabling

## References

- [FreeRADIUS Modules Documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/raddb/mods-available/index.html)
- [FreeRADIUS SQL Module](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/index.html)
- [FreeRADIUS SQL Counter Module](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sqlcounter/index.html)
- [FreeRADIUS EAP Module](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/eap/index.html)
