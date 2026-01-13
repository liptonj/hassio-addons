# OAuth/SSO Authentication Setup

This portal supports **local authentication** (username/password) as well as **OAuth/SSO** with:
- **Duo Universal Prompt** (OIDC-based, SDK v4)
- **Microsoft Entra ID** (Azure AD)

## Default Local Authentication

**Default credentials:**
- Username: `admin`
- Password: `admin`

⚠️ **CHANGE THESE IMMEDIATELY IN PRODUCTION!**

### Changing Local Admin Credentials

#### Option 1: Via Admin API (Recommended)
```bash
curl -X POST "http://localhost:8080/api/admin/change-password" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d "current_password=admin&new_password=YourNewSecurePassword"
```

The response will include a password hash. Save it to `ADMIN_PASSWORD_HASH` environment variable.

#### Option 2: Via Environment Variables
```bash
# Set in .env or docker-compose.yml
ADMIN_USERNAME=youradmin
ADMIN_PASSWORD=YourSecurePassword

# Or use a pre-hashed password:
ADMIN_PASSWORD_HASH=$2b$12$...your-bcrypt-hash...
```

---

## OAuth/SSO Configuration

### Authentication Modes

1. **Local Only** (default)
   - Admin login: Username/password
   - Public registration: Email/phone
   
2. **OAuth for Admin Only**
   - Admin login: OAuth (Duo/Entra ID)
   - Public registration: Still uses local methods
   - Set `OAUTH_ADMIN_ONLY=true`
   
3. **OAuth for All**
   - Admin login: OAuth
   - Public registration: OAuth (optional self-registration)
   - Set `OAUTH_ADMIN_ONLY=false`

---

## Duo Universal Prompt Setup

Duo's Universal Prompt uses **OIDC** (OpenID Connect) for authentication with 2FA.

### 1. Create Duo Application

