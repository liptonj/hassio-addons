# Meraki WPN Portal

![Meraki WPN Portal](https://img.shields.io/badge/Cisco-Meraki-00A4E4?style=flat-square&logo=cisco)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5?style=flat-square&logo=home-assistant)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react)

A self-service WiFi registration portal for Cisco Meraki networks, designed as a Home Assistant add-on. This portal enables residents/guests in multi-dwelling units (apartments, dormitories, senior living, hotels) to self-register for WiFi access and receive their personal credentials.

## Features

### 🌐 Public Portal
- **Self-Registration**: Residents can register for WiFi access with their name, email, and unit number
- **QR Code Generation**: Instant QR codes for easy device connection
- **Credential Retrieval**: "My Network" page to retrieve existing credentials
- **Invite Codes**: Optional controlled access via invite codes

### 🔐 Admin Dashboard
- **IPSK Management**: Create, view, revoke, and delete Identity PSKs
- **Device Association**: Link IPSKs to Home Assistant devices and areas
- **Invite Code Management**: Generate and manage registration invite codes
- **Statistics Dashboard**: Real-time overview of registrations and connections

### 🏠 Home Assistant Integration
- **WebSocket API**: Direct integration with Home Assistant via WebSocket
- **meraki_ha Integration**: Uses the IPSK Manager feature from meraki_ha
- **Areas & Devices**: Pull units from HA areas for registration dropdown

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 Meraki WPN Portal Add-on                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Backend                       │    │
│  │  • Registration API    • IPSK Management API            │    │
│  │  • Admin API           • HA WebSocket Client            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    React Frontend                        │    │
│  │  • Public Registration    • Admin Dashboard              │    │
│  │  • My Network Page        • IPSK Manager                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────┐
              │      Home Assistant       │
              │    meraki_ha integration  │
              └───────────────────────────┘
```

## Installation

### Prerequisites

1. **Home Assistant** with Supervisor
2. **meraki_ha integration** installed with IPSK Manager feature enabled
3. A **Meraki network** with Identity PSK enabled on your SSID

### Install via Home Assistant Add-on Store

1. Add this repository to your Home Assistant add-on store
2. Install "Meraki WPN Portal"
3. Configure the add-on (see Configuration section below)
4. Start the add-on

### Manual Installation

1. Clone this repository to your Home Assistant add-ons folder:
   ```bash
   cd /addons
   git clone https://github.com/yourusername/meraki-wpn-portal
   ```

2. Refresh the add-on store in Home Assistant

3. Install and configure the add-on

## Configuration

Configure the add-on through the Home Assistant UI or by editing the add-on configuration:

```yaml
# Home Assistant Connection
ha_url: "http://supervisor/core"
ha_token: "your-long-lived-access-token"

# Branding
property_name: "Sunset Apartments"
logo_url: "https://example.com/logo.png"
primary_color: "#00A4E4"

# Default Network Settings
default_network_id: "L_123456789012345678"
default_ssid_number: 1
default_group_policy_id: ""

# Authentication Methods
auth_self_registration: true
auth_invite_codes: true
auth_email_verification: false

# Registration Options
require_unit_number: true
unit_source: "ha_areas"  # ha_areas, manual_list, or free_text
manual_units: []

# IPSK Settings
default_ipsk_duration_hours: 0  # 0 = permanent
passphrase_length: 12
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `ha_url` | string | `http://supervisor/core` | Home Assistant URL |
| `ha_token` | password | - | Long-lived access token for HA API |
| `property_name` | string | `My Property` | Name displayed on the portal |
| `logo_url` | url | - | URL to property logo (optional) |
| `primary_color` | string | `#00A4E4` | Primary theme color |
| `default_network_id` | string | - | Meraki network ID for IPSK creation |
| `default_ssid_number` | int | `0` | Default SSID number (0-14) |
| `auth_self_registration` | bool | `true` | Allow self-registration |
| `auth_invite_codes` | bool | `true` | Enable invite code system |
| `require_unit_number` | bool | `true` | Require unit selection |
| `unit_source` | enum | `ha_areas` | Source for unit list |
| `passphrase_length` | int | `12` | Length of generated passphrases |

## Usage

### Public Portal

Access the public portal at `http://your-ha-instance:8080` or through the Home Assistant ingress panel.

**Registration Flow:**
1. User enters name, email, and selects their unit
2. Optionally enters an invite code if required
3. System creates an IPSK via Home Assistant/Meraki
4. User receives their WiFi credentials and QR code

### Admin Dashboard

Access the admin dashboard at `/admin` (requires Home Assistant authentication).

**Features:**
- View all IPSKs with status and associations
- Create new IPSKs manually
- Revoke or delete existing IPSKs
- Generate and manage invite codes
- View registration statistics

## Development

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pytest tests/ -v
```

## API Documentation

When running, API documentation is available at:
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to the main repository.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs and feature requests on GitHub Issues
- **Discussions**: Join the discussion on GitHub Discussions

## Acknowledgments

- [Cisco Meraki](https://meraki.cisco.com/) for their excellent networking platform
- [Home Assistant](https://www.home-assistant.io/) community
- The [meraki_ha](https://github.com/your/meraki_ha) integration team
