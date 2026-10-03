# Changelog

## 0.30.2.52

- Added Captive portal Settings with separate Appearance and Content pages,
  unsaved previews, logo uploads, colors, device/light/dark themes and welcome copy.
- Applied shared branding across public onboarding, authentication handoff and
  connection results, retaining functional error and result instructions.
- Added contrast-aware colors, bounded local images with metadata removed,
  scoped immediate saves and persistent skin settings included in add-on backups.
- Added portal skin, upload, preview, persistence and request-guard tests.

## 0.30.2.51

- Moved authentication and the user directory into a separate Identity & access
  Settings category, with independent provider forms available without IPSK.
- Kept Wi-Fi device rules and limits under IPSK, linking to shared identity
  services instead of embedding their credentials.
- Added scoped saves that preserve other settings and blank saved secrets,
  reusable provider validation, and legacy-form recovery to the right page.
- Grouped the complete configuration reference by identity and Wi-Fi purpose
  while preserving existing add-on option keys and authentication behavior.

## 0.30.2.50

- Added a central Settings menu with Certificates, Enrollment & Wi-Fi, IPSK,
  and System submenus, focused pages, breadcrumbs and mobile navigation.
- Moved existing configuration editors into their categories and added grouped,
  redacted summaries with direct links for Home Assistant-managed options.
- Preserved old bookmarks, form routes, ingress paths and CSRF protection.
- Improved dark-theme error-state contrast and added settings routing,
  configuration coverage and credential-redaction tests.

## 0.30.2.49

- Renamed the administration area to IPSK and split keys, devices, invitations,
  join codes, access rules and creation into focused pages.
- Added searchable, paginated inventories, direct device-to-key navigation and
  invitation labels with an additive MariaDB schema upgrade.
- Preserved non-secret form details after errors, clarified expiry choices and
  disclosed Duo settings only when the selected access rules need them.
- Improved mobile tables, control contrast and keyboard/accessibility behavior.
  Current-device success puts the password and Finish setup before the QR.
- Added regression coverage and completed the interface audit across light/dark
  themes and phone, tablet and desktop layouts.

## 0.30.2.48

- Fixed every iPSK WebSocket command schema to accept the portal's operation
  fields, including the empty network selection used by the options request.
  Companion version is now 1.5.2.
- Replaced the incomplete schema compatibility check with full portal payloads
  dispatched through Home Assistant's real ActiveConnection request handler.
  Unknown request fields still fail before provider calls.

## 0.30.2.47

- Fixed the bundled companion's Supervisor-user import for Home Assistant
  2026.9; kept authorization restricted to admins and the authenticated
  Supervisor service user. Companion version is now 1.5.1.
- Added compatibility checks that import and register the companion against
  the real Home Assistant package instead of fixture-only module stubs.

## 0.30.2.46

- Fixed a guidance variable collision that interrupted successful resident
  onboarding and validation recovery; help search now matches separate words.
- Verified this release with 140 portal tests, 30 real MariaDB checks,
  disposable certificate lifecycle/restart checks and all three architecture builds.

- Added installation guidance, read-only connection readiness and searchable
  in-app troubleshooting before deployment. Public resident pages include
  connection help and clear onboarding progress.
- Added database-backed resident search and pagination beyond 250 records;
  bounded key-table pagination, independent sorting and preserved filter links.
- Added searchable permitted-group account choices, field-specific validation
  and recovery of non-secret identity/device details.
- Disclosed secondary tools on phones and supplied progress for readiness checks.

- Completed the independent interface critique: put searchable device/key
  management above setup, disclose key creation, show another-device address
  fields only for that choice, preserve registration details after validation,
  and explain saving the one-time password and joining the resident network.
- Reused nonce-protected shared controls on resident pages for password copying,
  progress feedback and conditional fields; clarified account labels, dates,
  certificate choices and tool headings.
- Allowed the configured Duo host through the resident form policy so browser
  redirects complete. Contained provider error bodies in pages and logs, and
  rotated successful device-request tokens before releasing the session lock.
- Verified the shared Meraki connection against SDK 4.5.0b4 and documented
  Home Assistant's credential storage. Its integration now redacts Wi-Fi/RADIUS
  secrets in diagnostic and dashboard data and restricts key creation to admins.

