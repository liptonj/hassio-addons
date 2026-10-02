# Assessment B — detector and browser evidence

Date: 2026-10-02. Target slug: `admin-app-py`. Independent approved subagent; no Assessment A, prior audit, or surface history was read. No shipping source edits. Findings withheld until Assessment A was complete.

The full-parser CLI returned **exit 2, 82 raw warnings**. All were assessed as Home Assistant incumbent exceptions or structural false positives; **zero detector warnings were confirmed actionable**. One additional P2 portal issue was verified manually.

**Evidence recovery note:** the turn was deliberately interrupted before durable saving. Original temporary JSON, HTML and manifest files were absent on continuation. The accompanying JSON reconstructs the exact count/file/rule index and observed browser results from recorded tool output; it does not claim byte-identical original raw output. Missing snippets and hashes are not fabricated. No detector was rerun.

## Detector provenance

Original real attempt: `node /Users/jolipton/.agents/skills/impeccable/scripts/detect.mjs --json /tmp/codex-stepca-critique-b-fixtures/html`, exit 2. It warned that `htmlparser2`, `css-select`, `css-tree`, and `domutils` were unavailable and that regex fallback undercounts findings.

Authoritative run: `node /tmp/codex-stepca-audit-tools/detector/detect-antipatterns.mjs --json /tmp/codex-stepca-critique-b-fixtures/html`, exit 2, empty stderr. All 20 copied detector `.mjs`/`.js` files were byte-identical to the bundle. A 21-file comparison included the missing optional `detect.mjs` launcher; the same detector facade was invoked directly. Parser dependencies were already installed in the isolated tool copy.

Rendered 35 fresh HTTP responses from current source; 31 nonempty application pages carry warnings, three redirects have empty bodies and one is a standard 404. Scope includes all admin routes and certificate states; public enrollment; resident group/Duo/legacy entry, account, validation, ready and recovery states. No ignore list exists and no ignore rules were applied.

| Rule | Count | Disposition |
|---|---:|---|
| `overused-font` | 31 | incumbent-platform exception |
| `flat-type-hierarchy` | 18 | incumbent-platform exception / heuristic false positive |
| `dark-glow` | 31 | false positive |
| `cramped-padding` | 2 | false positive |

## Exact file/rule findings

All files were under `/tmp/codex-stepca-critique-b-fixtures/html/`. Every computed warning reports `line: 0`. The JSON contains the 82 warning instances and original snippets wherever the tool transcript retained them.

| File | Rule counts |
|---|---|
| authority.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| certificate-active.html | `overused-font` ×1, `dark-glow` ×1 |
| certificate-expiring.html | `overused-font` ×1, `dark-glow` ×1 |
| certificate-revoked.html | `overused-font` ×1, `dark-glow` ×1 |
| certificates-all.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| certificates.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| enroll-admin.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| enroll-gone.html | `overused-font` ×1, `dark-glow` ×1 |
| enroll-public.html | `overused-font` ×1, `dark-glow` ×1 |
| enroll-self.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| groups.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| mdm.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| not-found.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| options.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| portal-device-address.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-duo-account.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-duo.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| portal-group-account.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-group-finished.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| portal-group-ready.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| portal-group-validation.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-group.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| portal-legacy-ready.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-legacy.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-no-context.html | `overused-font` ×1, `dark-glow` ×1 |
| portal-supplied-url.html | `overused-font` ×1, `dark-glow` ×1 |
| residents.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `cramped-padding` ×2, `dark-glow` ×1 |
| sign.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| tools.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| trusted-cas.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |
| wifi.html | `overused-font` ×1, `flat-type-hierarchy` ×1, `dark-glow` ×1 |

## Verified dispositions

**overused-font** — Roboto follows the explicit Home Assistant identity in PRODUCT.md, DESIGN.md and the ui.py body font stack. Replacing it for novelty would conflict with the brief.

**flat-type-hierarchy** — The detector compares maximum/minimum font size across all headings, body, labels and captions, and warns below 2.0. HA uses 12px captions, 14px body, 16px labels and 20px card headings. Inspected screenshots had recognizable heading/card/task hierarchy. No task-level hierarchy failure was verified from these warnings.

**dark-glow** — ui.py .choice:has(input:checked) uses inset 0 0 0 1px var(--primary-color); focused inputs use 0 0 0 1px var(--focus-color). These are zero-blur selection/focus outlines. Browser screenshots show sharp outlines, not decorative glow. Recurrence on pages without choice cards comes from shared stylesheet inspection.

