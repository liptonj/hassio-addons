# IPSK portal — full Impeccable audit after critique fixes

Date: 2026-10-02 America/New_York (evidence collected across the UTC date boundary).
Target: `step-ca/admin/app.py` and its IPSK/public-resident helpers and shared UI.
Result: **PASS — no unresolved actionable findings in the audited local frontend scope.**

## Implementation integrity verdict

**Pass.** The section remains an intentional Home Assistant administration surface:
IPSK naming, focused routes, native controls, theme tokens, contextual actions,
and a distinct resident onboarding sequence. Shared public results now enforce
one-time password guidance consistently. Automated warnings were inspected in
context and resolved as documented pinned choices or false positives, not hidden.

## Audit health score

| Dimension | Score /4 | Evidence |
|---|---:|---|
| Accessibility | 3 | Zero axe WCAG A/AA/best-practice violations or incomplete checks; keyboard cancellation and return focus verified; manual non-text contrast corrected. Human screen-reader certification remains outside this run. |
| Performance | 4 | Lean server-rendered pages; inline SVGs with fixed dimensions, no external font/script/image requests; no framework bundle or layout-animation loop. Canonical creation fixture reached DOMContentLoaded in 18.5ms locally. |
| Responsive design | 4 | All 21 views at four widths; no document/table overflow or undersized action controls. Long data, empty/error states, stacked inventories and desktop reflow checked. |
| Theming | 4 | Light/dark token palettes pass text checks; control boundaries and checked indicators pass manual contrast. Shared HA theme adoption remains intact. |
| Implementation integrity | 4 | All critique findings addressed, secrets excluded from recovery drafts, exact key handoffs retained, deterministic findings triaged against the pinned design. |
| **Total** | **19/20** | **Excellent** |

Unresolved severity counts: **P0: 0 · P1: 0 · P2: 0 · P3: 0**.
No remaining frontend fix commands are recommended for this scope.

## Complete critique disposition

| Finding | Implemented result | Verification |
|---|---|---|
| P1: Admin key validation loses drafts | Whitelisted non-secret fields and selections survive errors; password stays blank; field errors and pre-submit requirements added | Regression submits an invalid password, renders the returned draft, checks escaping, selected SSID/policy and secret exclusion |
| P2: Phone row actions offscreen | Inventories stack with name/status, labelled metadata and wrapping actions; explicit table semantics retained | 320/390px screenshots and measurements; zero table overflow, all row actions visible |
| P2: Current-device QR precedes saving credentials | Network/password-copy and Finish setup precede a collapsed QR; another-device result stays QR first | Shared-result regression and real public HTTP tests; current/other/simple fixtures |
| P2: Disabled Duo features expose configuration | Group fields appear for verification or directory mode; SDK fields appear for verification; disabled/omitted fields retain saved values | Browser toggle combinations, expanded-field axe checks, settings-save and recovery regressions |
| P2: Devices require another key search | Stable key-ID links and return search/sort/page context; context survives Reveal/QR/revoke/delete feedback | Browser follows device→key→Reveal→device; regression distinguishes key-1 from key-10 |
| Invitations cannot be distinguished | Optional resident/purpose label, legacy invitation-number fallback and contextual revoke dialog | Parameterized labelled insert and validation test; rendered two invitation rows; additive migration SQL assertion |
| Resident attribution is ambiguous | Explicit explanation that name/email is a records label and does not select/verify an account | Creation form inspection |
| Numeric expiry is unclear | No expiry, day/week/month choices and custom hours; numeric no-script fallback | Browser maps one week to 168 submitted hours and verifies fallback |
| Private-address help repeats recovery instructions | Recovery retains platform instructions and omits duplicate private-address paragraph from general help | Shared helper/source inspection and connect fixture |
| Repeated actions lack row context | Accessible action names include key or invitation identity | Browser accessibility trees and axe checks |
| Toolbar says Certificates in IPSK | IPSK heading on IPSK routes | Browser headings across all seven admin routes |
| Long content wraps poorly | Fixed desktop table layout, wrapping cell content and actions; mobile title leading corrected | Long Latin/CJK/RTL fixture at all four widths; no overflow or incomplete contrast checks |
| Manual audit: insufficient control contrast | Shared outline strengthened; checked controls use accent fill | Light boundary 3.59:1; dark boundary 4.70:1; checked indicator at least 3.25:1; white check/button text 5.25:1 |

