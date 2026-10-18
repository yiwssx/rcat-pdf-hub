# CI resource lifecycle recovery (operator runbook)

Issue: [#158](https://github.com/yiwssx/rcat-pdf-hub/issues/158). This is a CI infrastructure repair, **not** Phase 7 production-release authorization.

## What happened

- On 2026-10-17, Ubuntu local CI remained green but 182 orphan `pdfhub-promtool-*` named volumes and 30 containers belonging to four `pdfhub-validation-*` projects remained on the host.
- The Prometheus validation script previously ran Compose `down` without `-v`, leaving its named volumes behind.
- Runtime test teardown previously ignored `docker compose down -v` failures. Explicit project-level verification is now mandatory.
- The production project `pdf-hub` and volumes `pdf-hub_postgres_data`, `pdf-hub_pdf_data`, `pdf-hub_valkey_data`, plus the entire `backups/` directory, are **not targets**.

## Permanent CI controls

- `scripts/cleanup-ci-project.sh` only accepts `pdfhub-promtool-N` or `pdfhub-validation-N`, matched to the corresponding `promtool` or `runtime` mode. It runs project-scoped Compose `down -v --remove-orphans` and then checks Compose ownership labels on remaining containers and volumes. If teardown or verification fails, the CI validation fails.
- `scripts/validate-prometheus.sh` invokes the helper through its EXIT/signal traps; successful output is not printed before cleanup.
- `scripts/validate-free.sh` also checks teardown before reporting `runtime: PASS`; on early failure it still attempts project-scoped cleanup.
- `scripts/test-ci-resource-cleanup.sh` uses a mock Docker binary to test guardrails and cleanup result propagation. Run `make validate-ops` for its invocation in the normal zero-cost validation pipeline.

## Retire old Promtool volumes on Ubuntu (operator only)

The scripts are available only after this change is merged and the host pulls that commit.

1. Run `bash scripts/cleanup-orphan-promtool-volumes.sh --dry-run` and review its candidate list. Strict name **and** Compose project/volume labels must match, and the volume must have zero container references.
2. When the candidate list is correct, run `CI_CLEANUP_CONFIRM=DELETE bash scripts/cleanup-orphan-promtool-volumes.sh --apply` with the existing Local CI lock available. This operation deletes the eligible orphaned Promtool volumes only; it does not delete containers or any `pdf-hub_*` volume.
3. Recheck: `docker volume ls -q | grep -c '^pdfhub-promtool-' || true`, `docker compose ls --all`, `make local-ci-doctor`, and `docker system df`.
4. Do not use `docker volume prune`, `docker system prune --volumes`, or `docker compose down -v` for the production `pdf-hub` project.

Some items may remain because labels are missing/mismatched, a container still references the volume, or the Local CI validation lock is held. **Review each skipped item; do not weaken the guard.**

## Historical validation projects

The 30 lingering containers belong to four named `pdfhub-validation-*` projects. Do **not** delete them in the same operation as orphan Promtool volumes. Capture exact Compose labels, image/container state, config paths and volume ownership first. Old runtime test worktrees may no longer exist. Any eventual retirement must use explicitly selected project names, and must preserve unrelated `pdf-hub` containers, volumes and backups.

## Production release boundary

The seven valid v0.6.0 backup directories are prior release evidence, not a current P7 snapshot or proven disaster recovery. Production requires a verified **current** backup, isolated DR evidence, authorized release version and rollback owner, and the production release-readiness gate. No deployment, tag, migration or restore is authorized by this repair.

## Local CI full-validation retry circuit breaker

Related issue: [#160](https://github.com/yiwssx/rcat-pdf-hub/issues/160). An Ubuntu journal excerpt shows repeated PR #159 failures on an unchanged commit, even though GitHub's CodeQL/Core API/Dependency Review workflows passed. Those GitHub checks **do not** identify the Local CI failure root cause; inspect the host-side test log.

The repaired `local-ci-prs.sh` stores a `base_sha:head_sha` result for each PR:

- `success`: no new full build, re-posts success status;
- `failure`: does not rerun the same commit pair; reports failed status, points to the host log;
- `attempt`: if the previous run was interrupted before recording success/failure, the next cycle reports an error but does not automatically start another expensive build;
- new base or head SHA: full validation is eligible again automatically;
- failed validation is **never** treated as PASS.

On Ubuntu, while PR #159 is repeatedly failing, stop **only** the schedule with `systemctl --user stop rcat-pdf-hub-local-ci.timer`. This does not terminate a running one-shot service. Investigate `.local-ci/logs/pr-159-<head_sha>.log` with `tail -n 120` and selective `grep -nEi 'error|failed|traceback|assert|warn'`, plus `journalctl --user -u rcat-pdf-hub-local-ci.service`. Review the *first causal error*; the final `FAIL` line alone is insufficient.

After the fix is merged, pushed/pulled onto Ubuntu and a precise failure has been corrected, the operator can inspect `bash scripts/local-ci-retry-pr.sh 159` and explicitly clear the SHA-pair failure/interruption cache using `bash scripts/local-ci-retry-pr.sh 159 --apply`. **The script will refuse to run while Local CI is active or its lock is held**, and it never posts green success. If the timer was stopped, re-enable it using `systemctl --user start rcat-pdf-hub-local-ci.timer` only when a new validation run is intended.

Regression tests: `bash scripts/test-local-ci-result-cache.sh`, `bash scripts/test-ci-resource-cleanup.sh`, `make validate-ops`. The pending local-ci/validate-free status on PR #159 is not a pass and must not be bypassed as evidence for Production Release.

### Existing Ubuntu timer schedule

The Local CI installer now uses `OnUnitInactiveSec=5min` instead of `OnUnitActiveSec=5min` so that an expensive completed run does not cause an immediate back-to-back start. This change affects newly installed/reinstalled user timers, not an existing service until its unit is updated.

After rollout on Ubuntu, inspect the current timer first: `systemctl --user cat rcat-pdf-hub-local-ci.timer`. When no full-validation run is active and the CI issue is resolved, run `make install-local-ci` to regenerate the user timer from the updated repository and verify with `systemctl --user list-timers --all`. Do not restart a currently running validation solely to change the timer.

### Resolved root cause for repeated #159 FAILs (Ubuntu log, 2026-10-18)

The operator-provided validation log explicitly reports 116 backend tests PASS, one production-stack Playwright E2E PASS, and all container/security policy checks PASS. Docker Compose also removed the `pdfhub-validation-2087395` test containers, named volumes and networks successfully. The ultimate failure was **after teardown**:

```
rm: cannot remove '/tmp/pdfhub-validation-nas-2087395': Operation not permitted
runtime: failed to remove temporary NAS directory
```

Root cause: `docker-compose.yml` uses `${PDFHUB_NAS_PATH:-./data/nas-placeholder}:/mnt/pdfhub-nas` as a host bind mount. If the host source does not exist, Docker/Compose can create it with ownership inappropriate for the unprivileged CI user. Under sticky `/tmp`, that user cannot delete the directory even when the Docker containers are gone.

Repair: `scripts/ci-nas-dir.sh create` now creates the narrowly named host path with `0700` mode as the current CI user before any Docker Compose build/up. After all ephemeral containers are removed, `scripts/ci-nas-dir.sh remove` checks exact path/ownership, refuses symlinks, and uses only `rmdir` (non-recursive). Unexpected files or ownership intentionally produce an actionable FAIL without broad `sudo rm -rf`. `scripts/test-ci-nas-dir.sh` covers ownership, permissions, non-empty directory preservation and symlink/collision guards. Cleanup failures no longer run twice.

Previous root-owned `/tmp/pdfhub-validation-nas-*` leftovers are not automatically deleted by this change. Inspect them separately before any privileged cleanup; never run a blind recursive delete.
