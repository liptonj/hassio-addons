# Database Configuration Options

## Quick Reference: Choose Your Database

The FreeRADIUS and Portal addons now support **automatic mode detection** and **multiple database backends**. Choose the option that fits your deployment:

---

## 🏠 Home Assistant Addon Mode

**When to use:** Running as Home Assistant add-ons  
**Database:** MariaDB Addon  
**Complexity:** ⭐⭐ (Medium)  
**Performance:** ⭐⭐⭐⭐ (Excellent)  
**Recommended for:** Most HA users

### Setup:

1. Install MariaDB add-on from HA store
2. Create database:
```sql
CREATE DATABASE wpn_radius CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'wpn_user'@'%' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON wpn_radius.* TO 'wpn_user'@'%';
```

3. Configure both addons:
```yaml
# config.yaml (both Portal and FreeRADIUS)
database_url: "mysql+pymysql://wpn_user:!secret wpn_db_password@core-mariadb:3306/wpn_radius"

# secrets.yaml
wpn_db_password: "your-secure-password"
```

---

## 🐘 Standalone with PostgreSQL

**When to use:** Docker Compose or production deployments  
**Database:** PostgreSQL 15+  
**Complexity:** ⭐⭐ (Medium)  
**Performance:** ⭐⭐⭐⭐⭐ (Excellent)  
**Recommended for:** Production, high-traffic

### docker-compose.yml:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: wpn_radius
      POSTGRES_USER: wpn_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U wpn_user"]
      interval: 10s

  portal:
    image: meraki-wpn-portal:latest
    environment:
      DATABASE_URL: postgresql://wpn_user:${DB_PASSWORD}@postgres:5432/wpn_radius
      RUN_MODE: standalone
    depends_on:
      postgres:
        condition: service_healthy

  freeradius:
    image: freeradius-server:latest
    environment:
      DATABASE_URL: postgresql://wpn_user:${DB_PASSWORD}@postgres:5432/wpn_radius
      RUN_MODE: standalone
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  postgres_data:
```

### .env file:
```bash
DB_PASSWORD=your-secure-password-here
```

---

## 🐬 Standalone with MySQL/MariaDB

**When to use:** Prefer MySQL ecosystem  
**Database:** MySQL 8+ or MariaDB 10.6+  
**Complexity:** ⭐⭐ (Medium)  
**Performance:** ⭐⭐⭐⭐ (Excellent)  
**Recommended for:** Production, existing MySQL infrastructure

### docker-compose.yml:

```yaml
version: '3.8'

