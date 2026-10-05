# Resident Access Manager migration

Scope: resident captive registration and Duo/no-sign-in device registration,
resident network settings, Meraki setup-portal assignment and owned key lifecycle.
Incumbent Home Assistant styling and all existing Duo modes are preserved.

The issuer can use Access Manager per-client iPSKs with an explicit client group,
hardware MAC and clientIpskOnly rule. Existing deployments retain legacy issuance
until configured for Access Manager. There is no password persistence or later
reveal. Pending operations are attributable before their remote write; mutation
uses one SDK attempt while retaining the authenticated Meraki HA HTTP connection,
limiter and shared retry settings. API-key mode uses the same service contracts.

Revocation verifies ownership, clears the key, removes only the resident group,
and confirms the result without deleting the client. External ownership changes
require Dashboard review. A separate configured setup SSID receives the captive
portal; existing resident certificate clients and profiles are untouched.

Validation: 283 unit/HTTP/SDK tests; real Home Assistant 2026.9.4 registration and
dispatch of all 15 strict admin/Supervisor-only bridge commands; targeted Ruff,
shell syntax and whitespace checks. A loopback server exercises the pinned real
Meraki SDK's create/list/revoke wire contracts and confirms a failed write gets
one attempt even when the shared session has three retries.

Browser review: local synthetic settings at desktop and 390px mobile, correct
SSID/group filtering, no horizontal overflow, and successful settings save with
a restart notice. Captures are in output/playwright/resident-access-manager-*.jpg.
These fixtures do not demonstrate live Wi-Fi association or real Meraki writes.
No shipping image assets were added.

Live preflight: resident onboarding is disabled, its target network is blank,
and MariaDB shows zero registered devices. Target network, resident SSID, setup
SSID and Access Manager client group still need selection. Previously observed
Access Manager policy reads failed with the existing Meraki connection; the
release exposes safe HTTP diagnostics to help resolve that service requirement.
No SSID, client key, Duo membership or certificate profile was modified in the
live preflight. Deployment verification will be recorded separately.
