# Step CA SCEP Server for Home Assistant

## About

This add-on runs [smallstep step-ca](https://github.com/smallstep/certificates)
(Apache-2.0), an open-source private certificate authority, and configures a
SCEP provisioner so that devices, MDM platforms with a static SCEP challenge
(Jamf Pro, Kandji, Mosyle, and others; see [Using an MDM](#using-an-mdm)),
and network gear can enroll for client certificates, for example for
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

- list issued certificates, filter by active, expired, or revoked (the list
  opens on **Active**, so revoked certificates are hidden), and search by
  name, SAN, or serial number;
- delete revoked and expired certificates from the list, one at a time or
  all at once (see [Revocation](#revocation));
- view a certificate's details and download it as PEM;
- revoke a certificate with a reason (the CRL is regenerated immediately);
- download the root CA, intermediate CA, a full CA bundle, and the current
  CRL, and add other CAs devices must trust, such as your RADIUS server's
  (see [RADIUS server CA](#radius-server-ca-and-other-trusted-cas));
- enroll devices with one-time links or QR codes, enroll the computer you are
  using, or issue a certificate directly (see
  [Enrolling devices](#enrolling-devices));
- sign certificate requests (CSRs) from other systems, such as a RADIUS or
  web server, or another CA (see
  [Signing certificate requests](#signing-certificate-requests));
- add, edit, and remove [certificate groups](#certificate-groups) and
  download MDM profiles.

The **Tools** tab is a menu: **Groups**, **MDM profiles**, **Sign a
request**, **Other trusted CAs**, and **Add-on options** (a read-only
summary of the running configuration).

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

## Certificate groups

Groups tell certificates apart, for example adults, kids, and guests, so a
RADIUS server or firewall can treat them differently. Each group has:

- its own SCEP URL, `…/api/step_ca_scep/scep/<name>`;
- its own OU (organizational unit). Every certificate the group issues gets
  this OU, whatever the device asks for. The other `certificate_subject`
  fields still apply;
- its own challenge, so a device can only join the group whose challenge
  it was given;
- optionally its own certificate lifetime;
- optionally `require_email`: certificates must carry an email subject
  alternative name (see [Requiring an email address](#requiring-an-email-address)).

Manage groups under **Certificates → Tools → Groups**: add a group, edit or
remove one, and click **Generate** for a random challenge. Saving writes the
add-on options and applies the change at once: step-ca reloads its
provisioners without a restart, and enrollments in progress are not
interrupted. If you edit `groups` in the add-on's Configuration tab instead,
the Groups page shows **Groups not applied**; click **Apply now** (or restart
the add-on). Other options still take effect on restart. In YAML:

```yaml
groups:
  - name: adults
    organizational_unit: Adults
    challenge: <a long random string>
  - name: kids
    organizational_unit: Kids
    challenge: <another long random string>
    cert_duration: 2160h
  - name: guests
    organizational_unit: Guests
    cert_duration: 168h
```

- **MDM**: make one SCEP profile per group, with the group's SCEP URL and
  challenge (or download it under **Tools → MDM profiles** with the group
  selected). Assign each profile to that group of devices or users.
- **Without an MDM**: choose the group when you create an enrollment link,
  enroll this device, or issue a .p12. A group without a `challenge` (like
  `guests` above) only accepts one-time enrollment links.
- The default SCEP URL keeps working as before, with the `certificate_subject`
  OU and `scep_challenge`.
- **Certificates** shows each certificate's OU.

Group names use lowercase letters, digits, `-`, and `_`, and cannot be
`enrollment` or the `scep_provisioner_name`.

### Requiring an email address

Some RADIUS servers identify the user from the certificate. Cisco Meraki
Access Manager, for example, matches a certificate field (an email subject
alternative name is recommended) against the user's Entra ID UPN, then
applies Entra group membership. Set `require_email: true` (or tick **Require
an email address**) on the groups whose certificates must carry one:

- the SCEP webhook refuses a request without an email SAN for the group,
  from an MDM or an enrollment link;
- enrollment links, **Enroll this device**, and .p12 issuing make the
  **Email address** field required and refuse to continue without one;
- MDM profiles for the group need the **Email address** variable, for
  example `{{userprincipalname}}` in Intune or `$OWNEREMAIL` in Meraki.

The OU still sets the group's baseline; Entra groups can grant more on top.
A guest group can leave `require_email` off, since guests are usually not in
your directory.

### Moving a device to another group

A certificate's OU cannot change. To move someone, for example from kids to
adults: move the device or user to the new group in your MDM (or send a new
enrollment link for the new group). The device installs a certificate from
the new group's profile; then revoke the old certificate on **Certificates**.
Removing the old profile in the MDM removes its certificate from the device.

### Using the OU in RADIUS

The RADIUS server reads the OU from the client certificate. For example, in
FreeRADIUS the subject is in `TLS-Client-Cert-Subject`, so a policy such as
`if (&TLS-Client-Cert-Subject =~ /OU=Kids/) { … }` can assign the kids VLAN.
Other servers (NPS, ClearPass, ISE, cloud RADIUS) have a similar
certificate-attribute rule.

Passpoint and OpenRoaming need certificates from the WBA's own PKI, which
this CA cannot issue. Groups apply to your own Wi-Fi.

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
2. On a Mac, **Certificate name** defaults to **Serial number of this
   iPhone, iPad, or Mac** (see [Serial number as the certificate
   name](#serial-number-as-the-certificate-name)); choose **Custom…** to
   enter a name such as `josh-macbook` instead. The device type is picked
   from the browser; change it if needed.
3. **Mac**: choose *iPhone, iPad, or Mac*, click **Download profile**, then
   open **System Settings → General → Device Management** and double-click
   the profile to install it. The Mac creates its own private key and
   requests the certificate over SCEP; the key never leaves the Mac.
4. **Windows**: choose *Other device*, note the password shown, download the
   .p12, double-click it, choose **Current User**, and enter the password.
   Import `root_ca.crt` into **Trusted Root Certification Authorities** if
   Windows does not already trust the CA.

Optionally enter an **Email address**, pick a **Group (OU)**, and add
**Other alternative names** (see
[Subject alternative names](#subject-alternative-names)).

The page creates a one-hour enrollment link behind the scenes, so the
enrollment shows up in the links table like any other.

### Serial number as the certificate name

Enrollment links and **Enroll this device** can name the certificate after the
device's serial number, the way an MDM fills in `$SERIALNUMBER`. Choose
**Device serial number** for the certificate name, or type a name containing
`$SERIALNUMBER`, such as `mac-$SERIALNUMBER`. On the device, the name can also
be picked on the enrollment page.

This works on iPhone, iPad, and Mac only. Their first profile is a *profile
service*: when it is installed, the device sends its serial number to Home
Assistant (at `/api/step_ca_scep/enroll/<token>/device`) and gets the real
profile back, which iOS and macOS then offer to install. On other devices,
enter a name instead.

The serial number is what the device reports; it is not checked against
Apple. The one-time challenge in the first profile ties the reply to the link,
which still works only once. This needs version 1.3.0 of the Home Assistant
integration, which the add-on installs; restart Home Assistant after updating
the add-on.

### Enrollment links

1. Under **New one-time link**, optionally enter a label, a fixed
   certificate name, and an **Email address**, and pick a **Group (OU)**,
   the same fields as **Enroll this device**. Under **More options**, add
   other alternative names, check the Home Assistant URL the device will
   use, set how long the link is valid (default `enrollment.link_hours`,
   24), and choose whether the profile sets up Wi-Fi.
2. Click **Create link**. The link and a QR code are shown **once**; copy the
   link or scan the QR code with the device. The link can be used once.
3. On the device, open the link, enter a certificate name if it was not fixed
   (or choose the device's serial number), and pick the device type:
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
4. Links are listed on the page under **Waiting**, **Used**, **Expired or
   cancelled**, and **All**, 10 to a page. Cancel a waiting link to make it
   unusable. Delete used, expired, and cancelled links one at a time or all
   at once; this does not affect their certificates. Links are also removed
   automatically 30 days after they expire.

Links are served through Home Assistant's own URL, so devices must be able to
reach it. Nothing needs to be configured: the add-on uses Home Assistant's
**External URL** (**Settings → System → Network**), or if none is set, the
hostname you opened Home Assistant with, and only then the Internal URL. The
URL is shown, and can be changed, when you create a link.

The .p12 files use 3DES and SHA-1 so that Android, Windows, and older Apple
devices can import them.

### Wi-Fi in the profile

Add networks under **Tools → Wi-Fi networks** (or `wifi_networks`) to add a
Wi-Fi payload for each to Apple profiles. An EAP-TLS network uses the
certificate from the profile's SCEP payload and trusts the root and
intermediate CA, and any CAs added under **Tools → Other trusted CAs**, for the RADIUS
server's certificate. For .p12 devices the page shows the
settings to enter by hand (EAP method TLS, CA certificate, identity, and
domain).

### Subject alternative names

Enrollment links, **Enroll this device**, and **Issue a certificate now**
have an **Email address** field, typically the user's sign-in email, and
optional **Other alternative names**: more email addresses, DNS names, and
IP addresses separated by commas (e.g. `laptop.example.com, 192.0.2.10`). The type of each entry is detected automatically. Only
administrators can set them; people opening an enrollment link cannot.

Apple profiles support email addresses and DNS names only, so IP addresses
are left out of certificates requested by iPhones, iPads, and Macs. .p12
certificates get all three.

### RADIUS server CA and other trusted CAs

If your RADIUS server's certificate comes from another CA (for example a
public CA or your network's own CA), add that CA so devices trust the server:

1. Open **Certificates → Tools → Other trusted CAs**.
2. Choose the certificate file (PEM or DER,
   `.pem`, `.crt`, `.cer`) or paste the PEM, and click **Add**. A PEM file may
   hold several certificates. Only CA certificates are accepted.

Added CAs are included in:

- **Apple profiles** (iPhone, iPad, Mac): as a certificate payload, and
  trusted for the Wi-Fi network's RADIUS server;
- **.p12 files**, together with the root and intermediate;
- **ca-bundle.pem**: root, intermediate, and the added CAs in one PEM file,
  on the **Authority** page and on the .p12 page of enrollment links.
  On Android, install it as a CA certificate and pick it as the Wi-Fi
  network's CA certificate.

Remove a CA with its **Remove** button. Changes apply to profiles and .p12
files created afterwards; devices already enrolled keep what they got.

### Signing certificate requests

Systems that create their own key, such as a RADIUS, web, or VPN server,
give you a certificate signing request (CSR). To sign it, open
**Certificates → Tools → Sign a request**, choose the
file (PEM or DER) or paste the PEM, pick the type, and click **Sign and
download**:

- **Server or client certificate**: signed by the intermediate CA through
  step-ca, with the Common Name and subject alternative names from the
  request, key usage for server and client authentication, and the
  `default_cert_duration` lifetime. `certificate_subject` attributes are
  applied as for other certificates. It appears on **Certificates** and can
  be revoked.
- **Subordinate CA**: signed by the root CA, keeping the requested subject
  unchanged, for 10 years or until the root expires, with these extensions:

  ```
  basicConstraints = critical,CA:true,pathlen:0
  keyUsage = critical,keyCertSign,digitalSignature
  ```
 Used for another CA whose
  certificates should be trusted wherever this root is, such as Meraki's
  SCEP CA (see [Platform notes](#platform-notes)).

The download (`<name>-chain.crt`, Base64 PEM) holds the signed certificate
followed by its CA chain up to the root. Each signing is written to the add-on log.

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

## Using an MDM

An MDM can deploy the same SCEP enrollment that enrollment links do. The
values for your installation, and each certificate as a separate download,
are on **Certificates → Tools → MDM profiles**.

Before you start:

- Set a strong `scep_challenge`. The MDM sends it to every device; anyone who
  learns it can obtain certificates, so change it if it leaks.
- Devices request their certificate themselves, so they must reach the SCEP
  URL. Use the Home Assistant URL that works where the devices are: the
  External URL if they enroll away from home.

### Download a ready-made profile (Apple devices)

Instead of entering the values by hand, download a profile under
**Certificates → Tools → MDM profiles → Download a profile for your
MDM** and upload it to your MDM as a custom profile. There is a separate
download for each device type: **iPhone and iPad profile** and **Mac
profile**. Upload both and assign each to those devices.

- The iPhone and iPad profile installs for the user and leaves out Mac-only
  Wi-Fi settings (connect at the login window).
- The Mac profile installs for the whole Mac (`PayloadScope` `System`, so the
  System keychain) and leaves out iPhone-only Wi-Fi settings (captive portal
  bypass, Passpoint MCC/MNC and HESSID).

Choose:

- **Contents**: certificates only; certificates and SCEP; or certificates,
  SCEP, and Wi-Fi when a network is set up. Every certificate is included: the
  root CA, the intermediate CA, and each of the **Other trusted CAs**.
- **Your MDM**: Meraki, Jamf Pro, Kandji, Intune, or another MDM. This fills the
  two menus below with that MDM's variables. Choose **Custom** in either menu
  to type a variable that is not listed.
- **Certificate name**: your MDM's variable for a unique value, which the
  MDM replaces on each device. For a device certificate use the serial
  number: `$SERIALNUMBER` in Jamf, `$DEVICESERIAL` in Meraki,
  `$SERIAL_NUMBER` in Kandji, `{{serialnumber}}` in Intune. For a user
  certificate use the user name: `$USERNAME` in Jamf, `$OWNERUSERNAME` in
  Meraki, `{{userprincipalname}}` in Intune.
- **Email address** (optional, unless the group requires one): your MDM's
  email variable, such as `$EMAIL` in Jamf, `$OWNEREMAIL` in Meraki, or
  `{{userprincipalname}}` in Intune. It is added to the certificate as an
  email subject alternative name, which RADIUS servers can match for
  EAP-TLS. The device needs a user assigned in the MDM.

The file is a standard, unsigned `.mobileconfig`, so any MDM can read it,
replace the variable, and sign it. The SCEP profiles contain the
`scep_challenge`, so keep them private. They need a public HTTPS Home
Assistant URL, as for enrollment links.

### What to put in the profile

To build the profile in your MDM instead, create one configuration profile
with these payloads.

1. **Certificate** payloads (Apple: *Certificate*; others: *Trusted
   certificate*), one for each file:
   - `ca-chain.pem`: this CA's full trusted chain (intermediate, then root)
     in one file;
   - each CA added under **Other trusted CAs**, such as your RADIUS server's
     CA. Its download includes its issuers if you added them too.

   If your MDM takes one certificate per payload instead, use
   `root_ca.pem` and `intermediate_ca.pem` as two payloads.
2. **SCEP** payload:

   | Field                  | Value                                                        |
   | ---------------------- | ------------------------------------------------------------ |
   | URL                    | `<Home Assistant URL>/api/step_ca_scep/scep/<provisioner>`   |
   | Name                   | Any name, e.g. the provisioner name `scep`                   |
   | Subject                | `CN=<device variable>`, e.g. `CN=$SERIALNUMBER` in Jamf      |
   | Subject alternative name | Optional: RFC 822 name (email) or DNS name                |
   | Challenge              | The `scep_challenge` value (static challenge)                |
   | Key size               | 2048 (or more; at least `min_public_key_length`)             |
   | Key type               | RSA                                                          |
   | Key usage              | Signing and encryption                                       |
   | Fingerprint            | Leave empty                                                  |
   | Allow export of key    | Off                                                          |

   Use a variable in the subject that is unique per device, so each
   certificate can be found and revoked in the **Certificates** list. If
   `certificate_subject` is set, its O, OU, L, ST, and C replace whatever the
   profile asks for; the Common Name and SANs come from the profile.
3. **Wi-Fi** payload (optional), for 802.1X EAP-TLS:
   - Security: WPA2/WPA3 Enterprise; accepted EAP type **TLS**.
   - Identity certificate: the SCEP payload.
   - Username: optional, e.g. the same variable as the Common Name.
   - Trusted certificates: the certificate payloads that issued your RADIUS
     server's certificate (this CA, or the RADIUS CA you added).
   - Trusted server certificate names: the names in the RADIUS server's
     certificate, e.g. `radius.example.com`.

### Platform notes

- **Jamf Pro**: use a *Computer* or *Mobile Device* configuration profile
  with the payloads above. The challenge type is *Static*. Jamf's *SCEP
  proxy* is not needed.
- **Kandji, Mosyle, SimpleMDM, Addigy, and other Apple MDMs**: use their
  SCEP and Certificate library items with the values above.
- **Microsoft Intune**: Intune's SCEP profiles use a one-time challenge that
  the CA must verify with Intune's validation API. step-ca's open-source
  release does not do this, so Intune SCEP profiles do not work with this
  add-on. Instead, download a ready-made profile with **Your MDM** set to
  Intune and upload it as a *Custom* profile (iOS/iPadOS or macOS): it
  carries the static challenge, and Intune replaces `{{…}}` variables such as
  `{{userprincipalname}}`. You can also deploy the CA certificates with
  Intune *Trusted certificate* profiles and enroll devices with enrollment
  links.
- **Android Enterprise and Windows MDMs** with a static-challenge SCEP
  profile (for example Workspace ONE): use the same URL, challenge, and
  certificates.
- **Cisco Meraki Systems Manager** runs its own SCEP CA. To make the
  certificates it issues trusted by this CA's root, sign Meraki's SCEP CA
  with this CA:
  1. In Meraki, go to **Organization → MDM** and download the SCEP CA
     certificate request (or the current SCEP CA certificate).
  2. On **Certificates → Tools → Sign a request**,
     choose that file, pick **Subordinate CA**, and select **Sign and
     download**. The root CA signs it with the extensions Meraki
     requires (`basicConstraints = critical,CA:true,pathlen:0` and
     `keyUsage = critical,keyCertSign,digitalSignature`), keeping Meraki's
     subject unchanged, valid for up to 10 years.
  3. Upload the downloaded `…-chain.crt` in Meraki. It holds the signed
     certificate followed by this root CA, the full trusted chain Meraki
     asks for.

  The signing is written to the add-on log.

### Your RADIUS server

The RADIUS server must trust the client certificates. Give it
`ca-chain.pem` (or `root_ca.pem` alone if it builds the chain from the
certificates the clients send). To reject revoked
certificates, see [Revocation](#revocation).

## Revocation

Revoked certificates are published in a CRL signed by the intermediate CA.
Issued certificates do not contain a CRL distribution point, so configure
relying systems to download the CRL themselves. For FreeRADIUS, periodically
fetch `<Home Assistant URL>/api/step_ca_scep/crl?pem` into its CA directory
and enable CRL checking.

Removing a device's profile from an MDM removes its certificate from the
device but does not revoke it. Revoke it on **Certificates** if it should no
longer be accepted.

Revoked and expired certificates can be deleted from the **Certificates**
list. This only hides them in the panel: step-ca's records are not changed,
and revoked certificates stay on the CRL until they expire. To bring one
back, open `…/cert/<serial>` and choose **Restore to the list**.

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

### `groups`

Certificate groups, each with `name`, `organizational_unit`, an optional
`challenge`, an optional `cert_duration` (for example `720h`) that sets
both the default and maximum lifetime, and an optional `require_email`. See
[Certificate groups](#certificate-groups); edit them under
**Certificates → Tools → Groups**.

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

### `wifi_networks`

Wi-Fi networks added to Apple profiles, one payload each. Edit them in the
panel under **Tools > Wi-Fi networks**: changes are saved here and used by new
profiles right away, without a restart. Profiles already on devices or
uploaded to an MDM keep the old settings until you replace them.

Each network:

- `ssid`: network name. Optional for a Passpoint network.
- `authentication`: `eap_tls` (default), where each device signs in with the
  certificate from this CA through a RADIUS server (WPA Enterprise); or
  `psk`, one shared password (WPA Personal).
- `password`: the network password for `psk`, 8 to 63 characters (or 64
  hex digits). Profiles with the network include it.
- `security`: `WPA2` (default), `WPA3`, or `Any`.
- `hidden`: the network does not broadcast its name.
- `auto_join`: join automatically (default on).
- `disable_mac_randomization`: turns off Private Wi-Fi Address for this
  network, so devices use their real MAC address on it (for DHCP
  reservations or MAC-based rules). iOS and iPadOS 14, macOS 15, and later;
  the device shows a privacy warning for the network.
- `radius_server`: `custom` (default) for your own RADIUS server, whose CA
  you add under **Tools > Other trusted CAs**; or `meraki_access_manager`,
  which makes devices trust Meraki Access Manager's RADIUS certificate. See
  [Cisco Meraki Access Manager](#cisco-meraki-access-manager).
- `radius_server_names`: optional. Pins the names in the RADIUS server's
  certificate that devices accept. Without it, devices accept any server
  certificate issued by the CAs the profile trusts, which is fine when that
  is this CA. It matters only when the CA also issues certificates to other
  servers, such as a public CA; Meraki's name is added for you.
- `proxy`: `none` (default), `manual`, or `auto`. A web proxy used on this
  network only. Apple applies it on iPhone and iPad; Macs also take the
  manual server and the PAC URL.
  - `manual`: `proxy_server`, `proxy_port`, and optionally `proxy_username`
    and `proxy_password`.
  - `auto`: `proxy_pac_url` (empty finds the proxy with WPAD) and
    `proxy_pac_fallback`, which connects directly when the PAC file cannot be
    reached.
- `captive_bypass`: the device does not look for a captive portal (sign-in
  page) on this network. iPhone and iPad.
- `mac_login_window`: a Mac joins the network at the login window, before
  anyone signs in, using the certificate in the System keychain (for network
  accounts and FileVault). The profile then installs for the whole Mac, which
  an administrator approves.
- `qos_marking`: Cisco Fast Lane QoS marking. `default` lets every app mark
  its traffic; `allowlist` lets only FaceTime and Wi-Fi Calling
  (`qos_apple_calls`) and the apps in `qos_apps` (bundle IDs) do it; `off`
  makes the device ignore Fast Lane on this network.
- `passpoint`: a Passpoint (Hotspot 2.0) network, found by its operator
  rather than only its SSID. Needs `eap_tls` and `passpoint_domain`.
  Optional: `passpoint_operator_name` (shown when connected),
  `passpoint_roaming_consortium_ois` (6 or 10 hex digits each),
  `passpoint_nai_realms`, `passpoint_mcc_mncs` (six digits each; iPhone and
  iPad), `passpoint_hessid` (iPhone and iPad), and `passpoint_roaming`, which
  allows roaming to partner providers.

Apple's option to join before the first unlock after a restart
(`AllowJoinBeforeFirstUnlock`) works only on Apple Vision Pro, so it is not
offered.

### `wifi`

The single network from earlier versions, with the first fields above. It is
used only while `wifi_networks` is empty; saving in the panel moves it to
`wifi_networks` and clears its `ssid`.

Apple profiles trust only the CAs they install for the Wi-Fi server's
certificate and do not ask the user. If the RADIUS server's certificate does
not chain to one of them, the device never joins the network.

### Cisco Meraki Access Manager

EAP-TLS needs trust in both directions.

**Devices trust Meraki.** Access Manager's RADIUS server presents a
certificate for `eap.meraki.com` issued under IdenTrust Commercial Root CA 1.
Set the network's RADIUS server to Meraki Access Manager; every Wi-Fi profile
(enrollment links, **Enroll this device**, and MDM downloads) then installs
that root as a trusted anchor and trusts the server name `eap.meraki.com`.
No upload is needed. Devices that installed a profile before the change need
the new one: remove the old profile and enroll again, or push the new MDM
profile.

**Meraki trusts devices.** In Meraki, go to **Access Manager > Configure >
Certificates** and upload the **Meraki Access Manager** download from
**Authority** (`<CA name>-ca-chain.crt`, the intermediate and root in one
file) as a single entry. Set its status to **Enabled**, turn **Trusted
Anchor** on, and choose **Subject Alternative Name RFC822** as the identity
field. Do not upload `ca-bundle.pem` or
the root and intermediate again as separate entries; Meraki rejects devices
with "The provided certificate is untrusted… signer being disabled, extra or
duplicate certificates in the chain" when the CA is missing, disabled, or
duplicated.

Access Manager matches a certificate field, ideally the email address, to the
user's Entra ID UPN; see [Requiring an email address](#requiring-an-email-address).

With Meraki Systems Manager, download the profile with **Certificates, SCEP,
and Wi-Fi** under **Tools > MDM**, so the Wi-Fi payload uses this CA's
certificate and trusts Meraki's server. A Wi-Fi payload configured separately
in Systems Manager cannot use the certificate from a custom profile. If the
device joined the SSID by hand before, forget the network first.

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
