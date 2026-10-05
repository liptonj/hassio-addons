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

Pending the source CI and installed-version verification.
