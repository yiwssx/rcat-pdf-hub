# Validation — zero-cost policy

RCAT PDF Hub 0.4.1 must remain **100% free of paid CI/CD, paid runners, paid hosted build minutes and paid cloud-service requirements**.

## Policy

- GitHub-hosted Actions workflows are not used.
- No paid runner, paid CI provider, paid build credit, billing increase or paid fallback is allowed.
- Validation runs on an institution-owned/local Linux machine using open-source tooling.
- Dependabot version-update configuration may monitor only direct npm dependencies declared in `apps/web/package.json`.
- Version-update automation generates patch updates only; minor and major version-update PRs are ignored at source.
- The configured version-update lane must not update pip, Docker images, GitHub Actions, lockfiles or transitive dependencies.
- GitHub security-update PRs may still be opened outside that version-update lane. Such PRs must run full `make validate-free` and are **never auto-merged**.
- A dependency change is eligible for automatic merge only when exactly one existing direct npm dependency changes from exact `x.y.z` to a higher patch in the same major/minor and only `apps/web/package.json` changes.
- `package-lock.json` is intentionally not committed by dependency automation; validation uses `npm install --package-lock=false` and must leave `package.json` unchanged.
- Pillow must be exact-pinned. The reviewed Phase 4 maintenance floor is `>=12.3.0,<13.0.0`; crossing to another major requires an explicit developer policy change and full validation.
- Python, Node and Compose service images are pinned to explicit release baselines. Infrastructure image upgrades are manual developer changes, never automatic dependency updates.
- S3 mode requires an explicit self-hosted `PDFHUB_S3_ENDPOINT_URL`; the application refuses implicit commercial-cloud fallback.
- Phase 4 requires a dedicated signed-download secret and the durable webhook dispatcher service.
- Warnings, deprecations and errors are failures.
- API, Web Console and README release metadata must report 0.4.1 / Phase 4 security maintenance; `PHASE4.md` retains 0.4.0 as the completed feature baseline.

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

`make validate-free` calls `scripts/validate-release-policy.py` as the single policy source of truth, then runs backend, frontend, Compose and runtime acceptance. Policy rules are intentionally not duplicated inside the shell script.

Runtime validation uses an isolated Compose project name (`pdfhub-validation-<pid>`) so it does not tear down or reuse volumes from the production `pdf-hub` project. It also verifies that the dedicated `webhook` dispatcher is running.

For a direct npm dependency PR/branch:

```bash
BASE_REF=origin/main make validate-dependency
```

The lightweight dependency gate verifies the diff before installing anything, then performs warning-free install, TypeScript typecheck and Next.js production build. It refuses minor/major updates, added/removed dependency names, multiple dependency changes, any non-`package.json` file change, or package metadata/script changes.

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
- GitHub CLI (`gh`) authenticated with repository read/status/merge access for PR status reporting and the narrow Dependabot npm patch merge lane

Install from the repository clone:

```bash
make install-local-ci
make local-ci-status
```

The systemd user timer runs approximately every five minutes. Each cycle:

1. fetches `origin/main`
2. if `main` has changed, creates a detached Git worktree and runs `make validate-free`
3. records the last fully validated main SHA only after all gates pass
4. checks all open PRs based on the current `main`
5. routes normal PRs and Dependabot PRs outside the direct npm patch lane through full `make validate-free`
6. posts `local-ci/validate-free` commit status (`pending`, `success`, `failure` or `error`) back to GitHub for the full-validation lane
7. **never auto-merges** normal PRs or security-maintenance PRs
8. separately checks Dependabot PRs that change exactly `apps/web/package.json`
9. requires those PRs to be Dependabot-authored and based on the current `main` SHA
10. runs `validate-direct-dependency.sh`
11. rechecks both main/head SHA after validation
12. squash-merges only a valid forward npm patch update that passed the warning-free frontend gate
13. merges at most one auto-eligible dependency PR per cycle so the next PR must be validated against the newly updated main

Successful full-PR validations are cached by base/head SHA. Failed PRs are retried on a later cycle, allowing transient network/tooling failures to recover without accepting a bad change.

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

The Phase 4 feature baseline (0.4.0) extends the completed Phase 3 production foundation with Image ↔ PDF conversion, signed short-lived downloads and durable webhook retry/dead-letter handling. Release 0.4.1 is the security/validation maintenance release for that feature baseline.

Release consistency checks are part of `make validate-policy` / `make validate-free`:

- Web Console version = `0.4.1`
- FastAPI version = `0.4.1`
- README status = `0.4.1 — Phase 4 security maintenance`
- `PHASE4.md` completion baseline present
- Pillow exact pin present and within reviewed secure range `>=12.3.0,<13.0.0`
- Phase 4 migration and regression tests present
- signed-download secret wired into Compose
- durable webhook dispatcher wired into Compose
- no GitHub-hosted workflow files
- Dependabot version-update config = npm direct only + patch PR generation only
- security/nonstandard Dependabot PRs routed to full validation with no auto-merge
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
