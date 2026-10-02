# Assessment A — Step CA design review — 2026-10-02

Method: independent design reviewer `/root/critique_design`, isolated from Assessment B, detector output, prior audits, and surface history. Operate mode. Targets: admin/app.py, admin/ui.py, admin/ipsk.py, admin/resident_access.py, admin/enroll.py. Product and design guidance read; native Home Assistant identity preserved.

## Design specificity verdict

The interface is convincingly specific to a Home Assistant certificate authority. Native themed controls, flat outlined cards, familiar Settings rows, certificate status, CA chain downloads, and device-specific enrollment steps fit its operating environment. Retain that visual world. The main shortfall is task hierarchy in the newer resident features: setup, sharing, provisioning, and existing-key management form a long page, while resident completion omits guidance already present in legacy registration.

## Design health score

All ten heuristics apply. These are design judgments across the full target, not technical conformance scores.

| # | Heuristic | Score / 4 | Evidence |
|---|---|---:|---|
| 1 | Visibility of system status | 3 | Active tabs, health tiles, expiry labels, results and admin progress work; resident POST pages lack shared progress behavior. |
| 2 | Match system / real world | 3 | Most actions use task language; certificate and hardware MAC concepts need translation for novice owners. |
| 3 | User control and freedom | 3 | Back links, session exit, filters, cancellable dialogs and restore-to-list support control; resident one-time credentials need stronger completion guidance. |
| 4 | Consistency and standards | 3 | Native HA patterns cohere; self-service completion loses legacy save/reconnect guidance. |
| 5 | Error prevention | 3 | Irreversible admin actions confirm and captured context stays server-side; current-device forms expose an irrelevant MAC field. |
| 6 | Recognition rather than recall | 3 | Labels, copy actions, hints and selected-choice detail help; resident-key management requires finding the bottom of setup. |
| 7 | Flexibility and efficiency | 2 | Certificate search/filters and direct Tools navigation help; resident records have no search/filter and sit below setup. |
| 8 | Aesthetic and minimalist design | 2 | CA and certificate public pages are focused; Residents exposes multiple jobs and unrelated fields. |
| 9 | Error recognition and recovery | 2 | Address recovery is actionable and self-service drafts survive errors; legacy registration returns to an empty form. |
| 10 | Help and documentation | 3 | Installation, RADIUS trust and device-address help are contextual; self-service success lacks a complete connection handoff. |
| **Total** | | **27/40** | **Acceptable: significant task-flow improvements needed.** |

## What works

1. Certificate health tiles link to relevant views; expiry combines dates and relative time; search and enrollment sit together. Details show validity, fingerprint and clear revocation consequences.
2. Public certificate enrollment has two understandable device choices and one Continue action. Its .p12 result prioritizes the one-time password warning, copy action, download expiry and numbered installation steps. This is a useful model for resident completion.
3. Technical setup is mostly disclosed when needed. CA details and advanced enrollment collapse; Wi-Fi setup groups decisions; persistent Tools navigation provides predictable routes. Randomized-address recovery gives corrective settings and a reconnection sequence before collecting personal data.

## Priority issues

### P1 — Self-service success does not clearly hand the current device over to the resident network

**Evidence:** Native desktop and 390px group-based resident success shows “Scan this QR on the device,” a literal password, Download QR, Finish captive portal and Add another device. All three actions are filled buttons. There is no instruction to save the password before leaving, reconnect to the named network, or keep private addressing off. This page is viewed on the device whose MAC was captured. Legacy success explicitly instructs saving/reconnecting and explains the five-minute captive window.

**Source:** `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/resident_access.py:384` creates the generic instruction; lines 387–393 consume current captive context and offer the exit. `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/ipsk.py:310` renders the passphrase without copy/save. Stronger legacy guidance is at `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/ipsk.py:692`.

**Impact:** A novice can leave the one-time result without retaining the credential, or assume a QR on their phone is the required next action. Add another device competes with completing the current connection. Credential loss likely needs administrator support because self-service never exposes existing passwords.

