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
from these automated checks. Deployment evidence will be appended after the
exact installed version and companion are verified.

Raw browser results, navigation checks, screenshots and container/source hashes
are saved alongside this record.
