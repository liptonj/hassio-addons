# Jandy TCX Client — Home Assistant Add-on

A Home Assistant add-on that connects to a Jandy TCX pool controller via the Zodiac cloud WebSocket API and publishes native Home Assistant sensors and binary sensors.

---

## How It Works

The add-on authenticates with the Zodiac/iAquaLink cloud (`prod.zodiac-io.com`), opens a persistent WebSocket connection to your TCX device, and pushes state updates directly into Home Assistant via the Supervisor REST API. No MQTT broker required.

---

## Installation

1. Add this repository to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
   `https://github.com/liptonj/hassio-addons`
2. Install the **Jandy TCX Client** add-on
3. Configure the options (see below)
4. Start the add-on

---

## Home Assistant Entities

The following entities are created automatically the first time a value is received from the TCX device:

| Entity ID | Type | Description |
|---|---|---|
| `sensor.tcx_pool_temperature` | Sensor | Pool water temperature (°F) |
| `sensor.tcx_air_temperature` | Sensor | Equipment enclosure air temperature (°F) |
| `sensor.tcx_swc_level` | Sensor | Salt water chlorinator output (%) |
| `sensor.tcx_light_color` | Sensor | Current pool light color |
| `binary_sensor.tcx_pump` | Binary Sensor | Pool pump/filter on or off |
| `binary_sensor.tcx_light` | Binary Sensor | Pool light on or off |

> **Note:** `sensor.tcx_air_temperature` reads from the sensor inside the pool equipment enclosure, not outdoor ambient air. It will not match your local weather.

---

## Configuration

| Option | Required | Default | Description |
|---|---|---|---|
| `JANDY_USERNAME` | Yes | — | Your iAquaLink account email |
| `JANDY_PASSWORD` | Yes | — | Your iAquaLink account password |
| `log_level` | No | `info` | Log verbosity: `debug`, `info`, `warn`, `error`, `crit` |
| `AUTO_RECONNECT` | No | `True` | Automatically reconnect on WebSocket drop |
| `RECONNECT_TIMER` | No | `60` | Seconds to wait before reconnecting |
| `PING_TIMER` | No | `60` | WebSocket ping interval in seconds |
| `WS_TRACE` | No | `False` | Enable verbose WebSocket frame logging |

Example configuration:

```yaml
log_level: info
JANDY_USERNAME: user@email.com
JANDY_PASSWORD: yourpassword
AUTO_RECONNECT: "True"
RECONNECT_TIMER: "60"
PING_TIMER: "60"
WS_TRACE: "False"
```

---

## REST API

The add-on exposes a small HTTP API on port `5050`:

### `GET /status`
Returns the current cached state of all sensors as JSON.

```json
{
  "water": 70.0,
  "air": 49.0,
  "system": "ON",
  "swc": "50%",
  "light": "OFF",
  "lightColor": "None"
}
```

### `POST /statecontrol`
Sends a desired state command to the TCX device.

```json
{
  "namespace": "filtration",
  "desired": { "pool": { "st": 1 } }
}
```

### `GET /tcxreconnect`
Forces a WebSocket reconnect to the TCX device.

---

## Migrating from the MQTT Version

Previous versions published sensor values to MQTT topics (`pool/TCX/pump`, `pool/TCX/swc`, etc.), which created HA entities via the MQTT integration. Those entity IDs differ from the new native ones.

After upgrading:

1. Rebuild and restart the add-on
2. New entities appear in HA automatically on first TCX message
3. Go to **Settings → Devices & Services → MQTT** and delete the old `pool/TCX/*` entities
4. Update any dashboards or automations to use the new entity IDs listed above

Sensor history does not carry over since the entity IDs changed.
