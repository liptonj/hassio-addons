# Settings Management System

## Overview

The Meraki WPN Portal features a **complete settings management system** that allows **ALL settings to be configured via the Admin UI** in standalone mode, including:

- ✅ **Meraki API Key** - Change API credentials without restart
- ✅ **Database Connection** - Switch databases on the fly
- ✅ **Admin Credentials** - Change username/password
- ✅ **OAuth Secrets** - Configure Duo/Entra ID
- ✅ **All Application Settings** - Branding, network defaults, etc.

### Key Features

1. **Encrypted Secrets Storage** - All secrets (API keys, passwords, tokens) are encrypted using Fernet
2. **Persistent Configuration** - Settings saved to `/config/portal_settings.json`
3. **Priority System** - Environment variables > Settings file > Defaults
4. **Backup & Restore** - Export/import settings with automatic backups
5. **Test Before Apply** - Validate connections before saving
6. **Hot Reload** - Most settings apply without restart

---

## Architecture

### Settings Priority (Highest to Lowest)

1. **Environment Variables** - Always take precedence
2. **Settings File** (`portal_settings.json`) - Editable via UI in standalone mode
3. **Defaults** - Hard-coded in `app/config.py`

### File Structure

```
/config/
├── portal_settings.json          # Current settings (secrets encrypted)
├── portal_settings.json.bak      # Automatic backup before each save
└── portal_settings.json.reset_backup_* # Backup before reset
```

### Example Settings File

```json
{
  "admin_username": "myadmin",
  "default_network_id": "L_123456789",
  "enable_oauth": true,
  "oauth_provider": "duo",
  "property_name": "Downtown Apartments",
  "secrets": {
    "admin_password_hash": "gAAAAABm...",
    "duo_client_secret": "gAAAAABm...",
    "meraki_api_key": "gAAAAABm..."
  }
}
```

---

## API Endpoints

### 1. Get All Settings

```http
GET /api/admin/settings/all
Authorization: Bearer YOUR_JWT_TOKEN
```

**Response:**
```json
{
  "run_mode": "standalone",
  "meraki_api_key": "***",
  "property_name": "My Property",
  "admin_username": "admin",
  "enable_oauth": false,
  "duo_client_secret": "***",
  ...
}
```

**Note:** Secrets are masked with `***`

### 2. Update Settings

```http
PUT /api/admin/settings/all
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "meraki_api_key": "your-new-api-key",
  "property_name": "New Property Name",
  "admin_password": "new_password_here",
  "database_url": "sqlite:////config/new_db.db",
  "enable_oauth": true,
  "oauth_provider": "duo",
  "duo_client_id": "your-duo-client-id",
  "duo_client_secret": "your-duo-secret",
  "duo_api_hostname": "api-xxxxx.duosecurity.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings saved successfully. RESTART REQUIRED for some changes to take effect.",
  "settings": { ... },
  "requires_restart": true
}
```

**Fields Requiring Restart:**
- `run_mode`
- `database_url`
- `secret_key`
- `meraki_api_key`
- `ha_url` / `ha_token`
- `enable_oauth` / `oauth_provider`
- OAuth secrets (`duo_client_secret`, `entra_client_secret`)

### 3. Test Connection Settings

Test settings **before** saving to ensure they work:

```http
POST /api/admin/settings/test-connection
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "meraki_api_key": "test-this-key",
  "database_url": "sqlite:////config/test.db",
  "enable_oauth": true,
  "oauth_provider": "duo",
  "duo_client_id": "...",
  "duo_client_secret": "...",
  "duo_api_hostname": "api-xxxxx.duosecurity.com"
}
```

**Response:**
```json
{
  "overall_success": true,
  "tests": {
    "meraki_api": {
      "success": true,
      "message": "Connected successfully. Found 1 organization(s).",
      "organizations": [...]
    },
    "database": {
      "success": true,
      "message": "Database connection successful."
    },
    "duo_oauth": {
      "success": true,
      "message": "Duo connection successful."
    }
  }
}
```

