# IPSK release 0.30.2.49 — 2026-10-03 UTC

**Step CA 0.30.2.49 is deployed and running.** Final verification at
**2026-10-03 03:20:39 UTC** confirmed the companion loaded after Core restarted
and the live iPSK options request returned five wireless networks.
The update replaced 0.30.2.48 on the existing Home Assistant installation.

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

## Publication and live verification

- Source commit `62c1564fe96c632d8d6821940e1cbde158bcf193`, pushed to master.
- [Linux CI](https://github.com/liptonj/hassio-addons/actions/runs/37092428768)
  passed all 153 tests and seven real HA compatibility checks for that commit.
- [Backup and update](https://github.com/liptonj/meraki-homeassistant/actions/runs/37092498710)
  completed the Step CA/MariaDB/Core settings backup before submitting the
  update. The workflow then failed reading the Supervisor update job record;
  this failure was not treated as evidence of deployment success.
- [Read-only inspection](https://github.com/liptonj/meraki-homeassistant/actions/runs/37092712236)
  independently confirmed Step CA 0.30.2.49 started, MariaDB 3.0.1 started,
  and Home Assistant 2026.9.4 online.
- [Final verification](https://github.com/liptonj/meraki-homeassistant/actions/runs/37092758924)
  passed. It rechecked the requested version, confirmed it stayed started,
  checked Core configuration, restarted Core and verified the loaded companion
  using the exact live request
  `{"type":"step_ca_scep/ipsk/options","network_id":""}`.
  No reinstall or new backup was needed in this final run.

The isolated containers, dedicated Colima profile and its data were removed;
Docker's original default context was restored. The existing default Colima
profile remains stopped. Unrelated workspace files and the WPN signing key
were excluded from the commit.

Live browser rendering in the HA iframe, physical Wi-Fi onboarding, Duo
callbacks/group membership and actual key writes were not exercised by this
deployment verification. The interface evidence is the earlier local audit;
its recorded source hashes remain historical, while the release evidence
records the final modules after lint cleanup.
