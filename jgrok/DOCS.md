# JGROK Agent for Home Assistant

## About

This add-on runs the JGROK agent inside a Home Assistant container. The agent
opens one outbound WSS/TLS connection on port 443 and does not expose an
inbound port. Routes assigned in the JGROK portal can forward traffic to Home
Assistant, another add-on, or another host that is reachable from the add-on.

Home Assistant installs the prebuilt multi-architecture image from
`ghcr.io/liptonj/jgrok`. Images are published for `amd64` and `aarch64`.

## Install and register

1. Install the **JGROK Agent** add-on.
2. Set `device_name` if you want a name other than `Home Assistant` in the
   JGROK portal.
3. Start the add-on and open its **Log** tab.
4. Open the URL printed in the log, sign in, enter the displayed five-character
   code, and approve the device.
5. Return to the log and confirm that registration was saved and the agent
   started.

The approval code expires after ten minutes. If it expires, restart the add-on
to request a new one.

## Persistent registration

The approved credential, relay assignment, expiration time, application ID,
and stable installation ID are saved at `/data/jgrok/credentials.json` inside
the add-on. Home Assistant provides `/data` as writable persistent add-on
storage, so the same registration is reused after an add-on restart or upgrade
and is included with the add-on's backup data.

The credential file and its directory use owner-only permissions. The JGROK
process runs as an unprivileged user. If the credential expires, the add-on
starts registration again while retaining the installation ID, allowing the
portal to rotate the existing device registration instead of creating a new
identity.

Uninstalling the add-on and choosing to remove its data deletes the saved
registration. You will need to register again after reinstalling it.

## Route targets

The add-on uses Home Assistant's add-on network. Use a network-reachable target
in the JGROK portal. Common examples are:

- `homeassistant:8123` for Home Assistant Core.
- An add-on hostname and port for another add-on.
- A LAN address such as `192.168.1.50:8080`.

`localhost` and `127.0.0.1` refer to the JGROK add-on container itself, not to
Home Assistant Core.

## Configuration

### `device_name`

The name shown during browser approval and in the JGROK portal. It is applied
when registration occurs.

## Troubleshooting

- If the log is waiting for approval, finish the browser flow or restart the
  add-on after the code expires.
- If registration cannot reach the control plane, verify outbound HTTPS access
  and DNS resolution from Home Assistant.
- If a saved registration was revoked in the portal, uninstall the add-on with
  its data and reinstall it, or remove the device in the portal before starting
  a new registration.
