# Changelog

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
