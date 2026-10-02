# Technical confirmation B — 2026-10-02

One bounded confirmation of the applied fixes against current source and an independent mock fixture. No shipping edits and no CLI detector rerun. Original Assessment B's 82-warning evidence remains unchanged.

## Result

- **246/246 functional assertions pass after asynchronous event completion**, across desktop 1280px and phone 320/390px, each light/dark. The raw first observations were 243 pass / 3 fail; all three failures sampled the disclosure before its `hashchange` handler. Waiting on the real `details.open` condition (at most 1 second) passed each. Raw observations are preserved in JSON.
- **48 axe all-rule scans**, with 48 successful nonce-authorized script loads. Four raw color-contrast nodes appear only on the resident success toast during its fade. One requested settled computed-style check gives opacity 1, foreground `rgb(241, 241, 241)`, background `rgb(50, 50, 50)`, **11.35:1 contrast**. All six settled legacy success toast scans have zero violations. There are no unresolved axe violations identified by this pass; axe incomplete checks remain explicitly recorded for manual judgment.
- **0 document overflows** in 48 states. **0 JavaScript page errors**. Twelve console resource errors are the expected HTTP 400 responses for deliberate invalid MAC and invitation submissions (two per combination).
- No remaining substantive defect found within this confirmation.

## Verified behavior

| Check | Exact evidence | Combinations |
|---|---|---|
| Nonce JavaScript | `documentElement.classList` includes `js`; nonce present; response CSP matches nonce where captured | 6 × 8 states |
| Current device MAC | wrapper hidden, input disabled, required false | 6 |
| Other device MAC | wrapper visible, input enabled, required true | 6 |
| Device draft recovery | Fixture TV, invalid MAC `02:11:22:33:44:55`, B-204 and `target=other` retained | 6 |
| Password copy | Actual clipboard equals `fixture-device-password`; toast `Copied Wi-Fi password` | 6 |
| Slow POST | Mutation observer captures `aria-busy="true"`, button `disabled=true`, text `Working…` before delayed navigation | 6 |
| Legacy invalid invite | Taylor Fixture / taylor@example.org / Room 310 retained; invitation blank; `INVALID-SECRET` excluded from returned HTML | 6 |
| Certificate filter | No-match row appears; clearing query restores 2 data rows | 6 |
| Admin filters | No matching keys appears; Clear filters restores 1 key row | 6 |
| Create-key jump | Hash `#create-device-key`, `details.open=true` after hashchange | 6 |
| Keyboard/table | Skip link Enter focuses main-content; labelled table region has tabindex 0 and headers, receives focus | 6 |

The controlled two-second delay was added only to the mocked legacy registration call. The observer recorded app-owned DOM mutations; it did not assign busy values. Fixture services contain synthetic data and passwords, with no real CA credentials or production signing keys.

## Browser and injection provenance

The native browser entry point returned `Browser is not available: iab` in this resumed environment. The Playwright skill fallback was used with installed Google Chrome. Pending navigation destroyed the original page evaluation context, so the remaining legacy/admin checks ran as a continuation; already collected resident checks were not rerun. A scratch variable declaration was repaired before that continuation reached the app.

Axe 4.13.0 was installed only in `/tmp/codex-stepca-technical-tools`. An owned fixture-only `/axe.js` endpoint served it. The script element carried each response's existing nonce. Application CSP was not weakened. These are automated browser scans, not Impeccable overlays. The original Assessment B overlay CSP failure remains separately documented.

Three immediate disclosure observations raced the asynchronous hashchange event. A narrow settled condition check resolved those observations. The requested single resident toast settled-style check resolved the animation-stage contrast flags; no further axe or detector round was run.

## Evidence and cleanup

Full raw axe violations/passes/incomplete counts, console messages, observable assertions, nonce/CSP checks, source SHA-256 hashes and fixture hash are in [confirmation-b-2026-10-02.evidence.json](confirmation-b-2026-10-02.evidence.json). Six screenshots are in `confirmation-b-2026-10-02-assets/`.

Owned preview PID **22728**, runtime `/tmp/codex-stepca-critique-venv/bin/python`, ports **49808/49809/49810**. Stop method: `kill -TERM 22728`, followed by process/port verification. All owned direct Playwright contexts and browser processes closed in `finally`; the temporary CLI browser PIDs 17671 and 19443 had already been stopped. No parent fixture was touched.

Cleanup verification: PID no longer exists; all three owned ports are closed.
