---
version: 1
slug: "admin-app-py"
primary_target: "admin/app.py"
related_targets:
  - "admin/ui.py"
  - "admin/enroll.py"
  - "admin/ipsk.py"
  - "admin/resident_access.py"
  - "admin/captive.py"
---

Resident Access Manager migration (2026-10-05): Network and onboarding selects
the key service and filters enabled resident SSIDs/client groups. Duo choices,
invitation checks and quotas remain in their established flows. New client keys
are shown once, pending writes have durable password-free attribution, and
owned revocation retains the client. The setup portal uses a separate configured
SSID with its current authentication. Browser and test evidence is recorded in
`.impeccable/audits/resident-access-manager/README.md`; live activation needs the
target network/SSID/group and NAC API access. Existing certificate profiles remain
valid. No visual identity or shipping image assets changed.

# Certificates and resident network panel (Step CA)

Scope: every page rendered by step-ca/admin/app.py, both the ingress admin panel (Certificates, Enroll, Residents, Authority, Tools) and the public enrollment pages (EnrollHandler). Mode: Operate.

Audience and job: a Home Assistant admin who enrolls or revokes a device, finds a certificate, or grabs a CA file in under a minute. A device owner who taps through a one-time link.

Constraints: stdlib server, inline CSS, nonce'd inline JS only, no external assets, MDI icons inlined as SVG paths. Preserve the route contracts, form semantics, and CSRF protection.

## Direction contract

THESIS: The panel is a native Home Assistant Settings page: tabbed subpage toolbar, outlined 12px cards, data table, filter chips, ha-alert banners, and settings rows. It refuses the generic admin scaffold of a stat-tile hero over cards stacked down the page.