**cramped-padding** — residents.html zero-padding div.card and section.card contain details.expand; summaries and contents own the insets. Browser measured card-header 16px 16px 8px and card-content 0px 16px 16px. Screenshots show inset QR content and disclosure labels; padding the wrapper would duplicate the insets.

## Supplemental actionable evidence

**P2 — irrelevant other-device MAC field** (`admin/resident_access.py:240`). At 390×844, This device was selected (`target=current`) while the Other device’s hardware MAC address field and instructions remained visible. The field was optional and empty; the current device address was already visible. It adds a needless decision and roughly 150px of mobile form content before Unit or room and the create action. Reveal it for Another device, keeping a usable no-script path and the existing CSP.

## Browser / overlay evidence

Native CUA used fresh IAB tab 2. Inspected 1280×900 desktop and 390×844 mobile in one bounded pass: inventory, Wi-Fi settings, public enrollment, resident recovery/selector/account, admin residents. Dark mode was inherited. Mobile inventory, enrollment, account and residents document widths measured 390 with no document overflow. Two post-resize screenshots were stale/composited and excluded from conclusions; the correct mobile enrollment capture followed reload. Native images are in the tool transcript; no separate PNG files were saved.

Mutable CDP preflight changed the title to Impeccable B preflight and appended a script tag: title changed=true, tag present=true, inline execution=false. Read-only Playwright evaluate was used only for DOM inspection.

Owned live detector server PID 45215 listened on 8400. Script `http://localhost:8400/detect.js` was appended on **five pages**: admin `/`, `/tools/wifi`, public `/enroll/<fixture-token>`, resident recovery from the supplied portal query, and admin `/residents`. Every append succeeded; every `script.onerror` set `window.__impeccableBExternal` to `blocked`. Admin CSP allows nonce scripts; resident CSP defaults to none. Controls were not weakened and no nonce was borrowed. **No detector executed and no user-visible overlay was presented.**

The titles were temporarily labeled `[Human]`. An initial inventory overlay check used `[id*=impeccable]` and incorrectly matched the script tag; its true result is not overlay evidence. The blocked load state and lack of detector execution are authoritative. Subsequent overlay checks returned false.

`tab.dev.logs({filter:"impeccable"})` was empty, as were captured warning/error logs. Empty logs do not establish a clean live scan. Browser detector findings are unavailable because execution was blocked.

`visible:false` creation returned “IAB visibility is not supported in a subagent thread”. Creation without a visibility option worked. Visibility was not forced or verified and no live human overlay was claimed. Native browser controls were sufficient; no terminal browser fallback was used.

## Fixture limits

The supplied Meraki query used `/grant`; the current `captive.grant_url` contract requires `/splash/grant`. The supplied URL yielded recovery (400); valid group/Duo/legacy states used `/splash/grant` without changing validation. `portal-group-finished.html` was actually Check your details (400) after consumed CSRF reuse, not successful logout. `portal-expired-callback.html` was captured after legacy mode and yielded a standard 404, not verified Duo expiry UI. Enrollment gone returned current source 404.

All services, credentials, CA fixtures, records and device keys were mocked. No live CA private key or WPN signing key was used. The live Home Assistant frame/theme bridge was not exercised inside a real HA installation.

## Cleanup and run notes

Preview PID 44738, ports 49608/49609/49610, stopped with `kill 44738`. Detector server PID 45215, port 8400, stopped via bundled live-server stop in owned temporary cwd. Both PIDs and all four ports were observed stopped/closed before interruption. The server stop warned `config_missing` for its source injection cleanup; temporary tags and titles had already disappeared through navigation/reload or tab closure.

Viewport was reset and owned successful tab 2 closed. Failed initial tab 1 could not be rebound for explicit close because its error document used a policy-blocked `data:` URL; it is subject to documented automatic cleanup of unmarked agent-created tabs at turn completion. Owned temporary fixture/server/preview files were absent on continuation; the original payload loss is disclosed rather than silently replaced. Shared detector tools were preserved.

Targets: `admin/app.py`, `admin/ui.py`, `admin/enroll.py`, `admin/ipsk.py`, `admin/resident_access.py`. `context.mjs` was not rerun. PRODUCT.md and DESIGN.md supplied incumbent HA constraints only.

Questions skipped: independent Assessment B returns evidence to parent synthesis; parent owns the critique close.