- Fixed the build context to include all resident modules and SDK requirements,
  removed an unavailable Alpine package and corrected MariaDB generated MAC
  columns so indexed expressions work across SQL padding modes.
- Added Step CA companion integration 1.5.0's authenticated Meraki SDK bridge;
  network-scoped choices, group-policy validation and key attribution/history
  use the existing Meraki connection and Step CA's MariaDB database.
- Completed a full local interface and implementation audit: corrected
  definition lists, inline link recognition, scrollable-table keyboard access,
  secret controls, mobile group actions and 44px action targets.
- Checked invitation expiry and freed recorded slots for revoked/expired keys.
- Serialized registration across both resident tables and validated authoritative
  Wi-Fi credentials before recording success; retained revoked device history.
- Bounded full WebSocket exchanges, request sizes and rate-limit memory; preserved submit-button values,
  improved enrollment QR quiet zones and respected explicitly disabled options.

- Added optional resident creation of device iPSKs with downloadable join QRs,
  attributed device records and limits in Step CA's MariaDB schema.
- Added administrator controls for Duo Universal SDK verification or a
  no-sign-in resident selector restricted to one Duo group through the Admin API.
- Bound Duo callbacks to browser state, nonce and username; rejected bypass
  responses, rechecked group membership and blocked legacy registration bypasses.
- Added secure resident sessions, duplicate-form protection and other-device
  hardware-MAC checks. No-sign-in selection cannot reveal existing passwords.

- Add separate downloadable Wi-Fi QRs for guest access and joining the
  setup network to register for an individual key. Save their existing
  network names and passwords in the Residents panel's QR network settings.
- Generate a join QR after creating a key for another device and add
  **Show QR** for existing active iPSKs. Password fields preserve spaces,
  and QR payloads escape Wi-Fi delimiter characters.
- Make the migrated WPN resident flow start through Meraki's default-PSK
  captive portal. Block missing, invalid and private/randomized device MACs
  before registration, with device-specific recovery instructions. Keep the
  captured address in a short-lived server session and record it in Step CA's
  database. Add validated click-through completion after registration.
- Fix resident database setup to include source IP and device MAC columns.
- Bring resident onboarding and Meraki iPSK administration into the Step CA
  panel. Resident records and one-time invitations use restricted tables in
  Step CA's MariaDB database; certificate issuance remains in Step CA.
- Add the public resident registration route through the Home Assistant
  integration and require MariaDB when resident onboarding is enabled.
- Create all portal records directly in Step CA's MariaDB for a new installation;
  removed the unneeded old WPN database import and its options.

## 0.30.2.45

- Reorganized Wi-Fi setup with a wider editor, consistent expandable sections,
  a live profile summary, saved networks, and an authentication/setup guide.
- Added PEAP, EAP-TTLS (with inner authentication), EAP-FAST, EAP-SIM,
  EAP-AKA, and legacy LEAP. Added account credentials, outer identity,
  per-connection passwords, optional client certificates, TLS limits, PAC,
  and SIM challenge settings in the UI, options schema, and Apple profiles.
- Corrected EAP server-trust placement and isolated hosted RADIUS CA trust
  per network. Manual setup instructions now match the selected EAP method.
- Standardized tool navigation, password visibility controls, field help,
  keyboard access, and submission feedback across the panel.
- Fixed optional profile-name validation and preserved spaces in SSIDs.
  Corrected WPA security and Mac login-window guidance.

## 0.30.2.44

- **Serial number enrollment removed**: enrollment links and **Enroll this
  device** no longer offer the device's serial number as the certificate
  name; enter a name instead. Links created with `$SERIALNUMBER` as their
  name stop working. MDM profiles still use your MDM's serial number
  variable, which the MDM fills in itself.

## 0.30.2.43

- **One-tap profile updates**: profiles installed on an iPhone or iPad from an
  enrollment link add an **Update** icon to the Home Screen. Tapping it
  installs the newest profile for the same certificate, which renews the
  certificate and picks up Wi-Fi changes. Macs get the update link to
  bookmark. Update links are listed under **Update links** and can be
  cancelled; each lasts 400 days after the profile was last installed.

## 0.30.2.42

