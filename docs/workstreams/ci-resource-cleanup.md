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
