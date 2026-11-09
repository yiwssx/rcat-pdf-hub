# RCAT PDF HUB — Engineering First execution board

**Owner decision: APPROVED 2026-11-09.** Original goal: make 90 distinct PDF tools selectable and functional; prioritize code delivery over repeated environment-wide proof collection. **Production deployments, existing/new feature-flag enablement and RBAC expansion require separate operator approval.**

## Three intentionally separate tracks

| Track | Canonical GitHub issue(s) | Active rule |
| --- | --- | --- |
| **Development** | [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) | Primary: create working tool choices and genuinely functional outputs. Close engineering batches on a scoped implementation + standard CI, even when not yet production certified |
| **QA / Release** | [#308 R1](https://github.com/yiwssx/rcat-pdf-hub/issues/308), [#262 T90](https://github.com/yiwssx/rcat-pdf-hub/issues/262) | Park full Compose, two-real-user Workspace tests, Thai physical golden layouts, native format and security negative host tests, performance and independent operator approval. Retain open; do not mark PASS |
| **Infrastructure** | [#195 CI](https://github.com/yiwssx/rcat-pdf-hub/issues/195), [#323 DR](https://github.com/yiwssx/rcat-pdf-hub/issues/323) | Preserve the four protected checks; Defer runner migration/Dependabot-specific observation and isolated DR while tool creation is the active priority |

The previous 11→5 issue consolidation reduced containers, not actual work. The 90-row [engineering inventory](t90-engineering-first-inventory.md) is the source of truth for **user-facing workflow completeness**, while the independent [T90 QA ledger](../../contracts/t90-rcat-pilot-acceptance.v1.json) records tested source and release evidence. Do NOT use `RELEASED=0` to declare software delivery 0%; do NOT equate `IMPLEMENTED` source entries with 90 usable buttons.

## Done means (Development, not Release)

- [ ] A user can explicitly discover/select the named tool in an authorized, feature-gated UI (no generic operation manually entered).
- [ ] Correct input type and actual owner enforced by existing backend; unsupported formats are rejected, not silently passed.
- [ ] User submits the typed request; existing API→queue→worker runs a genuine bounded engine and creates a retrievable file of the stated type (never a mock or renamed extension).
- [ ] Basic unit/contract tests and the repository's existing 4 Required Checks pass on exact PR HEAD.
- [ ] Document deliberately unsupported subsets and keep new routes default OFF until Production acceptance is separately approved.

Development and QA have distinct endpoints: `CODE COMPLETE` can coexist with `QA PENDING`; no field or CI-only check confers `VERIFIED` / `RELEASED`.

## Latest measured delivery (2026-11-09)

- [x] Source audit complete: all 90 registry IDs classified with explicit status.
- [x] [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339) Merge PASS — one shared guarded To-PDF Web workflow, 33 selectable formats, Publisher T21 withheld.
- [x] [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340) Merge PASS — one shared guarded From-PDF Web workflow, 16 selectable exporters; F15 blocked.
- [x] [PR #341](https://github.com/yiwssx/rcat-pdf-hub/pull/341) Merge PASS — genuine M23 add-image-to-PDF bounded engine, two-file owner-scoped API/worker, guarded UI and basic source tests.
- **Updated 90-tool Engineering readiness:** **59 CODE COMPLETE / 14 PARTIAL / 10 MISSING / 7 BLOCKED**, as enumerated [per tool](t90-engineering-first-inventory.md). Before these 3 PRs it was 9/63/11/7.
- QA certification ledger remains separately at **40 IMPLEMENTED / 1 STAGED / 49 UNASSESSED / 0 VERIFIED / 0 RELEASED**. Do not conflate QA ledger rows with code completion or claim live deployment.

## Working sequence (reduce duplicated integration work)

1. **Inventory 90** — completed 2026-11-09; initial baseline 9/63/11/7, now tracked per ID at current 59/14/10/7. These are conservative *workflow* statuses, not the 40/1/49 independent source ledger.
2. **DONE #339: Shared T90-2 Web converter** — 33 of 34 prepared To-PDF formats selectable with default OFF. T21 withheld. Six separate native/URL prototypes remain BLOCKED.
3. **DONE #340: Shared T90-3 Web exporter** — 16 selectable routes, owner/scopes, typed real outputs and existing download. F15 MOBI still BLOCKED.
4. **NEXT: Manage PDF missing 10 + incomplete 13** — M23 image overlay delivered by #341. Next target M20 viewer/partial and M24 bounded flatten, using same file/auth/job primitives. AI/chat/translation items require explicit engines and no fabricated results.
5. **Batch checks later** — coordinate only once per capability family, without moving physical QA/DR into the tool-development issue. Release gates remain independent.

## Guardrails and status reporting

- Existing Production R1 exposes nine principal processing workflows; no status or release flags changed by an engineering PR.
- A guarded route behind default-OFF flags is **not** an activated production capability. The opt-in UI must require `PDFHUB_STAGED_TO_PDF_WEB_ENABLED=true` plus matching API configuration on a separately authorized test stack only.
- No mass reclassification of 90 tools based on a routing table, a green build, or a signed-in browser alone.
- Critical security regressions affecting existing R1 are not intentionally ignored; their separately approved deployment/testing remains an operational duty.
- Each engineering PR should change a narrow reusable pipeline or source capability, be independently reviewable, and avoid CI workflow/ruleset reengineering unless the required checks are actually broken.

