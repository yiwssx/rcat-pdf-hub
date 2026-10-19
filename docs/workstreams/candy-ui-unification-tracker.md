# RCAT PDF Hub — Candy UI Unified Design System Master Tracker

Date started: **2026-10-19**  
Baseline: `main` `5ba802415e8518b7469f6111cce499ba2cf66d35`  
Audit: [Phase A static audit](../audits/candy-ui-phase-a-2026-10-19.md)  
Status: **ACTIVE / AUDIT UNDERWAY — no visual production changes deployed**

## Objective / guardrails

Unify **existing** Candy UI styling across user and administrator journeys without rewriting the workflow, migrating framework, weakening file/job ownership, or replacing the pink/purple soft-rounded identity. Work proceeds in phases A–E, with one independently testable PR per coherent scope.

The project is **not** completed by a successful code merge alone. The acceptance standard includes reproducible browser screenshots of key states at the sizes in the audit, all current functional/API authorization gates, and a controlled production rollout.

| ID | Phase / task | State | Dependency | Acceptance evidence |
| --- | --- | --- | --- | --- |
| UI-A1 | Read current code, ADRs and UI skills; identify sources of visual drift across user/Admin routes | **DONE** (source inspection) | none | audit report; baseline source SHA; evidence table A-01–A-10 |
| UI-A2 | Inventory route/state/viewport combinations, deterministic **mock-data** Playwright capture and screenshot artifact collection | **DONE (mock baseline only)** | A1 | PR #168 merged `9890d3f004ff276ccce4da267bfa50f7653c0bc2`; Web CI #39232638160 PASS; artifact `candy-ui-baseline` ID `12177877072` contains 42 PNGs + gallery; visual approval remains A3 |
| UI-A3 | Review screenshots, approve before/after criteria, severity and baseline with project owner | **PENDING** | A2 | signed-off baseline; exceptions recorded; Phase A closed |
| UI-B1 | Define Candy presentation foundation (typography, spacing, surfaces, control scale, responsive breakpoints) | **TODO** | A3 | inspected computed style/token table; no regressions at screenshot widths |
| UI-B2 | Consolidate redundant CSS overrides in limited scope, no blanket restyle | **TODO** | B1 | visual snapshots reviewed; Playwright, accessibility, CodeQL and build |
| UI-C1 | Fix selected-file row/grid and keyboard-friendly icon controls shared by one/multiple-file intakes | **TODO / P0** | B1 | one and multiple files, reorder/remove one-row alignment at desktop/mobile |
| UI-C2 | Balance upload/library layout and concise review CTA across 13 tools | **TODO / P1** | C1 | 13 routes with 0/1/2/many inputs; CTA visible at 1366×768 and 390×844 |
| UI-C3 | Align ToolWorkspace configuration/preview with intake and step indicator | **TODO** | C2 | all tool variants, input review/submit/preview, no payload/API change |
| UI-D1 | Unify Workspace / My Files / file-detail presentation and copy | **TODO** | B2 | empty/search/pagination/upload/error screens at 5 viewports |
| UI-D2 | Unify My Jobs, job status and result/download presentation | **TODO** | D1 | queued/running/completed/failed, expired/denied/output, valid download |
| UI-D3 | Apply visual foundation to six Admin areas, retaining isolation and audit controls | **TODO** | D2 | operator/viewer/admin negative permissions; responsive and accessible |
| UI-E1 | Automated screenshot comparisons, keyboard/a11y/contrast and long Thai filename checks | **TODO** | C/D | stable artifacts + approved diff thresholds, no hidden primary controls |
| UI-E2 | Final regression/readiness/rollback documentation and operator acceptance | **TODO** | E1 | CI, screenshots, diff review, production-mode deployment approval |

**State semantics:** `DONE` = explicit criterion proven; `TODO` = no implementation claimed; `PENDING` = waiting for evidence/approval; phases are NOT closed while any mandatory task is outstanding.

## Priority defects and ownership

- **P0 / A-01**: `tool-file-intake.tsx` reuses `.v3RecentFile` three-column grid for a row with four children in the multi-select case. Fix with dedicated selected-row presentation; does not change file IDs or processing order.
- **P1 / A-02–A-06**: fixed upload and card height, cramped 68/32 layout, multiple contradictory type scales, missing visual snapshot baseline.
- **P2 / A-07–A-10**: English/Thai mixture, raw MIME strings in user UI, inconsistent page headers and result/Admin spacing. Do not confuse these with a failure of API behavior.

## Explicit change control

1. **Read-only Phase A.** Store audits, test fixtures and baseline capture plans on a branch. No production web/Caddy/Gotenberg restart for evidence gathering.
2. **Design decision gate:** present reviewed desktop/mobile baseline and minimal foundation before changing visible UI. Preserve accepted ADR-0001 and ADR-0005 ownership/flow seams.
3. **Per-PR implementation:** one primary behavior/layout goal per PR; include source finding ID, screenshots before/after, and focused Playwright regression. CI success must not substitute for screenshot review.
4. **No unexpected libraries:** use current React/Next.js/CSS and installed repository skills unless a later independently reviewed need is demonstrated.
5. **Safety:** no production data in visual fixtures; no changes to authentication, file/job access checks, retention, quota, database migrations or Docker networks as UI work.
6. **Production:** server uses `docker-compose.yml` **plus** `docker-compose.prod.yml`. Deployment is an independent operator action after screenshot + runtime acceptance, with rollback instructions.
7. **Release:** do not retroactively reopen Phase 7 completion or mutate its historical tracker. This is a new, explicitly scoped UI unification workstream.

## Visual acceptance coverage

Dimensions: **1649×925, 1440×900, 1366×768, 768×1024, 390×844**.  
Data states: **empty, selected, multi-select, loading, error, ready, completed, expired/denied** as applicable.  
Coverage: home; 13 tool intake/configuration paths; file library/detail; My Jobs, job status, result; Admin login and 6 scoped areas.

Critical assertions:
- No unintended document-width horizontal scroll, clipped buttons, unreadable labels or invisible focus.
- Minimum practical hit-area of **44×44px** for action/icon controls (responsive exceptions documented).
- The selected file list keeps item number, filename, order/reorder/remove controls aligned.
- Main CTA is present in viewport and remains discoverable with long Thai names, browser zoom and mobile safe-area.
- Visual baselines are reviewed with deterministic font, content and browser settings; avoid brittle global pixel perfection thresholds.
- Job result/download remains owner-scoped and respects file expiry. Admin negative-permission states retain existing guarantees.

## Activity log

| Date | Scope | Evidence | Outcome |
| --- | --- | --- | --- |
| 2026-10-19 | A2 deterministic screenshot gallery | PR #168 merge `9890d3f004ff276ccce4da267bfa50f7653c0bc2`; Web CI #39232638160 PASS; CodeQL, Dependency Review PASS; `candy-ui-baseline` 42 PNG + HTML, downloaded and inspected representative operator/mobile/Admin images | **A2 DONE for synthetic screenshots; A3 operator sign-off and production verification PENDING** |
| 2026-10-19 | A1 baseline source audit and existing Skills inspection | `docs/audits/candy-ui-phase-a-2026-10-19.md`; source `5ba802415e8518b7469f6111cce499ba2cf66d35` | **Source audit completed. Phase A remains open for visual baseline.** |

## Handoff to next work period

1. Add mock-only screenshot capture workflow, ideally reusing existing Playwright routes and fixtures without hard-coding production session data.
2. Obtain or generate visual evidence for every route class and Admin area, review exceptions with the owner.
3. Begin B/C implementation only after the baseline is documented. P0 multi-file layout is the first controlled implementation candidate.