1. Log in to [Duo Admin Panel](https://admin.duosecurity.com)
2. Go to **Applications** > **Protect an Application**
3. Search for **Web SDK** and click **Protect**
4. Note your credentials:
   - **Client ID**
   - **Client Secret**
   - **API Hostname** (e.g., `api-xxxxx.duosecurity.com`)

### 2. Configure Redirect URI

In Duo application settings, add:
```
http://your-portal-domain.com/api/auth/callback
```

### 3. Environment Variables

```bash
ENABLE_OAUTH=true
OAUTH_PROVIDER=duo
OAUTH_ADMIN_ONLY=true  # or false for public registration

DUO_CLIENT_ID=your-client-id
DUO_CLIENT_SECRET=your-client-secret
DUO_API_HOSTNAME=api-xxxxx.duosecurity.com
OAUTH_CALLBACK_URL=http://your-portal-domain.com/api/auth/callback
```

### 4. Test Connection

```bash
# Health check
curl http://localhost:8080/api/auth/verify

# Initiate login (will redirect to Duo)
curl http://localhost:8080/api/auth/login/duo?username=testuser
```

---

## Microsoft Entra ID Setup

### 1. Register Application in Azure

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure:
   - **Name**: Meraki WPN Portal
   - **Supported account types**: Choose based on your needs
   - **Redirect URI**: `http://your-portal-domain.com/api/auth/callback`

### 2. Create Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Save the **Value** (you won't see it again!)

### 3. API Permissions

Add the following **Microsoft Graph** permissions:
- `openid` (for OIDC)
- `profile` (for user info)
- `email` (for user email)

Grant admin consent for your organization.

### 4. Environment Variables

```bash
ENABLE_OAUTH=true
OAUTH_PROVIDER=entra
OAUTH_ADMIN_ONLY=true  # or false for public registration

ENTRA_CLIENT_ID=your-application-client-id
ENTRA_CLIENT_SECRET=your-client-secret-value
ENTRA_TENANT_ID=your-tenant-id  # or "common" for multi-tenant
OAUTH_CALLBACK_URL=http://your-portal-domain.com/api/auth/callback
```

### 5. Test Connection

```bash
# Health check
curl http://localhost:8080/api/auth/verify

# Initiate login (will redirect to Microsoft)
curl http://localhost:8080/api/auth/login/entra
```

---

## Admin Portal OAuth Management

### View OAuth Settings
```bash
GET /api/admin/oauth-settings
Authorization: Bearer YOUR_JWT_TOKEN
```

### Update OAuth Settings (Standalone Mode Only)
```bash
PUT /api/admin/oauth-settings
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "enable_oauth": true,
  "oauth_provider": "duo",
  "oauth_admin_only": true,
  "duo_client_id": "...",
  "duo_client_secret": "...",
  "duo_api_hostname": "api-xxxxx.duosecurity.com"
}
```

**Note:** In Home Assistant add-on mode, OAuth settings must be configured in `config.yaml`.

---

## Login Flow

### Local Login
```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "yourpassword"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### OAuth Login

1. **Redirect user to:**
   ```
   GET /api/auth/login/duo
   # or
   GET /api/auth/login/entra
   ```

2. **User completes authentication** at provider (Duo/Entra ID)

3. **Provider redirects back to:**
   ```
   GET /api/auth/callback?code=...&state=...
   ```

4. **Portal issues JWT token** and redirects to:
   ```
   GET /auth-success?token=eyJ...
   ```

5. **Frontend stores token** and redirects to admin dashboard

---

## Troubleshooting

### OAuth provider health check failed
- Verify client ID and secret are correct
- Check network connectivity to provider
- Ensure API hostname is correct (Duo)

### State mismatch error
- Check that sessions are enabled in FastAPI
- Verify callback URL matches exactly

### Invalid redirect URI
- Ensure callback URL in provider settings matches `OAUTH_CALLBACK_URL`
- Include protocol (http/https) and port if non-standard

### User not found after OAuth
- Enable `oauth_auto_provision=true` to automatically create users
- Or manually create user accounts before OAuth login

---

## Security Best Practices

1. **Always use HTTPS in production** - OAuth requires secure connections
2. **Rotate client secrets regularly** - Update both provider and environment
3. **Use password hash** - Set `ADMIN_PASSWORD_HASH` instead of plain `ADMIN_PASSWORD`
4. **Enable OAuth for admin** - Use `OAUTH_ADMIN_ONLY=true` for sensitive operations
5. **Monitor login attempts** - Check logs for failed authentication
6. **Restrict callback URLs** - Only allow your actual domain in provider settings

---

## Example Docker Compose with OAuth

```yaml
version: '3.8'
services:
  meraki-wpn-portal:
    image: ghcr.io/yourusername/meraki-wpn-portal:latest
    ports:
      - "8080:8080"
    environment:
      # Run mode
      RUN_MODE: standalone
      
      # Meraki API
      MERAKI_API_KEY: your-api-key
      
      # Admin credentials
      ADMIN_USERNAME: admin
      ADMIN_PASSWORD_HASH: $2b$12$...
      
      # OAuth - Duo
      ENABLE_OAUTH: "true"
      OAUTH_PROVIDER: duo
      OAUTH_ADMIN_ONLY: "true"
      DUO_CLIENT_ID: your-duo-client-id
      DUO_CLIENT_SECRET: your-duo-secret
      DUO_API_HOSTNAME: api-xxxxx.duosecurity.com
      OAUTH_CALLBACK_URL: https://portal.example.com/api/auth/callback
      
      # Security
      SECRET_KEY: change-this-to-a-random-string
      
    volumes:
      - ./data:/config
```

---

## References

- [Duo Universal Prompt Documentation](https://duo.com/docs/duoweb)
- [Microsoft Entra ID OIDC](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-protocols-oidc)
- [OAuth 2.0 Authorization Code Flow](https://oauth.net/2/grant-types/authorization-code/)
