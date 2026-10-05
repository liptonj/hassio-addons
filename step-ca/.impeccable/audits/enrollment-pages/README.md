# Focused enrollment pages — 0.30.2.55

Enroll now opens a compact task chooser with four separate destinations:

- `/enroll/new`: new one-time link form, including its signing status and advanced options.
- `/enroll/links`: filtered, paginated inventory with cancel and deletion actions.
- `/enroll/self`: enrolling the computer using the panel.
- `/enroll/issue`: direct .p12 issuance.

All five main dropdowns remain available on each task page. The current task is
highlighted. Validation stays on its own page and retains entered details.
Results return to their task; inventory actions preserve the view and page. Old
fragment/query bookmarks and `/issue` POSTs remain compatible. Public device
enrollment retains its existing layout.

## Bounded verification

The initial browser pass covered all five routes at 1280px/light and 320px/dark,
each with navigation closed and Enroll open: 20 axe views, zero violations,
body overflow or clipped menus. No visual repair round was needed. Screenshots
show local fictional fixture data, not the production installation.

Nine interaction checks cover invalid link creation with retained label, valid
fixture link result/back navigation, inventory pagination/cancellation, three
legacy fragment targets, direct-issuance error recovery, keyboard Escape/focus
and native dropdown navigation without JavaScript. Label input values were
masked by browser tooling; retention was confirmed through the visible result
heading after correcting only the CN and resubmitting.

The expanded suite passed 203 tests and seven checks against Home Assistant
2026.9.4. Container builds and nonroot runtime probes passed for aarch64, amd64
and armv7. Every runtime matched all 11 admin source hashes and rendered all five
enrollment routes with all five dropdowns. Static checks passed. Machine-readable
results are in `release-checks.json`, `browser-checks.jsonl` and
`interaction-checks.json`.

## Deployment

Source CI [37337000619](https://github.com/liptonj/hassio-addons/actions/runs/37337000619)
passed for commit `28ad0a055b03ceaf42c1bc532325c7114ee65457`.

The initial deployment completed the Step CA/MariaDB backup at 16:01:23Z but
returned `unknown_error` while monitoring the update. A read-only inspection
confirmed version 0.30.2.55 started. The final exact-version run skipped
reinstallation and passed the running-version, Core configuration/restart,
companion-loaded and live IPSK options checks at 16:05:00Z (five wireless
networks). [Verification run 37337751094](https://github.com/liptonj/meraki-homeassistant/actions/runs/37337751094)
succeeded. Details are in `deployment.json`.

The temporary fixture server and browser tabs were closed. The isolated build
builder and Colima profile were removed, leaving the prior default profile
unchanged.
