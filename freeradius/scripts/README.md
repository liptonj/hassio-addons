# FreeRADIUS Validation & Testing Scripts

This directory contains practical scripts for validating and testing the FreeRADIUS deployment.

## Scripts

### 1. `ssh_tunnel.sh` (NEW - For Testing with Home Assistant)
Creates an SSH tunnel from your local machine to Home Assistant's MariaDB.

**Why?** Home Assistant's MariaDB addon is on an internal Docker network. This tunnel lets you test database connectivity from your Mac.

**Usage:**
```bash
# Start tunnel (keep this running in one terminal)
./scripts/ssh_tunnel.sh

# In another terminal, run tests
./scripts/test_with_tunnel.sh

# Or manually test
mysql -h 127.0.0.1 -P 3307 -u wpn-user -p wpn_radius
```

**Configuration:**
- Edit `HA_HOST` in script if HA is not at 192.168.14.50
- Tunnel maps `localhost:3307` → `core-mariadb:3306`
- Requires SSH access to Home Assistant

### 2. `test_with_tunnel.sh` (NEW - Automated Test)
Runs validation through SSH tunnel.

**Usage:**
```bash
# Make sure tunnel is running first!
./scripts/test_with_tunnel.sh
```

### 3. `validate_deployment.py`
Pre-deployment validation script that checks:
- Environment variables are set correctly
- Database connectivity (if DATABASE_URL provided)
- Database schema compatibility
- File structure is correct
- Python imports work (basic check)

**Usage:**
```bash
# Without database (checks file structure only)
python3 scripts/validate_deployment.py

# With database connection
export DATABASE_URL="postgresql://user:pass@host:5432/wpn_radius"
python3 scripts/validate_deployment.py
```

**Exit codes:**
- `0`: All checks passed or only warnings
- `1`: Critical issues found

### 2. `smoke_test.py`
Post-deployment smoke tests that verify:
- Health endpoint works
- Authentication is required
- Invalid tokens are rejected
- Config status endpoint works (with auth)
- Config reload works (with auth)

**Usage:**
```bash
# Basic test (health + auth checks only)
python3 scripts/smoke_test.py --api-url http://localhost:8000

# Full test (requires API token)
export API_AUTH_TOKEN="your-token-here"
python3 scripts/smoke_test.py --api-url http://localhost:8000

# Or pass token directly
python3 scripts/smoke_test.py --api-url http://localhost:8000 --api-token "your-token"
```

**Requirements:**
- `requests` module: `pip install requests`

**Exit codes:**
- `0`: All tests passed
- `1`: One or more tests failed

## Testing with Home Assistant MariaDB

Since Home Assistant's MariaDB addon runs on an internal Docker network, you can't connect directly from your Mac. Use the SSH tunnel approach:

### Step-by-Step Testing:

**Terminal 1 - Start SSH Tunnel:**
```bash
cd /Users/jolipton/Projects/hassio-addons-1/freeradius
./scripts/ssh_tunnel.sh
# Leave this running
```

**Terminal 2 - Run Tests:**
```bash
cd /Users/jolipton/Projects/hassio-addons-1/freeradius

# Option A: Automated test
./scripts/test_with_tunnel.sh

# Option B: Manual validation
export DATABASE_URL="mysql+pymysql://wpn-user:C1sco5150!@127.0.0.1:3307/wpn_radius"
python3 scripts/validate_deployment.py
```

**Test Database Access:**
```bash
# Using mysql client
mysql -h 127.0.0.1 -P 3307 -u wpn-user -p wpn_radius

# Check schema
mysql -h 127.0.0.1 -P 3307 -u wpn-user -pC1sco5150! wpn_radius \
  -e "DESCRIBE radius_clients;"
```

### Troubleshooting SSH Tunnel:

**"Connection refused"**
- Check SSH access: `ssh root@192.168.14.50`
- Verify HA is running: `ping 192.168.14.50`

**"Port already in use"**
- Another tunnel running: `lsof -i :3307`
- Kill existing: `kill $(lsof -t -i:3307)`