- **Serial number enrollment**: fixes "Could not obtain the final profile
  using the Encrypted Profile Service" when the enrollment link expired between
  downloading the profile and installing it (Enroll this device links last one
  hour). The downloaded profile now works for its own hour. A device that sends
  its serial number twice gets the same profile again instead of an error.

## 0.30.2.41

- **Wi-Fi networks**: a network can have its own **Profile name**, so the same
  SSID can be set up more than once (for example one entry for iPhones and
  one for Macs). **Include in every profile** chooses which networks
  enrollment links, Enroll this device, and the MDM all-networks profile set
  up; the others are downloaded on their own.
- **MDM profiles**: the Contents menu lists each network on its own, and
  **Download all (.zip)** gets every profile for iPhone and iPad and for Mac
  in one file.

## 0.30.2.40

- **MDM profiles**: separate **iPhone and iPad profile** and **Mac profile**
  downloads replace the Platform menu. Each leaves out the Wi-Fi settings the
  other device type alone uses, and an iPhone profile no longer installs for
  the system when a network connects at the Mac login window.
## 0.30.2.39

- **Wi-Fi networks**: profiles can set up more than one network. **Tools >
  Wi-Fi networks** lists them, with add, edit, and remove; the new
  `wifi_networks` option holds them. The single `wifi` network moves there the
  first time you save in the panel.
- New per-network settings: a manual or automatic (PAC) **proxy**, **skip
  captive portal detection** (iPhone and iPad), **connect at the Mac login
  window**, **QoS marking** (Cisco Fast Lane) with an app allow list, and
  **Passpoint** (Hotspot 2.0): domain, operator name, roaming consortium OIs,
  NAI realms, MCC/MNC, HESSID, and roaming.
## 0.30.2.38

- **Wi-Fi network**: new **Fixed Wi-Fi address** setting
  (`disable_mac_randomization`) turns off Private Wi-Fi Address for the
  profile's network, so devices use their real MAC address on it.

## 0.30.2.37

- **Serial number enrollment**: the add-on log shows each step (profile
  service served, the device's reply received, and why a reply was refused),
  and integration 1.3.1 logs a warning in Home Assistant when a device's
  reply is refused. Restart Home Assistant after updating.

## 0.30.2.36

- **Enrollment links and Enroll this device**: the certificate name can be the
  device's serial number on iPhone, iPad, and Mac, like an MDM's
  `$SERIALNUMBER`. Choose **Device serial number** (or use `$SERIALNUMBER`
  in the name); the device sends its serial number through an Apple profile
  service and then installs its certificate profile.
- Home Assistant integration 1.3.0 passes the device's reply through to the
  add-on. Restart Home Assistant after updating.

## 0.30.2.35

- **Wi-Fi**: pre-shared key networks. Choose **Pre-shared key** under
  **Tools > Wi-Fi network** (or set `wifi.authentication: psk` and
  `wifi.password`), and profiles set up a WPA Personal network with the
  password instead of EAP-TLS.
- **Tools > Wi-Fi network**: authentication, security, and RADIUS server are
  menus; the password and RADIUS fields show only for the chosen
  authentication; RADIUS server names moved under **Advanced**, since they
  are optional.

## 0.30.2.34

- **Tools > Wi-Fi network**: edit the SSID, security, auto-join, hidden,
  RADIUS server, and RADIUS server names in the panel. Saved to the add-on
  options and used by new profiles right away, with no restart. Before, these
  could only be changed on the add-on's Configuration tab.

## 0.30.2.33

- **Authority**: new **Meraki Access Manager** download, the CA chain as a
  single `.crt` ready to upload under Access Manager > Certificates, with
  the settings to choose.

## 0.30.2.32

- **Wi-Fi**: new `radius_server` option. With `meraki_access_manager`, Wi-Fi
  profiles (enrollment links and MDM downloads) trust Meraki Access
  Manager's RADIUS certificate (IdenTrust Commercial Root CA 1,
  `eap.meraki.com`), so iPhones and Macs join without an upload under
  **Other trusted CAs**. Before, profiles trusted only this CA and the
  uploaded CAs, so devices silently refused Meraki's server and never
  joined.
- **Docs**: Meraki Access Manager setup, including uploading **CA chain** as
  one enabled entry with Trusted Anchor on.

## 0.30.2.31

- **Enroll**: the new link form asks for the certificate name, an **Email
  address**, and the **Group (OU)** up front, like **Enroll this device**.
  Other alternative names moved under **More options**.
