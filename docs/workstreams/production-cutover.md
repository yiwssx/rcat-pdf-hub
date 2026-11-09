# RCAT PDF HUB — guarded production cutover (code ready, host not yet verified)

Owner decision: no operator-run test suites, no unsafe automatic production
writes, keep Google OIDC institutional access, backups, and DR mandatory.

## Single command for the authorized Ubuntu deployment account

The normal deployment entrypoint has **no manually supplied environment
variables, SHA, backup path, DR run ID or separate operator-run test suite**:

```bash
cd /opt/rcat-pdf-hub && git pull --ff-only origin main && python3 scripts/one-command-release.py
```

**Host Caddy customization:** On the first run, if the only tracked local
edit is `ops/caddy/Caddyfile`, the entrypoint preserves its exact bytes at
`.local-config/caddy/Caddyfile` (ignored by Git), appends only
`PDFHUB_CADDYFILE_PATH=./.local-config/caddy/Caddyfile` to the existing
`.env`, and atomically swaps the tracked file back to Git's version using a
new inode. The existing Caddy container's single-file bind mount retains
the original inode, so the active proxy configuration is not replaced
during this migration. The next approved Compose cutover uses the saved
site file. Any other tracked edit, staged Caddy change, conflicting site
file or conflicting environment setting fails closed. Never use
`git reset --hard` to discard the institution's Caddy configuration.
Run as the existing account that owns the repository and Docker access,
**not** with blind `sudo`. The code update by `git pull --ff-only` does not
restart services.

The orchestrator discovers the **actually running** production Compose mode
from Docker API container labels, verifies protected main SHA, read-only
institutional OIDC/HTTPS/ClamAV settings, and successful GitHub CI.
It then requires repository variable `RCAT_DR_RUNNER_READY=true` and an
online approved `rcat-dr-isolated` runner.

Only after these conditions does it create and verify a fresh live backup
(no automated pruning), dispatch the official isolated DR workflow, find
the run ID on GitHub and require a real restore PASS. The existing guarded
`production-cutover.sh` independently checks the exact SHA, official DR
run, and the **same backup's SHA256SUMS** before release scans, migrations,
application update, and health/readiness checks.

**If the runner is missing, cannot access the read-only snapshot, or any
gate fails, the command stops; it never invents evidence or deploys by
bypassing a failed test.** This command cannot provision the DR runner or
Google Workspace credentials just by being run on the Production host.

On a migration/readiness failure, the retained pre-release snapshot is
available for incident-controlled recovery with the previous app release;
do not blindly roll back application binaries after database migrations.

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

## Advanced manual release-agent sequence (normally unnecessary)

On the authorized *production* deployment host, after preparing the above:

```bash
cd /opt/rcat-pdf-hub
# Only after creating and snapshotting the current live backup:
git pull --ff-only origin main
export PDFHUB_COMPOSE_MODE=prod  # or prod-nas to match the live installation
export BACKUP=/absolute/path/to/verified-backup
export DR_RUN_ID=<approved-GitHub-isolated-DR-run-number>

# Optional diagnostic only; deploy runs every gate itself:
# bash scripts/production-cutover.sh check

export RCAT_DEPLOY_SHA="$(git rev-parse HEAD)"
RCAT_DEPLOY_CONFIRM=YES bash scripts/production-cutover.sh deploy
```

The check mode does **not** change Production. It checks same-SHA GitHub CI,
read-only Compose policy, backup integrity, and genuine GitHub run provenance,
same SHA, same snapshot checksum digest, and a DR PASS within 72 hours.
Any mismatch is a hard block. It never prints `.env` or raw backup contents.

The deploy mode needs an explicit exact SHA approval. It performs mandatory
release-only vulnerability scans, builds images *while old containers run*,
stops writer surfaces before running Alembic migrations, reconciles only the
app/worker/converter/Caddy surfaces without stopping PostgreSQL/Valkey or deleting
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
