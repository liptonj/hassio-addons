# Changelog

## 0.3.23

- Remove relay/control-plane selection from user configuration.
- Use the JGROK-managed production control address for device registration;
  the control plane assigns the appropriate relay.
- Continue bundling the signed JGROK 0.3.22 agent release.

## 0.3.22

- Update the bundled JGROK agent to the signed 0.3.22 release.

## 0.3.20

- Initial Home Assistant add-on for the signed JGROK 0.3.20 agent release.
- Added browser-code registration from the add-on log.
- Persisted the private device credential and installation identity under
  `/data/jgrok`.
- Added automatic re-registration for missing, invalid, or expired
  credentials.
- Published `amd64` and `aarch64` images to Docker Hub with a
  multi-architecture manifest.
