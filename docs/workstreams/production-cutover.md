# RCAT PDF HUB — standard production deployment

## One command — authorized Ubuntu host only

```bash
cd /opt/rcat-pdf-hub && git pull --ff-only origin main && python3 scripts/one-command-release.py
```

The operator supplies **no SHA, backup path, DR run ID, repository variable, or
extra passwords**. This is a live Production change (not a dry run); use the
existing authorized `rcat_iot_admin` account, not `sudo` by default.

## The required deployment path

1. Preserve the RCAT host-customized `ops/caddy/Caddyfile` bytes in
   `.local-config/caddy/Caddyfile` with a single `.env` path override. The
   *currently mounted* original Caddyfile remains untouched. Any unexpected
   tracked source change fails closed.
2. Confirm checked-out commit equals protected `origin/main`, an authenticated
   GitHub CLI, and `ci/required` SUCCESS on that **exact** commit.
3. Detect the actually running Compose project/mode from API container labels
   (prod vs prod-nas); validate production Compose and institutional-only
   Google OIDC, HTTPS cookies, restricted origins/roles and ClamAV policy.
   No secrets are printed or replaced.
4. Back up PostgreSQL and existing files from the **running older containers**
   to a new UTC-stamped directory. Avoid pruning earlier backups. Verify SHA256
   manifest, PostgreSQL dump header and storage archive integrity.
5. Invoke `production-cutover.sh deploy` with internally detected commit SHA,
   verified backup directory and explicit `RCAT_DEPLOY_CONFIRM=YES`. It
   independently repeats CI, RCAT policy and backup verification. Optional
   vulnerability scans can be enabled with `PDFHUB_RELEASE_EXTRA_SCANS=true`;
   regular GitHub dependency/security checks have already passed.
6. Prebuild reviewed application images; explicitly start ONLY the
   profile-guarded `clamav` service required by the RCAT Production
   fail-closed antivirus policy, and wait for the API's real ClamAV PING to
   respond before planned application downtime. If scanner startup fails,
   abort without stopping existing writers. Then stop application writers,
   apply migration, replace app/worker/web/Caddy containers without removing
   PostgreSQL/Valkey data or volumes, and require /healthz + /readyz success.

If a prior partial release already migrated and started new app containers
but `/readyz` reports only `clamav: false`, **do not run the whole release
again or blindly restore the migrated database**. Start only the missing
profile service with:
```bash
cd /opt/rcat-pdf-hub
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile security up -d --no-deps clamav
```
Then query the existing API `/readyz` until scanner definitions are ready.
For historical partial runs, actual Caddy-published `/readyz` must be HTTP
200 before acceptance. Starting the scanner is not itself a successful
readiness check.

Failures before the cutover leave the current services intact. Failures during
migration or readiness require **incident-controlled recovery** from the
retained pre-update backup and the compatible prior application version.
A verified backup is **not** a successful restore rehearsal; do not advertise
an untested RPO/RTO or automatic rollback. Preserve previous image references
and logs until acceptance.

## Separate workstream: automated isolated DR

Automated private DR is **not** a prerequisite for a normal Production update.
The existing `.github/workflows/isolated-dr.yml` remains **disabled** until
an approved dedicated runner, rootless Docker and read-only backup mount exist.
Do not change GitHub repository visibility just to run this workflow.
Do not set `RCAT_DR_RUNNER_READY=true` without a real secure runner.

An operator who expressly requests **strict isolated DR evidence** for a
future release can still use the existing `production-cutover.sh` with
`PDFHUB_RELEASE_REQUIRE_DR=true` plus a verified official `DR_RUN_ID`.
That mode must validate the restored snapshot digest, exact protected main
commit, and evidence freshness as before. The standard one-command runner
does **not** set either option.

## Guardrails

- Never use `git reset --hard` or `git clean -fd` to resolve local Caddy config.
- Never reset PostgreSQL volumes or use `docker compose down -v`.
- No automated production shutdown/rollback on failed migration; the verified
  backup and pre-deployment images are retained for controlled recovery.
- A successful GitHub Merge does **not** prove the Ubuntu host was deployed.
  The actual operator terminal must show `DEPLOYED` and readiness PASS.
