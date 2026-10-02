# Pre-install improvements — 2026-10-02

Later verification: `2026-10-02-release-readiness.md` records the current passing
tests, real MariaDB pagination, image builds and certificate lifecycle checks.
The verification notes below describe the earlier pre-install inspection.

Implemented the approved app improvements before installation/configuration.

## Changes

- Tools → Setup and checks: ordered installation instructions and explicit
  read-only database/companion/network/HTTPS readiness checks. Local Duo and QR
  configuration is distinguished from verified provider/device behavior.
- Tools → Help and troubleshooting: six searchable guides. Public resident
  pages have collapsed connection/recovery help and ordered onboarding progress.
- Supported server validation errors identify the input with aria-invalid and
  described error text. Native validation has visible field feedback. Bounded
  identity/device drafts survive correction; invitations/passwords do not.
- Permitted-group account choices can be filtered locally by name/username.
  Group-only fetching, membership revalidation and the existing 500-member
  bound remain. No tenant-wide directory fetch was introduced.
- MariaDB search covers the complete active resident/device inventory. Stable,
  allowlisted sorting and parameterized page queries replace the UI’s 250-row
  cutoff. Keys and records show 25 rows each with independent page/filter links.
- Sorting and secondary mobile tools disclose, preserving the main task.
- Docker packaging includes the new guidance module. Existing regression
  fixtures were aligned with the inventory API and corrected singular wording.

## Evidence and limits

Python source parses and shared JavaScript passes node --check. A native IAB
preview used synthetic records/services only: 301 records, 77 keys, 120 permitted
accounts. Desktop and 320px rendering, help search, independent page links,
account filtering, field-error association and empty-result guidance were
inspected in one batch plus a bounded confirmation. Mobile and desktop widths
matched the document width in the observed confirmation views. Mocked inventory
rendering does not establish MariaDB query correctness.

No new tests were added or run. The full regression suite, new MariaDB query,
container rebuilds, live provider checks and physical/assistive-technology work
remain unverified for these additions. The earlier 32/40 critique and 17/20
technical audit apply to their earlier source revision; no new score is claimed.

The owned preview and tab were stopped and viewport/media overrides reset.
No live credentials, WPN signing key, deployment settings or real certificates
were read or changed.

[Evidence](2026-10-02-preinstall-improvements.evidence.json) ·
[Readiness screenshot](preinstall-assets/setup-readiness.jpg)
