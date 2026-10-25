# Ubuntu 26.04 compatibility for rolling `ubuntu-latest` — evidence tracker

Status: **Compatibility evidence collected; the normal workflows remain on `ubuntu-latest` pending transition observation and governance gates**  
Master issue: [#195](https://github.com/yiwssx/rcat-pdf-hub/issues/195)  
Baseline main HEAD: `659a01f080600d6b3168b74ca863b73ca3a02160` (merge PR #194, 2026-10-25)  
Scope: **GitHub-hosted Actions VM only**. No production Ubuntu Server upgrade, app container base-image update, application activation, or deployment.

## Authoritative owner clarification — 2026-10-26

**Do not pin primary workflow runners to `ubuntu-26.04`.** The target is to keep all six CI workflows on `runs-on: ubuntu-latest` and make the project compatible with the actual Ubuntu 26.04 image selected by GitHub during the gradual October 19–November 19, 2026 transition. `ubuntu-latest` is a rolling label and may change again in future. Explicit `ubuntu-26.04` and `ubuntu-24.04` labels are acceptable **for isolated compatibility A/B tests**, not as the final primary workflow configuration. Historical suggestions to merge runner-label-only pinning PRs are superseded by this clarification.

Runner-only drafts [#200–#205](https://github.com/yiwssx/rcat-pdf-hub/pulls?q=is%3Apr+is%3Aclosed+ubuntu26) were **closed without merge**. Their already-green explicit 26.04 jobs remain valid compatibility evidence. On a confirmed severe runner regression, a scoped `ubuntu-24.04` pin may be considered as **temporary emergency rollback only**, subject to normal PR review.

Official source: https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/

## Baseline observed 2026-10-25 (historical; some governance findings subsequently resolved)

- Six existing workflow files; 13 applicable job variants counting matrices and conditional Dependabot jobs.
- All existing workflow jobs use `ubuntu-latest`; successful tested jobs in inspected logs explicitly show `Image: ubuntu-24.04`.
- Premerge Core API CI, Web CI, Dependency Review and postmerge CodeQL passed at the reviewed T90-0 lineage; none is proof of a green Ubuntu 26.04 execution.
- Core API CI exercises PostgreSQL 18.6 service, Valkey/RQ and SeaweedFS crash scenarios, pinned API/Gotenberg images and T90-0 architecture/no-activation controls.
- At initial baseline, main had no enforced ruleset. **Updated 2026-10-26:** active ruleset [#25837608](https://github.com/yiwssx/rcat-pdf-hub/rules/25837608) enforces PR approval and GitHub Actions CodeQL/dependency checks with no bypass. PR #198 still requires an eligible independent APPROVED review; security governance must not be relaxed.
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
- [x] Record initial absence of protection; then independently verify active main ruleset #25837608.
- [x] Enforce one eligible independent PR approval, resolved threads, up-to-date CodeQL Python/JS and dependency review, no deletion/force-push and no bypass in active main ruleset #25837608.
- [ ] Collect stable baseline references for all 13 applicable job variants, including the conditional Dependabot workflows.

### M1 — Emergency containment only
- [x] Default strategy: **keep** `runs-on: ubuntu-latest` and compare the actual selected image in logs. **Do not proactively pin Ubuntu 24.04 or 26.04.**
- [ ] Only if a real hard incompatibility is observed, prepare a narrowly scoped, reviewed temporary rollback of affected jobs to `ubuntu-24.04`, with criteria and a removal date.

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

### M4 — Controlled **automatic** changeover of rolling `ubuntu-latest` (no six runner-pinning PRs)
- [ ] Require all relevant compatibility and branch-governance checks green for the exact candidate SHA; merge only **actual compatibility fixes** (e.g. runtime cleanup #198, CI check availability #206, bot review gate #208) when independently reviewed.
- [x] Cancel the old six-workflow plan to pin `ubuntu-26.04`: runner-label-only drafts #200–#205 are closed **without merge**.
- [ ] Leave all original primary workflows on `ubuntu-latest`; detect GitHub's natural selection of Ubuntu 26.04 through runner logs in **real** PR, Web/API, CodeQL and Dependabot jobs. Review real failures by OS rather than assuming a version from the label.
- [ ] Keep `head_sha`, `base_sha`, no-stale-merge and independent approval requirements; no unapproved real bot merges. Observe actual bot and scheduled coverage after GitHub's rollout.

### M5 — Postmigration and rollback
- [ ] Capture representative real PR, scheduled CodeQL and real Dependabot-run evidence for all applicable variants.
- [ ] Observe for seven days or until scheduled and bot triggers are covered (whichever is later).
- [ ] On verified hard runner regression, change **only affected jobs** temporarily to `ubuntu-24.04` through an approved PR, with a return-to-`ubuntu-latest` plan; do not disable security or change production app.
- [ ] Close #195 only after the evidence and gates have been checked.

## Acceptance / stop conditions

**PASS** requires all six **primary workflows still specifying `ubuntu-latest`**, zero Ubuntu-26-specific regressions across applicable job variants, green backend & T90 recovery/migrations, reproducible Web E2E and Thai font checks, security review, enforced required checks, **real `ubuntu-latest` execution showing image Ubuntu 26.04 in logs**, real bot and scheduled evidence, and a documented temporary rollback.

**STOP** if an Ubuntu 26.04 probe fails, a test is skipped as a workaround, a policy/coverage gate is weakened, branch protection is not enforced, or bot-specific coverage is unproven. No production rollout in that state.

## Evidence to append

| Probe | GitHub Actions URL | Ubuntu runner image | Result / notes |
|---|---|---|---|
| Host tooling matrix | [Probe run 40237864271](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864271) | Explicit Ubuntu 24.04 / 26.04 | 16/16 overall probe success at prior SHA `05e1437`; Python 3.11–3.14 covered |
| Compose/API/Gotenberg | [Probe run 40237864271](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864271) | Explicit Ubuntu 26.04 | Successful at prior SHA, including Thai fonts |
| PostgreSQL/T90/RQ/S3 | [Probe run 40237864271](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864271) | Explicit Ubuntu 26.04 | Successful at prior SHA |
| Web/Playwright | [Probe run 40237864271](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864271) | Explicit Ubuntu 26.04 | Successful at prior SHA; mocked visual artifact |
| Full runtime | [Probe run 40237864271](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864271) | Explicit Ubuntu 26.04 | `make validate-free` successful at prior SHA |
| CodeQL/Dependency Review | [CodeQL 40237864162](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864162), [Dependency 40237864127](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/40237864127) | Primary workflow `ubuntu-latest`; probe includes explicit 26.04 | Prior checks successful; **after this documentation commit, re-check fresh exact-SHA CI** |
| Natural `ubuntu-latest` 26.04 migration | Pending | Must observe `Image: ubuntu-26.04` under actual `ubuntu-latest` config | Not yet proven by diagnostic-only jobs |
| Dependabot and scheduled actual events | Pending | Under `ubuntu-latest` after GitHub's rollout | Not yet proven; guarded by #207/#208 |

Official runner notice: https://github.com/actions/runner-images/issues/14748