**Fix:** Branch instructions by current/other device. For current: visibly instruct “Save your password, finish setup, then join [SSID] with it,” retain private-address guidance, explain the captive action, provide password copy feedback, and make Finish setup primary after saving. Make Add another device secondary. For another device, keep scan/download prominent. Preserve native components.

**Suggested command:** `$impeccable clarify`, then `$impeccable harden`.

### P2 — Existing resident keys are buried below setup and creation work

**Evidence:** With one resident and one live key, heading positions at 1365px are Residents y=1836 and Meraki iPSKs y=1999. At 390px, Residents starts at y=2722 and Meraki iPSKs at y=2905. Guest QR dominates the opening phone viewport; no record count, jump control or manage-keys action is visible. Source/DOM show no resident/key search or status filter.

**Source:** `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/app.py:2906` concatenates QRs, settings, full creation form, onboarding documentation, invitations, residents, then keys. The key table starts at `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/app.py:2899`.

**Impact:** Revoking a lost device or revealing a key requires repeated scrolling even with minimal data. Residents promises management but opens on QR distribution. Larger inventories would compound scan burden; large data was not simulated.

**Fix:** Add a compact top task row: Manage device keys, Create a key, Share setup QR. Make existing management directly reachable and show counts. Put setup QRs/creation in native disclosures or dedicated views. Add search by key/resident/SSID and status filtering.

**Suggested command:** `$impeccable shape` or `$impeccable distill`.

### P2 — “This device” still exposes the other-device hardware-address task

**Evidence:** Group account form has Device to connect = This device, with captured MAC displayed. Immediately below, Other device’s hardware MAC address and instructions remain visible. The unused field occupies substantial phone space.

**Source:** `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/resident_access.py:235` builds the selector; `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/resident_access.py:244` adds the MAC field whenever self-service is enabled, regardless of target.

**Impact:** Residents must decide whether to look up a MAC the portal already knows. They can enter a different MAC while This device stays selected, but the handler uses captured context, making that input misleading.

**Fix:** Reveal/require hardware address only for Another device. For This device, keep captured address as reference and ask for name/unit/invitation. Use a server-rendered target selection if public no-JavaScript remains, or narrowly scoped progressive disclosure if allowed.

**Suggested command:** `$impeccable distill` or `$impeccable clarify`.

### P2 — Legacy registration recovery discards entered details

**Evidence:** Source-only: ValueError from registration renders the error and Return to registration. GET renders empty name/email/unit/invitation fields. Self-service already rebuilds its form using session drafts. Provider failure was not visually simulated.

**Source:** `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/ipsk.py:677`; empty form at `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/ipsk.py:607`. Better pattern: `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/resident_access.py:372` and line 394.

**Impact:** A mistyped invitation or validation error requires retyping personal details on a phone, exactly when the resident is uncertain about success.

**Fix:** Re-render registration beside the actionable error with non-secret values preserved. Keep captive context for correction and mark the invalid field where identifiable.

**Suggested command:** `$impeccable harden`.

## Cognitive load

Certificate flow is low to moderate. Resident management fails **4/8** checklist items; these are local judgments rather than a claim every page is overloaded.

| Item | Result | Reason |
|---|---|---|
| Single focus | Fail on Residents | Sharing, identity setup, creation, invitations and management occupy one page. |
| Chunking | Pass within cards | Card groups are coherent; page sequence remains long. |
| Grouping | Pass | Cards, rows, sections and disclosures group related inputs. |
| Visual hierarchy | Fail on Residents | Guest QR dominates; existing-key management starts several screens below. |
| One thing at a time | Fail in current-device form | Other-device MAC work accompanies the current-device choice. |
| Minimal choices | Pass for primary public tasks | Device choices = 2; fixture group selector = 2 residents. |
| Working memory | Pass in most tasks | Identity/device context remains visible; credential retention is fragile at the self-service end. |
| Progressive disclosure | Fail in resident account | MAC guidance ignores target; admin creation remains expanded above records. |

