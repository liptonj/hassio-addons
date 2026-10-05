# Certificate email display — 0.30.2.56

The live Home Assistant certificate list contained Cloudflare-generated
`/cdn-cgi/l/email-protection` links displaying `[email protected]`. The app's
renderer emitted the original certificate SAN values as escaped text. Its CSP
only permits the application's nonce-bearing script, so Cloudflare's injected
decoder cannot restore the addresses.

The shared certificate/admin/public-enrollment document renderer now encloses
its body in Cloudflare's documented email opt-out comments. Responses also
include `Cache-Control: no-store, no-transform`; the comments protect the page
when an intermediate ingress/proxy does not preserve that directive. CSP,
certificate contents and stored email values remain unchanged. No Cloudflare
zone-wide configuration changes are required.

Reference: [Cloudflare Email Address Obfuscation](https://developers.cloudflare.com/waf/tools/scrape-shield/email-address-obfuscation/).

Validation: 206 tests passed, including a real RFC822Name certificate rendered
in list/detail pages, response policy and public enrollment coverage. Seven
Home Assistant 2026.9.4 compatibility checks passed. Ruff, Python compilation
and whitespace checks passed. No layout, JavaScript or dependency changes were
introduced. Architecture builds/runtimes remain covered by the immediately
preceding 0.30.2.55 release; they were not repeated for this HTML/header fix.

Deployment and live display verification pending.
