# IPSK page structure review — 2026-10-02

The Residents screen mixed inventories, administration, credential sharing and
setup in one document. Anchor links and collapsed forms still left every task
on the same page. The section is now named IPSK and defaults to Wi-Fi keys.

## Changes

- Separate URLs for Wi-Fi keys, registered devices, invitations, join codes and
  access settings, with consistent local navigation and current-page state.
- Dedicated key-creation and QR-configuration pages with return links.
- Inventory-specific search, sort and pagination; status filtering only on keys.
- POST results stay on the relevant task, including one-time invitation codes,
  created key QRs, settings errors and save feedback. Legacy form URLs remain
  supported; /residents bookmarks redirect with their query parameters.
- Unrelated pages avoid live key and network-option requests. The devices page
  retains reconciliation of remote expired/revoked keys before listing records.
- Home Assistant theme, CSP, CSRF checks, native confirmations and existing
  credential behavior are retained.

## Verification

144 Python regression tests pass. Python compilation and git diff --check pass.
The Impeccable mechanical detector returned no findings for the modified Python
UI sources; that scanner does not replace browser inspection.

A local preview used only synthetic records and mocked providers. One batched
inspection and one confirmation covered desktop and narrow mobile views,
light and dark themes, task navigation, search/status filtering and clear
recovery. Observed document widths matched 1280px desktop and 320px/390px
mobile viewports. Forms are capped at 760px; desktop join codes use two columns.
Scrollable tables retain keyboard-accessible regions on narrow screens.

[Desktop fixture preview](ipsk-pages/desktop-light.png) ·
[Mobile fixture preview](ipsk-pages/mobile-dark.png)

This change has not been deployed. No production credentials, Meraki keys,
Home Assistant settings or database records were changed. The fixture server
and browser viewport/theme overrides were cleaned up after verification.
