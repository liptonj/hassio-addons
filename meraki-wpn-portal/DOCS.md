# Meraki WPN Portal - Documentation

## Overview

The Meraki WPN Portal is a Home Assistant add-on that provides a self-service WiFi registration portal for Cisco Meraki networks using Identity PSK (IPSK).

## Installation

1. Navigate to **Settings** → **Add-ons** in Home Assistant
2. Click the **Add-on Store** button
3. Click the three-dot menu and select **Repositories**
4. Add the repository URL: `https://github.com/yourusername/hassio-addons`
5. Find "Meraki WPN Portal" and click **Install**

## Configuration

### Required Settings

| Option | Description |
|--------|-------------|
| `ha_token` | A long-lived access token for Home Assistant API access |
| `default_network_id` | Your Meraki network ID (found in Meraki Dashboard URL) |

### Getting a Long-Lived Access Token

1. Go to your Home Assistant profile page
2. Scroll down to "Long-Lived Access Tokens"
3. Click "Create Token"
4. Give it a name like "Meraki WPN Portal"
5. Copy the token and paste it into the add-on configuration

### Finding Your Meraki Network ID

1. Log into the Meraki Dashboard
2. Navigate to your network
3. Look at the URL - it will contain something like `L_123456789012345678`
4. Copy this ID into your configuration

## Features

### Public Registration Portal

The public portal is accessible without authentication and allows residents to:

- Register for WiFi access by providing their name and email
- Select their unit/room from a dropdown (if configured)
- Enter an invite code if required
- Receive WiFi credentials including SSID, password, and QR code

### My Network Page

Registered users can retrieve their credentials by entering their email address.

### Admin Dashboard

Administrators can access the dashboard at `/admin` to:

- View statistics on registrations and IPSKs
- Manage individual IPSKs (create, revoke, delete)
- Generate and manage invite codes
- View current settings

## Unit/Room Selection

You can configure how units are presented to users:

### Option 1: Home Assistant Areas (Recommended)

Set `unit_source: ha_areas` to automatically populate the dropdown with areas from Home Assistant.

### Option 2: Manual List

Set `unit_source: manual_list` and provide a list:

```yaml
manual_units:
  - "101"
  - "102"
  - "201"
  - "202"
```

### Option 3: Free Text

Set `unit_source: free_text` to allow users to type any unit number.

## Authentication Methods

### Self-Registration

When `auth_self_registration: true`, anyone can register for WiFi access. This is suitable for open environments.

### Invite Codes

When `auth_invite_codes: true`, you can require or optionally accept invite codes. Generate codes through the admin dashboard.

### Combining Methods

- Both enabled: Users can register freely OR use an invite code
- Only invite codes: Registration requires a valid invite code
- Only self-registration: Standard open registration

## IPSK Settings

### Duration

Set `default_ipsk_duration_hours` to control how long IPSKs remain valid:

- `0`: Permanent (no expiration)
- `24`: 24 hours
- `168`: 1 week
- `720`: 30 days

### Passphrase Length

Set `passphrase_length` between 8 and 32 characters. Longer passphrases are more secure.

## Ports

| Port | Description |
|------|-------------|
| 8080 | Public registration portal |
| 8099 | Ingress port (internal to HA) |

## Troubleshooting

### "Failed to connect to Home Assistant"

1. Verify your `ha_token` is correct
2. Ensure the token hasn't expired
3. Check that `ha_url` is correct (usually `http://supervisor/core` for add-ons)

### "Failed to create IPSK"

1. Verify your `default_network_id` is correct
2. Ensure Identity PSK is enabled on your Meraki SSID
3. Check that the meraki_ha integration is properly configured

### Registration Not Working

1. Check the add-on logs for error messages
2. Verify all required fields are configured
3. Test the Home Assistant connection in the admin dashboard

## API Reference

### Public Endpoints

```
GET  /api/options              - Get portal configuration
POST /api/register             - Register for WiFi access
GET  /api/my-network           - Retrieve existing credentials
GET  /api/areas                - Get available units/areas
```

### Admin Endpoints (Require Authentication)

```
GET    /api/admin/ipsks              - List all IPSKs
POST   /api/admin/ipsks              - Create new IPSK
DELETE /api/admin/ipsks/{id}         - Delete IPSK
POST   /api/admin/ipsks/{id}/revoke  - Revoke IPSK

GET    /api/admin/invite-codes       - List invite codes
POST   /api/admin/invite-codes       - Create invite code
DELETE /api/admin/invite-codes/{id}  - Delete invite code

GET    /api/admin/dashboard          - Dashboard statistics
GET    /api/admin/settings           - Current settings
```

## Security Considerations

1. **Always use HTTPS** in production for the public portal
2. **Protect your HA token** - treat it like a password
3. **Use invite codes** for controlled environments
4. **Monitor registrations** through the admin dashboard
5. **Revoke unused IPSKs** regularly

## Support

For issues and feature requests, please use the GitHub Issues page.