### 4. Export Settings (Backup)

```http
GET /api/admin/settings/export?include_secrets=false
Authorization: Bearer YOUR_JWT_TOKEN
```

**Response:**
```json
{
  "success": true,
  "settings": { ... },
  "includes_secrets": false,
  "warning": null
}
```

**With Secrets:**
```http
GET /api/admin/settings/export?include_secrets=true
```

⚠️ **Warning:** Only use `include_secrets=true` for secure backups!

### 5. Import Settings (Restore)

```http
POST /api/admin/settings/import
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "property_name": "Restored Property",
  "meraki_api_key": "restored-key",
  ...
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings imported successfully. RESTART REQUIRED."
}
```

### 6. Reset to Defaults

```http
POST /api/admin/settings/reset
Authorization: Bearer YOUR_JWT_TOKEN
```

**Response:**
```json
{
  "success": true,
  "message": "Settings reset to defaults. Backup created. RESTART REQUIRED."
}
```

---

## Security

### Encryption

All secrets are encrypted using **Fernet** (symmetric encryption) before being saved to disk.

**Encryption Key:**
```bash
# Generate a new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in environment
export SETTINGS_ENCRYPTION_KEY=your-generated-key
```

**⚠️ IMPORTANT:** 
- Keep the `SETTINGS_ENCRYPTION_KEY` secret!
- Use the **same key** across restarts or settings will be unreadable
- If you lose the key, you'll need to reset settings to defaults

### Secret Fields

The following fields are **automatically encrypted** when saved:

- `secret_key`
- `admin_password`
- `admin_password_hash`
- `ha_token`
- `supervisor_token`
- `meraki_api_key`
- `duo_client_secret`
- `entra_client_secret`
- `oauth_client_secret`

### Access Control

- Settings management is **only available in standalone mode**
- Requires `EDITABLE_SETTINGS=true` (default in standalone)
- All endpoints require **admin authentication** (JWT token)
- In Home Assistant mode, settings must be edited via `config.yaml`

---

## Usage Examples

### 1. Initial Setup via UI

```bash
# Step 1: Login
curl -X POST "http://localhost:8080/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  -o token.json

TOKEN=$(jq -r '.access_token' token.json)

# Step 2: Test Meraki API key
curl -X POST "http://localhost:8080/api/admin/settings/test-connection" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"meraki_api_key":"your-key-here"}'

# Step 3: Save settings
curl -X PUT "http://localhost:8080/api/admin/settings/all" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "meraki_api_key": "your-key-here",
    "property_name": "My Apartments",
    "admin_password": "new_secure_password",
    "default_network_id": "L_123456789",
    "primary_color": "#00A4E4"
  }'

# Step 4: Restart if needed
docker restart meraki-wpn-portal
```

### 2. Enable OAuth via Settings

```bash
# Step 1: Test Duo connection
curl -X POST "http://localhost:8080/api/admin/settings/test-connection" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_oauth": true,
    "oauth_provider": "duo",
    "duo_client_id": "your-client-id",
    "duo_client_secret": "your-secret",
    "duo_api_hostname": "api-xxxxx.duosecurity.com",
    "oauth_callback_url": "https://portal.example.com/api/auth/callback"
  }'

# Step 2: If test passes, save settings
curl -X PUT "http://localhost:8080/api/admin/settings/all" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_oauth": true,
    "oauth_provider": "duo",
    "oauth_admin_only": true,
    "duo_client_id": "your-client-id",
    "duo_client_secret": "your-secret",
    "duo_api_hostname": "api-xxxxx.duosecurity.com",
    "oauth_callback_url": "https://portal.example.com/api/auth/callback"
  }'

# Step 3: Restart to apply OAuth changes
docker restart meraki-wpn-portal
```

### 3. Change Database

```bash
# Test new database connection
curl -X POST "http://localhost:8080/api/admin/settings/test-connection" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"database_url":"postgresql://user:pass@localhost/dbname"}'

# If test passes, update
curl -X PUT "http://localhost:8080/api/admin/settings/all" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"database_url":"postgresql://user:pass@localhost/dbname"}'

# Restart required
docker restart meraki-wpn-portal
```

