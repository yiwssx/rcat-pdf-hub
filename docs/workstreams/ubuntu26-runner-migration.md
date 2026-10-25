# Ubuntu 26.04 GitHub Actions runner migration — compatibility tracker

Status: **M2 compatibility PR in progress; NOT approved for rollout**  
Master issue: [#195](https://github.com/yiwssx/rcat-pdf-hub/issues/195)  
Baseline main HEAD: `659a01f080600d6b3168b74ca863b73ca3a02160` (merge PR #194, 2026-10-25)  
Scope: **GitHub-hosted Actions VM only**. No production Ubuntu Server upgrade, app container base-image update, application activation, or deployment.

## Facts verified 2026-10-25

- Six existing workflow files; 13 applicable job variants counting matrices and conditional Dependabot jobs.
- All existing workflow jobs use `ubuntu-latest`; successful tested jobs in inspected logs explicitly show `Image: ubuntu-24.04`.
- Premerge Core API CI, Web CI, Dependency Review and postmerge CodeQL passed at the reviewed T90-0 lineage; none is proof of a green Ubuntu 26.04 execution.
- Core API CI exercises PostgreSQL 18.6 service, Valkey/RQ and SeaweedFS crash scenarios, pinned API/Gotenberg images and T90-0 architecture/no-activation controls.
- Branch API reports `protected: false`; repository rulesets enumeration returned empty. Enforcing required CI and review before rollout is a **release blocker**.
- Web CI currently uses `actions/upload-artifact@v4` and emitted a Node 20 compatibility warning on the Ubuntu 24.04 runner. Its remediation is a separate, controlled change.
- Some Dependabot failures predate Ubuntu 26.04; triage new failures against known preexisting lock/policy failures.

## Guardrails

1. The new probe workflow is deliberately scoped to PR changes in this tracker/probe and manual dispatch, with *no deploy, merge, secrets, production service access, or write permissions* except CodeQL's required `security-events: write`.
2. Capture runner identity and `/etc/os-release` for each job; never infer OS from the `ubuntu-latest` label.
3. Use explicit `ubuntu-26.04` for new probe jobs; include a limited `ubuntu-24.04` A/B host-tool matrix.
4. Keep existing CI and app Dockerfiles, app runtime images, locks, SHA verification and T90-0 feature gates unchanged during compatibility testing.
5. Compare result at exact head SHA; refresh this document and re-run checks if `main` advances or the test branch is rebased.
6. Existing Dependabot automation cannot be faithfully exercised by an ordinary PR. Treat real Dependabot policy/auto-merge trigger coverage as an **unmet separate acceptance gate** until confirmed on 26.04.

## Ordered rollout / gate checklist

### M0 — Baseline and governance
- [x] Inspect current `main` SHA, all six workflows, critical versions, log OS identity, previous successful runs.
- [x] Record absence of legacy branch protection and repository rulesets (observed via API).
- [ ] Enable enforced PR review / required check protection on `main` through administrative settings; confirm **effective** protections and no bypass.
- [ ] Collect stable baseline references for all 13 applicable job variants, including the conditional Dependabot workflows.

### M1 — Temporary containment (separate optional PR)
- [ ] If rolling `ubuntu-latest` transitions begin before M2 completes, open a separate minimal PR pinning *existing* runners to `ubuntu-24.04`. Do not alter `main` directly. Keep rollback PR small.

### M2 — Ubuntu 26.04 evidence
- [ ] Run version/OS diagnostics; collect explicit `Image: ubuntu-26.04` lines for all 26.04 jobs.
- [ ] Compare host Python 3.11–3.14 and operator scripts on Ubuntu 24.04 and 26.04.
- [ ] Check Compose config/profiles, Prometheus, pinned API/Gotenberg images and Thai fonts.
- [ ] Run API coverage/contract, PostgreSQL 18.6 migration rehearsal and Valkey/RQ/SeaweedFS recovery.
- [ ] Run Next.js Node 24, npm lock reproducibility, typecheck, build, Chromium/Playwright E2E and visual artifact capture.
- [ ] Run isolated full `make validate-free` including production-like disposable stack, cleanup, readiness and E2E stack.
- [ ] Run CodeQL and dependency review on explicit Ubuntu 26.04.
- [ ] Test Python security and npm patch policy checks without merging dependencies; separately observe real bot-triggered workflows before declaring done.
- [ ] Record exact run URLs and failed step details. Never mark M2 passed based on YAML alone.

### M3 — Regression isolation
- [ ] Fix only observed incompatibilities on narrow PRs, retaining all coverage, warning and security gates.
- [ ] Evaluate `upload-artifact` Node 24 upgrade separately with artifact verification.
- [ ] Do not change pinned app base images merely because the CI host OS changed.

### M4 — Controlled main migration (not part of this probe)
- [ ] Require all relevant M2 checks and branch governance PASS on the candidate SHA.
- [ ] Make small workflow-only PRs: dependency review/CodeQL, Web, Core API, Python Dependabot, npm auto-merge last.
- [ ] Keep `head_sha`, `base_sha` and no-stale-merge invariants. No bot auto-merge activation as a migration test.

### M5 — Postmigration and rollback
- [ ] Capture representative real PR, scheduled CodeQL and real Dependabot-run evidence for all applicable variants.
- [ ] Observe for seven days or until scheduled and bot triggers are covered (whichever is later).
- [ ] On hard regression, revert **only affected jobs** temporarily to `ubuntu-24.04`; do not disable security or change production app.
- [ ] Close #195 only after the evidence and gates have been checked.

## Acceptance / stop conditions

**PASS** requires zero Ubuntu-26-specific regressions across all six workflows / thirteen job variants, green backend & T90 recovery/migrations, reproducible Web E2E and Thai font checks, security review, enforced required checks, traceable runner-image logs, and a documented rollback.

**STOP** if an Ubuntu 26.04 probe fails, a test is skipped as a workaround, a policy/coverage gate is weakened, branch protection is not enforced, or bot-specific coverage is unproven. No production rollout in that state.

## Evidence to append

| Probe | GitHub Actions URL | Ubuntu runner image | Result / notes |
|---|---|---|---|
| Host tooling matrix | Pending | Pending | Not yet executed |
| Compose/API/Gotenberg | Pending | Pending | Not yet executed |
| PostgreSQL/T90/RQ/S3 | Pending | Pending | Not yet executed |
| Web/Playwright | Pending | Pending | Not yet executed |
| Full runtime | Pending | Pending | Not yet executed |
| CodeQL/Dependency Review | Pending | Pending | Not yet executed |

Official runner notice: https://github.com/actions/runner-images/issues/14748
