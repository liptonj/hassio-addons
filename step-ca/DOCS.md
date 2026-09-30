# Step CA SCEP Server for Home Assistant

## About

This add-on runs [smallstep step-ca](https://github.com/smallstep/certificates)
(Apache-2.0), an open-source private certificate authority, and configures a
SCEP provisioner so that devices, MDM platforms (Intune, Jamf, Meraki SM,
etc.), and network gear can enroll for client certificates, for example for
802.1X / EAP-TLS with the FreeRADIUS add-on.

The add-on is built on the official `smallstep/step-ca` container image.

## How it is reached

SCEP is served on **Home Assistant's own port** (8123, or whatever URL you
already use for Home Assistant, including an existing tunnel or reverse
proxy). No extra port or tunnel is needed.

Home Assistant ingress requires a logged-in Home Assistant user, which SCEP
clients cannot provide. The add-on therefore bundles a small companion
integration, **Step CA SCEP**, that registers a few unauthenticated routes in
Home Assistant and forwards only those requests to the add-on over the
internal add-on network:

| Purpose                     | URL                                                        |
| --------------------------- | ---------------------------------------------------------- |
| SCEP                        | `<Home Assistant URL>/api/step_ca_scep/scep/<provisioner>` |
| Root CA certificate         | `<Home Assistant URL>/api/step_ca_scep/roots.pem`          |
| Revocation list (DER)       | `<Home Assistant URL>/api/step_ca_scep/crl`                |
| Revocation list (PEM)       | `<Home Assistant URL>/api/step_ca_scep/crl?pem`            |
| Enrollment links            | `<Home Assistant URL>/api/step_ca_scep/enroll/<token>`     |

