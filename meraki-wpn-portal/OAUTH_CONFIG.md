# Meraki WPN Portal - Configuration Examples

## OAuth/SSO Configuration

### Duo Security (Universal SDK v4)

The implementation uses **Duo Universal SDK v4** with the modern Universal Prompt (not the deprecated iframe v2). This provides OIDC-based authentication with enhanced security and accessibility.

**Reference**: [Duo Web SDK v4 Documentation](https://duo.com/docs/duoweb)

```bash
# Enable OAuth
ENABLE_OAUTH=true
OAUTH_PROVIDER=duo

# Duo Universal SDK credentials (from Duo Admin Panel)
DUO_CLIENT_ID=your_duo_integration_key
DUO_CLIENT_SECRET=your_duo_secret_key
DUO_API_HOSTNAME=api-xxxxxxxx.duosecurity.com

# Callback URL (update based on your domain)
OAUTH_CALLBACK_URL=https://your-domain.com/api/auth/callback

# Optional: Restrict OAuth to admin portal only
OAUTH_ADMIN_ONLY=false

# Auto-provision users on first login
OAUTH_AUTO_PROVISION=true
```

**Setup Duo Universal Prompt:**
1. Log in to [Duo Admin Panel](https://admin.duosecurity.com/)
2. Go to **Applications** → **Protect an Application**
3. Search for **Web SDK** and click **Protect**
4. Note the following from the application details:
   - **Client ID** (Integration key)
   - **Client secret** (Secret key)  
   - **API hostname** (e.g., `api-xxxxxxxx.duosecurity.com`)
5. Add your **Redirect URI**: `https://your-domain.com/api/auth/callback`
6. Ensure "Universal Prompt" is activated (not the legacy iframe prompt)

**Duo Universal Prompt Features:**
- ✅ Modern, accessible UI with OIDC/OAuth 2.0
- ✅ Supports Duo Push, SMS, phone call, hardware tokens
- ✅ Passwordless authentication with Duo Passport
- ✅ Device Trust policies
- ✅ Phishing-resistant MFA
- ❌ **Does NOT use iframe** (deprecated v2 SDK)

**Important**: The Duo Universal SDK v4 uses a redirect-based flow, not an iframe. Traditional Duo Prompt (iframe) reached end of support on March 30, 2024.

### Microsoft Entra ID (Azure AD)

```bash
# Enable OAuth
ENABLE_OAUTH=true
OAUTH_PROVIDER=entra

# Entra ID OAuth credentials
ENTRA_CLIENT_ID=your_application_client_id
ENTRA_CLIENT_SECRET=your_client_secret
ENTRA_TENANT_ID=your_tenant_id

# Callback URL (update based on your domain)
OAUTH_CALLBACK_URL=https://your-domain.com/api/auth/callback

# Optional: Restrict OAuth to admin portal only
OAUTH_ADMIN_ONLY=false

# Auto-provision users on first login
OAUTH_AUTO_PROVISION=true
```

**Setup Entra ID:**
1. Go to Azure Portal → Azure Active Directory
2. App registrations → New registration
3. Set Redirect URI to your callback URL
4. Copy Application (client) ID and Directory (tenant) ID
5. Certificates & secrets → New client secret
6. API permissions → Add Microsoft Graph → openid, profile, email

## Standalone Mode with Editable Settings

```bash
# Run mode
RUN_MODE=standalone

# Allow settings changes via API
EDITABLE_SETTINGS=true

# Meraki Dashboard API
MERAKI_API_KEY=your_meraki_api_key
DEFAULT_NETWORK_ID=L_123456789
DEFAULT_SSID_NUMBER=0

# Portal configuration
PROPERTY_NAME=My Property
PRIMARY_COLOR=#00A4E4

# Database
DATABASE_URL=sqlite:////data/meraki_wpn_portal.db

# Security
SECRET_KEY=your-secret-key
```

## Usage

### OAuth Login Flow

**Admin Login:**
```
1. Navigate to /admin
2. Click "Login with Duo" or "Login with Microsoft"
3. Authenticate with OAuth provider
4. Redirect back with access token
```

**Public Registration with OAuth:**
```
1. Navigate to /
2. Click "Sign in with Duo/Microsoft"
3. Authenticate and auto-provision
4. Complete WiFi registration
```

### API Endpoints

```bash
# Initiate OAuth login
GET /api/auth/login/duo
GET /api/auth/login/entra

# OAuth callback (automatic)
GET /api/auth/callback

# Get settings (admin)
GET /api/admin/settings
Authorization: Bearer <token>

# Update settings (standalone mode only)
PUT /api/admin/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "property_name": "Updated Property",
  "primary_color": "#FF5733",
  "enable_oauth": true
}
```

## Security Notes

1. **Always use HTTPS in production** - OAuth requires secure connections
2. **Keep secrets secure** - Never commit client secrets to version control
3. **Validate redirect URIs** - Only whitelist your domains in OAuth apps
4. **Use strong SECRET_KEY** - Generate with `openssl rand -hex 32`
5. **Restrict admin access** - Set `OAUTH_ADMIN_ONLY=true` for public portals
