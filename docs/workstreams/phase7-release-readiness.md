# Phase 7 — Release readiness and operator handoff

Status: **CANDIDATE PREPARATION ONLY — NO PRODUCTION AUTHORIZATION**  
Source of truth: [Phase 7 Master Tracker](phase7-experience-workflow-tracker.md)  
Baseline: released `v0.6.0` (immutable). Phase 7 release version: **not selected**.

## Verified P7H.1 evidence (2026-10-09)

- PR [#151](https://github.com/yiwssx/rcat-pdf-hub/pull/151) merged as `eb51a7bd61fe741d734c59b309a2000feb004218`; [Web CI #37909217495](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/37909217495) passed **61 Playwright tests**, TypeScript check and production build. [CodeQL #37909217792](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/37909217792) and [Dependency Review #37909218130](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/37909218130) passed.
- Workflow regression covers tool intake/configuration → queued job → refresh/completed → durable result/reload → output-file handoff to a second tool, with zero browser reuploads and payload ID assertions. Existing Playwright coverage includes foreign-job/result/file denial, non-admin Admin navigation denial, scoped Admin triage/audit failure, quota and retention recovery.
- API code did **not** change between the [last Core API CI green #37908227263](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/37908227263) on PR #149 and the P7H.1 merge. GitHub comparison of `882ef978bb0ccfadc597debc428cca015a552074...eb51a7bd61fe741d734c59b309a2000feb004218` changes only `PHASE7.md`, Playwright specs and the tracker. This carries forward backend contract/coverage evidence without falsely claiming a fresh Core API run for #151.
- PR #151 asserts mobile horizontal overflow at **390px**, the repository's automated accessibility audit on Admin Overview/Jobs/Storage/Access/Integrations, and keyboard activation of the Storage read action.
- Web CI emitted **performance candidates only**, not production budgets. Mobile Admin candidate DOM nodes / resource counts / encoded bytes: Overview **153 / 14 / 182,129**; Jobs **136 / 15 / 182,180**; Storage **110 / 14 / 182,129**; Access **179 / 16 / 185,522**; Integrations **119 / 16 / 185,522**. Existing Phase 6 enforced budgets for `/` and `/files` are unchanged. Do not promote single-run candidates to thresholds without repeatable comparable runs.

**Boundary:** H.1 denotes repository-level functional, negative-path, security and browser regression evidence. This is **not** approval to roll out. Real-environment full `make validate-free`, image scans, production verification, DR/backup and rollback are H.2 gates.

## P7H.2 gate register

| Gate | Required proof | Current state |
| --- | --- | --- |
| Repository change review | No unresolved PR / merge conflict / critical security review finding; PR #151 and Phase 7 code lineage reviewed | PR #151 merged; final release-scope review **pending** |
| CI security | Fresh CodeQL and Dependency Review for any new code changes | PR #151 checks green; recheck if code changes |
| Backend contract / coverage | Core API checks for any backend changes; `validate-api-contract.py` and coverage floor remain enforced | PR #149 green; no API changes through #151; H.2 local revalidation **pending** |
| All-in-one local gate | Institution-owned Linux executor runs `make local-ci-doctor` and **`make validate-free`** against exact candidate commit; retain logs and exit code | **PENDING — not run in this handoff** |
| Code release readiness | `PDFHUB_RELEASE_MODE=code make release-readiness` on exact candidate; store SBOM and scan evidence | **PENDING** |
| Operator release decision | Approve target release version, exact commit, downtime/rollback owner, change window and written authorization | **PENDING** |
| Pre-production data safety | Verified current backup, backup checksum verification, isolated DR drill, configured retention and alerts, storage capacity, migration review | **PENDING** |
| Production gate | On authorized operator host: `BACKUP=<verified-backup> URL=<production-url> make release-readiness`; production Compose/security, image SBOM/Trivy, load smoke and DR must pass | **PENDING — production access not used** |
| Staged deployment / verification | Approved limited rollout; verify `/healthz`, `/readyz`, user tool/job/result, expired output, authenticated Admin read and audit without inspecting private documents | **PENDING — deployment not authorized** |
| Rollback rehearsal | Proven ability to restore previously deployed image/commit/configuration and traffic routing; data restore only under separately acknowledged recovery procedure | **PENDING** |
| Final release | Create a *new* tag/release only at the selected approved P7 version on the verified deployed SHA; publish operator evidence | **BLOCKED until all gates and authorization** |

## Operator execution sequence (do not execute without release authorization)

1. Freeze the candidate SHA and inspect release diff from immutable `v0.6.0`, with explicit review for schema migrations, environment variables, external integrations and persistent storage implications.
2. On the institution-owned **validation** host, run `make local-ci-doctor`, `make validate-free`, then `PDFHUB_RELEASE_MODE=code make release-readiness`. Record each command, host/runtime versions, full logs, exact SHA, pass/fail and generated SBOM findings. **Stop on any failure.**
3. Obtain explicit owner approval of a version, release window, accessible rollback owner, and the precise deployed Git SHA. Do not infer authorization from a green PR or from this document.
4. Before any production mutation, confirm valid backup and `BACKUP=<path> make backup-verify`. Run an isolated DR drill. Compare Compose and environment configuration, verify alerts, disk capacity, authentication provider and correct reverse-proxy routing. Do not disable controls for a green result.
5. Run the production gate (`BACKUP=<path> URL=<url> make release-readiness`) from the intended host using the approved environment, then perform staged rollout only in the agreed window. Check authenticated user and Admin journeys with non-sensitive test documents. Record smoke evidence, monitoring/queue/storage state and owner acknowledgment.
6. If rollback is triggered, stop further traffic promotion; restore the **last known-good application image/commit and verified config** using the institution's Compose/reverse-proxy deployment procedure. Verify health and worker compatibility. Database/file restoration is **not** an automatic part of app rollback: if data recovery is required, invoke the separate documented destructive restore procedure only with explicit acknowledgment and verified matching backup.
7. Only after successful production verification and explicit sign-off, create an approved P7 Git tag/release at the verified SHA. Never repoint or replace `v0.6.0`.

## Explicit stop conditions

- Any failing security, coverage, API-contract, browser, image scan, migration, restore/DR, production readiness, or operator acceptance gate.
- Missing local validation evidence or unknown deployment SHA.
- Cross-user document exposure, loss of human/session RBAC, missing durable Audit intent, unbounded Admin triage or unexpected service-key privilege.
- Expired/missing outputs represented as successes, unreviewed tool input substitution or duplicate jobs.
- Unauthorized production access, missing backup, unapproved version or unclear rollback ownership.

## Deferred scope

Institution-wide identity editing, cross-account job/file mutations, repair endpoints, new workflow engines and unmeasured performance claims remain **out of scope**. Any future permission expansion requires its own security decision and tracker.
