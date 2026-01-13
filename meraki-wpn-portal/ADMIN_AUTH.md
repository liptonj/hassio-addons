# Admin Authentication & OAuth Configuration Summary

## Overview

The Meraki WPN Portal now supports **multiple authentication methods** for admin access:

1. **Local Authentication** - Username/password (always available)
2. **OAuth/SSO** - Duo Universal Prompt (OIDC) and Microsoft Entra ID
3. **Hybrid Mode** - Mix local and OAuth as needed

---

## Quick Start

### Default Admin Credentials

**⚠️ CHANGE IMMEDIATELY IN PRODUCTION!**

```
Username: admin
Password: admin
```

### Login Endpoints

```bash
# Local login
POST /api/auth/login
{
  "username": "admin",
  "password": "admin"
}

# OAuth login (redirects to provider)
GET /api/auth/login/duo?username=user@example.com
GET /api/auth/login/entra

# Check auth status
GET /api/auth/verify
```

---

## Configuration Options

### Environment Variables

```bash
# Admin Credentials (Local Auth)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
ADMIN_PASSWORD_HASH=  # Optional: use pre-hashed password

# OAuth/SSO
ENABLE_OAUTH=false
OAUTH_PROVIDER=none  # or "duo" or "entra"
OAUTH_ADMIN_ONLY=false  # If true, only admin uses OAuth

# Duo (OIDC / SDK v4)
DUO_CLIENT_ID=
DUO_CLIENT_SECRET=
DUO_API_HOSTNAME=api-xxxxx.duosecurity.com

# Microsoft Entra ID
ENTRA_CLIENT_ID=
ENTRA_CLIENT_SECRET=
ENTRA_TENANT_ID=

# OAuth Callback
OAUTH_CALLBACK_URL=http://your-domain.com/api/auth/callback
```

### Home Assistant config.yaml

```yaml
options:
  admin_username: "admin"
  admin_password: "admin"
  
  enable_oauth: false
  oauth_provider: "none"
  oauth_admin_only: false
  
  duo_client_id: ""
  duo_client_secret: ""
  duo_api_hostname: ""
  
  entra_client_id: ""
  entra_client_secret: ""
  entra_tenant_id: ""
  
  oauth_callback_url: ""
```

---

## Admin API Endpoints

### 1. Change Password (Local Auth)

```http
POST /api/admin/change-password
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "current_password": "admin",
  "new_password": "YourNewSecurePassword123!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Password changed successfully",
  "new_password_hash": "$2b$12$...",
  "instruction": "Save this hash to ADMIN_PASSWORD_HASH environment variable"
}
```

### 2. Get OAuth Settings

```http
GET /api/admin/oauth-settings
Authorization: Bearer YOUR_JWT_TOKEN
```

**Response:**
```json
{
  "enable_oauth": true,
  "oauth_provider": "duo",
  "oauth_admin_only": true,
  "oauth_auto_provision": true,
  "duo_client_id": "...",
  "duo_client_secret": "***",
  "duo_api_hostname": "api-xxxxx.duosecurity.com",
  "entra_client_id": "",
  "entra_client_secret": "",
  "entra_tenant_id": "",
  "oauth_callback_url": "http://..."
}
```

### 3. Update OAuth Settings (Standalone Mode Only)

```http
PUT /api/admin/oauth-settings
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "enable_oauth": true,
  "oauth_provider": "duo",
  "oauth_admin_only": true,
  "duo_client_id": "your-client-id",
  "duo_client_secret": "your-secret",
  "duo_api_hostname": "api-xxxxx.duosecurity.com",
  "oauth_callback_url": "https://portal.example.com/api/auth/callback"
}
```

**Response:**
```json
{
  "success": true,
  "message": "OAuth settings updated. Restart required to apply changes."
}
```

---

## Authentication Modes

### Mode 1: Local Only (Default)

```bash
ENABLE_OAUTH=false
ADMIN_USERNAME=admin
ADMIN_PASSWORD=YourSecurePassword
```

- Admin login: Username/password via POST `/api/auth/login`
- Public registration: Email/phone/invite codes

### Mode 2: OAuth for Admin Only

```bash
ENABLE_OAUTH=true
OAUTH_PROVIDER=duo
OAUTH_ADMIN_ONLY=true
DUO_CLIENT_ID=...
DUO_CLIENT_SECRET=...
DUO_API_HOSTNAME=...
```

- Admin login: Duo/Entra ID via GET `/api/auth/login/duo` or `/entra`
- Public registration: Still uses local methods (email/phone/invite)
- **Use case:** Secure admin access with 2FA, while keeping public registration simple

### Mode 3: OAuth for All

```bash
ENABLE_OAUTH=true
OAUTH_PROVIDER=duo
OAUTH_ADMIN_ONLY=false
```

