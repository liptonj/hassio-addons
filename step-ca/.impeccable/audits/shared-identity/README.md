# Shared identity settings — 0.30.2.51

Authentication and User directory now live under Settings → Identity & access,
independently of IPSK. Both pages work with IPSK disabled or its Wi-Fi network
and database unconfigured. IPSK Device access contains consumer rules and
limits, with links to the shared providers rather than embedded credentials.
Provider fields, validation and rendering are extracted into identity_settings.

Each provider form saves only its allowed fields. Other settings and blank
saved secrets are preserved; secrets never enter rendered saved values or error
drafts. Active IPSK requirements still prevent clearing necessary provider
configuration. Legacy combined forms remain supported and validation errors
on provider fields hand off to the appropriate shared page. Existing option
keys remain under resident_onboarding for configuration/runtime compatibility.
This is the current Duo verification and group-scoped directory; primary
password SSO and other application integrations are not added by this change.

## Checks

- 175 portal tests passed on Python 3.14 with exact CI dependencies, including
  provider-independent setup, scoped writes, retained secrets, bad CSRF,
  validation recovery, policy protection and complete nested option coverage.
- Seven real Home Assistant 2026.9.4 compatibility checks passed.
- All three images built and ran: aarch64, amd64 and armv7. Ten packaged admin
  hashes match source; each runtime rendered eight settings routes, including
  the shared hub and provider pages. The first native build encountered an
  Alpine package I/O/download error; retry succeeded.
- Ruff, Python compilation, Bash/JavaScript syntax, configuration parsing and
  whitespace checks passed.
- One browser inspection covered 25 routes at 1440px/light, 390px/dark,
  320px/light and 768px/dark: 100 views, zero axe violations/incomplete results,
  runtime error pages or horizontal overflow.
- The bounded form confirmation exercised five mobile/dark states: directory
  error/success, authentication error/success and IPSK policy success. All passed
  axe with zero incomplete results/overflow. Safe drafts remained, new secrets
  were blank on recovery, saved secrets stayed out of inputs, and IPSK had no
  provider credential fields. The fixture policy could require the configured
  shared authentication and retain the directory while changing the device limit.

Browser saves were made only against local in-memory fixtures. No deployed
credentials, user records, provider writes or identity rules were changed by
these checks. Screenshots are local fixture previews. Live iframe rendering,
physical Wi-Fi/Duo acceptance and new application consumers were not exercised.
No new independent critique score is claimed. Raw results and hashes are saved
alongside this record; live deployment evidence is below.

## Publication and cleanup

Source commit `2a49e31cdf802dfc77d9f9dc5b8d7e68c4751153` was pushed to master.
[Linux CI](https://github.com/liptonj/hassio-addons/actions/runs/37141058054)
passed all 175 portal tests and seven real Home Assistant compatibility checks.
The fixture browser and server were closed, and the dedicated Colima profile
and its container data were removed. Docker's original default context was
restored. Unrelated files and the WPN signing key were excluded from commits.

## Live deployment

**Step CA 0.30.2.51 is deployed and running.** Final verification at
**2026-10-03 17:44:01 UTC** confirmed the add-on stayed started, Core
configuration checked successfully, Home Assistant restarted, the companion
loaded, and the live iPSK options request returned five wireless networks.

- [Backup and update](https://github.com/liptonj/meraki-homeassistant/actions/runs/37141124848)
  completed the Step CA/MariaDB/Core settings backup and submitted the update.
  The workflow then failed reading the Supervisor update job (`unknown_error`);
  this failure was not treated as deployment success.
- [Read-only inspection](https://github.com/liptonj/meraki-homeassistant/actions/runs/37141419219)
  independently confirmed Step CA 0.30.2.51 installed and started, MariaDB
  started, and both relevant integrations loaded.
- [Final verification](https://github.com/liptonj/meraki-homeassistant/actions/runs/37141461850)
  passed stability, Core configuration/restart and live companion checks.
  Backup/update were skipped because the requested version was installed.

The live read-only request was
`{"type":"step_ca_scep/ipsk/options","network_id":""}`. This update moves
configuration ownership in the interface without migrating option keys or
changing the deployment's existing credentials and identity rules. Live HA
iframe rendering and actual Duo/physical Wi-Fi flows were not captured.
