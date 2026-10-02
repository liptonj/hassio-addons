# Release readiness — 2026-10-02

Ready to commit and push the two release candidates, then perform the first
installation and configuration. Live provider/device acceptance remains pending.
No commit, push, release publication or deployment was performed.

## Candidate and verification

- Step CA add-on **0.30.2.46**, bundled companion **1.5.0**. Origin master is
  still the source for 0.30.2.44, so this candidate has a new add-on version.
- **140 portal tests passed**, including 14 new guidance/readiness regressions.
  Corrected a local variable that shadowed the guidance module during onboarding
  POSTs, preserved the hardware-address error contract and fixed multiword help search.
- **30 real MariaDB 10.11 checks passed** on disposable fresh and previous Step CA
  schemas. New inventory coverage seeded 303 matching legacy/account-device rows,
  traversed all pages without duplicates, found a record beyond 250 and checked
  literal search terms, sorting and bounds. No WPN database migration was used.
- **8 certificate/startup checks passed**: MariaDB-backed startup, real issuance
  with a decryptable PKCS#12 chain, renewal, revocation, published CRL, SCEP
  capabilities, bundled companion installation and healthy restart retaining the root.
- **aarch64, amd64 and armv7 images built and ran**. Packaged portal modules match
  current source hashes; companion Python parses and pinned Duo packages import.
- Meraki feature branch now starts at current beta **3.2.9-beta.1**. Four overlaps
  were resolved with both upstream behavior and SDK/secret protections retained.
  SDK stays pinned to **4.5.0b4**. Two new tests cover secret redaction when retries
  are exhausted. Full quality checks pass: lint, format, Bandit, mypy and
  **1,172 tests / 7 existing skips**. Unfiltered pytest passes
  **1,172 tests / 8 existing skips**.

Exact source hashes, image IDs, checks, log hashes and cleanup are recorded in
`2026-10-02-release-readiness.evidence.json`. Earlier audit evidence describes
earlier source revisions and is retained as history.

## Release sequence

1. Commit the Meraki changes on `codex/meraki-sdk-secrets`, push and review a PR
   targeting `beta`. Its merge workflow assigns the next beta version.
2. Publish Step CA 0.30.2.46 from this add-on repository. There is no image
   reference in its config and no Step CA container-publishing job in the current
   build workflow; Home Assistant Supervisor builds the add-on from source.
3. Install/start MariaDB and Step CA, install/discover the bundled companion and
   restart Home Assistant as needed. Open Setup and checks, then configure the
   resident network/policy, QR credentials and optional Duo group/verification.
4. Verify guest access, setup captive onboarding, rejected private MAC addresses,
   current/other-device QR onboarding, Duo allowed/denied membership and callbacks,
   public HTTPS and device certificate enrollment on the installed system.

Meraki's repository has `ENABLE_HACS_DEPLOY=true` and the HA secret names present.
Publishing its beta can automatically install the integration and restart Home
Assistant. The secret values and destination were not inspected or used; a
working-tree push alone does not invoke that release workflow.

## Commit scope

- Add-on: the authorized `step-ca/` source, configuration, docs, tests and audit
  records. Review new files explicitly rather than staging the repository wholesale.
- Meraki: the 20 modified tracked files enumerated by the evidence record.
- Other workspace files are outside this release candidate.

Production acceptance, physical-device accessibility and provider integration
cannot be inferred from disposable fixtures. The previous critique scores are
historical; this verification does not claim a new design score.
