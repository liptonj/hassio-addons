# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Home Assistant administrator** (primary). Runs a homelab or small office on Home Assistant and operates this add-on as their private certificate authority, mostly to put devices on 802.1X / EAP-TLS Wi-Fi (often with the FreeRADIUS add-on) and to hand certificates to servers, VPNs, and MDMs. Opens the panel from the Home Assistant sidebar on a desktop or laptop, occasionally a phone. Visits are episodic: enroll a new device, revoke a lost one, grab a CA file for a RADIUS server or MDM, sign a CSR (for example Meraki's SCEP CA).
- **Device owner** (secondary). A family member or colleague who received a one-time enrollment link or QR code. Opens it on the device being enrolled, usually an iPhone, Android phone, or laptop, with no Home Assistant login and no PKI knowledge. Needs to know what to tap and nothing more.
- **Resident** (secondary). A household member or tenant who needs an individual Meraki Wi-Fi key. Connects with the default setup PSK and opens the captive portal without a Home Assistant login. Turns off private/randomized addressing for the network if prompted, enters their details and (when enabled) a one-time invitation, then saves the passphrase or scans its Wi-Fi QR code.

## Product Purpose

A private CA (smallstep step-ca with a SCEP provisioner) and Meraki resident iPSK manager that live inside Home Assistant, reached over Home Assistant's own port. The management panel lets an admin see every issued certificate, revoke, enroll devices without an MDM via one-time links (signed Apple profiles or password-protected .p12 files), sign uploaded CSRs, manage extra trusted CAs, operate resident Wi-Fi onboarding and iPSKs, and download the CA chain, bundle, and CRL. Step CA is the only certificate authority; resident iPSK records use the same MariaDB database as Step CA. Success: an admin can enroll or revoke a device in under a minute and always knows the health of the CA.

## Positioning

The CA is in the house already: no separate server, port, or tunnel. Home Assistant's login gates the panel, its URL carries SCEP, and enrollment works from a QR code without an MDM.

## Operating Context

- Panel served through Home Assistant ingress, inside Home Assistant's frame, limited to HA administrators. Home Assistant's own theme (light or dark) surrounds it.
- Public enrollment pages are proxied by the bundled integration under `/api/step_ca_scep/enroll/<token>` and opened on the device being enrolled.
- Public resident registration is proxied by the same integration at `/api/step_ca_scep/portal`; resident and invitation tables live in Step CA's MariaDB schema, accessed with a least-privilege account.
- Server-rendered HTML from a single Python `http.server` app (`step-ca/admin/app.py`); no build step, no framework, no external assets. Strict CSP: inline CSS; small nonce'd inline JS is permitted (user decision, 2026-10-01). No external fonts or images.
- Certificate inventory comes from step-ca's MariaDB tables; with the embedded database the inventory is unavailable but CA downloads still work.

## Capabilities and Constraints

- Setup/help: ordered installation guidance, explicit read-only readiness checks, searchable troubleshooting and public connection help. Configured settings are distinguished from verified service/device behavior. Resident inventories use database search and paging; allowed Duo-group choices support local filtering.

- Certificates: list by status (active, expired, revoked), search by name, SAN, or serial; detail with PEM download; revoke with RFC 5280 reason codes (cannot be undone; CRL regenerated).
- Enrollment: enroll this computer; one-time links with label, optional CN and SANs, HA URL, validity hours, optional Wi-Fi payload; link list with cancel; issue a .p12 directly. Links and passwords are shown once.
- Resident Wi-Fi: default-PSK captive portal registration with a hardware-MAC check, recovery guidance, and optional one-time invitation; per-resident Meraki iPSKs; admin creation, reveal, revoke, and delete; live key list and resident list. Separate shareable QRs join guest access or the setup network for registration. Creating a key for another device displays its downloadable join QR; active existing keys can generate a current QR. All new records use MariaDB; this portal does not issue certificates.
- Resident self-service: administrators can allow new device-key creation with Duo Universal SDK factor verification or without sign-in. An optional no-sign-in selector includes only members of one Duo group, retrieved through the Duo Admin API. Group membership is enforced again before key creation. Unverified selection attributes a key but does not prove identity; no self-service mode exposes existing passwords. Account and device records share Step CA's database.
- Profile signing status: verified (publicly trusted cert, e.g. Let's Encrypt) or not verified (signed by this CA).
- CA: root and intermediate details and downloads, ca-chain.pem, ca-bundle.pem, CRL, SCEP URL, MDM values, extra trusted CAs (add/remove), CSR signing (leaf or subordinate CA).
- IPSK management: separate Wi-Fi key, registered device, invitation, join-code pages; key creation uses a dedicated route. The Settings dropdown groups certificate, enrollment/Wi-Fi, IPSK, shared identity, captive portal and system configuration into focused submenus; IPSK device access and QR settings live there. Authentication and the user directory have independent pages under Identity & access for reuse by other features. The main section is named IPSK.
- Captive portal branding: focused Appearance and Content settings with draft previews, local logo uploads, theme and contrast-aware colors, welcome copy and footer. Shared branding spans the public connection and identity flows; operational result/error headings remain intact.
- Terminology: certificate name (CN), alternative names (SANs), enrollment link, profile, .p12, CA chain, CA bundle, CRL, SCEP, provisioner.

## Brand Commitments

- Name: "Step CA SCEP Server"; panel title "Certificates"; CA name configurable (default "Home Assistant CA"). Icon: mdi:certificate.
- Visual world: stays within Home Assistant's own theming (HA tokens, MDI icons, Settings-page components), and adopts the user's live HA theme where it can (user decision, 2026-10-01).
- Voice: plain, precise, instructional. States consequences (revocation cannot be undone, link shown once) without alarm.

## Evidence on Hand

No screenshots, testimonials, or metrics. Real data comes only from the running CA; do not invent counts or claims.

## Product Principles

1. Trust is shown, not claimed: fingerprints, validity, and signing status are visible where decisions are made.
2. Irreversible actions announce themselves: revocation, one-time secrets, and signing are unmistakable and deliberate.
3. The common job comes first: enroll a device, find a certificate, grab a CA file. Reference values stay available but out of the way.
4. Device owners need steps, not PKI.

## Accessibility & Inclusion

Works at phone width for public pages; respects light and dark color schemes; keyboard-operable forms.
