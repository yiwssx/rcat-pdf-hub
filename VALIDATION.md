# Validation — Phase 5 zero-cost production gate

RCAT PDF Hub 0.5.0 must remain **100% free of paid CI/CD, paid runners, paid hosted build minutes and paid cloud-service requirements**.

## Policy

- Standard application PRs use full `make validate-free` on institution-owned/local Linux hardware.
- GitHub-hosted Actions are limited to two guarded Dependabot workflows in this public repository: one npm patch lane and one Python security-validation lane.
- The narrow Dependabot npm auto-merge lane requires `apps/web/package.json` and `apps/web/package-lock.json` to move together for a bot-only direct forward patch update, then revalidates the exact base/head before squash merge.
- A Dependabot Python security PR that changes exactly one existing exact pin in `apps/api/requirements.txt` is validated by full `make validate-free` on a read-only hosted runner. The workflow materializes only the verified requirements manifest onto trusted base code and never auto-merges.
- Any other nonstandard/security dependency PR remains owned by the local full-validation lane and is never auto-merged.
- Direct npm dependency patches must pass typecheck, production build and Playwright browser smoke before merge.
- `apps/web/package-lock.json` is committed as the reproducible frontend dependency graph; CI, Docker builds, local validation and dependency validation use `npm ci` and verify the manifest/lockfile are not mutated.
- Python/Node/container images and security baselines are explicit. Phase 5 uses the reviewed Next.js `16.3.x` security line and the reviewed Pillow 12.x floor `>=12.3.0,<13.0.0`.
- S3 mode requires an explicit self-hosted `PDFHUB_S3_ENDPOINT_URL`.
- Optional management services bind to loopback by default.
- Browser regression, operations scripts and production Compose flow are mandatory gates.
- Warnings and deprecations are treated as validation failures.

## Required local host

- Linux
- Python **3.12**
- Node **24** + npm/npx
- Docker Engine + Docker Compose plugin
- Playwright-compatible Chromium runtime libraries
- Git, curl, flock
- GitHub CLI (`gh`) authenticated to the repository for local CI status reporting

Fresh Debian/Ubuntu Playwright bootstrap, after installing frontend dependencies:

```bash
cd apps/web
npm ci --no-audit --no-fund
npx playwright install-deps chromium
```

The project installs Chromium headless shell automatically during browser validation. It can also be preinstalled with:

```bash
make install-e2e-browser
```

## Validation commands

```bash
make validate-policy
make validate-ops
make validate-backend
make validate-frontend
make validate-e2e
make validate-compose
make validate-runtime
```

All gates:

```bash
make validate-free
```

### What each gate proves

`validate-policy` checks release metadata, frozen/security dependency baselines, zero-cost policy, Phase 5 components, management binding, monitoring rules and CI architecture.

`validate-ops` syntax-checks backup/restore/DR/local-CI scripts and compiles Python operator tooling.

`validate-backend` creates a clean Python 3.12 environment, installs exact requirements, treats warnings as errors, runs pytest and validates fresh/adopted Alembic migration paths.

`validate-frontend` performs a warning-free `npm ci` from the committed lockfile, TypeScript typecheck and production Next.js build while ensuring package metadata and the lockfile are not mutated.

`validate-e2e` runs Playwright Chromium against the UI with mocked API responses. Protected mocks require the correct `X-API-Key`, so authentication propagation regressions cannot produce a false green result.

`validate-compose` validates default, all-profile and NAS Compose configurations.

`validate-runtime` uses an isolated `pdfhub-validation-<pid>` Compose project, builds production containers, checks `/healthz` and `/readyz`, runs API tests in the container, verifies the webhook dispatcher, then runs a real browser flow through **Caddy → production Next.js → real FastAPI → RQ worker/storage**: API-key login → upload → image-to-PDF job → download → preview.

## Direct npm dependency validation

```bash
BASE_REF=origin/main make validate-dependency
```

The gate rejects:

- minor/major version changes
- added/removed dependency names
- multiple dependency changes
- changes outside `apps/web/package.json` and `apps/web/package-lock.json`
- package script/metadata drift
- non-forward patches

An eligible patch must keep the lockfile root manifest synchronized with `package.json` and still pass `npm ci`, typecheck, production build and browser smoke.

## Python security dependency validation

The hosted Python security lane is intentionally narrower than a normal full PR workflow. Before any PR-supplied dependency is installed, it checks that:

- the author is `dependabot[bot]`
- the base branch is `main`
- the only changed file is `apps/api/requirements.txt`
- exactly one existing `name[extras]==x.y.z` pin advances
- no dependency name or extras set changes
- the raw manifest diff contains only the verified removed and added pin