**"Tunnel closes immediately"**
- Check SSH key/password authentication
- Try with password: `ssh root@192.168.14.50` (should work)

## Validation Workflow

### Before Deployment:
```bash
# 1. Validate configuration and file structure
python3 scripts/validate_deployment.py

# 2. If validation passes, proceed with deployment
# (Follow DEPLOYMENT_GUIDE.md)
```

### After Deployment:
```bash
# 1. Run smoke tests
export API_AUTH_TOKEN="your-token"
python3 scripts/smoke_test.py --api-url http://your-server:8000

# 2. If smoke tests pass, deployment is successful
```

## What Has Been Actually Tested

### ✅ Validated (by scripts):
1. **File structure** - All required files exist ✅
2. **Old directory removed** - No conflicting radius-app/ directory ✅
3. **Python syntax** - All Python files compile without errors ✅
4. **Docker build** - Image builds successfully ✅
5. **Module structure** - radius_app package imports (basic check) ✅

### ⚠️ Not Yet Tested:
1. **Database connectivity** - Needs DATABASE_URL environment variable
2. **Schema compatibility** - Needs actual database connection
3. **Config generation** - Needs database with data
4. **RADIUS daemon** - Needs full deployment
5. **Authentication flow** - Needs running API
6. **Integration tests** - Need pytest and dependencies

## Running Full Test Suite

The integration and E2E tests require a full environment with dependencies installed.

### Option 1: Inside Docker Container
```bash
# Build the image
docker build -t freeradius-test .

# Run tests inside container (if pytest is installed)
docker run --rm \
  -e DATABASE_URL="your-db-url" \
  -e API_AUTH_TOKEN="your-token" \
  freeradius-test \
  python3 -m pytest /usr/bin/radius_app/tests/ -v
```

### Option 2: With uv (if package structure exists)
```bash
# This would require a pyproject.toml in freeradius/
# Currently not set up as freeradius is Docker-based addon
```

## Environment Variables

### Required for Full Validation:
- `DATABASE_URL` - Database connection string
  - PostgreSQL: `postgresql://user:pass@host:5432/db`
  - MySQL: `mysql+pymysql://user:pass@host:3306/db`
  - SQLite: `sqlite:////path/to/db.db`

### Required for Production:
- `API_AUTH_TOKEN` - API authentication token (48+ chars recommended)
- `CERT_PASSWORD` - Certificate encryption password (24+ chars recommended)
- `DEPLOYMENT_MODE` - `ha_addon` or `standalone` (auto-detected if not set)

### Optional:
- `LOG_LEVEL` - `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: INFO)
- `API_PORT` - API port (default: 8000)

## Interpreting Results

### Validation Script Output:
```
✅ Green checkmarks - Passed
⚠️  Yellow warnings - Should fix but not blocking
❌ Red errors - Must fix before deployment
```

### Smoke Test Output:
```
✅ PASS - Test passed
❌ FAIL - Test failed, check logs
```

## Troubleshooting

### "DATABASE_URL not set"
- This is expected if testing without database
- For full validation, set DATABASE_URL environment variable

### "Dependencies not installed"
- This is expected outside Docker
- Scripts check what they can without dependencies
- Full testing requires Docker environment

### "Old directory exists: radius-app"
- Run: `rm -rf rootfs/usr/bin/radius-app`
- Should only have `radius_app/` (with underscore)

### Smoke tests can't connect
- Check FreeRADIUS API is running
- Check URL is correct (default: http://localhost:8000)
- Check firewall allows connection to port 8000

## CI/CD Integration

These scripts can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Validate Deployment
  run: python3 scripts/validate_deployment.py
  
- name: Build Docker Image
  run: docker build -t freeradius .
  
- name: Run Smoke Tests
  run: |
    docker-compose up -d
    sleep 10
    python3 scripts/smoke_test.py
```

## Next Steps

After validation and smoke tests pass:
1. Review DEPLOYMENT_GUIDE.md for full deployment procedures
2. Set up monitoring (health check endpoint)
3. Configure alerting for failures
4. Plan rollback procedure
5. Document runbook for your environment