Decision points exceeding four options: five main admin sections, five certificate filters, five enrollment-link filters, six tool routes, seven revocation reasons, seven lifetime options, eight Wi-Fi authentication methods, five MDM vendors, nine Meraki certificate-name variables. Most are native selects for genuine domain decisions; do not collapse everything just to meet a numeric threshold. Six tool links wrap to three phone rows but provide orientation.

## Emotional journey

Administrator: status reassures → enrollment offers a preferred link path with advanced choices → one-time credential result announces its limits → numbered install guidance sustains confidence. Resident administrator: entry looks like QR distribution → management requires searching down the page → direct row actions clarify the task. Resident: address rejection is an understandable valley with concrete recovery → displayed identity/context reassures → unrelated MAC work causes hesitation → key creation is the peak → missing save/connect guidance weakens the end.

## Persona red flags

- **Alex, episodic administrator:** Lost-key revocation begins on QR distribution and reaches keys at y=2905 on phone. No inventory search/status filter; certificate inventory has both.
- **Jordan, first-time resident:** Other-device MAC input looks like a required lookup even with This device selected. Scan instructions cannot be followed with the camera on the same phone. Finish captive portal does not explain saving/reconnecting.
- **Casey, distracted mobile resident:** Resident password has no copy action. Network-settings switching or Add another device can lose the result, without a self-service save-before-leaving warning. Legacy errors require retyping.

No extra project persona was invented; the documented audiences support these task-specific archetypes. Native accessibility snapshots were read; a full assistive-technology session was not performed.

## Minor observations

- Sign a request, Other trusted CAs and Add-on options repeat the page title above a same-title card: P3 redundancy.
- Resident admin dates include raw datetime microseconds; use the readable certificate-list formatting.
- Public device choices explain private keys/CA chains before installation; shorten novice-facing descriptions while retaining details.
- Resident public markup omits shared script, so slow POSTs lack admin enrollment progress/disabled feedback. Server safeguards exist; no real-network duplicate creation was observed.
- Group selector lists usernames such as alex.resident beneath Choose your name. Prefer display names where available. Large group scale was not inspected.

## Questions for synthesis

1. Which first: resident save/connect guidance, administrator management, or current/other-device form clarity?
2. Should Residents open on existing keys, or sharing access with a prominent Manage keys action?
3. Scope: all four issues, or P1 handoff plus current-device clarity first?

## Browser and cleanup provenance

Native CUA Chrome, new tabs 13305771 admin, 13305774 enrollment, 13305777 resident. No existing tab reused. Desktop snapshots/screenshots at 1365×900 and 1728px default; phone 390×844. Browser override initially affected only active resident tab; tab-scoped CDP metrics produced confirmed 390px admin/enrollment. Overrides cleared/reset; all three tabs explicitly closed. Screenshots inspected in native output; no saved image file is asserted.

One bounded pass: admin list, expiring detail, Enroll, Residents, Authority, all six tools; enrollment entry, mocked .p12 success, invalid-link recovery; resident group entry/account/success, mocked Duo entry/account, legacy entry/success, invalid grant recovery, randomized-address recovery. No shipping edits or iterative polishing round.

Owned fixture `/tmp/codex-stepca-critique-a-preview.py`, generated data `/tmp/codex-stepca-critique-a-fixtures`, listeners 49508/49509/49510. Original PID 43995 and later PID 44864 terminated during fixture-only adjustments; final runner session 65938 stopped by Ctrl-C, exit 130. Generated-only certificate/profile result mocks prevented real issuance. Public.public locally mapped /enroll paths to avoid the integration proxy. Chrome blocked the first mismatched integration-path submit and zero-body preview-mode navigation; local fixture mapping and HTTP preview-mode request resolved inspection. These are preview limitations, not product defects. Correct grant endpoint is /splash/grant; supplied /grant example produced recovery.

No actual credentials, real CA private files, WPN data/.signing_key, live Meraki/Duo services, detector output, prior audits or other review findings inspected. Shipping source unchanged. Initial combined report/cleanup shell command was rejected before execution because rm -f was disallowed; file-edit writing and scoped Python cleanup used instead. Owned temporary fixture script/data removed after stopping; durable output is this assessment only.
