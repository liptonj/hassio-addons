---
version: 1
slug: "admin-app-py"
primary_target: "admin/app.py"
related_targets: []
---

# Certificates panel (step-ca admin + public enrollment pages)

Scope: every page rendered by step-ca/admin/app.py, both the ingress admin panel (Certificates, Enroll, Authority) and the public enrollment pages (EnrollHandler). Mode: Operate.

Audience and job: a Home Assistant admin who enrolls or revokes a device, finds a certificate, or grabs a CA file in under a minute. A device owner who taps through a one-time link.

Constraints: stdlib server, inline CSS, nonce'd inline JS only, no external assets, MDI icons inlined as SVG paths. Routes, form field names, and CSRF are unchanged.

## Direction contract

THESIS: The panel is a native Home Assistant Settings page: tabbed subpage toolbar, outlined 12px cards, data table, filter chips, ha-alert banners, and settings rows. It refuses the generic admin scaffold of a stat-tile hero over cards stacked down the page.

OWN-WORLD: HA default tokens (primary #03a9f4, background #fafafa/#111111, card #fff/#1c1c1c, divider at 12% alpha, success/warning/error/info), overridden live by the user's actual HA theme read from the parent frame. Roboto and system stack, MDI icons, pill buttons, 8px filter chips, monospace only for serials, fingerprints, URLs, and passwords.

STORY: The admin sees at once whether the CA is healthy and what is expiring, finds a device, and acts. Revocation and one-time secrets stop them deliberately. A device owner sees two big choices and numbered steps.

FIRST VIEWPORT: A 56px toolbar with the title and three tabs (Certificates, Enroll, Authority) at top; on mobile the tabs move to a bottom bar. Below it, one outlined health card in a single row: CA valid until, active count, expiring within 30 days (a link that filters), revoked. Then a search field with filter chips and the "Enroll device" filled button at the right, then the data table with expiry shown as a date plus relative time.

FORM: canon (the user took the standing exit: "stay within the theming of Home Assistant"), the category standard played straight at HA's own craft level; seed key 25759b36. Signature interaction: the panel wears the user's live HA theme, and every serial, fingerprint, URL, and password has a copy action that confirms with an HA-style toast. Motion: the toast rises with an exponential ease-out; the revoke dialog fades and scales in; reduced motion turns both off.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
