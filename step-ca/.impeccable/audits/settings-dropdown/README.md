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

Finish verdict: ready for release. All 191 tests, seven real Home Assistant
compatibility checks, Ruff, JavaScript/Bash syntax and whitespace checks passed.
All three architecture images built and passed non-root runtime probes; packaged
source hashes match the release, and all 11 runtime settings routes render the
new dropdown without the old sidebar. No unrelated files were staged.
