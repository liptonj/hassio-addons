# Settings category dropdown — 0.30.2.53

The main Settings tab opens six category links and All settings. The permanent
category sidebar is removed; focused pages expose their siblings through
In this category. Dropdowns use native details/summary and links, preserving
ingress URLs, all saved settings, current-category/page selection and bookmarks.
Mobile opens the main menu above the bottom bar. Escape restores trigger focus;
outside clicks close menus. Native navigation works with JavaScript disabled.

The initial batched desktop/mobile inspection encountered a tool timeout after
reaching System tools on desktop. Unsaved metrics from that partial sweep were
discarded. The remaining desktop pages and mobile category/submenu checks were
recorded incrementally: 17 axe checks with zero violations, overflow or menus
outside the viewport. Keyboard Enter/Escape and actual category link selection
passed; native no-script selection navigated from Identity to Captive portal.
No product defects requiring a repair/confirmation round were found.

Screenshots are local source fixtures, not live Home Assistant screenshots. No
production provider settings or device records were edited during these checks.
No new independent critique score is claimed. Release and deployment evidence
are recorded alongside this document.

Finish verdict: published; deployment blocked by the Home Assistant connection.
All 191 tests, seven real Home Assistant
compatibility checks, Ruff, JavaScript/Bash syntax and whitespace checks passed.
All three architecture images built and passed non-root runtime probes; packaged
source hashes match the release, and all 11 runtime settings routes render the
new dropdown without the old sidebar. No unrelated files were staged.

Source CI passed for release commit `0ddcb80b2b13cebab768133ebca3a3873282f708`.
Deployment on 2026-10-05 failed at the first Supervisor connection, before any
backup or update began. A separate read-only inspection returned HTTP 522.
Version 0.30.2.53 is not verified live; the last successful live verification was
0.30.2.52 on 2026-10-03. See `deployment.json` for workflow evidence. Restoring
the Home Assistant deployment connection is required before retrying the release.
