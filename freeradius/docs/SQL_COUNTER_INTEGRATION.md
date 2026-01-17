# FreeRADIUS SQL Counter Integration

## Overview

Per [FreeRADIUS SQL Counter documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sqlcounter/index.html), the SQL Counter module tracks usage from accounting data (`radacct` table) and enforces session time limits.

## Features

SQL Counter supports three types of session time limits:

1. **Total Session Time** (`Max-All-Session`) - Never resets, cumulative across all sessions
2. **Daily Session Time** (`Max-Daily-Session`) - Resets daily, tracks session time within current day
3. **Monthly Session Time** (`Max-Monthly-Session`) - Resets monthly, tracks session time within current month

## Configuration

### SQL Counter Module

The SQL Counter module configuration is generated automatically and includes:

- `noresetcounter` - Total session time tracking (never resets)
- `dailycounter` - Daily session time tracking (resets daily)
- `monthlycounter` - Monthly session time tracking (resets monthly)

### Virtual Server Integration

SQL Counter modules are added to the `authorize` section:

```unlang
authorize {
    files
    sql {
        ok = return
    }
    noresetcounter    # Total session time limit
    dailycounter      # Daily session time limit
    monthlycounter    # Monthly session time limit
    eap
    pap
}
```

### Setting Limits

Limits are stored in `radcheck` table per FreeRADIUS SQL Counter documentation:

```sql
-- Total session time limit (15 hours = 54000 seconds)
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('ipsk-12345', 'Max-All-Session', ':=', '54000');

-- Daily session time limit (3 hours = 10800 seconds)
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('ipsk-12345', 'Max-Daily-Session', ':=', '10800');

-- Monthly session time limit (90 hours = 324000 seconds)
INSERT INTO radcheck (username, attribute, op, value)
VALUES ('ipsk-12345', 'Max-Monthly-Session', ':=', '324000');
```

## API Usage

### Set Session Limits

```http
POST /api/v1/sql-counter/set-limits
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "username": "ipsk-12345",
  "max_all_session": 54000,      // 15 hours total
  "max_daily_session": 10800,    // 3 hours per day
  "max_monthly_session": 324000  // 90 hours per month
}
```

### Get SQL Counter Config

```http
GET /api/v1/sql-counter/config?sql_module_instance=sql
Authorization: Bearer YOUR_TOKEN
```

## How It Works

1. **Accounting**: SQL module logs accounting data to `radacct` table
2. **Authorization**: SQL Counter queries `radacct` for user's session time
3. **Limit Check**: Compares current usage against limits in `radcheck`
4. **Enforcement**: If limit exceeded, authentication is rejected

### Example Flow

1. User authenticates with PSK
2. SQL Counter checks `radcheck` for `Max-Daily-Session` attribute
3. SQL Counter queries `radacct` for today's session time
4. If `today_session_time >= Max-Daily-Session`, authentication fails
5. If under limit, authentication succeeds and accounting continues

## Requirements

Per FreeRADIUS SQL Counter documentation:

1. **SQL Module**: Must be configured and enabled
2. **Accounting via SQL**: Accounting must be logged to `radacct` table via SQL module
3. **radacct Table**: Must exist with proper schema (created by SQL module)
4. **radcheck Table**: Must exist for storing limit attributes

## Database Queries

SQL Counter uses database-specific queries:

### MySQL/MariaDB

```sql
-- Total session time
SELECT SUM(AcctSessionTime) FROM radacct WHERE UserName='%{%k}'

-- Daily/Monthly session time
SELECT SUM(AcctSessionTime - GREATEST((%b - UNIX_TIMESTAMP(AcctStartTime)), 0))
FROM radacct
WHERE UserName='%{%k}'
AND UNIX_TIMESTAMP(AcctStartTime) + AcctSessionTime > '%b'
```

### PostgreSQL

```sql
-- Total session time
SELECT SUM(AcctSessionTime) FROM radacct WHERE UserName='%{%k}'

-- Daily/Monthly session time
SELECT SUM(AcctSessionTime - GREATEST((%b - EXTRACT(epoch FROM AcctStartTime)), 0))
FROM radacct
WHERE UserName='%{%k}'
AND EXTRACT(epoch FROM AcctStartTime) + AcctSessionTime > '%b'
```

## Use Cases

### Guest WiFi Limits

```json
{
  "username": "guest-user",
  "max_daily_session": 10800,  // 3 hours per day
  "max_monthly_session": 324000  // 90 hours per month
}
```

### Premium User Limits

```json
{
  "username": "premium-user",
  "max_all_session": 864000  // 240 hours total (no daily/monthly limits)
}
```

### Time-Based Access Control

Combine with time restrictions in policies to enforce:
- Business hours only access
- Weekday vs weekend limits
- Peak vs off-peak hour restrictions

## Integration with PSK Authentication

SQL Counter works seamlessly with PSK authentication:

1. PSK user authenticates via SQL module (from `radcheck`)
2. SQL Counter checks session time limits (from `radcheck`)
3. If limits not exceeded, authentication succeeds
4. Accounting data logged to `radacct` via SQL module
5. Next authentication checks updated usage

## References

- [FreeRADIUS SQL Counter Documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sqlcounter/index.html)
- [FreeRADIUS SQL Module Documentation](https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sql/index.html)