OWN-WORLD: HA default tokens (primary #03a9f4, background #fafafa/#111111, card #fff/#1c1c1c, divider at 12% alpha, success/warning/error/info), overridden live by the user's actual HA theme read from the parent frame. Roboto and system stack, MDI icons, pill buttons, 8px filter chips, monospace only for serials, fingerprints, URLs, and passwords.

STORY: The admin sees at once whether the CA is healthy and what is expiring, finds a device, and acts. Revocation and one-time secrets stop them deliberately. A device owner sees two big choices and numbered steps.

FIRST VIEWPORT: A 56px toolbar with the title and five tabs (Certificates, Enroll, Residents, Authority, Tools) at top; on mobile the tabs move to a bottom bar. Below it, one outlined health card in a single row: CA valid until, active count, expiring within 30 days (a link that filters), revoked. Then a search field with filter chips and the "Enroll device" filled button at the right, then the data table with expiry shown as a date plus relative time.

FORM: canon (the user took the standing exit: "stay within the theming of Home Assistant"), the category standard played straight at HA's own craft level; seed key 25759b36. Signature interaction: the panel wears the user's live HA theme, and every serial, fingerprint, URL, and password has a copy action that confirms with an HA-style toast. Motion: the toast rises with an exponential ease-out; the revoke dialog fades and scales in; reduced motion turns both off.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Wi-Fi setup task (implemented 2026-10-02)

The task extends the established Settings-page world with a network editor, saved-network list, and setup guide. It adds task sections and shared controls without changing the HA identity. Source truth is `admin/app.py` for composition and copy, `admin/ui.py` for shared styling and behavior, and `admin/enroll.py` for authentication and profile payloads.

THESIS: Certificate setup stays understandable from the network choice through installation.

STORY: Match the network, choose how the device authenticates, verify server trust, then install a fresh profile.

FIRST VIEWPORT: Above 860px, a compact saved-network list and setup guide occupy the left column (`minmax(280px, 1fr)`), beside a wider editor on the right (`minmax(0, 2fr)`), with a 24px gap. At 860px and below, the DOM order puts the editor first, followed by the saved networks and guide, with a 16px gap. “Network editor” and “Saved networks & guide” jump links retain direct access to both regions. This composition belongs to the Wi-Fi surface; other panel pages retain their incumbent layout.

FORM: Network details and Authentication are open initially. Connection behavior, Proxy, Device-specific behavior, QoS, and Passpoint use disclosure sections that open when saved settings require them. Server trust & TLS is an open section within a method-dependent region. Form sections use 56px minimum summaries, divider borders, 20px insets (16px mobile), and the shared HA chevron behavior.

SIGNATURE: Changing authentication reveals its relevant credential fields and updates a polite live profile summary: method, security, and whether the network appears in every enrollment profile or a separate MDM profile. The summary contains no secrets.

## Authentication and installation guidance

- EAP-TLS uses the issued device certificate and an optional 802.1X identity; an empty identity uses the certificate name.
- PEAP, EAP-TTLS, and EAP-FAST expose account credentials, an optional outer identity, per-connection password prompting, and an optional device certificate. EAP-TTLS adds inner authentication; EAP-FAST adds paired PAC controls with authenticated provisioning.
- EAP-SIM and EAP-AKA expose carrier guidance for compatible iPhone or iPad SIMs. EAP-SIM adds minimum RAND challenges. The SIM supplies the Wi-Fi identity.
- LEAP exposes legacy account credentials and a warning that it has no TLS tunnel. It does not show server-certificate trust controls.
- Pre-shared key exposes the shared network password. TLS server trust and limits appear only for EAP-TLS, PEAP, EAP-TTLS, and EAP-FAST. Passpoint is for supported enterprise EAP methods; shared keys and LEAP are unsupported.

Saved rows show the authentication method and security alongside network details. The guide explains that these settings configure client profiles; access points and RADIUS must already match. Changes apply to new downloads, and installed profiles must be replaced. Apple profiles configure the network; other devices receive method-specific setup instructions. TEAP, EAP-PWD, and EAP-AKA′ are not offered by Apple's managed Wi-Fi payload.

## Shared controls and states from this task

All six tools (Groups, Wi-Fi networks, MDM profiles, Sign a request, Other trusted CAs, Add-on options) use the wrapping tool navigation with a visible current-page state. Admin and public enrollment pages include a keyboard-visible skip link to main content.

Shared form behavior associates direct field hints through `aria-describedby`, adds named Show/Hide controls to password fields, opens enclosing disclosure sections for native invalid controls, and focuses server error alerts. POST submissions expose `aria-busy`, disable submit buttons, and show “Working…”. Focus outlines, focused field borders/rings, and linked-table-row indicators all use `--focus-color`, aliased to the active theme's accent ink. Method-specific validation applies to relevant authentication settings; unrelated EAP text cannot block switching to a pre-shared key. Saved secrets remain absent from input values and are preserved when the edit field is left empty, unless explicitly removed or superseded by the selected credential behavior.

## Finish evidence

Final review disposition: ship for the three material findings; all resolved. Method instruction accuracy, hidden-field validation, and focus contrast were resolved. Desktop and mobile captures at the repository's `.impeccable/review/desktop.png` and `mobile.png` are synthetic previews; they do not demonstrate live Home Assistant operation. Fourteen tests and Python, JavaScript, YAML, and whitespace checks passed for the implementation. Live HA theme adoption, RADIUS interoperability, and physical-device installation remain unverified. No shipping raster assets were introduced.

## Resident captive portal (2026-10-02)

The migrated WPN flow uses the incumbent HA public enrollment world. The default setup PSK opens Meraki's click-through captive portal; the hardware MAC check precedes the resident form. Direct visits explain how to connect. A private, missing or invalid MAC stops registration and shows device-specific recovery instructions. The form uses the MAC captured in a 15-minute server session, with no editable MAC field. Successful registration shows the resident key and Wi-Fi QR, then offers a validated Meraki grant link for a five-minute completion window. Residents reconnect with their individual key and keep private addressing off for that network.

Public page bodies use the existing `card-content` inset, 16px input text to avoid mobile focus zoom, and 44px minimum actions. The admin Residents list includes the captured hardware MAC. Only the resident public surface receives these control overrides.

Verification: 31 local tests passed (17 captive flow/policy and persistence checks and 14 existing Wi-Fi/profile checks). Desktop 1280px and mobile 390px previews covered direct entry, private-MAC rejection, registration and completion with mocked resident creation. Screenshots are development previews; live Meraki redirection, splash policies and physical-device connection remain unverified. EXCAP fields are unsigned; the local-bit check conservatively rejects local MACs and does not authenticate the initial redirect or prevent spoofing.

## Guest, registration and other-device QR flows (2026-10-02)

The Residents page now begins with two downloadable join codes: Guest access uses the existing guest key; Join and create a key uses the setup key and leads into Meraki captive registration. The administrator supplies their existing network credentials in a collapsed QR settings section. Password inputs do not contain saved secrets. Guest splash bypass and setup captive policies must already exist in Meraki.

Administrators can create a key for another device and immediately download its join QR. Active existing keys have a Show QR action. Device codes use the actual SSID and current revealed password returned by Home Assistant; revoked, expired or incomplete key details cannot produce a QR. Generated codes preserve literal credentials, escape Wi-Fi payload delimiters, include a four-module quiet zone and a white background, and contain the Wi-Fi credentials rather than a hardware binding.

The QR pair uses two columns on desktop and one on mobile. Generated device details appear above the pair. Mobile inputs use 16px text and buttons have 44px minimum height. The existing HA form, button, disclosure, alert and CSRF patterns remain in use. Empty network settings give a direct recovery link; failure to retrieve a newly created key's QR reports the created key without making a second key.

Verification: 47 local tests passed, including 16 QR settings, encoding, authorization and key workflow checks. Desktop 1280px and mobile 390px previews cover the QR cards, settings, creation and existing-key QR actions using mocked services. These are scoped implementation checks; a full independent Impeccable critique is still pending. Live Home Assistant, Meraki splash behavior and physical scanning remain unverified. No shipping raster assets were introduced.

## Resident self-service and Duo (2026-10-02)

The Residents administrator page adds a collapsed Resident self-service and Duo section. Administrators independently allow other-device creation and choose whether Duo verification is required. Without verification, a group-only selector is optional; otherwise the resident enters a name and email. The group selector is explicitly unverified attribution. The directory calls only the configured group's paged members endpoint and selected-user details, never all tenant users. Empty, inactive, inaccessible or oversized groups stop the flow.

Public pages retain the HA enrollment visual world and present one identity step followed by one device form. The device form selects the captured current device or asks for another device's hardware MAC. Successful creation shows the literal SSID, password and downloadable QR, followed by Add another device. Errors retain device-name, unit and MAC drafts. Forms use 16px input text and 44px actions. Mobile administrator control overrides use main-content specificity because custom page CSS precedes the shared stylesheet.

Duo verification uses the official Universal SDK with browser-bound, single-use state and nonce, username validation, factor evidence and fresh group membership checks. It supplies factor verification, not primary password SSO. Administrator credentials remain blank in saved-secret fields. Resident sessions are server-side, expire after 30 minutes and are invalidated by policy changes. A no-sign-in session begins through captive setup. No self-service mode retrieves existing passwords. Device attribution, limits and invitations use Step CA's MariaDB schema; certificates remain in the existing CA.

Verification: 72 local tests passed, including 25 self-service/Duo tests. Two batched browser rounds covered desktop 1280px and mobile 390px selector, Duo login, device form, no-sign-in name/email, private-target rejection with draft recovery, generated QR and administrator settings. The Duo redirect and service responses in these previews are fixtures. No horizontal page overflow, missing input labels or saved secret values were observed. Mobile admin input specificity was corrected from computed-style evidence after confirmation. SQL schema/grants and SDK usage are locally inspected or mocked; a Docker image build, live Duo enrollment, MariaDB migration, HA proxy deployment and physical Meraki connection remain unverified. No shipping raster assets were introduced. Full independent critique remains pending.

## Full audit (2026-10-02)

All local audit findings were corrected. The final pass covered 63 automated
accessibility views at 1280px and 320px, default light/dark themes, private-MAC
rejection, resident device draft recovery and generated QRs. Five interaction
checks covered enlarged text, submission values, password visibility and
confirmation-dialog focus. No violations, page overflow, missing labels,
broken control relationships or JavaScript errors remained in those fixtures.
The 88 local tests pass. The HTML detector emitted 48 reviewed pattern flags
for the incumbent HA font/scale, focus/selection strokes and padded card
composition; none represented an actionable defect. Parser dependencies were
installed in an isolated temporary tool directory for the full detector pass.

### Runtime continuation and new-install clarification

The user clarified that this is a new installation. The old WPN database
reader, startup option, translation and fixtures were removed; all portal data
is created directly in Step CA's MariaDB. The current verification supersedes
earlier unverified image/database notes above.

Final images build and import on aarch64, amd64 and armv7. Real MariaDB 10.11.19
passes 26 checks across fresh and previous Step CA schemas. Actual disposable
CA issuance, PKCS#12 decoding, renewal, revocation, CRL publication, SCEP
capabilities, companion install and renewal after restart pass. The companion
1.5.0 adds the missing Meraki SDK bridge; SDK 4.5.0b2 passes an actual loopback
HTTP contract check. Attribution/history stays in MariaDB without passwords.
112 unit/contract tests pass. The network picker loads the correct scope; four
all-rule accessibility scans pass at desktop/mobile widths in light/dark after
correcting the invitation action heading.

Production Home Assistant/Meraki/Duo and physical device installation remain
unverified. The independent critique still awaits the already-requested
permission for its two reviewers. See `../audits/2026-10-02-full-audit.md`.

### Meraki SDK and secrets follow-up

Meraki HA now pins 4.5.0b4 in its manifest, development dependency and lockfile.
Stable 4.5.0 was evaluated; its missing Push API operations require retaining
the beta line. The new beta passes Step CA's 112 local contract tests. Meraki HA
has regression coverage for actual token refresh on loopback, recursively
redacted diagnostic/dashboard/subscription payloads, preserved runtime data,
administrator-only key creation and credential-safe provider errors. Cisco
secrets and tokens stay in Home Assistant's existing stores, with no Step CA
copy; those stores are filesystem-backed, not encrypted vaults. No shipping UI
layout changed and no further cosmetic self-QA was run. Updated evidence is in
`../audits/2026-10-02-meraki-sdk-secrets-evidence.json`.

### Portal request follow-up

The public form policy now permits only the configured Duo HTTPS host when
verification is required. Chromium reproduced the previous blocked POST
redirect; a native submission reached a controlled Duo response after the fix,
with zero console errors. Provider exception bodies, including lazy directory
paging errors, are contained and basic registration logs omit reflected bodies.
Successful device requests rotate their form token while still marked busy.

119 portal checks pass. Current images build and run on aarch64, amd64 and armv7;
26 MariaDB checks and eight disposable CA lifecycle/restart checks pass again.
The public CA root is unchanged. This was functional verification, with no
additional cosmetic review round. The previously retained audit data disk was
removed with explicit `--data` cleanup. Independent critique and deployed
provider/physical-device checks remain pending. Current evidence is in
`../audits/2026-10-02-portal-final-evidence.json`.

### Independent critique fixes

Two isolated reviewers assessed the complete current interface after explicit
user approval. The design assessment found one P1 and three P2 resident-flow
issues; the detector/browser assessment independently confirmed the irrelevant
other-device field. The design assessment completed before detector findings
entered synthesis. Both preserved the incumbent Home Assistant visual world.

Resident management now precedes setup with counts, task links, search and key
status filtering. Creation/setup are disclosed. The resident account form
reveals/disables/requires the other-device field according to the selected
target. Validation retains non-secret details. Success emphasizes saving the
one-time password, supplies shared copy feedback and distinguishes this-device
connection from other-device scanning. Nonce-protected shared controls provide
submission feedback. Related account labels, date formatting, novice device
descriptions and repeated tool headings were clarified.

Independent assessments and the bounded confirmation are archived under
`../critique/`. Detector results retain their original provenance; the interrupted
raw temporary files were lost and the evidence index was reconstructed from
recorded output without fabricated hashes or snippets.

### Final critique/runtime confirmation (2026-10-02)

This entry supersedes historical pending-review and test-count notes above.
The approved independent design confirmation resolves all four priorities and
five minor observations, improving the Nielsen score from 27/40 to 32/40.
Keys begin at y=503 rather than y=2905 on the inspected 390px layout.
The independent detector reviewed 82 raw flags across 31 nonempty application
pages without disabling rules; none was actionable. No detector overlay ran
because CSP blocked its external script. The original interrupted temporary
payload loss is disclosed in the durable assessment.

126 current portal checks, 26 real MariaDB checks and eight disposable CA
lifecycle/restart checks pass. Current images build and run on aarch64, amd64
and armv7 with matching packaged source hashes. Meraki SDK 4.5.0b4 remains the
latest compatible beta verified on October 2; the matching integration source
retains its passing 1,141-test evidence. Disposable CA/database/image data and
parent preview were removed. Colima temporarily selected the critique context;
deletion selected default, while the default profile remained stopped and
unchanged. See `../audits/2026-10-02-critique-final-evidence.json` and the two
independent confirmation reports. Deployed providers, physical devices and a
physical assistive-technology session remain unverified.

### Pre-install improvements (2026-10-02)

Added Setup and checks, searchable help, resident progress/recovery, group-only
account filtering, complete-inventory MariaDB search and independent pagination/
sorting. Secondary tools and sorting disclose on narrow/task-focused surfaces.
Source syntax and desktop/320px mocked rendering were inspected. No full test
suite, container rebuild, live provider check or independent rescore was run for
this addition. The earlier 32/40 critique and 17/20 audit remain historical
assessment results, not a new score for this revision. See the pre-install
change record under ../audits/.

### Central Settings (2026-10-03)

The current navigation is Certificates, Enroll, IPSK, Authority and Settings.
Settings supersedes historical Tools navigation: a four-category hub and
focused subpages provide a desktop sidebar, breadcrumbs and a mobile native
disclosure. Existing forms are moved without changing their validation or
CSRF protection; Home Assistant-managed configuration has redacted saved
summaries and a direct edit link. Operational inventories stay under IPSK.
All add-on option keys are covered by the grouping test.

The bounded inspection and one confirmation covered 88 final views, with zero
axe findings, incomplete checks or horizontal overflow; keyboard and no-script
menus passed. This is scoped verification, not a new independent audit score.
See `../audits/settings-menu/`.

### Identity & access (2026-10-03)

The Settings hub now has five categories. Authentication and User directory
are independent forms under Identity & access; they are available with IPSK
disabled and do not require its network/database configuration. IPSK Device
access holds consumer policy and limits, linking to those shared services.
The new module provides provider field groups, validation and rendering;
scoped saves preserve unrelated options and retained secrets. Legacy option
keys remain compatible. Current runtime remains Duo verification plus a
group-scoped directory, not primary password SSO.

### Meraki configuration (2026-10-05)

Settings now includes Meraki Connection, SSIDs and portals, and Access Manager.
The existing HA visual world, shared controls and admin/CSRF boundaries remain.
Connection settings prefer the Meraki HA session with an optional API key fallback.
Enabled SSIDs include every authentication mode; human-readable change previews
precede SSID/splash writes and per-client Access Manager key assignment.

The bounded desktop/light and phone/dark inspection and confirmation covered the
three pages and two previews. SSID 0, labels, layout, connection testing, both
preview/apply flows and SSID read-back passed with local fixtures. Static detection
reported no findings; rendered detector scanning was unavailable without Puppeteer.
251 tests and the twelve-command real Home Assistant 2026.9.4 compatibility check
passed, including real SDK HTTP fixtures. This is scoped functional verification,
not a new independent accessibility or design score. Evidence is in
`../../../output/playwright/meraki-browser-check.json`. Live providers, physical
devices, a container rebuild and deployment remain unverified. WPN enablement and
matching Access Manager policy conditions still require Meraki Dashboard.

### Access Manager certificate defaults (2026-10-05)

New Wi-Fi profiles select Access Manager and EAP-TLS. EAP-TTLS defaults to PAP;
unsupported enterprise methods receive field validation. The SSID editor now
offers enterprise Access Manager authentication and no captive portal. Existing
explicit custom-server profiles retain their setting and require replacement
profiles when migrated. Certificate trust and matching rules require Dashboard.

Desktop/light and phone/dark checks covered the Wi-Fi editor and enterprise SSID
form with no horizontal overflow. Preview/apply/read-back passed on a local
fixture. All 255 tests and the real Home Assistant twelve-command validation
passed, including enterprise writes through the actual Meraki SDK to a loopback
HTTP fixture. Evidence is in `../../../output/playwright/access-manager-*`.
Resident self-service remains iPSK without RADIUS; deployment and live device
authentication have not been tested.

### Deployed Meraki and IPSK checks (2026-10-05)

Version 0.30.2.60 is installed and running, with no update backup requested.
Live checks confirmed Meraki network/SSID discovery, Duo connection health and
the group directory read (zero members in the active configured group). Live
verification corrected non-root options-file access and Duo Active status casing.
Access Manager policy reads remain unavailable with the current connection;
physical authentication and full Duo sign-in remain unverified. Existing working
Access Manager client profiles require no replacement for this deployment.
The local suite and final source CI passed all 260 tests and the real companion
compatibility check. See
`../audits/meraki-configuration/` for deployment evidence and limits.
