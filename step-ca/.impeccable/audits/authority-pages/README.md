# Focused Authority pages — 0.30.2.57

The previous Authority dropdown's overview, root, intermediate, downloads and
endpoints options all opened the same large `/ca` document at different anchors.
Those tasks now have distinct pages and direct dropdown destinations:

| Menu option | Destination | Information owner |
| --- | --- | --- |
| Authority overview | `/ca` | Task chooser with brief CA name, expiry and status |
| Root CA | `/ca/root` | Root subject, issuer, validity start/end, serial, SHA-256, individual PEM |
| Intermediate CA | `/ca/intermediate` | Issuing certificate's own fields and individual PEM |
| Downloads | `/ca/downloads` | File selection, contents and formats |
| Endpoints | `/ca/endpoints` | Configured public URL source and SCEP/root/CRL URLs |
| Device trust certificates | `/settings/certificates/trust` | Existing shared Settings editor, one form |

Root/intermediate detail fields come from the selected certificate file, not
from configuration labels. Status accounts for not-yet-valid certificates,
expiry and renewal within 180 days. Root details still work if the intermediate
file is unavailable. Files are closed after reading.

The six downloads preserve existing URLs and bytes: root PEM, intermediate PEM,
intermediate-to-root PEM chain, the same chain with a Meraki-compatible `.crt`
filename, root/intermediate/additional-device-trust PEM bundle, and PEM CRL.
The `.crt` variant is intentional format packaging, now explicitly labelled.
The guidance was checked against [Cisco's Access Manager deployment guide](https://documentation.meraki.com/Platform_Management/Access_Manager/Access_Manager_Deployment_Guide).

Endpoint URLs match the bundled Home Assistant views. SCEP uses the configured challenge policy;
root and CRL downloads are public. The final backend trace confirmed default
SCEP accepts unvalidated requests when its static challenge is unset, while
groups without a static challenge accept one-time enrollment links only. Those
policies now appear on Endpoints without exposing challenge values. CRL endpoints distinguish DER from
`?pem`. Missing base URLs offer recovery with no fabricated copyable values.
Group challenges and other secrets are absent. Endpoint availability is not
claimed merely from configuration. Device trust management remains one canonical
Settings screen; its repeated inner heading is now Additional CA certificates.

## Bounded verification

The initial pass covered five Authority pages at 1280px/light and 320px/dark,
with menus closed/open: 20 axe views. One confirmation covered the shared trust
heading repair at both widths and menu states: four views. The inspected views had zero
violations, horizontal overflow or clipped menus. Eight interaction checks cover
four old fragment bookmarks, keyboard open/close/focus, the canonical trust
settings form and native no-script dropdown navigation. Screenshots are fictional
local fixture previews, not the production CA.

214 tests and seven Home Assistant 2026.9.4 compatibility checks passed. All
three architecture builds and nonroot runtime probes passed, rendering all five
Authority pages and matching all 11 admin module source hashes. Regression checks
compare real RFC5280 certificate metadata and PEM chain bytes to the displayed
labels. Static checks passed. Two verification-harness assumptions were corrected:
the trust heading uses the Settings shell's class, and the runtime probe's
cryptography import must not shadow its source-hash dictionary. No product defect
was hidden by those harness repairs.

Source CI passed and version 0.30.2.57 was deployed. The backup completed before
the update; its initial Supervisor job monitor returned `unknown_error`.
Read-only inspection confirmed the requested version started. One verification
attempt then encountered a connection failure before Core restart; a second
inspection again confirmed the add-on started. The final workflow passed the
Core configuration check, restart, companion-load check and live iPSK request
(five wireless networks). See `deployment.json` for exact run identities.

All six live Authority destinations were opened and their contents checked.
Root and intermediate fingerprints match their downloaded production PEMs;
the intermediate signature verifies with the root public key. The downloaded
chain contains intermediate then root. Downloads lists six choices, Endpoints
shows the eight expected companion URLs and five challenge-policy rows, and
Device trust certificates opens one shared Settings page with one upload form.
No ingress sessions, certificate values or challenge values are saved in
`live-menu-checks.json`. A Home Assistant reconnect invalidated the initial
ingress session; refreshing it restored navigation. An optional live `.crt`
download byte comparison timed out; the regression checks prove its contents,
and no successful live `.crt` comparison is claimed.

A final backend-policy trace corrected the blanket SCEP authorization wording
and added per-provisioner challenge policy. Regression tests and final source
builds cover that correction. No third visual pass was performed.
