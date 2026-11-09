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

## Working sequence (reduce duplicated integration work)

1. **Inventory 90** — completed 2026-11-09 baseline: CODE COMPLETE 9, PARTIAL 63, MISSING 11, BLOCKED 7; all IDs enumerated with code links. These are conservative *workflow* statuses, not the 40/1/49 independent source ledger.
2. **Shared T90-2 Web converter** — implement one reusable upload/owner/scope/job/result UI for 34 prepared to-PDF Backend routes, not 34 independent frontends. **Withhold T21** because of a known blank output page. Six separate native/URL options remain BLOCKED and are never shown as supported.
3. **Shared T90-3 Web exporter** — one PDF selector and grouped output variants for 16 known exporters (typed MIME and method/parameter safety). F15 MOBI remains BLOCKED until a genuine licensed engine exists.
4. **Manage PDF missing 11 + incomplete 13** — implement targeted new engines for M23 image overlay, M24 bounded flatten etc. Reuse authenticated upload, queue, artifact, download, audits. Unimplemented AI/chat/translation items require separate scoped technical designs and must not produce fabricated results.
5. **Batch checks later** — coordinate only once per capability family, without moving physical QA/DR into the tool-development issue. Release gates remain independent.

## Guardrails and status reporting

- Existing Production R1 exposes nine principal processing workflows; no status or release flags changed by an engineering PR.
- A guarded route behind default-OFF flags is **not** an activated production capability. The opt-in UI must require `PDFHUB_STAGED_TO_PDF_WEB_ENABLED=true` plus matching API configuration on a separately authorized test stack only.
- No mass reclassification of 90 tools based on a routing table, a green build, or a signed-in browser alone.
- Critical security regressions affecting existing R1 are not intentionally ignored; their separately approved deployment/testing remains an operational duty.
- Each engineering PR should change a narrow reusable pipeline or source capability, be independently reviewable, and avoid CI workflow/ruleset reengineering unless the required checks are actually broken.

