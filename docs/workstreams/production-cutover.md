# RCAT PDF HUB — guarded production cutover (code ready, host not yet verified)

Owner decision: no operator-run test suites, no unsafe automatic production
writes, keep Google OIDC institutional access, backups, and DR mandatory.

## What this replaces

A release must **not** redo `make validate-free` on the Ubuntu host. GitHub
`ci/required` checks the exact protected main SHA. Only release-specific
source/image supply-chain scanning, a verified backup and **one real, separate
rootless DR restore** are additional acceptance evidence.

The repository already contains:
- `scripts/release1-host-preflight.py`: read-only Compose JSON policy gate;
  requires RCAT-only Google OIDC, HTTPS, secure cookies, disabled auto-login,
  locked-down workers, and ClamAV fail-closed. It prints only field names, not
  secret values.
- `scripts/verify-backup.sh`: verifies the real PostgreSQL dump, storage
  archive and checksums.
- `.github/workflows/isolated-dr.yml`: **inert** until the dedicated runner
  and repository variable `RCAT_DR_RUNNER_READY=true` exist.
- `scripts/production-cutover.sh`: read-only `check` and explicit `deploy`.

## Prerequisites — required before production modification

1. Authorized Ubuntu host deployment account; existing production `.env`;
   dedicated rootless DR runner on another isolated daemon. Never run the
   release script through a public PR job, on untrusted code or with a production
   Docker socket exposed to GitHub-hosted workers.
2. Create a **fresh coherent backup from the still-running old deployment**
   using its original Compose mode. This must happen **before** updating host
   source and before any migration. Verify it with the existing backup tool.
3. Make that exact snapshot available to the private DR runner as a read-only
   mount. Run the protected `isolated-dr.yml` workflow manually. It must
   finish `success` and upload its sanitized `dr-evidence.json` artifact
   proving a restore with a matching SHA256SUMS digest.
4. Fetch the reviewed GitHub main commit onto the release host via normal
   fast-forward. Confirm no tracked local source modifications and keep the
   original backup untouched. Never overwrite `.env` or public DNS.
5. Provide `BACKUP=/absolute/path/to/that-snapshot` and `DR_RUN_ID` equal
   to the **successful GitHub Actions run ID**, not an arbitrary local report.

## Unattended release agent sequence (no user-run test suite)

On the authorized *production* deployment host, after preparing the above:

```bash
cd /opt/rcat-pdf-hub
# Only after creating and snapshotting the current live backup:
git pull --ff-only origin main
export PDFHUB_COMPOSE_MODE=prod  # or prod-nas to match the live installation
export BACKUP=/absolute/path/to/verified-backup
export DR_RUN_ID=<approved-GitHub-isolated-DR-run-number>

bash scripts/production-cutover.sh check

export RCAT_DEPLOY_SHA="$(git rev-parse HEAD)"
RCAT_DEPLOY_CONFIRM=YES bash scripts/production-cutover.sh deploy
```

The check mode does **not** change Production. It checks same-SHA GitHub CI,
read-only Compose policy, backup integrity, and genuine GitHub run provenance,
same SHA, same snapshot checksum digest, and a DR PASS within 72 hours.
Any mismatch is a hard block. It never prints `.env` or raw backup contents.

The deploy mode needs an explicit exact SHA approval. It performs mandatory
release-only vulnerability scans, builds images *while old containers run*,
stops writer surfaces before running Alembic migrations, recreates only the
app/worker/converter surfaces without stopping PostgreSQL/Valkey or deleting
volumes, then requires actual /healthz + /readyz success. It does **not**
invoke `docker compose down -v`, reset DNS, alter backup timers, or rerun
`make validate-free`.

## Recovery and rollback boundary

Source/binary rollback alone is **not** safe if a schema migration was
applied. On failure, preserve the untouched pre-release snapshot, original
git revision and logs. A recovery operator must restore the snapshot using
the *matching prior release source* and `scripts/restore.sh` in an
incident-controlled window. Do not attempt an unverified automatic
PostgreSQL downgrade, force-push or blind `docker volume rm`.

**No deployment or DR PASS is claimed until the Ubuntu host and the separate
private runner provide direct evidence.** This repository-only handoff is
not a substitute for host access or Production authorization.
