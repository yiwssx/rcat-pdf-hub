# CI-LEAN-00 — safe migration from polling Local CI to Lean Automated CI

Owner decision: approved 2026-11-08. Tracker: #318.

## Invariants
- The operator never executes test suites, DR drills or Docker builds to get a PR merged.
- No paid runner, no new secrets, no Production mutation during migration.
- Keep CodeQL and Dependency Review. No bypass of authentication, data isolation or migration checks.
- API and workers use the single reviewed `python:3.12.14-slim-bookworm` image and hashed lock file.
- Ubuntu's system Python is **not** an application runtime and must not be downgraded or duplicated.
- Release/DR procedures are **not** claims of successful recovery until actual isolated evidence exists.

## Lean CI (current)
`.github/workflows/lean-ci.yml` always reports `ci/required` on PRs and
`main` pushes. It uses a pinned Python 3.12 application image and routes by
actual changed paths:
- Docs only: policy and scope self-tests. No Docker.
- Operator/Compose/DR: syntax, Compose render and DR port assertions.
- Backend: build the canonical Docker image, run the backend coverage suite
  **once** plus OpenAPI contract validation.
- Database schema/model/migration changes: additionally run real PostgreSQL 18
  upgrade/rollback in **disposable GitHub-hosted** containers.
- Worker queue, storage and T90 crash-safety changes: additionally run the
  existing real Valkey/RQ + SeaweedFS fault-injection probe on disposable
  PostgreSQL, Valkey and S3 containers. Python dependency/image changes run
  both integration tracks.
- Web: Node 24 typecheck, build, browser smoke **once**; app/components/auth
  changes also select the UI/accessibility regression suite in the **same**
  Playwright invocation.
- Thai Gotenberg: build/test only for converter image changes.
- Unknown files: conservative routing to all relevant lanes.

The risk service script explicitly refuses non-GitHub-hosted runners and
exposes service ports on 127.0.0.1 only. It never handles Production backups,
Production secrets or a production Compose project.

The separate Dependabot Python security Workflow is read-only and **does
not** run `make validate-free`. Its dedicated job checks eligibility of the
bot-only one-pin change and generates the full hash-locked dependencies for
review. The ordinary required Lean CI owns build, coverage, migrations and
queue/storage regressions for changed Python dependencies. No auto-merge
permission is added.

A `workflow_dispatch` invocation intentionally selects all lanes for
exceptional investigation; routine PRs must not repeat completed suites.

## Historical required checks (already migrated)
Repository Ruleset: `main-required-review-and-security-checks`, ID `25837608`.
It requires:
1. CodeQL (python)
2. CodeQL (javascript-typescript)
3. Review dependency changes
4. api
5. web
6. Host tooling on Python 3.11
7. Host tooling on Python 3.12
8. Host tooling on Python 3.13
9. Host tooling on Python 3.14
10. Build and check Thai Office converter image

`local-ci/validate-free` is **NOT** a required branch check in this Ruleset.
The old four-version matrix and duplicate hosted workflows have now been removed
in merged PR #320, after the Ruleset was migrated to `ci/required` plus
CodeQL (both languages) and Dependency Review.

## Completed cutover procedure (historical record)
1. Merge the bootstrap PR **only after** the new `ci/required` check and all still-required legacy checks succeed. Do not update the Ruleset while the new check is failing.
2. Confirm `ci/required` also runs on the exact merged `main` SHA.
3. Update only GitHub Ruleset ID `25837608`: retain CodeQL (both languages) and Review dependency changes, add `ci/required` (GitHub Actions), and only then remove `api`, `web`, the four Python host job names and Gotenberg legacy job. Keep PR review, non-fast-forward and deletion protections intact. Without a Ruleset administration action, this is explicitly BLOCKED; do not pretend it is automated.
4. Verify one small PR can satisfy the new required check; only then land a follow-up change removing redundant legacy hosted CI jobs and Python matrix entirely.
5. Retire the polling Local CI Service/Timer **after** Ruleset cutover. This requires an authorized host action to disable `rcat-pdf-hub-local-ci.timer`; never touch `rcat-pdf-hub-backup.timer`.
6. Update legacy docs/trackers and close #318 only when GitHub Ruleset and host-service evidence are recorded.

## Release handoff (not operator-run tests)
`scripts/release-readiness.sh` uses `scripts/verify-ci-evidence.sh` to verify
`ci/required` success on the **exact** current GitHub main SHA. It does not
repeat `make validate-free` merely for bookkeeping.

Release-specific source/image security gates, backup integrity, isolated DR,
load checks, RBAC/OIDC and institutional pilot acceptance remain separate.
These should be executed by a purpose-built isolated runner connected through
an approved private control path; no Production SSH credentials or backup data
may be put into GitHub-hosted PR jobs.

A private release/DR runner has not yet been confirmed; release/DR evidence is still pending:
do not lower any safety gate or declare a release accepted merely because the
user no longer wants to perform manual tests.

## Recovery
If `ci/required` fails, leave the old Ruleset unchanged and fix the code.
If a Ruleset change prevents merges, restore the previous required checks
using the ten names above. Do not enable bypass or disable CodeQL/dependency
reviews to make the CI appear green.
