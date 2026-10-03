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