- **Enroll this device** and **Issue a certificate now** also have a
  separate **Email address** field; it becomes required for groups that
  require an email.

## 0.30.2.30

- **Groups**: adding, editing, or removing a group in the panel applies it
  right away. step-ca reloads its provisioners without restarting, so
  devices keep enrolling. Groups changed in the Configuration tab show
  **Groups not applied** with an **Apply now** button; restarting the add-on
  still works as a fallback.

## 0.30.2.29

- **Certificates**: delete revoked and expired certificates from the list,
  one at a time or with **Delete all**. They are only hidden in the panel;
  revoked certificates stay on the CRL. A deleted certificate's page offers
  **Restore to the list**.
- **Enroll**: the links list has **Waiting**, **Used**, **Expired or
  cancelled**, and **All** filters with counts, shows 10 links per page, and
  can delete used, expired, and cancelled links one at a time or all at once.
  Cancelling a link keeps you on the same page.

## 0.30.2.28

- **Tools** is now a menu with a page for each tool: **Groups**, **MDM
  profiles**, **Sign a request**, **Other trusted CAs**, and **Add-on
  options**.
- New **Groups** page: add, edit, and remove certificate groups (name, OU,
  challenge with a **Generate** button, lifetime, require email) from the
  panel. Saving writes the add-on options; **Restart** applies them.
- New `require_email` group option: the group's certificates must carry an
  email subject alternative name, for RADIUS servers such as Meraki Access
  Manager that match it against the user's Entra ID UPN. The SCEP webhook
  refuses requests without one, and enrollment links, **Enroll this device**,
  .p12 issuing, and MDM profiles ask for it.
- **MDM profiles**: choose your MDM (Meraki, Jamf Pro, Kandji, Intune) to
  pick the certificate name and email variables from a menu, or choose
  **Custom** to type your own. Intune can use the downloaded profile as a
  custom profile.
- Names and descriptions for every option in the add-on's Configuration tab.

## 0.30.2.27

- New `groups` option: certificate groups such as adults, kids, and guests.
  Each group has its own SCEP URL (`…/scep/<name>`), challenge, and optional
  lifetime, and its certificates always carry the group's OU, so a RADIUS
  server can assign a VLAN or policy per group. Choose the group for
  enrollment links, **Enroll this device**, .p12 issuing, and MDM profile
  downloads. **Certificates** shows each certificate's OU. See
  **Certificate groups** in the documentation.
- For .p12 issuing and **Sign a certificate request**, an OU in the request
  now takes priority over the `certificate_subject` OU (which still fills in
  when the request has none). This is how .p12 certificates get their group's
  OU; a signed request (for example from a RADIUS server) keeps its own OU.

## 0.30.2.26

- Fix the image build for 0.30.2.25: the new `admin/ui.py` was left out of
  the Docker build context.

## 0.30.2.25

- Redesigned the panel and the enrollment pages to follow Home Assistant's
  own look, and to take on your Home Assistant theme when opened from the
  sidebar.
- **Certificates**: a health bar shows how many certificates are active,
  expiring soon, expired, and revoked. Each row shows how much of its
  validity is left.
- **Enroll**: the one-time link form and the link list sit on the left.
  Enrolling this computer and issuing a certificate now sit on the right.
- **Authority** shows only the CA: the root and intermediate (folded into
  panels), the CA chain, bundle, and CRL downloads, and the endpoint URLs.
- New **Tools** tab: **Sign a request**, **Other trusted CAs**, and
  **Using an MDM** as collapsible panels, plus a read-only summary of the
  add-on options (issued subject, SCEP challenge, Wi-Fi, storage). When
  signing, choose server certificate or subordinate CA to see what will be
  signed, including the CA extensions.
- Step CA SCEP integration 1.2.2: the setup dialog no longer shows
  "Translation error: UNCLOSED_TAG".

## 0.30.2.24

- Download ready-made, unsigned `.mobileconfig` profiles for any MDM under
  **CA & downloads → Using an MDM**, for iOS/iPadOS or macOS: the
  certificate payloads only, or the certificates with the SCEP payload, and
  optionally the Wi-Fi payload. Enter your MDM's serial number or user name
  variable (for example `$SERIALNUMBER` or `$OWNERUSERNAME`) as the
  certificate name, and optionally its email variable (for example `$EMAIL`
  or `$OWNEREMAIL`) as an email alternative name. The macOS profile installs
  for the whole Mac.

