# Settings UI - Comprehensive Admin Portal

## Overview

The Settings UI has been completely rebuilt to provide **full configuration management** in standalone mode.

## Features

### ✅ **1. Meraki API Configuration**
- API key input with show/hide toggle
- Secure masked input by default

### ✅ **2. Admin Security**
- Change admin password with current password verification
- Modal dialog for password changes
- Validation: minimum 8 characters, confirmation matching

### ✅ **3. OAuth / SSO Integration**
- Toggle OAuth on/off
- Support for **Duo Security** and **Microsoft Entra ID**
- Provider-specific configuration fields:
  - **Duo**: Client ID, Client Secret, API Hostname
  - **Entra ID**: Client ID, Client Secret, Tenant ID
- OAuth behavior options:
  - Admin-only mode
  - Auto-provision users
  - Custom callback URL

### ✅ **4. Portal Branding**
- Property name
- Logo URL
- Primary color picker with hex input

### ✅ **5. Network Defaults**
- Default Network ID
- Default SSID Number (0-15)
- Default Group Policy ID
- IPSK Duration (0 = permanent)
- Passphrase Length (8-63 chars)

### ✅ **6. Public Registration Options**
- Self-registration toggle
- Invite codes toggle
- Email verification toggle
- Unit number requirement toggle

### ✅ **7. Actions**
- **Save Changes** - Persist settings to file
- **Test Connection** - Validate Meraki API & OAuth credentials
- **Reset to Defaults** - Reset all settings (creates backup first)

### ✅ **8. User Feedback**
- Success notifications (green)
- Warning notifications (yellow) - e.g., "Restart required"
- Error notifications (red)
- Auto-dismiss after 5 seconds

## Mode Detection

The UI automatically detects the operating mode:

- **Standalone + Editable**: Full UI shown with all inputs
- **Home Assistant Mode**: Read-only view with link to HA config panel
- **Standalone + Non-Editable**: Informational message

## API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/settings/all` | GET | Fetch all settings (secrets masked) |
| `/admin/settings/all` | PUT | Update settings |
| `/admin/settings/test-connection` | POST | Test Meraki API & OAuth |
| `/admin/settings/reset` | POST | Reset to defaults |
| `/admin/change-password` | POST | Change admin password |

## Security

- **Secrets masked by default** - API keys, OAuth secrets shown as `••••••••`
- **Show/hide toggles** - Click eye icon to reveal temporarily
- **No secrets in localStorage** - Only admin JWT token stored
- **Current password required** - For password changes
- **Password strength validation** - Minimum 8 characters

## Visual Design

- Clean, organized sections with icons
- Color-coded notifications
- Responsive layout
- Modal dialogs for critical actions
- Loading states for all async operations

## Testing

To test the Settings UI:

1. **Start in standalone mode**:
   ```bash
   cd frontend && npm run dev
   cd ../backend && uv run fastapi dev app/main.py
   ```

2. **Login as admin** at `http://localhost:5173/admin`

3. **Navigate to Settings** - Click "Settings" in admin nav

4. **Test features**:
   - Change Meraki API key
   - Configure OAuth (Duo or Entra)
   - Update branding
   - Click "Test Connection"
   - Click "Save Changes"
   - Try changing admin password

## File Structure

```
frontend/src/
├── api/client.ts          # API functions added
├── pages/admin/
│   └── Settings.tsx       # Complete UI implementation
```

## Environment Variables

Settings priority (highest to lowest):
1. **Environment variables** (`.env` or Docker `-e`)
2. **Settings file** (`config/portal_settings.json`)
3. **Defaults** (hardcoded in `config.py`)

## Next Steps

- [ ] Add import/export settings feature
- [ ] Add settings validation feedback (real-time)
- [ ] Add OAuth test authentication flow
- [ ] Add network/SSID discovery from Meraki API
- [ ] Add settings history/audit log
