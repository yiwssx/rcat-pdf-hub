# Validation — Phase 5 zero-cost production gate

RCAT PDF Hub 0.5.0 must remain **100% free of paid CI/CD, paid runners, paid hosted build minutes and paid cloud-service requirements**.

## Policy

- No GitHub-hosted Actions workflow is used.
- Validation runs on institution-owned/local Linux hardware.
- Normal PRs and nonstandard/security dependency PRs use full `make validate-free` and are never auto-merged by the full-validation lane.
- The narrow Dependabot auto-merge lane accepts only bot-only direct npm forward patch updates that change exactly `apps/web/package.json`.
- Direct dependency patches must pass typecheck, production build and Playwright browser smoke before merge.
- `package-lock.json` remains untracked; validation uses `npm install --package-lock=false` and confirms package metadata is not mutated.
- Python/Node/container images and security baselines are explicit. Phase 5 uses Next.js `16.3.3` and the reviewed Pillow 12.x floor `>=12.3.0,<13.0.0`.
- S3 mode requires an explicit self-hosted `PDFHUB_S3_ENDPOINT_URL`.
- Optional management services bind to loopback by default.
- Browser regression, operations scripts and production Compose flow are mandatory gates.
- Warnings and deprecations are treated as validation failures.

## Required host

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
npm install --package-lock=false --no-audit --no-fund
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

`validate-frontend` performs warning-free npm install, TypeScript typecheck and production Next.js build while ensuring no lockfile/package mutation.

`validate-e2e` runs Playwright Chromium against the UI with mocked API responses. Protected mocks require the correct `X-API-Key`, so authentication propagation regressions cannot produce a false green result.

`validate-compose` validates default, all-profile and NAS Compose configurations.

`validate-runtime` uses an isolated `pdfhub-validation-<pid>` Compose project, builds production containers, checks `/healthz` and `/readyz`, runs API tests in the container, verifies the webhook dispatcher, then runs a real browser flow through **Caddy → production Next.js → real FastAPI → RQ worker/storage**: API-key login → upload → image-to-PDF job → download → preview.

## Direct dependency validation

```bash
BASE_REF=origin/main make validate-dependency
```

The gate rejects:

- minor/major version changes
- added/removed dependency names
- multiple dependency changes
- non-`apps/web/package.json` changes
- package script/metadata drift
- non-forward patches

An eligible patch must still pass install, typecheck, production build and browser smoke.

## Local CI

Install the systemd user executor:

```bash
make install-local-ci
make local-ci-status
make local-ci-doctor
```

The installer now requires a reachable Docker daemon plus authenticated `gh` access. This is intentional: if GitHub status reporting is unavailable, PR enforcement must fail visibly instead of silently validating only `main`.

Each cycle:

1. fetches `origin/main`
2. runs `make validate-free` when main changes
3. records the exact fully validated main SHA
4. checks open non-draft PRs against current main
5. marks stale PR heads with `local-ci/validate-free = error`
6. routes normal/nonstandard PRs through full validation
7. posts `local-ci/validate-free` pending/success/failure/error
8. routes an eligible Dependabot direct npm patch to the dedicated dependency lane
9. posts `local-ci/dependency` pending/success/failure/error
10. rechecks main/head SHA before accepting a result
11. auto-merges only a validated eligible Dependabot forward patch
12. writes the most recent cycle timestamp/SHA locally

Normal PRs are **not auto-merged**.

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
- Next.js security baseline = `16.3.3`
- prior Phase 3/4 feature baselines retained
- no GitHub-hosted workflow
- no paid infrastructure requirement

No paid cloud service is required for any validation, recovery or deployment step.
