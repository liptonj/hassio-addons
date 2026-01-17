# Quick Testing Guide - Home Assistant MariaDB

## TL;DR - How to Test Database from Your Mac

```bash
# Terminal 1: Start tunnel (keep running)
cd /Users/jolipton/Projects/hassio-addons-1/freeradius
./scripts/ssh_tunnel.sh

# Terminal 2: Run tests
./scripts/test_with_tunnel.sh
```

That's it! ✅

---

## Why Do I Need a Tunnel?

Home Assistant's MariaDB addon is on an **internal Docker network**:
- ❌ Can't access from: `192.168.14.50:3306` (port not exposed)
- ✅ Can access from: SSH tunnel to `core-mariadb:3306`

The tunnel maps:
```
Your Mac (127.0.0.1:3307) → SSH → HA (192.168.14.50) → core-mariadb:3306
```

---

## What Gets Tested?

### Via SSH Tunnel (from your Mac):
1. ✅ Database connectivity
2. ✅ Schema validation (tables, columns)
3. ✅ File structure
4. ✅ Environment variables

### From Actual Deployment (inside HA):
5. ✅ API health endpoint
6. ✅ Config generation
7. ✅ RADIUS daemon
8. ✅ Authentication flow

---

## Database Connection Strings

### From Your Mac (with tunnel):
```bash
mysql+pymysql://wpn-user:C1sco5150!@127.0.0.1:3307/wpn_radius
```

### From FreeRADIUS Addon (production):
```bash
mysql+pymysql://wpn-user:C1sco5150!@core-mariadb:3306/wpn_radius
```

**Note:** Different hostnames! `127.0.0.1` vs `core-mariadb`

---

## Quick Commands

### Start Tunnel:
```bash
./scripts/ssh_tunnel.sh
# Press Ctrl+C to stop
```

### Test Everything:
```bash
./scripts/test_with_tunnel.sh
```

### Test Database Only:
```bash
mysql -h 127.0.0.1 -P 3307 -u wpn-user -pC1sco5150! wpn_radius -e "SELECT 1;"
```

### Check Schema:
```bash
mysql -h 127.0.0.1 -P 3307 -u wpn-user -pC1sco5150! wpn_radius <<EOF
SHOW TABLES;
DESCRIBE radius_clients;
DESCRIBE udn_assignments;
EOF
```

### Run Validation:
```bash
DATABASE_URL="mysql+pymysql://wpn-user:C1sco5150!@127.0.0.1:3307/wpn_radius" \
  python3 scripts/validate_deployment.py
```

---

## Common Issues

### "Connection refused"
```bash
# Check SSH works
ssh root@192.168.14.50 "echo 'SSH works!'"

# Check HA is reachable
ping 192.168.14.50
```

### "Port 3307 in use"
```bash
# Find what's using it
lsof -i :3307

# Kill it
kill $(lsof -t -i:3307)
```

### "Tunnel keeps closing"
```bash
# Check SSH password/key
ssh root@192.168.14.50

# If fails, check your SSH config
cat ~/.ssh/config
```

### "Database connection failed"
```bash
# Verify tunnel is running
lsof -i :3307

# Test with mysql client first
mysql -h 127.0.0.1 -P 3307 -u wpn-user -p
```

---

## For CI/CD or Automated Testing

Not recommended - SSH tunnel is for local development only.

For CI/CD:
1. Deploy to test HA instance
2. Run tests from within HA network
3. Use smoke tests against deployed API

---

## Next Steps After Validation Passes

1. ✅ Deploy FreeRADIUS addon to Home Assistant
2. ✅ Configure with `database_url: mysql+pymysql://wpn-user:PASSWORD@core-mariadb:3306/wpn_radius`
3. ✅ Run smoke tests: `./scripts/smoke_test.py --api-url http://homeassistant.local:8000`
4. ✅ Test actual RADIUS authentication
5. ✅ Monitor logs for issues

---

## Security Note

**SSH tunnels are for development/testing only!**

For production:
- ✅ Use internal Docker hostnames (`core-mariadb`)
- ✅ No external database access
- ✅ All traffic stays in HA network
- ❌ Don't expose MariaDB port 3306 to the internet!