### 4. Backup & Restore

```bash
# Export with secrets for full backup
curl -X GET "http://localhost:8080/api/admin/settings/export?include_secrets=true" \
  -H "Authorization: Bearer $TOKEN" \
  > settings_backup.json

# Later, restore from backup
curl -X POST "http://localhost:8080/api/admin/settings/import" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @settings_backup.json
```

---

## Environment Variables

### Enable Settings Management

```bash
# Standalone mode (default)
RUN_MODE=standalone

# Allow settings to be edited via UI (default: true in standalone)
EDITABLE_SETTINGS=true

# Encryption key for secrets (REQUIRED for persistent secrets)
SETTINGS_ENCRYPTION_KEY=your-fernet-key-here
```

### Disable Settings Management

```bash
# Use environment variables only (no file-based settings)
EDITABLE_SETTINGS=false

# Or run in Home Assistant mode
RUN_MODE=homeassistant
```

---

## Troubleshooting

### "Settings cannot be edited in this mode"

**Cause:** Not in standalone mode or `EDITABLE_SETTINGS=false`

**Solution:**
```bash
export RUN_MODE=standalone
export EDITABLE_SETTINGS=true
```

### "Failed to decrypt value"

**Cause:** `SETTINGS_ENCRYPTION_KEY` changed or missing

**Solution:**
```bash
# Option 1: Restore original encryption key
export SETTINGS_ENCRYPTION_KEY=your-original-key

# Option 2: Reset settings (loses encrypted secrets)
curl -X POST "http://localhost:8080/api/admin/settings/reset" \
  -H "Authorization: Bearer $TOKEN"
```

### Settings Not Persisting After Restart

**Cause:** Settings file not in persistent volume

**Solution:**
```yaml
# docker-compose.yml
volumes:
  - ./config:/config  # Ensure /config is mounted
```

### "Test connection failed"

**Cause:** Invalid credentials or network issue

**Solution:**
- Verify credentials are correct
- Check network connectivity
- Review error message in response
- Check application logs

---

## Best Practices

1. **Always Test First** - Use `/settings/test-connection` before saving
2. **Backup Before Major Changes** - Export settings before big updates
3. **Keep Encryption Key Safe** - Store `SETTINGS_ENCRYPTION_KEY` in secrets manager
4. **Use Environment for Secrets in Production** - More secure than file-based storage
5. **Monitor Logs** - Check logs after settings changes
6. **Restart When Required** - Some settings need restart to take effect

---

## UI Integration

The admin dashboard should provide a settings page with:

1. **Tabbed Interface:**
   - General (property name, branding)
   - Network (Meraki API, network defaults)
   - Authentication (OAuth, admin credentials)
   - Database
   - Advanced

2. **Features:**
   - "Test Connection" button for each section
   - Visual indicator for "Requires Restart"
   - Export/Import buttons
   - Reset to defaults with confirmation
   - Real-time validation

3. **Example React Component:**

```tsx
const SettingsPage = () => {
  const [settings, setSettings] = useState<AllSettings | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  
  const loadSettings = async () => {
    const response = await fetch('/api/admin/settings/all', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    setSettings(await response.json());
  };
  
  const testConnection = async (testData: any) => {
    const response = await fetch('/api/admin/settings/test-connection', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(testData)
    });
    return await response.json();
  };
  
  const saveSettings = async () => {
    const response = await fetch('/api/admin/settings/all', {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    });
    const result = await response.json();
    
    if (result.requires_restart) {
      alert('Settings saved! Restart required.');
    }
  };
  
  // ... render form ...
};
```

---

## References

- **Settings Manager Code:** `backend/app/core/settings_manager.py`
- **Settings Schemas:** `backend/app/schemas/settings.py`
- **Admin API:** `backend/app/api/admin.py`
- **Configuration:** `backend/app/config.py`
