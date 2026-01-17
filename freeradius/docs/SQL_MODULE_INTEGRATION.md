# FreeRADIUS SQL Module Integration

## Overview

Per [FreeRADIUS SQL documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/index.html), the SQL module allows FreeRADIUS to query user data directly from the database at runtime, rather than using static users files.

## Architecture Options

### Option 1: Static Users Files (Current Implementation)
- **Pros**: Simple, fast, no database queries at runtime
- **Cons**: Requires config regeneration when PSK data changes
- **Use Case**: Small deployments, infrequent PSK changes

### Option 2: SQL Module (Recommended for Dynamic PSK)
- **Pros**: Real-time updates, no config regeneration needed, scales better
- **Cons**: Requires database connection, slightly slower than files
- **Use Case**: Large deployments, frequent PSK changes, dynamic user management

## SQL Module Tables

Per FreeRADIUS SQL documentation, the following tables are used:

### User-Specific Tables

1. **radcheck** - User check attributes (authentication)
   - `username`: User identifier (PSK ID or email)
   - `attribute`: Attribute name (e.g., "Cleartext-Password")
   - `op`: Operator (:=, ==, +=, etc.)
   - `value`: Attribute value (e.g., PSK passphrase)

2. **radreply** - User reply attributes (authorization)
   - `username`: User identifier
   - `attribute`: Attribute name (e.g., "Cisco-AVPair")
   - `op`: Operator (:=, +=)
   - `value`: Attribute value (e.g., "udn:private-group-id=100")

### Group-Based Tables

3. **radusergroup** - User group membership
   - `username`: User identifier
   - `groupname`: Group name
   - `priority`: Processing order (lower = higher priority)

4. **radgroupcheck** - Group check attributes
   - `groupname`: Group name
   - `attribute`: Attribute name
   - `op`: Operator
   - `value`: Attribute value

5. **radgroupreply** - Group reply attributes
   - `groupname`: Group name
   - `attribute`: Attribute name
   - `op`: Operator
   - `value`: Attribute value

### Accounting Tables

6. **radacct** - Accounting records
7. **radpostauth** - Post-authentication logging

## Operators

Per FreeRADIUS SQL documentation, operators are critical:

- **:=** - Always matches (check) or replaces/adds (reply)
- **==** - Matches if attribute equals value (check only)
- **+=** - Always matches and adds to list (check/reply)
- **!=** - Matches if attribute not equal to value (check only)
- **=~** - Regular expression match (check only)
- **!~** - Regular expression non-match (check only)

## PSK Authentication with SQL Module

### Example radcheck Entry

```sql
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('ipsk-12345', 'Cleartext-Password', ':=', 'my-secret-psk');
```

### Example radreply Entry (with UDN)

```sql
INSERT INTO radreply (username, attribute, op, value)
VALUES ('ipsk-12345', 'Cisco-AVPair', ':=', 'udn:private-group-id=100');
```

### Processing Flow

1. User authenticates with PSK passphrase
2. FreeRADIUS queries `radcheck` for username (PSK ID)
3. If found, evaluates check attributes (Cleartext-Password := "passphrase")
4. If check matches, queries `radreply` for reply attributes
5. Adds reply attributes to authorization response (UDN ID, group policy, etc.)
6. If user in `radusergroup`, processes group attributes

## Implementation

The `SqlConfigGenerator` class provides:

1. **SQL Module Configuration** - Generates `mods-enabled/sql` config
2. **Schema Creation** - Creates radcheck/radreply tables
3. **PSK Sync** - Syncs PSK data from portal database to radcheck/radreply

## Virtual Server Integration

The SQL module is added to the `authorize` section:

```unlang
authorize {
    files          # Check static users file first
    sql {          # Then check SQL database
        ok = return
        notfound = return
    }
    eap
    pap
}
```

## Benefits for PSK Authentication

1. **Real-time Updates**: PSK changes in portal database immediately available
2. **No Config Regeneration**: No need to regenerate users files
3. **Scalability**: Handles large numbers of users efficiently
4. **Dynamic Groups**: Group-based policies via radusergroup
5. **UDN Lookup**: UDN ID can be queried dynamically via USER → PSK relationship

## Migration Path

1. Generate SQL module configuration
2. Create radcheck/radreply tables
3. Sync existing PSK data to radcheck/radreply
4. Enable SQL module in virtual server
5. Test authentication
6. Optionally disable files module for PSK (keep for MAC bypass)

## References

- [FreeRADIUS SQL Module Documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/index.html)
- [FreeRADIUS SQL Data Usage Reporting](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/data-usage-reporting.html)
- [FreeRADIUS SQL ODBC](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/odbc.html)
