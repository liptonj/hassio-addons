# Meraki and IPSK deployment — 2026-10-05

Step CA **0.30.2.60** is installed and running. The updates were submitted through
Home Assistant's Apps UI with its backup switch off, as requested by the user.
Home Assistant was restarted to load companion 1.6.0. No SSIDs, client keys,
certificate profiles, Duo memberships or connection credentials were changed.

Live verification found and corrected two issues: the non-root Python service
could not open Supervisor's options.json (fixed in 0.30.2.59 by reading the
authenticated Supervisor API), and the Duo group check rejected the documented
capitalized Active status (fixed in 0.30.2.60). Bypass, Disabled and unknown group
statuses remain rejected. Existing working Access Manager clients need no new
profiles for this deployment.
Group status spellings are documented in [Duo's Admin API](https://duo.com/docs/adminapi#get-group-info).

The local suite passed **260 tests**. Source CI for 0.30.2.58 and 0.30.2.59 passed
the full suite and real Home Assistant 2026.9.4 twelve-command compatibility
checks. Final source CI for 0.30.2.60 also passed all 260 tests and the real
companion compatibility check. Deployment used the passing local suite and
direct live checks while the final CI run waited for a GitHub runner.

Live checks confirmed five wireless networks through Meraki HA without a saved
fallback API key, three enabled SSIDs in the checked network, a successful Duo
connection and a successful group directory read with zero permitted users.
The configured group is active and has no members. Full Duo factor/callback
sign-in and physical-device authentication were not performed.

Access Manager policy reads failed for both checked networks with the current
Meraki HA connection; permissions or beta API availability require investigation.
The browser also blocked the Meraki connection/test URL with
ERR_BLOCKED_BY_CLIENT; SSID discovery and Duo POST checks worked. No browser
protections were disabled.

Exact revisions and CI identities are in deployment.json. Local screenshots
and test logs are under output/playwright, including step-ca-60-running.jpg and
step-ca-60-update-no-backup.jpg. Production screenshots and credentials are
not included in this repository.
