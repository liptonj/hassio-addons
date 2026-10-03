# Deployment — 2026-10-02

Final live inspection at **2026-10-03 00:23:12 UTC** (October 2 locally)
confirmed Home Assistant **2026.9.4** online, with:

- Step CA add-on **0.30.2.47**, started.
- Step CA companion integration `step_ca_scep`, loaded and enabled.
- Meraki integration **3.2.9-beta.2**, loaded and enabled.
- MariaDB add-on **3.0.1**, started; its service was available during deployment.

## Regression and correction

The new iPSK companion code in 0.30.2.46 imported a Supervisor identity constant
from the wrong Home Assistant module. This prevented the companion and its
configuration flow from loading. Commit `2d3a3b2` uses the actual hassio constant
and adds compatibility coverage against Home Assistant 2026.9.4. The bundled
companion version is 1.5.1. Commit `e56aae4` installs the Supervisor integration's
dynamic dependency in CI. Both the 140 portal tests and the five real Home
Assistant compatibility checks passed on Linux.

The deployment helper initially attempted to read the add-on-only MySQL
credential service through Core. It now checks public service availability;
Step CA obtains credentials through its own authorized Supervisor connection.
The successful Step CA run found 0.30.2.47 already installed, verified its
MariaDB selection, restarted Core and confirmed the companion loaded. That run
did not perform another installation or create a backup.

## Publication and evidence

- Add-on feature commit: `d5a8876`, pushed to master; compatibility fix: `2d3a3b2`.
- [Step CA compatibility CI](https://github.com/liptonj/hassio-addons/actions/runs/37080873267): passed.
- [Step CA live verification](https://github.com/liptonj/meraki-homeassistant/actions/runs/37081385597): passed.
- [Meraki PR 181](https://github.com/liptonj/meraki-homeassistant/pull/181): merged into beta as `985b06a2719012511df08c414206b0df68b97976` after all checks passed.
- [Meraki release and deployment](https://github.com/liptonj/meraki-homeassistant/actions/runs/37081594689): passed; installed version verified after Core restart.
- [Final inspection](https://github.com/liptonj/meraki-homeassistant/actions/runs/37081802425): passed; both integrations loaded and versions matched.
- Meraki full local quality checks: **1,182 tests passed**, seven existing skips,
  with lint, formatting, security and type checks passing.

The Meraki deployment selected the integration by its repository identity.
The legacy WPN add-on was not selected. No WPN database migration was performed.
Live guest/resident Wi-Fi, Duo membership/callbacks, physical-device enrollment
and public HTTPS acceptance still require the installation's provider and
network configuration. This deployment record does not claim those checks or a
new design score. Earlier release and image-build evidence remains historical.
