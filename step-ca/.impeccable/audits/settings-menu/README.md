# Central Settings — 0.30.2.50

The Settings tab replaces Tools and groups configuration into Certificates,
Enrollment & Wi-Fi, IPSK and System. Each category opens focused pages with a
sidebar and breadcrumbs on desktop and a native disclosure menu on mobile.
Operational inventories remain under IPSK. Existing editors retain validation,
CSRF protection and ingress handling. Old bookmarks redirect and old forms
remain accepted. Home Assistant-managed options have redacted saved summaries
and a direct Configuration link. Every top-level add-on option is accounted for.

## Verification

- 164 portal tests passed on Python 3.14 with the exact CI dependency versions.
- Seven real Home Assistant 2026.9.4 companion compatibility checks passed.
- All three architecture images built and ran: aarch64, amd64 and armv7.
  Nine packaged admin module hashes match this release, including settings_menu.
  Each runtime rendered the Settings hub and all four categories successfully.
- Ruff, Python compilation, Bash/JavaScript syntax, YAML/JSON parsing and
  whitespace checks passed.
- Initial browser inspection covered 22 routes at 1440px light and 390px dark.
  One existing MDM error chip had 4.42:1 dark-theme contrast; its ink was lightened.
- The single confirmation covered all 22 routes at 1440px light, 390px dark,
  320px light and 768px dark: 88 views, zero axe violations/incomplete results,
  runtime error pages or horizontal overflow. Reduced-motion preference was set.
- Keyboard activation opened the mobile submenu. Without JavaScript, all
  category and IPSK subpage links remained visible with zero overflow.

The local preview used fixture options and providers. No production credentials
were used in browser testing, and no provider or resident data was changed.
This is scoped settings verification, not a new independent critique score.
Real MariaDB/certificate lifecycle evidence from release 0.30.2.49 remains
historical; this change adds no database migration or CA behavior.
Live HA iframe rendering and physical Wi-Fi/Duo acceptance remain separate
from these automated checks. Deployment evidence below confirms the exact installed version and companion.

Raw browser results, navigation checks, screenshots and container/source hashes
are saved alongside this record.

## Publication

Source commit `fdfa0dfde2cf6584dd11ece7b0bb3bdf9dd0f449` was pushed to master.
[Linux CI](https://github.com/liptonj/hassio-addons/actions/runs/37135092513)
passed all 164 portal tests and seven real Home Assistant compatibility checks.
The temporary browser and fixture server were closed. The dedicated Colima
profile and container data were removed; the original default Docker context
was restored and the existing default Colima profile remains stopped.
Unrelated workspace files and the WPN signing key were excluded from commits.

## Live deployment

**Step CA 0.30.2.50 is deployed and running.** Final verification at
**2026-10-03 16:07:26 UTC** confirmed the add-on stayed started, Core
configuration checked successfully, Home Assistant restarted, the companion
loaded, and the live iPSK options request returned five wireless networks.

- [Backup and update](https://github.com/liptonj/meraki-homeassistant/actions/runs/37135143725)
  completed the Step CA/MariaDB/Core settings backup and submitted the update.
  The workflow then failed while reading the Supervisor update job record
  (`unknown_error`); this was not treated as deployment success.
- [Read-only inspection](https://github.com/liptonj/meraki-homeassistant/actions/runs/37135467434)
  confirmed 0.30.2.50 installed and started, MariaDB started, and the companion
  loaded. The HA update entity still showed the preceding version, so the
  Supervisor's installed add-on record was used as the authoritative result.
- [Final verification](https://github.com/liptonj/meraki-homeassistant/actions/runs/37135555065)
  passed stability, Core configuration/restart and live companion checks. It
  skipped backup/update because the requested version was already installed.

The exact live read-only request was
`{"type":"step_ca_scep/ipsk/options","network_id":""}`. No production
key writes, settings edits or physical Wi-Fi/Duo flows were exercised by this
verification. The screenshots show the local fixture UI; live HA iframe
rendering was not captured.