With the default provisioner name the SCEP URL is, for example,
`https://ha.example.com/api/step_ca_scep/scep/scep`. All other Home Assistant
URLs keep requiring login. Enrollment links only work for a valid, unexpired
one-time token (see [Enrolling devices](#enrolling-devices)).

## Management page

The add-on adds a **Certificates** panel to the Home Assistant sidebar. Only
Home Assistant **administrators** (and the owner) can open it: the panel is
hidden from other users, and the page itself checks each request against
Home Assistant's user list and refuses anyone who is not an administrator.
It lets you:

- list issued certificates, filter by active, expired, or revoked, and search
  by name, SAN, or serial number;
- view a certificate's details and download it as PEM;
- revoke a certificate with a reason (the CRL is regenerated immediately);
- download the root CA, intermediate CA, a full CA bundle, and the current
  CRL, and add other CAs devices must trust, such as your RADIUS server's
  (see [RADIUS server CA](#radius-server-ca-and-other-trusted-cas));
- enroll devices with one-time links or QR codes, enroll the computer you are
  using, or issue a certificate directly (see
  [Enrolling devices](#enrolling-devices)).

The certificate list is read from step-ca's database, so it needs the
`database` option set to `mariadb` (the default).

## Database

By default step-ca stores its records of issued and revoked certificates in
the official **MariaDB** add-on. No MariaDB configuration is needed. On each
start the add-on uses the MariaDB add-on's service account, provided through
the Supervisor, only to set up its own database and accounts:

- a database named by `mariadb_database` (default `stepca`);
- `stepca_rw`, used by step-ca, with access to that database only;
- `stepca_ro`, used by the management page, with read-only access.

Their passwords are generated on first start and kept in
`/data/step/secrets`.

Install and start the MariaDB add-on before starting this add-on. If MariaDB
is not available, the add-on waits briefly and then stops with an error.

If you do not want to use MariaDB, set `database` to `embedded`. step-ca
then keeps its records in `/data/step/db`, but the management page cannot
list certificates.

Changing `database` later does not copy records between the two. The CA keys
and SCEP enrollment keep working, but certificates issued before the switch
no longer show up in the management page, and revocations made before the
switch are no longer enforced.

The MariaDB database is included in the MariaDB add-on's backups, not this
add-on's, so back up both.

## First start

1. Install and start the MariaDB add-on, then install this add-on.
2. Set a strong `scep_challenge`.
3. Start the add-on and open the **Log** tab. On the first start it:
   - creates a new root CA, intermediate CA, and RSA SCEP registration
     authority (RA) certificate and prints the root fingerprint;
   - copies the integration to `/config/custom_components/step_ca_scep`;
   - announces itself to Home Assistant through Supervisor discovery.
4. **Restart Home Assistant** so it loads the integration.
5. Go to **Settings → Devices & services**. Under **Discovered**, add
   **Step CA SCEP** and confirm.
6. Check `<Home Assistant URL>/api/step_ca_scep/scep/scep?operation=GetCACaps`
   in a browser; it should list `AES`, `SHA-256`, and `POSTPKIOperation`.

Keys and passwords are stored in `/data/step` and are included in Home
Assistant backups, so **protect your backups**.

When a new add-on version ships a newer integration, the log asks you to
restart Home Assistant again.

Distribute the root certificate (`roots.pem`) to the systems that need to
trust issued certificates, such as your RADIUS server. MDM platforms usually
also need the root as a trusted certificate profile.

## Certificate subject

The organization details in certificates are set with `certificate_subject`:

| Option                | Subject field | Example        |
| --------------------- | ------------- | -------------- |
| `organization`        | O             | `Acme Inc`     |
| `organizational_unit` | OU            | `IT`           |
| `locality`            | L             | `San Jose`     |
| `state`               | ST            | `California`   |
| `country`             | C             | `US`           |

- **CA certificates**: applied when the CA is first created. The root and
  intermediate are named `<ca_name> Root CA` and `<ca_name> Intermediate CA`.
  Changing the options later does not change an existing CA; to use new values
  for the CA itself, start over (see below).
- **Issued certificates**: applied on every restart. Fields you set replace
  whatever the client asked for; the Common Name, SANs, and any field you
  leave empty come from the client's request.

Leave all fields empty to keep step-ca's default behavior of copying the
subject from the request.

## Enrolling devices

Devices do not need an MDM. Open **Certificates → Enroll devices** in the
sidebar. There are three ways to get a certificate onto a device:

- **Enroll this device**: the Mac or Windows PC you have the panel open on.
- **Enrollment link**: phones, tablets, and other people's devices, with a
  one-time link and QR code.
- **Issue a certificate now**: anything else; downloads a .p12 straight from
  the panel.

### Enroll this device (Mac and Windows)

1. On the Mac or PC, open **Certificates → Enroll devices → Enroll this
   device**.
2. Enter a certificate name (e.g. `josh-macbook`). The device type is picked
   from the browser; change it if needed.
3. **Mac**: choose *iPhone, iPad, or Mac*, click **Download profile**, then
   open **System Settings → General → Device Management** and double-click
   the profile to install it. The Mac creates its own private key and
   requests the certificate over SCEP; the key never leaves the Mac.
4. **Windows**: choose *Other device*, note the password shown, download the
   .p12, double-click it, choose **Current User**, and enter the password.
   Import `root_ca.crt` into **Trusted Root Certification Authorities** if
   Windows does not already trust the CA.

Optionally enter **Alternative names** (see
[Subject alternative names](#subject-alternative-names)).

The page creates a one-hour enrollment link behind the scenes, so the
enrollment shows up in the links table like any other.

### Enrollment links

1. Under **Create an enrollment link**, optionally enter a label, a fixed
   certificate name, and alternative names, check the Home Assistant URL the device will use, set
   how long the link is valid (default `enrollment.link_hours`, 24), and
   choose whether the profile sets up Wi-Fi.
2. Click **Create link**. The link and a QR code are shown **once**; copy the
   link or scan the QR code with the device. The link can be used once.
3. On the device, open the link, enter a certificate name if it was not fixed,
   and pick the device type:
   - **iPhone, iPad, or Mac**: downloads a signed configuration profile with
     the root and intermediate CA, a SCEP payload with a one-time challenge,
     and (if configured) the Wi-Fi network. Install it under **Settings →
     Profile Downloaded** (iOS/iPadOS) or **System Settings → General →
     Device Management** (macOS). The device generates its key and enrolls
     over SCEP. The profile must be installed within an hour and only works
     once.
   - **Other device** (Android, Windows, Linux): the add-on creates the key
     and certificate and offers a password-protected .p12 for 10 minutes,
     plus the root CA certificate and `ca-bundle.pem`. The password is shown
     only once.
4. Pending, used, expired, and cancelled links are listed on the page. Cancel
   a pending link to make it unusable.

Links are served through Home Assistant's own URL, so devices must be able to
reach it. Nothing needs to be configured: the add-on uses Home Assistant's
**External URL** (**Settings → System → Network**), or if none is set, the
hostname you opened Home Assistant with, and only then the Internal URL. The
URL is shown, and can be changed, when you create a link.

The .p12 files use 3DES and SHA-1 so that Android, Windows, and older Apple
devices can import them.

### Wi-Fi in the profile

Set `wifi.ssid` to add an EAP-TLS Wi-Fi payload to Apple profiles. It uses the
certificate from the profile's SCEP payload and trusts the root and
intermediate CA, and any CAs added under **CA & downloads**, for the RADIUS
server's certificate. List your RADIUS server
certificate names in `wifi.radius_server_names` (e.g. `radius.example.com`)
so devices do not ask to trust the server. For .p12 devices the page shows the
settings to enter by hand (EAP method TLS, CA certificate, identity, and
domain).

### Subject alternative names

Enrollment links, **Enroll this device**, and **Issue a certificate now**
take optional **Alternative names**: email addresses, DNS names, and IP
addresses separated by commas (e.g. `josh@example.com, laptop.example.com,
192.0.2.10`). The type of each entry is detected automatically. Only
administrators can set them; people opening an enrollment link cannot.

Apple profiles support email addresses and DNS names only, so IP addresses
are left out of certificates requested by iPhones, iPads, and Macs. .p12
certificates get all three.

### RADIUS server CA and other trusted CAs

If your RADIUS server's certificate comes from another CA (for example a
public CA or your network's own CA), add that CA so devices trust the server:

1. Open **Certificates → CA & downloads**.
2. Under **Other trusted CAs**, choose the certificate file (PEM or DER,
   `.pem`, `.crt`, `.cer`) or paste the PEM, and click **Add**. A PEM file may
   hold several certificates. Only CA certificates are accepted.

Added CAs are included in:

- **Apple profiles** (iPhone, iPad, Mac): as a certificate payload, and
  trusted for the Wi-Fi network's RADIUS server;
- **.p12 files**, together with the root and intermediate;
- **ca-bundle.pem**: root, intermediate, and the added CAs in one PEM file,
  on the **CA & downloads** page and on the .p12 page of enrollment links.
  On Android, install it as a CA certificate and pick it as the Wi-Fi
  network's CA certificate.

Remove a CA with its **Remove** button. Changes apply to profiles and .p12
files created afterwards; devices already enrolled keep what they got.

### Profile signing

iOS and macOS show unsigned profiles, or profiles signed by a private CA, as
**Not Verified**. The add-on signs profiles with a publicly trusted
certificate so they show as **Verified**. The certificate only signs
profiles; its name does not have to match Home Assistant's URL. It is chosen
in this order:

1. **The Let's Encrypt add-on's certificate in `/ssl`** (recommended).
   Install Home Assistant's official **Let's Encrypt** add-on and configure it
   for your domain; with its DNS challenge (e.g. Cloudflare) no port needs to
   be open. It writes `/ssl/fullchain.pem` and `/ssl/privkey.pem`, which this
   add-on uses by default. Certificates from the DuckDNS add-on or any other
   publicly trusted certificate in `/ssl` work too; set
   `profile_signing.ssl_certificate` and `ssl_key` if the file names differ.
   New certificates and renewals are picked up within an hour.
2. Otherwise profiles are signed by this CA and show as Not Verified. They
   still install and work.

The **Enroll devices** page shows whether signing is **Verified** and, if not,
why.

## Revocation

Revoked certificates are published in a CRL signed by the intermediate CA.
Issued certificates do not contain a CRL distribution point, so configure
relying systems to download the CRL themselves. For FreeRADIUS, periodically
fetch `<Home Assistant URL>/api/step_ca_scep/crl?pem` into its CA directory
and enable CRL checking.

## Optional direct ports

The add-on's own ports (`9080` SCEP over HTTP, `9000` step-ca HTTPS API) are
disabled by default. Enable them in the add-on's **Network** section only if a
client must reach step-ca without going through Home Assistant.

## Configuration

### `ca_name`

Name used for the root and intermediate CA subjects. Only applied when the
CA is first created.

### `certificate_subject`

Organization (O), organizational unit (OU), locality (L), state (ST), and
two-letter uppercase country code (C). See
[Certificate subject](#certificate-subject).

### `dns_names`

Hostnames and IP addresses in step-ca's own HTTPS certificate. Only relevant
if you enable the direct `9000` port. Changes take effect on restart.

### `scep_provisioner_name`

The last path segment of the SCEP URL.

### `scep_challenge`

Shared challenge password clients must send. If empty, **anyone who can reach
the SCEP URL can obtain a certificate**, and a warning is logged.

### `encryption_algorithm`

Content encryption algorithm used in SCEP responses:
`0` DES-CBC, `1` AES-128-CBC, `2` AES-256-CBC (default), `3` AES-128-GCM,
`4` AES-256-GCM. Use `0` only for legacy clients that do not support AES.

### `min_public_key_length`

Minimum RSA key size accepted from clients.

### `include_root`

Include the root CA in the GetCACert response.

### `force_cn`

Always add the Common Name to the certificate's SANs.

### `default_cert_duration` / `max_cert_duration`

Lifetime of issued certificates, e.g. `8760h` (one year). The maximum must be
greater than or equal to the default.

### `install_integration`

Copy the bundled Step CA SCEP integration into Home Assistant's
`custom_components` folder on start (default `true`). Turn this off if you
manage the integration yourself.

### `database`

`mariadb` (default) stores step-ca's records in the MariaDB add-on and
enables the certificate list on the management page. `embedded` uses
step-ca's built-in database. See [Database](#database).

### `mariadb_database`

Name of the MariaDB database step-ca uses (default `stepca`). Do not point
this at a database used by something else, such as Home Assistant's
recorder.

### `enrollment`

- `public_url` (hidden; enable **Show unused optional configuration
  options** to set it): overrides the detected Home Assistant URL, e.g.
  `https://ha.example.com`. Not needed normally.
- `link_hours`: how long enrollment links stay valid (1-168, default 24).

### `profile_signing`

Publicly trusted certificate for signing Apple profiles. See
[Profile signing](#profile-signing).

- `ssl_certificate`, `ssl_key`: file names in `/ssl` (default
  `fullchain.pem` and `privkey.pem`, as written by the Let's Encrypt add-on).

### `wifi`

Wi-Fi network added to Apple profiles. Leave `ssid` empty for none.

- `ssid`: network name.
- `security`: `WPA2`, `WPA3`, or `Any`.
- `hidden`: the network does not broadcast its name.
- `auto_join`: join automatically.
- `radius_server_names`: names in your RADIUS server's certificate that
  devices should trust.

## Administration

A JWK provisioner named `admin` is also created. Its password is stored in
`/data/step/secrets/provisioner_password` and can be used with the `step` CLI
for manual certificate issuance.

## Starting over

To discard the CA and create a new one, uninstall the add-on with its data
removed and install it again. All previously issued certificates will stop
chaining to a trusted root.

## Troubleshooting

- `404` on `/api/step_ca_scep/...`: Home Assistant has not been restarted
  since the integration was installed, or the integration has not been added
  under **Devices & services**.
- `503`: the integration is installed but has no configured entry.
- `502`: Home Assistant cannot reach the add-on; make sure it is running.
- "MariaDB is not available": install and start the MariaDB add-on, or set
  `database` to `embedded`.
- "Could not create the MariaDB database": check the MariaDB add-on's log;
  the add-on needs the MariaDB add-on's service account, which the Supervisor
  provides automatically.
- "Only Home Assistant administrators can manage certificates": the logged-in
  user is not an administrator. Change it under **Settings → People**.
- The CRL route returns `404`: restart Home Assistant after updating the
  add-on so it loads integration 1.1.0.
- Enrollment links return `404`: the link was used, cancelled, or has
  expired, or Home Assistant has not been restarted since the add-on updated
  the integration to 1.2.0.
- "Set enrollment.public_url in the add-on options first": the Home
  Assistant URL could not be detected. Set the External URL under
  **Settings → System → Network**.
- Profiles show as **Not Verified**: check the **Enroll devices** page and
  the add-on log for the reason. Usually the Let's Encrypt add-on has not
  run yet or failed; check its log.
- A profile fails to install with a SCEP error: its one-time challenge was
  already used or is over an hour old. Open the link again, or use
  **Enroll this device**, to get a fresh profile.

- `badRequest` from the client usually means a wrong challenge password.
- If a client complains that it cannot encrypt to the CA, make sure it selects
  the RSA RA certificate (the first certificate in the GetCACert response).
- If the add-on fails with "Could not configure the SCEP provisioner", the
  message ends with step's own error. Check the duration options and that
  `scep_provisioner_name` is not `admin` or `enrollment`.
