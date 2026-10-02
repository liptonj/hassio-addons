# Step CA full audit — 2026-10-02

> Revision note: this completed audit describes the revision in its saved evidence.
> Subsequent pre-install guidance/pagination improvements are recorded in
> [the pre-install change record](2026-10-02-preinstall-improvements.md).
> Its historical test counts, image IDs and scores are not new verification of those additions.

## Implementation integrity verdict

**Pass for the local implementation; production sign-off remains pending.**

The consolidated product uses one Step CA certificate authority and its existing
MariaDB database. Resident registration, invitations, per-device attribution,
Duo policies and guest/setup/device QR flows use the same administration panel.
Certificate operations retain their existing CA enrollment and revocation path.
The UI follows the established Home Assistant design tokens and navigation.

The exercised local checks pass, including real images, MariaDB and a disposable CA. Deployment checks remain open. The approved independent design and detector assessments are complete. The design confirmation resolves its four priorities and five minor observations; the technical confirmation is recorded separately below.

## Audit health score

Scores describe the available verification, including its limits. Automated
accessibility results are not a claim of full WCAG conformance.

| Dimension | Score | Evidence / limit |
|---|---:|---|
| Accessibility | 3/4 | Earlier 63-view audit plus current 48-scan confirmation: no unresolved violations; transient toast findings and eight incomplete results retained. Keyboard focus checked. A physical screen-reader session remains unverified. |
| Performance | 4/4 | Inline, shared CSS/JS, local SVGs, no external fonts/assets, bounded sessions and rate-limit storage. No production latency benchmark. |
| Responsive design | 4/4 | 1280px and 320px layouts, 200% root text scaling at 640px, 44px action targets, no observed page overflow. |
| Theming | 3/4 | Default light and dark modes passed contrast checks. Live inheritance from a deployed Home Assistant theme remains unverified. |
| Implementation integrity | 3/4 | 126 unit/contract tests, 26 real MariaDB checks, three architecture builds and disposable CA lifecycle checks pass; deployed provider checks remain outstanding. |
| **Total** | **17/20 — Good** | **No remaining detected defects in the exercised local UI fixtures.** |

## Executive summary

- Corrected **28 technical portal findings: 3 P0, 16 P1 and 9 P2**, plus **four independent critique priorities and five minor observations**, and the five Meraki integration findings below. One earlier migration finding was retired when the user clarified this is a new installation.
- **126 local tests pass**, including actual loopback Home Assistant WebSocket
  contract tests, SDK wire contracts, database boundaries, Wi-Fi profiles,
  captive gates, QR encoding, lifecycle handling and configuration controls.
- The earlier technical audit recorded **63 axe page/state scans and five interaction
  checkpoints**; the independent confirmation checks the subsequent resident UI changes. No missing labels, broken `aria-controls`, JavaScript errors,
  small action buttons or horizontal page overflow were detected.
- The largest correctness fixes were image packaging, MariaDB generated columns,
  the missing Meraki bridge, replacement key lifecycle and registration serialization.
- Real MariaDB **10.11.19** passes **26 checks** across fresh and existing Step CA schemas. No WPN database import remains.
- Final images build for **aarch64, amd64 and armv7** and import all portal modules and SDKs.
- A disposable CA passes actual CSR/.p12 issuance, renewal, revocation, CRL publication, SCEP capability discovery, companion installation and renewal after restart.
- The local Meraki integration had no iPSK handlers. Step CA companion **1.5.0** now supplies the authenticated bridge using its existing Meraki SDK session. The actual **Meraki SDK 4.5.0b4** passed the subsequent loopback HTTP contract check; no production Wi-Fi keys were created.

## Meraki SDK and credential follow-up

