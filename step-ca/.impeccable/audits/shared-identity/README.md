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
alongside this record; deployment evidence follows after live verification.
