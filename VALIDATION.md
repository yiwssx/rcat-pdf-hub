# Validation — zero-cost policy

RCAT PDF Hub 0.4.0 must remain **100% free of paid CI/CD, paid runners, paid hosted build minutes and paid cloud-service requirements**.

## Policy

- GitHub-hosted Actions workflows are not used.
- No paid runner, paid CI provider, paid build credit, billing increase or paid fallback is allowed.
- Validation runs on an institution-owned/local Linux machine using open-source tooling.
- Dependabot may monitor only direct npm dependencies declared in `apps/web/package.json`.
- Dependabot is configured to generate patch updates only; minor and major version-update PRs are ignored at source.
- Dependabot must not update pip, Docker images, GitHub Actions, lockfiles or transitive dependencies.
- A dependency change is eligible only when exactly one existing direct dependency changes from exact `x.y.z` to a higher patch in the same major/minor.
- `package-lock.json` is intentionally not committed by dependency automation; validation uses `npm install --package-lock=false` and must leave `package.json` unchanged.
- Python, Node and Compose service images are pinned to explicit release baselines. Infrastructure image upgrades are manual developer changes, never automatic dependency updates.
- S3 mode requires an explicit self-hosted `PDFHUB_S3_ENDPOINT_URL`; the application refuses implicit commercial-cloud fallback.
- Phase 4 requires a dedicated signed-download secret and the durable webhook dispatcher service.
- Warnings, deprecations and errors are failures.
- API, Web Console and documentation release metadata must all report 0.4.0 / Phase 4.

## Local validation commands

Run on an Internet-connected Linux host with **Python 3.12**, **Node 24/npm**, Docker Engine and Docker Compose plugin:

```bash
make validate-policy
make validate-backend
make validate-frontend
make validate-compose
make validate-runtime
```

Or run everything:

```bash
make validate-free
```

`make validate-free` first runs `scripts/validate-release-policy.py`, which verifies zero-cost/dependency rules, Phase 4 components and frozen runtime image baselines, then runs backend, frontend, Compose and runtime acceptance.

Runtime validation uses an isolated Compose project name (`pdfhub-validation-<pid>`) so it does not tear down or reuse volumes from the production `pdf-hub` project. It also verifies that the dedicated `webhook` dispatcher is running.

For a direct dependency PR/branch:

```bash
BASE_REF=origin/main make validate-dependency
```

The dependency gate verifies the diff before installing anything, then performs warning-free install, TypeScript typecheck and Next.js production build. It refuses minor/major updates, added/removed dependency names, multiple dependency changes, any non-`package.json` file change, or any package metadata/script change.

## Automatic zero-cost local CI

The repository includes a polling executor that runs on institution-owned Linux hardware. It does not use GitHub-hosted runners.

Prerequisites:

- Linux with systemd user services
- Git
- Python **3.12**
- Node **24** + npm
- Docker Engine + Docker Compose plugin
- `flock` (util-linux)
- `curl`
- GitHub CLI (`gh`) authenticated with repository read/status/merge access for PR status reporting and Dependabot merge

Install from the repository clone:

```bash
make install-local-ci
make local-ci-status
```

The systemd user timer runs approximately every five minutes. Each cycle:

1. fetches `origin/main`
2. if `main` has changed, creates a detached Git worktree and runs `make validate-free`
3. records the last fully validated main SHA only after all gates pass
4. checks open non-Dependabot PRs based on the current `main`
5. runs full `make validate-free` for at most one new/changed normal PR per cycle
6. posts `local-ci/validate-free` commit status (`pending`, `success`, `failure` or `error`) back to GitHub
7. **never auto-merges normal PRs**; the status is an acceptance signal for human/developer merge decisions
8. checks open Dependabot PRs
9. accepts only Dependabot-authored PRs based on the current `main` SHA that change exactly `apps/web/package.json`
10. runs `validate-direct-dependency.sh`
11. rechecks both main/head SHA after validation
12. squash-merges only a valid forward patch update that passed the warning-free frontend gate
13. merges at most one dependency PR per cycle so the next PR must be validated against the newly updated main

Successful normal-PR validations are cached by base/head SHA. Failed PRs are retried on a later cycle, allowing transient network/tooling failures to recover without accepting a bad change.

Local state and logs are stored under `.local-ci/` and are ignored by Git.

View logs:

```bash
journalctl --user -u rcat-pdf-hub-local-ci.service
```

Uninstall:

```bash
make uninstall-local-ci
```

A normal user service runs while that user has a systemd user manager. On a dedicated always-on machine, the administrator can enable user lingering once if needed; this is an operating-system setting and does not require any paid service.

## Application baseline

The Phase 4 application baseline extends the completed Phase 3 production foundation with Image ↔ PDF conversion, signed short-lived downloads and durable webhook retry/dead-letter handling. Validation covers backend tests, fresh/adopted Alembic migration checks, frontend typecheck/production build, Compose validation and full runtime acceptance. The zero-cost CI architecture does not depend on hosted runner minutes.

Release consistency checks are part of `make validate-policy` / `make validate-free`:

- Web Console version = `0.4.0`
- FastAPI version = `0.4.0`
- README status = Phase 4 complete
- `PHASE4.md` completion baseline present
- Pillow image-conversion dependency pinned explicitly
- Phase 4 migration and regression tests present
- signed-download secret wired into Compose
- durable webhook dispatcher wired into Compose
- no GitHub-hosted workflow files
- Dependabot = npm direct only + patch PR generation only
- no tracked `package-lock.json`
- Python/Node base images pinned to exact release baselines
- Compose runtime images pinned to explicit release tags
- no default/recommended paid cloud providers in user-facing configuration/docs
- explicit self-hosted S3 endpoint guard present
- local main/PR/Dependabot CI scripts present

## Production validation

Before production deployment:

1. Run `make secrets`, populate `.env`, then `make config`.
2. Run `make validate-free` on an Internet-connected validation/deployment host.
3. Run `make up`.
4. Confirm `http://SERVER:8080/healthz` and `/readyz`.
5. Exercise upload → preview → PDF operation → job poll → download.
6. Exercise multiple images → PDF and PDF → images ZIP.
7. Issue a short-lived signed download URL; verify a valid URL downloads and a tampered/expired token is rejected.
8. If using webhooks, configure a narrow `PDFHUB_WEBHOOK_ALLOWED_HOSTS`, verify HMAC signatures, simulate an unavailable receiver, confirm retry → `dead`, then replay from Admin.
9. If using S3 mode, verify the configured self-hosted endpoint and bucket.
10. If using ClamAV, confirm fail-closed behavior with a safe EICAR acceptance test in a controlled environment.
11. Use TLS before public Internet exposure and set `PDFHUB_SESSION_COOKIE_SECURE=true`.
12. Back up PostgreSQL and storage together.

No paid cloud service is required for any validation or deployment step.
