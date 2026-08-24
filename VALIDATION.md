# Validation — zero-cost policy

RCAT PDF Hub must remain **100% free of paid CI/CD, paid runners and paid hosted build minutes**.

## Policy

- GitHub-hosted Actions workflows are not used.
- No paid runner, paid CI provider, paid build credit, billing increase or paid fallback is allowed.
- Validation runs on an institution-owned/local Linux machine using open-source tooling.
- Dependabot may monitor only direct npm dependencies declared in `apps/web/package.json`.
- Dependabot must not update pip, Docker images, GitHub Actions, lockfiles or transitive dependencies.
- A dependency change is eligible only when exactly one existing direct dependency changes from exact `x.y.z` to a higher patch in the same major/minor.
- `package-lock.json` is intentionally not committed by the dependency-update workflow; validation uses `npm install --package-lock=false` and must leave `package.json` unchanged.
- Warnings, deprecations and errors are failures.

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

For a direct dependency PR/branch:

```bash
BASE_REF=origin/main make validate-dependency
```

The dependency gate verifies the diff before installing anything, then performs warning-free install, TypeScript typecheck and Next.js production build. It refuses minor/major updates, added/removed dependency names, multiple dependency changes, any non-`package.json` file change, or any package metadata/script change.

## Application baseline

The Phase 3 application baseline previously passed backend tests, fresh/adopted Alembic migration checks, frontend production build, Compose validation and full runtime acceptance including S3/SeaweedFS and ClamAV. The zero-cost CI change does not alter application source code or dependency versions.

## Production validation

Before production deployment:

1. Run `make secrets`, populate `.env`, then `make config`.
2. Run `make validate-free` on the deployment host.
3. Run `make up`.
4. Confirm `http://SERVER:8080/healthz` and `/readyz`.
5. Exercise upload → preview → PDF operation → job poll → download.
6. If using webhooks, configure a narrow `PDFHUB_WEBHOOK_ALLOWED_HOSTS` and verify HMAC signatures.
7. Use TLS before public Internet exposure.

No paid cloud service is required for any validation step.