The SDK dependency belongs to `/Users/jolipton/Projects/meraki-homeassistant`.
Its manifest, development dependency and lockfile now pin **4.5.0b4**, the latest
beta verified against PyPI on October 2, 2026. Stable 4.5.0 was evaluated, but
the full integration suite proved it lacks `getOrganizationApiPushTopics` and
other existing Push API operations. The beta retains those operations and its
aiohttp transport. This is an intentional beta requirement, not a stable release
claim. See the [published beta](https://pypi.org/project/meraki/4.5.0b4/).

Additional corrected findings in that integration:

| Finding | Correction |
|---|---|
| Diagnostic data contained SSID PSKs and nested RADIUS/relay secrets | Redact the complete export recursively, preserving live coordinator data. |
| Dashboard responses and live subscriptions forwarded credentials | Apply the same redaction to panel data and legacy overview/device/SSID/subscription responses. |
| Any signed-in user could create a key and receive its password | Require a Home Assistant administrator before invoking the key manager. |
| OAuth/API failures could echo credentials into logs or visible errors | Log operation/status only; omit provider bodies and authentication headers, and suppress original exception chains at the wrapper boundary. |
| Token refresh silently accepted incompatible SDK transports or missing tokens | Fail closed and verify real outgoing Authorization headers before and after refresh against a loopback fixture. |

Cisco client secrets remain in Home Assistant **Application credentials**;
access and refresh tokens remain in the Meraki integration's **config entry**.
Step CA does not copy them into MariaDB or add-on options. Home Assistant's
filesystem storage is not an encrypted vault; configuration directory access
and backups need appropriate protection. Duo credentials remain in protected
Supervisor add-on options as described below. This review did not open actual
credential files or change live accounts.

The follow-up verification and source hashes are recorded in
`2026-10-02-meraki-sdk-secrets-evidence.json`. **1,141 Meraki tests pass**,
with eight pre-existing skips and no warnings. The repository's complete quality
script passes lint, formatting, security checks, typing and its test run.
**112 Step CA tests passed** at that follow-up. The subsequent portal fixes below
brought the count to **119**. The independent critique changes bring it to **126**, with fresh image/database/CA evidence. Meraki's SDK
is installed by the Home Assistant integration, outside the Step CA image.

## Portal request and secret follow-up

| Finding | Priority | Correction and evidence |
|---|---|---|
| `form-action 'self'` blocked the Duo POST redirect in Chromium | P1 | Allow only the validated, configured Duo HTTPS origin when verification is required. A native browser submission failed before the fix and reached a controlled Duo response afterward with zero console errors. |
| Duo provider exceptions and basic registration cleanup logs could reflect secrets | P1 | Contain SDK exceptions, including lazy directory paging and provider `ValueError`, behind generic service errors; omit provider bodies from request and cleanup logs. Regression tests check reflected secrets are absent. |
| Successful device creation cleared its busy flag before rotating the form token | P2 | Rotate the token and clear its draft under the session lock while the request is still busy. A regression test checks that ordering. |

Browsers can enforce the form policy through redirects, as documented by
[MDN's form-action reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/form-action).
The final browser confirmation intercepted the dummy Duo URL through CDP Fetch.
An earlier interception attempt allowed one dummy authorization GET to return
HTTP 400; it contained only the literal fixture state, with no credentials or
real account. No live provider changes were made.

The current portal source was rebuilt and run on all three architectures.
MariaDB's 26 checks and the seven CA checks pass again; an eighth check renews
a certificate issued on the current image after restart. The public root
certificate hash is unchanged across image replacement and restart. See
[current critique/runtime evidence](2026-10-02-critique-final-evidence.json). Earlier portal evidence is retained for its historical revision.

## Scope

Reviewed every Step CA administration route: certificate inventory and its
active/all/expired/revoked/search-empty states, certificate details, enrollment
links, self-enrollment, Residents, Authority, Tools, Groups, Wi-Fi profiles,
MDM profiles, CSR signing, additional CAs and add-on options. Public views cover
one-time certificate enrollment, unavailable links, captive entry, private-MAC
rejection, group selection, Duo entry, legacy registration, device forms,
validation recovery and generated device QR results.

Implementation review also covered database setup/upgrades/grants, request
parsing, public proxy contracts, SDK boundaries, settings/schema/translations,
startup behavior, invitation use, key cleanup and concurrency protections.
WPN was inspected as a feature and provider-contract reference. The user clarified
this is a new installation: its old database reader, option, validation and tests
were removed. All portal records are created in Step CA’s MariaDB.

## Corrected findings

Every recommendation below has been applied locally. Locations reference the
current source, rather than a deployed image.

### P0 — release blockers found by real container/database execution

| Finding | Correction and evidence |
|---|---|
| Docker build context excluded resident modules and SDK requirements | Added every copied source to `.dockerignore`; builds and module imports pass on all declared architectures. |
| Alpine has no `py3-sqlite3` package | Removed the invalid package. The later new-install clarification also removed all application SQLite usage. |
| Indexed generated MAC column depended on SQL CHAR padding mode | `RTRIM(mac_address)` makes the expression consistent. Real MariaDB accepted both fresh and upgraded schemas; SQL-mode and replacement-index checks pass. |

### Further P1 and P2 findings from runtime integration

| Finding | Priority | Correction and evidence |
|---|---|---|
| Installed Meraki source lacked every required iPSK handler | P1 | Added Step CA companion 1.5.0’s administrator/Supervisor-only SDK bridge for all seven operations; verified exact SDK requests on loopback. |
| SSID/policy choices described a different network | P1 | Load choices for the selected network; validate the actual network, enabled iPSK SSID and group policy before creation. Browser switching and SDK checks pass. |
| Admin key attribution depended on an unspecified external store | P1 | `stepca_ipsks` stores scope, attribution and lifecycle history in the same MariaDB; no password column. Real restricted-account reads/writes pass. |
| Public proxy deadline was shorter than its bounded provisioning flow | P1 | 180-second overall proxy deadline covers separately bounded SDK, Duo and database operations. SDK timeout errors instruct the administrator to check Dashboard before retrying creation. |
| Key creation could reach Meraki without a portal database | P1 | Fail before any API request and disable creation when MariaDB is unavailable; regression test proves no provisioning call. |
| WebSocket could wait indefinitely after a successful handshake | P1 | Deadline wraps the whole message exchange, including authentication and reply waits. A stalled loopback response now fails with recovery guidance; admin lookup is bounded too. |
| Invitation action column had an empty heading | P2 | Added “Actions”; four all-rule axe scans pass in desktop/mobile and light/dark. |

The earlier WPN invitation-import finding is superseded by removal of the import
feature. Current invitations are checked for expiry inside the registration
transaction; consumption and concurrent use are verified against real MariaDB.

### P1 — major

| Finding and location | Category / user impact | Standard and applied correction | Command |
|---|---|---|---|
| Invalid definition lists — `admin/ui.py:87`, `admin/app.py` certificate, Authority, MDM and options renderers | Accessibility: copy/download controls appeared outside the term's definition, disrupting semantic relationships. | WCAG 1.3.1. Added shared `kv_row`; actions now live inside `<dd>` with the value. | `$impeccable harden` |
| Inline links distinguishable only by color — `admin/ui.py:686` | Accessibility: links in help and explanatory text could be missed in either theme. | WCAG 1.4.1. Underlined inline links; buttons and icon controls retain their own shape. | `$impeccable harden` |
| Resident table not keyboard-scrollable — `admin/ui.py:933` | Accessibility: Safari keyboard users could not reach horizontally clipped columns. | WCAG 2.1.1. Named, focusable table regions with existing focus indicators. | `$impeccable harden` |
| Revoked/expired keys retained quota and MAC reservations — `admin/db_setup.py:196`, `admin/ipsk.py:136`, `admin/resident_access.py:390`, `admin/app.py:1574` | Implementation integrity: replacement registration failed or a resident appeared at their device limit. | Active-only generated unique MAC/email indexes preserve history. Revocation updates both resident stores; explicit remote expiry/revocation releases slots before issuing keys. Blank legacy email cannot aggregate unrelated residents' quotas. | `$impeccable harden` |
| Cross-flow device registration race — `admin/ipsk.py:72`, `admin/resident_access.py:390` | Implementation integrity: two concurrent flows could provision the same MAC across separate tables. | Database-scoped, bounded advisory lock per MAC is acquired before snapshot reads and held through commit/rollback. Resident-account row locks retain quota serialization. | `$impeccable harden` |
| Registration committed without authoritative SSID — `admin/ipsk.py:360` | Implementation integrity: an invitation and key could be recorded even though a usable join QR could not be generated. | Validated the actual returned SSID and passphrase before inserting records or consuming an invitation. Rollback removes the unrecorded remote key. | `$impeccable harden` |
| Malformed/negative request sizes and ambiguous fields — `admin/app.py:1421`, `3900`, `3956` | Implementation integrity: malformed requests could block a worker or select an unintended field value. | Reject malformed/negative/oversized bodies before reading; reject duplicate mutation fields. SCEP webhook input is bounded and fails closed. | `$impeccable harden` |
| Startup ignored explicitly disabled options — `run.sh:76`, `80` | Implementation integrity: `invite_required: false` and `install_integration: false` were replaced by a true fallback. | Explicit false checks retain the configured choice; missing values retain the true default. Regression tests execute the actual filters. | `$impeccable harden` |

### P2 — minor

| Finding and location | Category / user impact | Applied correction | Command |
|---|---|---|---|
| Unstable password-control relationships — `admin/ui.py:906` | Accessibility: unnamed input IDs produced empty control references; wrapping-label names changed with Show/Hide. | Assigned stable IDs, retained the field's original name and supplied button-specific names and state. Showing and hiding were verified on the same element. | `$impeccable harden` |
| Small actions and narrow input text — `admin/ui.py:681`, `687` | Responsive: reduced tap area and avoidable phone input zoom. | 44px action height and icon width; 16px input text on narrow screens. WCAG 2.5.5 target-size guidance; all exercised action controls met this size. | `$impeccable adapt` |
| Group action row squeezed names to individual letters — `admin/ui.py:679` | Responsive: group details became difficult to read at 320px. | Rows with three or more actions place the action group below the text on narrow screens. | `$impeccable adapt` |
| Enrollment QR lacked a full quiet zone/backing — `admin/app.py:330` | Implementation integrity: downloaded SVGs could be less reliable on dark backgrounds or near neighboring content. | Four quiet modules and an explicit white SVG backing, matching Wi-Fi QR behavior. | `$impeccable harden` |
| Submission progress omitted a named submitter — `admin/ui.py:940` | Implementation integrity: shared POST handling could drop a clicked button's name/value while disabling controls. This was a latent shared-control defect. | Preserve the submitter's value in a hidden field before disabling buttons; native submission verified as `kind=apple`. | `$impeccable harden` |
| Rate-limit storage and flow allowance — `admin/ipsk.py:545` | Performance/integrity: unique addresses accumulated indefinitely; selecting an identity consumed device-creation attempts. | Expire stale entries, cap storage, separate identity/device budgets, and provide a larger bounded allowance for configured self-service. No change to resident quotas. | `$impeccable optimize` |
| Legacy captive cookie omitted Secure — `admin/ipsk.py:529` | Implementation integrity: session cookies could be sent over plain HTTP. | Secure/HttpOnly/SameSite cookies and an explicit HTTPS deployment requirement in the docs. | `$impeccable harden` |

## Detector verification

The initial Python-source detector returned no findings, which does not cover
rendered HTML. The full detector was therefore run on **16 rendered HTML
fixtures** with `htmlparser2`, `css-select`, `css-tree` and `domutils` available
in an isolated temporary tool directory. The first parser-degraded attempt was
superseded by this full run.

The final detector emitted **48 raw flags, zero verified actionable findings**:

| Pattern | Flags | Verified disposition |
|---|---:|---|
| Overused font | 16 | Roboto is the established Home Assistant product constraint, documented in DESIGN.md. Replacing it would break the requested identity. |
| Flat type hierarchy | 14 | Compact settings hierarchy intentionally uses 12–24px text, clear headings, labels and section structure. Screenshots confirm the actual task hierarchy. |
| Dark glow | 16 | The matching shadows are zero-blur focus/selection border strokes. They provide state and focus feedback, rather than decorative blurred halos. |
| Cramped padding | 2 | Resident card contents are inset by padded header/content children or table cells. Screenshots confirm the inset; parent-card padding is intentionally zero. |

No detector rule was disabled or added to an ignore list. See the saved raw
[detector evidence](2026-10-02-detector-evidence.json).

## Functional requirements checked

| User requirement | Local implementation status | Remaining verification |
|---|---|---|
| One certificate system | Step CA retains certificate creation/enrollment/revocation. Resident modules do not issue certificates. | Physical SCEP/MDM installation and deployed CA behavior. Disposable CA issuance, renewal and revocation pass. |
| Step CA database for iPSK onboarding | Five restricted portal tables in Step CA’s MariaDB; 26 real database checks pass. No old database is opened. | Deployed MariaDB version and backup configuration. |
| Default-PSK captive onboarding | Captured server-side context, invitation policy, validated grant target, short completion grant. | Physical Meraki captive redirect and policies. |
| Block randomized MAC registration | Rejects locally administered/multicast/invalid MACs before provisioning; other-device MAC is checked too. | Physical devices. Unsigned EXCAP fields do not cryptographically prove a MAC; documented. |
| Guest QR | Encodes the configured guest network credentials. | Actual guest policy must bypass splash. |
| Setup QR to create an iPSK | Encodes setup Wi-Fi; captive registration then provisions an individual key. | Actual setup policy, walled garden and installed iPSK provider. |
| Create another device's key/QR | Admin and resident routes create a key, validate network credentials and generate a downloadable QR. | Physical onboarding and actual provider response. |
| Resident optional verification | Duo Universal SDK factor verification, or unverified resident choice/name/email under admin policy. | Live Duo credentials, redirects, group permissions and walled garden. |
| Group-only resident choices | Duo Admin API reads only the configured group, rejects oversized groups, rechecks membership and active status. | Live group and tenant access. |
| SDK settings storage | SDK/Admin credentials are saved under `resident_onboarding` in Home Assistant add-on options; saved-secret fields stay blank. | Production option configuration. |
| Meraki Access Manager account API | Research is documented; the verified client/group APIs are distinct from a resident account directory. Duo remains the implemented directory source. | Organization's Early API Access entitlement and a verified account-directory contract. |

Cisco documents Access Manager APIs under `nac` and Early API Access.
[Official Access Manager docs](https://documentation.meraki.com/Platform_Management/Access_Manager#APIs).
The verified [NAC clients](https://developer.cisco.com/meraki/api-v1/get-organization-nac-clients/)
and [client groups](https://developer.cisco.com/meraki/api-v1/get-organization-nac-clients-groups/)
endpoints provide client/group records. No resident account-directory endpoint
was verified for this deployment; this audit does not claim one is connected.

## Patterns and positive findings

The main recurring issues were shared semantic/control behavior and consistency
between remote key lifecycle and local registration state. Fixes are shared in
`ui.py` or the resident services, rather than duplicated across pages.

Maintain these established strengths:

- Admin ingress identity checks and CSRF protection remain in place.
- Public links/session secrets are bounded and requests fail closed.
- QR credentials remain literal, validated and correctly escaped.
- Duo state/nonce/username checks, group checks and bypass rejection remain tested.
- Core service credentials and CA/database credentials stay on the server.
- Resident self-service never reveals an existing device's password.
- Destructive certificate dialogs focus Cancel first and restore the trigger.
- Light/dark tokens, reduced-motion handling and keyboard skip navigation remain.

## Release requirements — still open

1. **Deployed provider:** install/restart Step CA companion 1.5.0 and verify it can use this Home Assistant instance’s Meraki HA connection, OAuth/API permissions and target policy. Source, schema and actual SDK wire contracts pass locally; production access is unavailable here.
2. **Deployed database:** the isolated MariaDB/image/startup checks pass. Confirm the deployment’s database version and backups. No old WPN import is required.
3. **Live Home Assistant, Duo and Meraki:** verify ingress permissions/proxy,
   HTTPS cookies, callback redirects, group-only selection, key creation and
   removal, guest/setup policies and QR scans on physical devices.
4. **Certificate/device validation:** perform physical SCEP, .p12 and MDM installs using the deployed CA.
   Actual issuance, renewal, revocation and CRL refresh passed against a disposable
   fixture CA, including renewal after restart. No deployed certificates or live
   network settings were changed.
The approved independent critique is complete, with its corrected priorities confirmed.
Production sign-off cannot be established from local fixtures alone. No deployment or external credential changes occurred.

## Verification and run notes

- Test suite: **126 passed**, including actual Meraki SDK HTTP and Home Assistant WebSocket loopback contracts.
- Real database: **26 passed** on MariaDB 10.11.19, across fresh and previous Step CA schemas.
- Actual image/startup: all three architectures build/import; a disposable CA passes eight lifecycle/startup checks.
- Provider account access, physical devices and deployed Home Assistant remain unverified.
- Syntax: Python parse/compile, shell syntax, JSON and YAML passed; all **22**
  resident option/schema/translation fields match; whitespace diff check passed.
- Browser: **53 initial views**, then one confirmation round covering **63 axe
  views and five interaction checkpoints**, plus keyboard skip-link inspection.
  The confirmation harness was resumed after it wrongly navigated to a POST-only
  URL. The application was not changed to accommodate that URL. A password
  locator was corrected to keep referencing the same button after its name changed.
- One upstream SDK fixture warning remains: PyJWT reports the provider's standard
  40-byte secret below SHA512's recommended HMAC size. Credentials were not
  lengthened or the warning suppressed to manufacture a green result.
- Detector: earlier full HTML parser run, 48 reviewed flags. The independent broader assessment produced 82 reviewed flags across 31 nonempty application pages. No actionable detector findings or ignore rules in either run.
- The preview listeners and audit browser were stopped. CLI scratch files from
  this run were removed. Local screenshots/tooling remain under `/tmp`; persisted
  evidence is adjacent to this report. No shipping raster assets were introduced.
- Existing unrelated changes and the WPN signing key were preserved.

[Browser evidence](2026-10-02-browser-evidence.json) ·
[Detector evidence](2026-10-02-detector-evidence.json)

## Follow-up scope

The local implementation audit and independent critique corrections are complete.
The remaining release checks concern deployed providers and physical devices;
they do not represent unresolved local findings. No deployment is claimed.

## Runtime evidence and scope clarification

[Runtime evidence](2026-10-02-runtime-evidence.json) includes final image IDs,
real MariaDB results, CA lifecycle results and the network-picker confirmation.
The old WPN migration is absent from shipping Python, startup, options and
translations. Certificates and all new portal metadata use the same configured
MariaDB database. Earlier references to importing an old database are superseded
by the user’s new-install clarification.

The earlier architecture checks ran in a dedicated `stepca-audit` Colima profile.
The current critique rebuild used a separate `stepca-critique` profile with
isolated Docker configuration. Colima temporarily selected its Docker context;
deleting the profile selected `default`. Its pre-start context was not recorded,
so this report does not claim restoration of an unknown selection. The existing
default profile remains stopped with its original resources. User containers
and production credentials were not changed.
No host ports were published. Only disposable fixture certificates were issued.
The cross-platform legacy Docker builder initially reused the wrong cached base
platform; isolated BuildKit builds verified the final platform-specific images.
Browser instrumentation initially hit the active CSP and a stale preview process;
confirmation used the page’s existing nonce and restarted only the owned fixture.
Neither product security controls nor detector rules were disabled.

Primary contracts: [Meraki SDK create API](https://developer.cisco.com/meraki/api-v1/create-network-wireless-ssid-identity-psk/),
[Meraki SSID modes](https://developer.cisco.com/meraki/api-v1/get-network-wireless-ssids/),
[MariaDB generated-column consistency](https://mariadb.com/docs/server/reference/sql-statements/data-definition/create/generated-columns),
[Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/).

The prior cleanup removed the Colima VM but retained its container data disk.
This follow-up discovered that retention and corrects the earlier removal claim.
After revalidation, cleanup used `colima delete --profile stepca-audit --force
--data` to remove the dedicated fixture runtime data as well. The owned browser
and preview were stopped. Runtime evidence and build logs were preserved; the existing default
Colima profile remains unchanged. The current run’s temporary context selection
is disclosed above.

## Independent critique and final confirmation

Method: dual-agent (A: `/root/critique_design`; B: `/root/critique_detector`).
The user approved both isolated reviewers. Assessment A finished before B’s
findings entered synthesis. One correction batch and one bounded confirmation
resolved every identified local issue. **Critique: 32/40, previously 27/40;
audit: 17/20. Zero remaining actionable priorities in the assessed local scope.**
These scores reflect verification limits and product complexity rather than
a perfect or deployed-conformance claim.

| Corrected independent finding | Applied correction | Confirmation |
|---|---|---|
| P1: one-time resident credential lacked connection handoff | Save/copy warning, current-device finish/join steps, other-device scan guidance; secondary actions demoted | Actual clipboard/toast and target-specific instructions pass |
| P2: resident management buried under setup | Counts, task links, search/status/clear; keys before collapsed creation/setup | Keys at y=503 rather than y=2905 on 390px; filtering and jump disclosure pass |
| P2: irrelevant other-device MAC task | Hide and disable for current; reveal and require for other | Both states and private-MAC draft recovery pass in six combinations |
| P2: legacy validation discarded identity details | Preserve bounded escaped name/email/unit beside focused error; do not retain invitation | Corrected invitation succeeds with non-secret draft retained |

Five minor observations are also resolved: duplicate tool headings, datetime
microseconds, novice certificate descriptions, username/account labeling and
public progress feedback. Nonce-protected shared controls retain CSP and
no-store. A controlled two-second provider delay proves aria-busy, disabled
submit and Working… in all six size/theme combinations.

The technical confirmation covers 1280/320/390px in light/dark: **246/246
assertions after event completion, 48 axe scans, zero page errors and zero
document overflows**. Twelve HTTP 400 console messages are expected invalid
MAC/invitation responses. Three initial disclosure assertions sampled before
hashchange; bounded condition checks passed. Four raw contrast flags sampled
a fading toast; settled opacity is 1 with 11.35:1 contrast. Eight axe incomplete
color-contrast results are preserved for overlapping toast or clipped table
columns; they are not represented as automated passes. No unresolved violation
was identified. Keyboard skip and named table focus pass; a physical screen
reader session remains unverified.

The broader independent full-parser detector emitted **82 raw flags** (31 font,
31 zero-blur focus/selection strokes, 18 scale warnings, two nested-card
padding warnings). All were reviewed against the incumbent HA brief and
rendered interface; zero actionable findings, zero disabled rules. External
detector injection was blocked by CSP on five pages, so no live overlay ran.
Interrupted original temporary payloads were lost; the durable evidence index
faithfully recovers recorded counts and locations without invented hashes.
The confirmation uses authorized nonce axe injection, not a detector overlay.
Its native IAB was unavailable; an isolated Playwright/Chrome fallback completed
the bounded checks.

Fresh current-source images build and import on all three architectures;
**126 portal tests, 26 real MariaDB checks and eight actual disposable CA
checks pass**. Packaged and browser-confirmed source hashes match. CA renewal
after restart retains the root fingerprint. The Meraki integration’s 20
source hashes still match its passing 1,141-test SDK/security evidence.

Both reviewers stopped their fixtures and owned browsers. The parent preview
is stopped. The dedicated `stepca-critique` VM and its data disk were deleted
with explicit `--data`; the existing default profile remains stopped and
unchanged. Temporary Docker context selection is disclosed above. No deployed
provider, physical device, real account or production certificate was changed.

[Design confirmation](../critique/confirmation-a-2026-10-02.md) ·
[Technical confirmation](../critique/confirmation-b-2026-10-02.md) ·
[Current runtime/source evidence](2026-10-02-critique-final-evidence.json)
