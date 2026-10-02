# Assessment A confirmation — 2026-10-02

Method: one bounded design confirmation by `/root/critique_design`, using the original Assessment A as backlog. No additional aesthetic scan, detector run, redesign proposal, or shipping source edit. Current source reviewed in admin/app.py, admin/ui.py, admin/ipsk.py and admin/resident_access.py. The native Home Assistant Operate identity remains intact.

## Verdict

**All four original priority findings are resolved in the inspected source and mocked browser flows. No remaining actionable priority from this backlog.** The five minor observations are addressed, with slow-submit transition behavior supported by source but not captured during instantaneous mock responses. This is a narrow confirmation, not a new full-product or production integration certification.

## Priority confirmation

| Original finding | Result | Current evidence |
|---|---|---|
| P1: self-service success lacks save/connect handoff | Resolved | Current-device result warns that the password is shown once, says to save it, finish setup, then join the named network. Private-address guidance and five-minute setup-window explanation are present. Copy Wi-Fi password produces a visible/accessible Copied Wi-Fi password toast. Finish setup is primary; Download QR and Add another device are secondary. Other-device result explicitly says to scan with the other device and offers download/manual-password alternatives. |
| P2: existing resident keys buried under setup | Resolved | Manage resident access opens with counts, three task links, search and key status. Wi-Fi keys begin at y=503 in the confirmed 390px viewport, versus y=2905 previously. Creation/setup are disclosed below records. Missing search produces No matching keys and No matching device records with corrective guidance; Clear filters restores records. Revoked status excludes the active mock key, while the separate Registered devices table remains visible. Create a key opens #create-device-key and its native disclosure. |
| P2: irrelevant other-device MAC field on This device | Resolved | Actual browser state for This device: MAC group hidden, input disabled, required=false. Switching to Another device: group visible, input enabled, required=true. Randomized MAC rejection focuses a readable error and retains device name, target, entered MAC and unit. Switching back to current produces successful mocked creation using captured context. |
| P2: legacy registration errors lose entered details | Resolved | INVALID invitation returns the editable form with Confirmation Resident, confirmation@example.org and unit 101 retained. Invitation is blank, and the actionable error receives focus. Entering VALID completes in the same captive session. |

Current source anchors: `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/resident_access.py:388` for warning and target-specific completion; `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/ipsk.py:314` for copied Wi-Fi password; `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/app.py:2741` for task access; `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/app.py:2820` for creation disclosure; `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/resident_access.py:244` for controlled MAC disclosure; `/Users/jolipton/Projects/hassio-addons-1/step-ca/admin/ipsk.py:542` and line 691 for legacy draft recovery.

## Minor observations

- **Repeated tool titles:** resolved in source. Cards now use Running configuration, Device trust certificates and signing-specific content headings instead of immediately repeating the page title.
- **Raw resident datetime microseconds:** resolved in the browser. Registered devices and Invitation codes show readable minute precision with UTC, e.g. 2026-10-02 21:44 UTC.
- **PKI-heavy public device descriptions:** resolved in source. Apple choice says the profile sets up the certificate; Other device names the password-protected certificate file and promises installation steps.
- **Public script/progress omission:** public pages now include nonce-bound shared UI script and a matching CSP nonce. Actual conditional disclosure, copy toast and error focus demonstrate script execution. The shared POST handler sets aria-busy, disables submit, and changes its label to Working…. Instant mock replies prevented capturing that transient state; the parent's separate technical check owns slow-submit verification.
- **Choose your name while listing usernames:** resolved. Browser entry labels the selector Resident account and placeholder Choose your account, matching the listed usernames. Display-name support and large groups are outside this narrow confirmation.

## Updated Nielsen scores

All ten remain applicable. Scores combine the unchanged initial review with confirmation of the corrected backlog; areas outside the fixes were not re-audited.

| # | Heuristic | Score / 4 | Reason |
|---|---|---:|---|
| 1 | Visibility of system status | 3 | Counts, selected filters, copy toast and focused recovery are visible; slow-request progress still needs technical confirmation. |
| 2 | Match system / real world | 3 | Target-specific instructions and simpler certificate choices remove avoidable translation; some PKI/device terminology remains intrinsic. |
| 3 | User control and freedom | 3 | Clear filters, task jumps, session exit and correction flows work; irreversible/one-time operations retain their deliberate constraints. |
| 4 | Consistency and standards | 4 | Reviewed fixes reuse the native HA controls, shared copy/error behaviors and consistent completion hierarchy. |
| 5 | Error prevention | 3 | Conditional required state and existing confirmation guardrails work; no claim that every external integration error is prevented. |
| 6 | Recognition rather than recall | 4 | Management is immediately discoverable, device context stays visible, and save/connect instructions accompany the credential. |
| 7 | Flexibility and efficiency | 3 | Resident search/status/clear and direct task access now complement certificate inventory controls. |
| 8 | Aesthetic and minimalist design | 3 | Management leads; setup/creation disclose; current-device form avoids unrelated fields. |
| 9 | Error recognition and recovery | 3 | Legacy and self-service drafts survive the inspected validation failures, with plain focused errors. |
| 10 | Help and documentation | 3 | Task-specific handoff guidance now closes the resident journey; broad searchable help was not added or re-evaluated. |
| **Total** | | **32/40 — Good** | **Previously 27/40.** |

## Cognitive and journey update

The original four local cognitive failures are resolved: management has a clear primary job, keys lead the hierarchy, current-device flow asks only relevant questions, and setup/other-device work is disclosed. No new failure identified against the eight-item backlog checklist. Legitimate domain menus exceeding four choices remain as originally documented.

The resident success peak now ends with explicit saving and connection instructions. Administrator management starts with records and filters; residents can correct validation failures without rebuilding identity details. Alex's buried-key concern, Jordan's irrelevant MAC/same-phone scan concerns, and Casey's missing copy/retyping concerns are addressed in the inspected scenarios.

## Scope and provenance

Fresh native CUA Chrome tabs: 13306025 admin and 13306028 resident. No user tab reused. Desktop 1365×900 and phone 390×844 were inspected in one bounded confirmation sequence using tab-scoped CDP viewport sizing. Viewport overrides cleared and both tabs explicitly closed.

Used parent-owned current-source mocked fixture at 49708 and 49710, executable source `/tmp/codex-stepca-critique-confirm-preview.py`, parent exec session 68448. The parent confirmed exclusive mode control; switched group to legacy for the invitation recovery scenario, then restored group. Parent fixture server left running; no parent files/processes cleaned up by this reviewer.

Screenshots inspected in native tool output, not asserted as saved image artifacts. A label locator did not resolve the implicit Key status label although DOM/native accessibility named it correctly; the role/name locator worked. One copy lookup initially used the old Passphrase terminology; fresh accessibility state identified Copy Wi-Fi password, which then worked. These were tool targeting limitations, not product findings.

Limits: only mocked services and synthetic identities/passwords. Did not follow Finish setup to the Meraki grant endpoint, join a real network, validate a physical QR camera scan, inspect live CA/Meraki/Duo credentials, simulate large inventories, or run an assistive-technology session. No new certificate issuance was needed for the source-only simplified device-copy confirmation. Slow-submit progress is source-confirmed and left to the parent's technical browser check. No shipping edits; durable output is this confirmation.

Questions skipped: zero remaining actionable priorities from this confirmation backlog.
