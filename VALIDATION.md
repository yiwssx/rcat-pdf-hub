# Validation — zero-cost policy

RCAT PDF Hub 0.3.0 must remain **100% free of paid CI/CD, paid runners, paid hosted build minutes and paid cloud-service requirements**.

## Policy

- GitHub-hosted Actions workflows are not used.
- No paid runner, paid CI provider, paid build credit, billing increase or paid fallback is allowed.
- Validation runs on an institution-owned/local Linux machine using open-source tooling.
- Dependabot may monitor only direct npm dependencies declared in `apps/web/package.json`.
- Dependabot must not update pip, Docker images, GitHub Actions, lockfiles or transitive dependencies.
- A dependency change is eligible only when exactly one existing direct dependency changes from exact `x.y.z` to a higher patch in the same major/minor.
- `package-lock.json` is intentionally not committed by dependency automation; validation uses `npm install --package-lock=false` and must leave `package.json` unchanged.
- S3 mode requires an explicit self-hosted `PDFHUB_S3_ENDPOINT_URL`; the application refuses implicit commercial-cloud fallback.
- Warnings, deprecations and errors are failures.
- API, Web Console and documentation release metadata must all report 0.3.0 / Phase 3.

## Local validation commands

Run on an Internet-connected Linux host with Python, Node/npm and Docker Engine + Compose plugin:

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

Runtime validation uses an isolated Compose project name (`pdfhub-validation-<pid>`) so it does not tear down or reuse volumes from the production `pdf-hub` project.

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
- Python 3
- Node/npm
- Docker Engine + Docker Compose plugin
- `flock` (util-linux)
- GitHub CLI (`gh`) authenticated with permission to read and merge this repository if automatic Dependabot merge is desired

Install from the repository clone:

```bash
make install-local-ci
make local-ci-status
```

The systemd user timer runs approximately every five minutes. Each cycle:

1. fetches `origin/main`
2. if `main` has changed, creates a detached Git worktree and runs `make validate-free`
3. records the last fully validated main SHA only after all gates pass
4. checks open Dependabot PRs
5. accepts only Dependabot-authored PRs based on the current `main` SHA that change exactly `apps/web/package.json`
6. runs `validate-direct-dependency.sh`
7. rechecks both main/head SHA after validation
8. squash-merges only a valid forward patch update that passed the warning-free frontend gate
9. merges at most one dependency PR per cycle so the next PR must be validated against the newly updated main

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

The Phase 3 application baseline previously passed backend tests, fresh/adopted Alembic migration checks, frontend production build, Compose validation and full runtime acceptance including SeaweedFS and ClamAV. The zero-cost CI architecture does not depend on hosted runner minutes.

Release consistency checks are now part of `make validate-policy`:

- Web Console version = `0.3.0`
- FastAPI version = `0.3.0`
- README status = Phase 3 complete
- no GitHub-hosted workflow files
- direct npm Dependabot only
- no tracked `package-lock.json`
- no default/recommended paid cloud providers in user-facing configuration/docs
- explicit self-hosted S3 endpoint guard present
- local CI scripts present

## Production validation

Before production deployment:

1. Run `make secrets`, populate `.env`, then `make config`.
2. Run `make validate-free` on an Internet-connected validation/deployment host.
3. Run `make up`.
4. Confirm `http://SERVER:8080/healthz` and `/readyz`.
5. Exercise upload → preview → PDF operation → job poll → download.
6. If using S3 mode, verify the configured self-hosted endpoint and bucket.
7. If using ClamAV, confirm fail-closed behavior with a safe EICAR acceptance test in a controlled environment.
8. If using webhooks, configure a narrow `PDFHUB_WEBHOOK_ALLOWED_HOSTS` and verify HMAC signatures.
9. Use TLS before public Internet exposure.
10. Back up PostgreSQL and storage together.

No paid cloud service is required for any validation or deployment step.
