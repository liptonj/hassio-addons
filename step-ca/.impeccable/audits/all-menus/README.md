# All section dropdowns — 0.30.2.54

Certificates, Enroll, IPSK, Authority and Settings now share native disclosure
dropdowns. Certificates links to all five status views. Enroll links to its
overview, one-time link form, links table, this-computer enrollment and issuance
form. IPSK links to keys, devices, invitations, join codes and key creation.
Authority links to CA details, downloads and endpoints. The first four also
link to their relevant settings; Settings retains six independent categories.
The duplicate horizontal IPSK page navigation is removed.

Desktop uses the existing Home Assistant toolbar and theme. At 641–1100px the
title is visually hidden, remaining available to assistive technology, and
trigger spacing tightens. Phones keep five equal bottom-bar triggers, with
visible carets and bounded menus above the bar. Selection closes menus;
Escape restores trigger focus. Opening another menu closes the previous one.
Real links and native disclosure controls remain usable without JavaScript.

One initial inspection and one confirmation round recorded 27 axe views at
1280px light, 641px light and 320px dark, with no accessibility violations or
horizontal overflow. The initial pass found Certificates clipped at the left
edge; confirmation found a 1px Enroll clip at 641px. The first two desktop menus
now align to their trigger's left edge. The final Enroll correction was derived
from its observed trigger bounds, without a third visual inspection round.
All 28 distinct submenu destinations rendered without errors, and every
fragment target existed; authority disclosures opened through hash links.
Keyboard Enter/Escape, single-menu behavior, real Root CA selection and native
no-script navigation to Registered devices passed.

Screenshots are local source fixtures, not production Home Assistant screenshots.
The accessibility harness used CDP because the browser's read-only evaluation
scope does not expose page globals. No-script checks used native browser
controls because script-backed locators cannot click with execution disabled.
No production settings, credentials or device records were changed.

All 195 tests, seven real Home Assistant compatibility checks, Ruff, JavaScript
and Bash syntax, and whitespace checks passed. amd64, aarch64 and armv7 images
built and passed non-root runtime probes; all 11 packaged module hashes match
the final source. Each of the 11 runtime settings routes rendered all five
dropdowns. Release details are in `release-checks.json`; deployment is recorded
separately. No independent critique score or full new audit is claimed.

Finish verdict: implemented and verified locally; awaiting source CI and the
Home Assistant deployment connection.