Five IPSK navigation destinations and the five-state key filter remain intentional,
labelled choices. They serve separate tasks/states; collapsing them would add a
navigation step without fixing a demonstrated task failure. No critical overload
remains from exposed inactive configuration or device-to-key recall.

## Technical evidence

- **153 Python tests pass**, including 9 new critique regressions. Compile and
  `git diff --check` pass. Tests are fixture-based; no real keys were issued.
- **84 automated rendered checks**: 21 views at 1440px/light/reduced motion,
  390px/dark, 320px/light/reduced motion and 768px/dark. axe-core **4.13.0**;
  tags: WCAG 2 A, AA, WCAG 2.1 AA and best-practice. All report zero violations,
  zero incomplete checks, zero horizontal document/table overflow and zero
  measured action controls below 44×44 CSS pixels.
- **4 additional desktop-reflow checks** at 720 CSS pixels/DPR 2, equivalent to
  the layout width of a 1440px viewport at 200% zoom, pass without overflow or
  axe findings. This is a reflow emulation, not a physical browser zoom test.
- Keyboard opens destructive confirmation, focuses Cancel, dismisses with Escape
  and returns to the initiating control. No destructive request was submitted.
- Device selection reveals/enables/requires the other-device MAC. Default current
  MAC stays read-only. No-script key creation remains usable.
- Theme tokens update with light/dark emulation. Reduced-motion toast transition
  is 0s; state feedback remains present. Final canonical browser console had no
  errors/warnings. Physical device and live iframe-theme behavior are not claimed.
- All canonical pages use real renderers/helpers. Public success now uses the
  actual shared result helper, rather than copied representative markup.

## Deterministic scan and exceptions

The original bundled Python-file scan returns zero findings, with the expected
limitation that Python-generated DOM is not reconstructed. The exact bundled
scripts were copied to a temporary runner and its four HTML/CSS parser dependencies
installed there; no user skill files or project dependency files changed.
The final parser-enabled scan of all 21 canonical rendered pages produced **59
raw warnings**, with no dependency fallback or parser errors:

| Rule | Count | Verified disposition |
|---|---:|---|
| overused-font | 21 | Pinned HA Roboto/system family; intentional |
| flat-type-hierarchy | 13 | Pinned HA type roles; rendered hierarchy clear |
| dark-glow | 21 | Sharp keyboard focus rules; false positive |
| wide-tracking | 3 | Literal password copy data; false positive for body prose |
| cramped-padding | 1 | Disclosure summary supplies 12px/16px padding; false positive |

**Zero actionable detector findings remain.** The raw JSON is retained alongside
its explicit resolution record; no detector ignores were introduced.

## Patterns and positive findings

The fixes address shared causes: safe draft restoration, conditional provider
configuration, task context, one result helper, consistent mobile tables and
contrast-safe control tokens. Focus, copy announcements, progress, confirmation
consequences, one-time warnings and no-secret draft handling remain intact.

## Scope and practical limits

This is the full five-dimension frontend audit for the IPSK/admin-resident scope
reviewed in the critique, including shared shell/control changes. It is not a
live Meraki/Duo, HA installation or screen-reader certification. Services were
mocked; public POST behavior was checked through local HTTP/unit fixtures.
Docker's daemon was unavailable, so the new MariaDB label migration was verified
through SQL/schema regression, not against a running database. The migration
runs at add-on startup and is additive/idempotent. Restart is needed after update.
No deployment, production configuration change, commit or push occurred.

## Saved evidence and cleanup

Evidence directory: [ipsk-fixes](ipsk-fixes/).
- `browser-audit.json`, `behavior-checks.json`, `desktop-reflow-2x.json`
- `manual-contrast.json`, `source-detector.json`, `rendered-detector.json`
- `detector-resolution.json`, `rendered-pages.json`, `source-hashes.json`
- `test-results.txt`
- `mobile-keys-dark.png`, `mobile-success-dark.png`, `desktop-access-light.png`

Both owned browser tabs closed and all emulation overrides reset. The local
preview server stopped. Newly created preview/detector scratch files removed;
final evidence stays in this directory. Existing unrelated workspace changes and
previous tooling were preserved.
