# Validation record â€” 2026-11-01

## Completed locally

- Existing source and ZIP found; all 68 selected baseline code/config/test files matched by SHA-256.
- Fresh independent PostgreSQL 18.6 QA cluster, dedicated api_sentinel_review database and non-superuser application role. No existing user database was used, copied, seeded or upgraded.
- Alembic upgrade through the new GET/HEAD restriction succeeded; `alembic check` reported no new upgrade operations.
- 106 backend tests passed (original 96 plus 10 new method-boundary cases). HTTP test targets use fixtures, MockTransport, mocked DNS/socket backends and controlled in-process servers. No live third-party endpoint was probed.
- 24 frontend tests passed. Production TypeScript/Vite build passed with the installed Node 24.19.0; CI targets Node 22 and has not run. Python runtime: 3.12.14.
- Ruff check passed after import ordering fixes; added Linux helpers reviewed/linted, not executed on Linux.
- npm ci used the lockfile, with lifecycle scripts disabled; frontend build still passed. npm audit: 0 reported advisories.
- PyPI JSON advisory metadata for all 35 pinned Python requirements: no listed advisories; all offered a Linux or platform-independent wheel. This is not an independent complete vulnerability audit or proof each Python/CPU combination installs.
- Browser reviewed with the candidate's fictional paused records: dark dashboard and light report captured without private profile/operational data.
- Publication file inventory and pattern scan reviewed; no active credentials found in included source. The test string `https://u:p@example.com` is an intentional rejection fixture, not an active secret.

## CI preparation, not a remote result

Workflow uses Ubuntu 24.04, Python 3.12, Node 22 and PostgreSQL 18, disposable CI-only credentials, monitoring disabled, explicit test database, migrations, Ruff, backend/frontend tests, schema check, frontend build and npm audit. Job timeout 15 minutes, contents:read and checkout persist-credentials:false. Official v7 action refs were resolved via GitHub API and pinned to commit SHAs; see ci.yml. Dependency images/packages remain versioned by tag/version, not container digest/package hashes.

No candidate remote, push, GitHub Actions run, badge, published release or Alignerr approval is claimed. Workflow syntax review and local checks do not prove CI passed. Docker/Compose and Linux/WSL2 were not executed. WSL was absent; installation would require owner-controlled administrator steps and potentially restart.

## Known remaining limits

Local app, no authentication/multiuser authorization, no email/webhook delivery, no automatic retention. Reference-art permissions, Alignerr eligibility require confirmation. The owner approved public wasatnight/api-sentinel and MIT licensing on 2026-11-01. The private HTTPCore adapter remains a dependency-coupling risk. An independent security/legal audit has not been performed.