## 0.30.2.23

- Signed certificate requests download as `<name>-chain.crt` instead of
  `.pem`, because Meraki only accepts `.crt` or `.cer` for its SCEP CA. The
  content is unchanged (Base64 PEM).
- The **Subordinate CA** option shows the extensions it sets:
  `basicConstraints = critical,CA:true,pathlen:0` and
  `keyUsage = critical,keyCertSign,digitalSignature`.

## 0.30.2.22

- Fix "2 is not a valid CSR version" when signing Meraki's SCEP CA request.
  Requests with a version other than the standard v1 are now accepted; their
  signature is still checked. Files that are not a certificate request show
  a clear error instead of the error page.

## 0.30.2.21

- **Sign a subordinate CA** is now **Sign a certificate request** and also
  signs ordinary requests (CSRs), for example from a RADIUS, web, or VPN
  server. These are signed by the intermediate CA through step-ca with
  server and client authentication, listed on **Certificates**, and can be
  revoked. The download holds the certificate and its full CA chain.

## 0.30.2.20

- New **Sign a subordinate CA** card on **CA & downloads**: upload another
  CA's certificate request (for example Cisco Meraki Systems Manager's SCEP
  CA) and download it signed by the root CA, with the root, as one chain
  file to upload back. The requested subject is kept unchanged; the
  certificate is a CA with path length 0 and key usage certificate signing
  and digital signature.

## 0.30.2.19

- New `ca-chain.pem` download on **CA & downloads**: the intermediate and
  root CA in one file, for MDMs that require a full trusted chain. The
  **Using an MDM** card uses it instead of separate root and intermediate
  files.
- An uploaded CA's download includes its issuers when they were uploaded
  too.

## 0.30.2.18

- Fix the add-on staying in "starting" when the first `dns_names` entry is a
  public name (for example your External URL host). The container health
  check now asks step-ca on 127.0.0.1 instead of that name on port 9000.

## 0.30.2.17

- The start-up log shows the SCEP, root CA, and CRL URLs with your Home
  Assistant URL (`enrollment.public_url` or the External URL) instead of a
  placeholder.
- Hide step-ca's own "primary server URL" and "root certificates" lines,
  which point at its internal port 9000 that devices do not use.

## 0.30.2.16

- Add an icon for the add-on and the Step CA SCEP integration
  (integration 1.2.1; Home Assistant 2026.3 or later shows it). Restart
  Home Assistant after the add-on installs the new integration version.

## 0.30.2.15

- Versions are now numbered `0.30.2.N`. Home Assistant treated
  `0.30.2-10` and later as older than `0.30.2-9`, so the update button
  stayed disabled. This release contains the changes from 0.30.2-10 to
  0.30.2-14.

## 0.30.2-14

- Fix enrollment and CA page URLs using the address Home Assistant was
  opened with (for example `http://home.local`) instead of the public URL.
  The URLs are now read over Home Assistant's websocket, and Home Assistant
  Cloud remote access (nabu.casa) is used when no External URL is set. The
  detected URLs are written to the add-on log.

## 0.30.2-13

- The enrollment link form says where the Home Assistant URL came from
  (External URL, `enrollment.public_url`, or the address Home Assistant was
  opened with) and how to set a public HTTPS URL when it is not one. A
  failure to read the URLs from Home Assistant is logged.
- The .p12 download page always offers `ca-bundle.pem` with the root and
  intermediate CA, not only when other CAs were uploaded.

## 0.30.2-12

- New **Using an MDM** section in the documentation and card on
  **Certificates → CA & downloads** with the SCEP URL, challenge, subject,
  key, and Wi-Fi values for an MDM profile (Jamf Pro, Kandji, Mosyle, and
  others).