services:
  mysql:
    image: mariadb:10.11
    environment:
      MYSQL_DATABASE: wpn_radius
      MYSQL_USER: wpn_user
      MYSQL_PASSWORD: ${DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql

  portal:
    environment:
      DATABASE_URL: mysql+pymysql://wpn_user:${DB_PASSWORD}@mysql:3306/wpn_radius

  freeradius:
    environment:
      DATABASE_URL: mysql+pymysql://wpn_user:${DB_PASSWORD}@mysql:3306/wpn_radius

volumes:
  mysql_data:
```

---

## 📁 Standalone with SQLite (Shared File)

**When to use:** Development, testing, small deployments  
**Database:** SQLite 3  
**Complexity:** ⭐ (Simple)  
**Performance:** ⭐⭐ (Limited)  
**Recommended for:** Dev/test ONLY

**⚠️ WARNING:** Not recommended for production due to limited concurrent write performance.

### docker-compose.yml:

```yaml
version: '3.8'

services:
  portal:
    environment:
      DATABASE_URL: sqlite:////data/shared.db
    volumes:
      - ./data:/data  # Shared volume

  freeradius:
    environment:
      DATABASE_URL: sqlite:////data/shared.db
    volumes:
      - ./data:/data  # Same volume
```

**When SQLite is OK:**
- ✅ Development and testing
- ✅ Single-user demos
- ✅ < 10 concurrent users
- ❌ Production deployments
- ❌ High traffic
- ❌ Multiple concurrent writers

---

## ☁️ External/Managed Database

**When to use:** Cloud deployments (AWS, GCP, Azure)  
**Database:** RDS, Cloud SQL, Azure Database  
**Complexity:** ⭐⭐⭐ (Higher)  
**Performance:** ⭐⭐⭐⭐⭐ (Excellent)  
**Recommended for:** Enterprise, multi-region

### Configuration:

```yaml
# .env or config
DATABASE_URL=postgresql://user:password@my-db.region.rds.amazonaws.com:5432/wpn_radius
```

**Benefits:**
- Managed backups
- High availability
- Automatic updates
- Easy scaling

**Considerations:**
- Network latency (use same region)
- Connection limits (configure pool size)
- Cost

---

## 🔄 Auto-Detection Logic

The application automatically detects deployment mode:

**HA Addon Mode detected when:**
- File `/data/options.json` exists, OR
- Environment variable `SUPERVISOR_TOKEN` is set

**Standalone Mode detected when:**
- Neither of the above conditions are true

**Override detection:**
Set `RUN_MODE` environment variable:
```bash
RUN_MODE=addon    # Force addon mode
RUN_MODE=standalone  # Force standalone mode
```

---

## 📊 Comparison Matrix

| Database | HA Addon | Standalone | Complexity | Performance | Concurrent | Production |
|----------|----------|------------|------------|-------------|------------|------------|
| **MariaDB (HA)** | ✅ | ❌ | Medium | Excellent | High | ✅ |
| **PostgreSQL** | ❌ | ✅ | Medium | Excellent | Very High | ✅ |
| **MySQL/MariaDB** | ❌ | ✅ | Medium | Excellent | High | ✅ |
| **SQLite** | ❌ | ✅ | Simple | Limited | Low | ❌ |
| **Cloud DB** | ✅ | ✅ | Higher | Excellent | Very High | ✅ |

---

## 🚀 Quick Start Commands

### HA Addon Mode:
```bash
# 1. Install MariaDB addon
# 2. Create database (SQL commands above)
# 3. Configure both addons with database_url
# 4. Add password to secrets.yaml
# 5. Restart both addons
```

### Standalone (PostgreSQL):
```bash
# 1. Copy docker-compose.yml
# 2. Create .env file with DB_PASSWORD
# 3. Start services
docker-compose up -d

# 4. Check logs
docker-compose logs -f
```

### Standalone (SQLite - Dev Only):
```bash
# 1. Update docker-compose.yml with SQLite config
# 2. Create data directory
mkdir -p ./data

# 3. Start services
docker-compose up -d
```

---

## 🔧 Testing Database Connection

### From Portal/FreeRADIUS container:

**PostgreSQL:**
```bash
psql postgresql://wpn_user:password@postgres:5432/wpn_radius -c "SELECT 1"
```

**MySQL/MariaDB:**
```bash
mysql -h mysql -u wpn_user -p wpn_radius -e "SELECT 1"
```

**SQLite:**
```bash
sqlite3 /data/shared.db "SELECT 1"
```

---

## ⚙️ Configuration Reference

### Required Environment Variables:

```bash
# Database URL (auto-detected if not provided)
DATABASE_URL=<connection-string>

# Deployment mode (optional, auto-detected)
RUN_MODE=auto|addon|standalone

# Connection pool settings (optional)
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
```

### Connection String Formats:

```bash
# PostgreSQL
DATABASE_URL=postgresql://user:password@host:5432/database
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/database

# MySQL/MariaDB
DATABASE_URL=mysql+pymysql://user:password@host:3306/database

# SQLite
DATABASE_URL=sqlite:////absolute/path/to/database.db
```

---

## 📝 Migration Checklist

- [ ] Choose database option based on deployment
- [ ] Setup database (create DB, user, permissions)
- [ ] Configure both Portal and FreeRADIUS with same DATABASE_URL
- [ ] Test database connection from both services
- [ ] Run migration script (if migrating from old setup)
- [ ] Verify both services start successfully
- [ ] Test end-to-end: Portal creates client → FreeRADIUS sees it
- [ ] Monitor logs for any database errors
- [ ] Backup database regularly

---

## 🆘 Troubleshooting

### Connection Refused

**Problem:** `Connection refused` or `Cannot connect to database`

**Solutions:**
1. Check database service is running: `docker-compose ps`
2. Verify hostname in DATABASE_URL (use service name from docker-compose)
3. Check network connectivity between containers
4. Verify credentials are correct

### Authentication Failed

**Problem:** `Access denied` or `Authentication failed`

**Solutions:**
1. Check username and password in DATABASE_URL
2. Verify user has been created in database
3. Verify user has correct permissions (GRANT statement)
4. Check password doesn't have special characters that need URL encoding

### Table Not Found

**Problem:** `Table 'radius_clients' doesn't exist`

**Solutions:**
1. Run database migrations from Portal (creates tables)
2. Check DATABASE_URL points to correct database
3. Verify both services use same DATABASE_URL

### Concurrent Write Errors (SQLite only)

**Problem:** `Database is locked` or `SQLITE_BUSY`

**Solutions:**
1. Enable WAL mode (handled automatically)
2. Consider upgrading to PostgreSQL/MySQL for production
3. Reduce concurrent writes
4. Increase timeout settings

---

## 📚 Additional Resources

- [Implementation Plan](/Users/jolipton/.cursor/plans/freeradius_mariadb_refactor.plan.md)
- [Agent Handoff Doc](/Users/jolipton/Projects/hassio-addons-1/freeradius/AGENT_HANDOFF.md)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [MariaDB Docker](https://hub.docker.com/_/mariadb)

---

**Last Updated:** 2026-01-13  
**Version:** 1.0
