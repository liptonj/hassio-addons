# Step CA SCEP Server

A private certificate authority for Home Assistant that issues client
certificates over SCEP, built on the open-source
[smallstep step-ca](https://github.com/smallstep/certificates) container.

SCEP is served on Home Assistant's own port at
`/api/step_ca_scep/scep/<provisioner>` by a bundled companion integration, so
no extra port or tunnel is required. A **Certificates** panel in the Home
Assistant sidebar lists, downloads, and revokes issued certificates, with
records stored in the MariaDB add-on.

Devices can be enrolled without an MDM: send a one-time link or QR code, or
click **Enroll this device** in the panel on a Mac or Windows PC. Apple
devices get a Let's Encrypt-signed profile that enrolls over SCEP and can set
up EAP-TLS Wi-Fi; other devices get a .p12 file.

See [DOCS.md](DOCS.md) for setup and configuration.
