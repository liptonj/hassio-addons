# Documentation

## Overview

This Home Assistant add-on provides an [ngrok](https://ngrok.com) agent that uses the official ngrok v3 Docker image. It automatically stays up-to-date with the latest ngrok releases and follows [official ngrok Docker patterns](https://ngrok.com/docs/using-ngrok-with/docker).

## How to use

1. Add the Github repo to your Hass.io: <https://github.com/dy1io/hassio-addons>
2. Install the addon
3. Configure the options in the addon (see descriptions for each option below).
4. Add this addon to your `trusted_proxies` list in `configuration.yaml`.

    ```yaml
      http:
        use_x_forwarded_for: true
        trusted_proxies:
        - 127.0.0.1
        - 172.30.32.0/24
        - 172.30.33.0/24
    ```

    **Note**: _If you've modified your Supervisor or Docker network you may_
    _need to update the addresses for your system. See [Home Assistant's documentation][trusted_proxies_docs]_
    _for more info._

5. Start the addon
6. Restart Home Assistant Core

**Note**: _If you did not specify a `subdomain` or `hostname` you will need to_
_open the web interface to get your ngrok.io url, or you can use the_
_[API](#home-assistant-integration) to be notified through Home Assistant._

Example add-on configuration:

```yaml
  log_level: info
  auth_token: my-auth-token
  region: us
  tunnels:
    # HTTP tunnel with custom domain
    - name: hass
      proto: http
      addr: 8123
      hostname: ha.example.com
    # Let's Encrypt verification (HTTP only)
    - name: lets-encrypt
      proto: http
      addr: 80
      bind_tls: false
      hostname: ha.example.com
    # TCP tunnel with random address
    - name: database
      proto: tcp
      addr: core-mariadb:3306
      inspect: false
    # TCP tunnel with reserved address (from ngrok dashboard)
    - name: ssh
      proto: tcp
      addr: 22
      hostname: 5.tcp.ngrok.io:21829
```

### TCP Tunnel Setup

For **TCP tunnels** (like databases, SSH, etc.):

1. **Random TCP address** - Omit `hostname`:
   ```yaml
   - name: database
     proto: tcp
     addr: 3306  # or core-mariadb:3306
   ```
   ngrok will assign a random address like `3.tcp.ngrok.io:12345`

2. **Reserved TCP address** - Get from [ngrok dashboard](https://dashboard.ngrok.com/cloud-edge/tcp-addresses):
   ```yaml
   - name: database
     proto: tcp
     addr: 3306
     hostname: 5.tcp.ngrok.io:21829
   ```
   You'll always get the same TCP address

## Options

**Note**: _Remember to restart the add-on when the configuration is changed._

### Option: `auth_token` (Required)

Your ngrok authentication token. Get one from the [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).

**Important**: This is required for all tunnel types in ngrok v3.

### Option: `api_key` (Optional)

Your ngrok API key for programmatic access to the ngrok API. This is optional and only needed if you want to interact with ngrok's management API.

### Option: `region`

Specifies where the ngrok client will connect to host its tunnels. The following
options are available:

| **Option** | **Location**  |
| :--------: | :------------ |
| us         | United States |
| eu         | Europe        |
| ap         | Asia/Pacific  |
| au         | Australia     |
| sa         | South America |
| jp         | Japan         |
| in         | India         |

Default: `us`

### Option: `tunnels`

A list of tunnels. Use the options defined below to create you tunnels. You
must specify at least the `name`, `proto`, and `addr` for each tunnel. For more
details, see [ngrok's documentation][ngrok_docs_tunnels].

| Option        | Protocol  | Description                                                                                         |
| ------------- | --------- | --------------------------------------------------------------------------------------------------- |
| `name`*       | all       | unique name for the tunnel must only use `a-z` `0-9` `-` or `_`                                     |
| `proto`*      | all       | tunnel protocol name, one of http, https, tcp, tls                                                  |
| `addr`*       | all       | forward traffic to this local port number, network address, or hostname:port (e.g., core-mariadb:3306) |
| `hostname`    | all       | For HTTP/HTTPS: your custom domain (e.g., ha.example.com). For TCP: reserved TCP address (e.g., 5.tcp.ngrok.io:21829) |
| `metadata`    | all       | arbitrary user-defined metadata that will appear in the ngrok service API when listing tunnels      |
| `inspect`     | all       | enable http request inspection                                                                      |
| `proxy_proto` | all       | PROXY protocol version (1 or 2) for passing client connection info                                  |
| `websocket_tcp_converter` | http | convert WebSocket connections to TCP (requires Traffic Policy in v3)                         |
| `compression` | http      | enable gzip compression                                                                             |
| `auth`        | http      | HTTP basic authentication credentials to enforce on tunneled requests                               |
| `subdomain`   | http, tls | subdomain name to request (deprecated - use hostname instead)                                       |
| `host_header` | http      | Rewrite the HTTP Host header to this value, or preserve to leave it unchanged                       |
| `bind_tls`    | http      | bind an HTTPS or HTTP endpoint or both true, false, or both                                         |
| `crt`         | tls       | PEM TLS certificate at this path to terminate TLS traffic before forwarding locally                 |
| `key`         | tls       | PEM TLS private key at this path to terminate TLS traffic before forwarding locally                 |
| `client_cas`  | tls       | PEM TLS certificate authority at this path will verify incoming TLS client connection certificates. |
| `remote_addr` | tcp       | bind the remote TCP port on the given address (deprecated - use hostname instead)                   |

*required

## Home Assistant Integration

You can leverage the ngrok client API to expose your tunnel status to Home
Assistant. This is done by creating a REST API sensor in your Home Assistant
`configuration.yaml`.

### Example: Get Public URL

If you want to monitor the public URL that ngrok generates, you can do that through
a [RESTful sensor][rest_docs] in Home Assistant.

1. Add this to your `configuration.yaml` or create a new [package file][packages_docs].

    ``` YAML
    sensor:
      - platform: rest
        resource: http://localhost:4040/api/tunnels/hass
        name: Home Assistant URL
        value_template: '{{ value_json.public_url }}'
    ```

    **Note**: _If you changed the default tunnel name, replace `hass` in the_
              _example with your tunnel name._

2. Reboot Home Assistant Core

Now you will have a sensor called `sensor.home_assistant_url` You could then use
this to create an automation each to alert you of the public url.

### Further reading

You can monitor almost anything about the tunnel as long as it is active.
See [ngrok's api documentation][ngrok_docs_api] for details.

## ngrok v3 Changes

This add-on now uses ngrok v3 with the [official Docker image](https://ngrok.com/docs/using-ngrok-with/docker). Key changes:

### Configuration Format
- Uses v3 configuration format internally
- Your existing v2-style config options are automatically converted
- Auth option now uses Traffic Policy engine for basic authentication

### Deprecated Options
- `subdomain`: Use `hostname` instead (still works but generates a warning)
- Advanced TLS options (`host_header`, `crt`, `key`, `client_cas`) now require Traffic Policy configuration

### Address Format Support
The `addr` option now supports:
- Port numbers: `8123`
- IP addresses with ports: `192.168.1.100:8123`
- Hostnames with ports: `core-mariadb:3306`, `homeassistant.local:8123`

### Always Up-to-Date
The add-on automatically uses the latest official ngrok release, ensuring you have access to the newest features and security updates.

[ngrok_docs_tunnels]: https://ngrok.com/docs#tunnel-definitions
[rest_docs]: https://www.home-assistant.io/integrations/rest/
[packages_docs]: https://www.home-assistant.io/docs/configuration/packages/
[ngrok_docs_api]: https://ngrok.com/docs#client-api
[trusted_proxies_docs]: https://www.home-assistant.io/integrations/http#reverse-proxies