The workflow then checks out trusted base code, materializes only the verified `requirements.txt`, sets up Python 3.12 and Node 24, and runs `make validate-free`. It has `contents: read` only and contains no merge job.

## Local CI

Install the systemd user executor:

```bash
make install-local-ci
make local-ci-status
make local-ci-doctor
```

The installer requires a reachable Docker daemon plus authenticated `gh` access. This is intentional: if GitHub status reporting is unavailable, PR enforcement must fail visibly instead of silently validating only `main`.

Each cycle:

1. fetches `origin/main`
2. runs `make validate-free` when main changes
3. records the exact fully validated main SHA on success, or records the failing main SHA on failure
4. continues PR routing even when current `main` fails, so a corrective or security PR cannot be starved behind a broken baseline
5. checks open non-draft PRs against current main
6. marks stale PR heads with `local-ci/validate-free = error`
7. routes normal/nonstandard PRs through full validation
8. posts `local-ci/validate-free` pending/success/failure/error
9. routes an eligible Dependabot direct npm patch to the dedicated local dependency lane only when current `main` is fully passing
10. posts `local-ci/dependency` pending/success/failure/error
11. rechecks main/head SHA before accepting a result
12. auto-merges only a validated eligible Dependabot forward npm patch
13. writes the most recent cycle timestamp/SHA locally

Normal PRs are **not auto-merged**. The local dependency auto-merge lane is suppressed while the current main SHA fails full validation.

Diagnostics:

```bash
make local-ci-doctor
journalctl --user -u rcat-pdf-hub-local-ci.service
```

`local-ci-doctor` checks tool versions, Docker/Compose, GitHub authentication/repository access, timer state, latest validated main and local-CI commit-status presence on current PR heads.

## Phase 5 operational validation

### Backup integrity

```bash
make backup
BACKUP=./backups/<timestamp> make backup-verify
```

A backup includes PostgreSQL custom-format dump plus local/NAS data archive or self-hosted S3 object archive, `manifest.env` and `SHA256SUMS`.

### Restore

Restore is destructive and requires explicit acknowledgement:

```bash
PDFHUB_RESTORE_CONFIRM=YES \
BACKUP=./backups/<timestamp> \
make restore
```

The restore gate verifies checksums before replacement, clears only Valkey DB 0 ephemeral RQ state, runs migrations and waits for health/readiness.

### Disaster recovery drill

```bash
BACKUP=./backups/<timestamp> make dr-drill
```

The drill restores into a disposable isolated Compose project, validates health/readiness, executes a small load smoke and tears the environment down.

### Scheduled backup

```bash
make install-backup
make backup-status
```

Default schedule is daily at 02:30 with 14-day retention. Operators can set `PDFHUB_BACKUP_ON_CALENDAR`, `PDFHUB_BACKUP_ROOT` and `PDFHUB_BACKUP_RETENTION_DAYS` before installation.

### Monitoring

Prometheus loads `ops/prometheus/alerts.yml`. Rules cover:

- API scrape unavailable
- elevated 5xx ratio
- high p95 latency
- queue backlog
- repeated job failures

Prometheus rule routing/notification delivery is intentionally infrastructure-controlled; connect it to the institution's chosen internal alert receiver without introducing a commercial-service requirement.

### Load smoke

```bash
URL=http://localhost:8080 \
REQUESTS=100 CONCURRENCY=10 \
MAX_ERROR_RATE=0.01 MAX_P95_MS=1500 \
make load-smoke
```

The standard-library test reports throughput, error rate and mean/p50/p95/p99 latency and fails when configured thresholds are exceeded.

## Release readiness

Code-only gate:

```bash
PDFHUB_RELEASE_MODE=code make release-readiness
```

Production gate:

```bash
BACKUP=./backups/<timestamp> \
URL=https://pdf.example.org \
make release-readiness
```

Production mode runs full repository validation, local-CI doctor, backup verification, isolated DR drill and target load smoke. `PDFHUB_RELEASE_SKIP_DR=true` exists only for an explicit operator exception; a normal production release should not skip the DR drill.

## Release 0.5.0 acceptance baseline

- Phase 5A frontend/auth/management hardening implemented
- Phase 5B local-CI/status/dependency security hardening implemented
- Phase 5C backup/restore/DR/alerts/load/release tooling implemented
- Web Console and FastAPI report `0.5.0`
- Next.js remains on the reviewed `16.3.x` security line
- prior Phase 3/4 feature baselines retained
- GitHub-hosted execution is restricted to the two guarded Dependabot workflows described above
- no paid infrastructure requirement

No paid cloud service is required for any validation, recovery or deployment step.
