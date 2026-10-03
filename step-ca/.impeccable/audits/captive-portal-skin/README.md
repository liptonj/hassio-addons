# Captive portal skin verification

Local source fixture previews, not screenshots of the deployed Home Assistant
instance. The logo and Example Wi-Fi copy are fictional test inputs, never live
settings. No product raster assets were introduced.

The bounded review used one initial matrix (52 views, including draft/saved
forms and welcome/Duo/ready/error states at 1280, 390 and 320 pixels in both
ambient themes) and one confirmation batch (5 views, invalid-color recovery,
custom light colors and final forms). Both batches report zero axe violations
and no horizontal overflow. The initial screenshot captures clipped physical
pixels on the high-DPI host; retained final images use explicit CSS viewport
clipping. Metrics and axe checks used the correct CSS layout dimensions.

Native browser input confirmed saving with JavaScript disabled. An automation
locator timed out while JavaScript was disabled; the native accessibility click
submitted successfully and displayed “Portal settings saved”. Logo upload,
preview persistence, save and immediate public rendering were verified.

`browser-round1.json` and `browser-confirmation.json` contain the recorded
checks. Release and deployment evidence is recorded separately.

Finish verdict: shipped and verified in Step CA 0.30.2.52. All 189 tests, seven
real Home Assistant compatibility checks, Ruff, shell syntax and whitespace
checks passed. Container builds and non-root runtime probes passed for amd64,
aarch64 and armv7, including all three image codecs and storage. GitHub source
CI passed before the backed-up update.

Supervisor reported an update-job error after submitting the update. A read-only
inspection confirmed 0.30.2.52 started; final verification skipped reinstallation,
checked stability, checked/restarted Core and confirmed the companion loaded and
the live IPSK options request returned five networks. See `deployment.json`.

Scope limit: branding interactions and visual checks used a local source
fixture. Deployment verification checks installed/running version and real
companion behavior; fictional logos and copy were never applied to live settings.
Duo-hosted prompt branding is managed by Duo. No new independent critique score
is claimed.
