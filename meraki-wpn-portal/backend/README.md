# Meraki WPN Portal - Backend

FastAPI backend for the Meraki Wireless Personal Network (WPN) Portal.

## Features

- Self-service WiFi registration portal
- Identity PSK (IPSK) management via Meraki Dashboard API
- Home Assistant integration via WebSocket API
- SQLite database for user and registration data
- QR code generation for easy WiFi connection

## Modes

### Standalone Mode
Direct integration with Meraki Dashboard API. Set `MERAKI_API_KEY` environment variable.

### Home Assistant Mode
Uses the `meraki_ha` integration via Home Assistant WebSocket API.

## Development

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install dependencies
uv sync --all-groups

# Run development server
uv run uvicorn app.main:app --reload --port 8080
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RUN_MODE` | `standalone` or `homeassistant` | `standalone` |
| `MERAKI_API_KEY` | Meraki Dashboard API key | - |
| `DATABASE_URL` | SQLite database path | `sqlite:///./meraki_wpn_portal.db` |
| `SECRET_KEY` | JWT secret key | - |
| `PROPERTY_NAME` | Property/building name | `My Property` |

## License

MIT