- Download each uploaded CA (for example the RADIUS server's CA) as its own
  .pem, for MDM certificate payloads.

## 0.30.2-11

- Add other CAs devices must trust, such as the RADIUS server's CA, under
  **Certificates → CA & downloads**. They are included in Apple profiles
  (and trusted for the Wi-Fi network), .p12 files, and a new
  `ca-bundle.pem` download.
- Optional subject alternative names (email addresses, DNS names, IP
  addresses) for enrollment links, **Enroll this device**, and direct .p12
  issuing.
- **CA & downloads** shows the SCEP, root, and CRL URLs with your Home
  Assistant URL.
- Explain the browser's "insecure download" warning when Home Assistant is
  opened over HTTP, with a link to the HTTPS URL.

## 0.30.2-10

- The Certificates panel shows errors (for example database errors) on the
  page and in the add-on log. They were returned as server errors, which
  Home Assistant shows as "The app is starting" indefinitely.

## 0.30.2-9

- Fix a start-up loop ("Could not configure the SCEP provisioner: client GET
  https://<dns name>:9000/admin/admins failed: context deadline exceeded")
  when the first `dns_names` entry resolves on the network but does not
  answer. Provisioners are now always written to ca.json directly.

## 0.30.2-8

- Remove the retired `profile_signing` Let's Encrypt options (`acme_domain`,
  `acme_email`, `dns_provider`, `dns_credentials`, `acme_staging`) from the
  saved configuration on start, so they no longer show in the editor.

## 0.30.2-7

- Sign enrollment profiles with the certificate from Home Assistant's
  Let's Encrypt add-on in `/ssl`. The built-in Let's Encrypt client (lego)
  and the `profile_signing.acme_*`, `dns_provider`, and `dns_credentials`
  options are removed. The certificate is re-checked hourly, so one issued
  after the add-on starts is picked up without a restart.
- "Could not configure the SCEP provisioner" now includes step's error.

## 0.30.2-6

- Detect the Home Assistant URL for enrollment automatically: the External
  URL, else the hostname Home Assistant was opened with, else the Internal
  URL. `enrollment.public_url` is now hidden and only needed as an override.

## 0.30.2-5

- `enrollment.public_url` accepts a trailing slash or a bare hostname
  (`https://` is assumed).

## 0.30.2-4

- New `certificate_subject` option (O, OU, L, ST, C) for the CA certificates
  (on creation) and issued certificates.
- Create a dedicated MariaDB database with its own accounts: `stepca_rw` for
  step-ca and read-only `stepca_ro` for the management page. The MariaDB
  service account is only used for setup.
- Restrict the management page to Home Assistant administrators.
- Enroll devices without an MDM: one-time enrollment links and QR codes,
  **Enroll this device** for the Mac or Windows PC you are using, and direct
  .p12 issuing from the management page.
- Apple devices get a configuration profile with the CA certificates, a SCEP
  payload with a one-time challenge, and optionally an EAP-TLS Wi-Fi network
  (new `wifi` options). Other devices get a password-protected .p12.
- Sign profiles with a publicly trusted certificate from Let's Encrypt via
  DNS-01 or from `/ssl` (new `profile_signing` options), so iOS and macOS show
  them as Verified.
- New `enrollment` options for the public URL and link lifetime.
- The SCEP challenge is now checked by an internal webhook, which also accepts
  the one-time challenges from enrollment profiles.
- Integration 1.2.0 serves the enrollment pages at
  `/api/step_ca_scep/enroll/...`.

## 0.30.2-3

- Add a **Certificates** management page (ingress panel): list, search,
  inspect, download, and revoke issued certificates, and download the CA
  certificates and CRL.
- Store step-ca's records in the MariaDB add-on through the Supervisor
  `mysql` service (new `database` and `mariadb_database` options).
- Enable CRL generation and serve it at `/api/step_ca_scep/crl`
  (integration 1.1.0).

## 0.30.2-2

- Serve SCEP and the root certificate on Home Assistant's own port through a
  bundled `step_ca_scep` integration at `/api/step_ca_scep/...`.
- Install the integration into `custom_components` automatically
  (`install_integration` option) and announce the add-on through Supervisor
  discovery.
- Disable the add-on's direct host ports by default.

## 0.30.2-1

- Initial add-on based on `smallstep/step-ca` 0.30.2.
- Automatic root and intermediate CA creation in `/data/step`.
- SCEP provisioner with challenge password, configurable encryption
  algorithm, key length, and certificate lifetimes.
- Dedicated RSA SCEP RA certificate, renewed automatically before expiry.
- SCEP served over HTTP (9080) and HTTPS (9000).