- Admin login: OAuth
- Public registration: OAuth (with auto-provisioning)
- **Use case:** Full SSO integration for both admin and residents

---

## Security Best Practices

### 1. Change Default Credentials Immediately

```bash
# Generate a strong password
openssl rand -base64 24

# Use the admin API to change it
curl -X POST "https://portal.example.com/api/admin/change-password" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d "current_password=admin&new_password=YOUR_STRONG_PASSWORD"

# Save the hash to environment
export ADMIN_PASSWORD_HASH="$2b$12$..."
```

### 2. Use Password Hash in Production

```bash
# Generate hash (use Python bcrypt or admin API)
python3 -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('YourPassword'))"

# Set in environment
ADMIN_PASSWORD_HASH=$2b$12$...
# ADMIN_PASSWORD=  # Leave blank when using hash
```

### 3. Enable OAuth for Admin Access

```bash
ENABLE_OAUTH=true
OAUTH_PROVIDER=duo
OAUTH_ADMIN_ONLY=true
```

Benefits:
- ✅ Multi-factor authentication (Duo)
- ✅ Centralized user management
- ✅ No password storage
- ✅ Audit logs via provider

### 4. Use HTTPS in Production

```bash
# OAuth requires HTTPS
OAUTH_CALLBACK_URL=https://portal.example.com/api/auth/callback
```

### 5. Restrict Callback URLs

In Duo/Entra ID settings:
- ✅ Only allow your actual domain
- ❌ Don't use wildcards
- ❌ Don't allow localhost in production

---

## Duo Universal Prompt (OIDC) Details

### Why OIDC?

Duo's **Universal Prompt** (SDK v4) uses **OpenID Connect (OIDC)** instead of the older Web SDK v2:

**Benefits of OIDC:**
- ✅ Standards-based authentication
- ✅ Better security (no iframes, no inline scripts)
- ✅ Supports modern browsers
- ✅ Future-proof (v2 is deprecated)

### Setup Steps

1. **Create Duo Application**
   - Log in to [Duo Admin Panel](https://admin.duosecurity.com)
   - Applications → Protect an Application → Web SDK
   - Save: Client ID, Client Secret, API Hostname

2. **Configure Redirect URI**
   ```
   https://your-portal.com/api/auth/callback
   ```

3. **Set Environment Variables**
   ```bash
   DUO_CLIENT_ID=your-client-id
   DUO_CLIENT_SECRET=your-secret
   DUO_API_HOSTNAME=api-xxxxx.duosecurity.com
   ```

4. **Test Health Check**
   ```bash
   curl https://your-portal.com/api/auth/verify
   ```

### Login Flow

1. User clicks "Login with Duo"
2. Portal redirects to: `GET /api/auth/login/duo?username=user@example.com`
3. Duo shows Universal Prompt (2FA)
4. User completes 2FA
5. Duo redirects to: `GET /api/auth/callback?code=...&state=...`
6. Portal validates and issues JWT
7. User redirected to admin dashboard with token

---

## Troubleshooting

### "Invalid username or password"
- Check `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables
- If using `ADMIN_PASSWORD_HASH`, verify it's a valid bcrypt hash
- Ensure no trailing whitespace in credentials

### "OAuth provider not enabled"
- Verify `ENABLE_OAUTH=true`
- Check `OAUTH_PROVIDER` matches "duo" or "entra" (case-insensitive)
- Restart the application after changing OAuth settings

### "OAuth provider health check failed"
- **Duo:** Verify `DUO_API_HOSTNAME`, `DUO_CLIENT_ID`, `DUO_CLIENT_SECRET`
- **Entra ID:** Check `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`
- Test network connectivity to provider

### "Settings cannot be edited in this mode"
- OAuth settings can only be updated via Admin API in **standalone mode** with `EDITABLE_SETTINGS=true`
- In Home Assistant mode, edit `config.yaml` instead

### "State mismatch" during OAuth callback
- Ensure sessions are enabled (FastAPI middleware)
- Check that callback URL matches exactly in provider settings
- Verify cookies are allowed in browser

---

## Testing

### Test Local Login
```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

### Test OAuth Initiation
```bash
# Should redirect to Duo/Entra ID
curl -L http://localhost:8080/api/auth/login/duo?username=test@example.com
```

### Test Auth Verification
```bash
curl http://localhost:8080/api/auth/verify
```

---

## References

- **Full OAuth Setup Guide:** [OAUTH_SETUP.md](./OAUTH_SETUP.md)
- **Duo Documentation:** https://duo.com/docs/duoweb
- **Entra ID Documentation:** https://learn.microsoft.com/en-us/azure/active-directory/develop/
- **Environment Variables:** [env.example](./env.example)
