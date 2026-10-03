# IPSK release 0.30.2.49 — 2026-10-03 UTC

Publication and deployment are pending. The intended update replaces Step CA
0.30.2.48 on the existing Home Assistant installation.

## Checks

- 153 tests passed against Python 3.14 and the exact CI dependency versions.
- Seven real Home Assistant 2026.9.4 compatibility checks passed.
- 32 real MariaDB 10.11 checks passed on disposable fresh and legacy schemas,
  including invitation labels, repeat migrations, permissions and registration races.
- All three supported images (aarch64, amd64 and armv7) built and ran.
  Packaged portal hashes match the release source.
- Seven certificate/startup checks passed: issuance, renewal, revocation, CRL,
  SCEP capabilities and installed companion 1.5.2. Restart stayed healthy and
  retained the root certificate. Certificates belonged only to the disposable CA.
- Ruff lint, Python compilation, Bash/JavaScript syntax, YAML/JSON parsing and
  whitespace checks passed. Unused imports/locals and compact test statements
  were cleaned up; existing rendered UI audit evidence remains applicable.
- The preceding interface audit exercised 84 rendered views with no axe
  violations or incomplete results. See 2026-10-02-ipsk-clean-audit.md.

Exact hashes and container/database evidence: 2026-10-03-ipsk-release-checks.json.

The release adds an invitation-label column at startup. The existing deployment
helper backs up Step CA, MariaDB and Home Assistant settings before updating,
then verifies the installed version and companion with a live read-only iPSK
options request. Provider writes and physical Wi-Fi/Duo acceptance are outside
these automated deployment checks.
