# RCAT PDF Hub — Candy UI audit (Phase A, 19 October 2026)

**Baseline:** `main` at `5ba802415e8518b7469f6111cce499ba2cf66d35`  
**Method:** read-only repository inspection + screenshots supplied by the operator in the project conversation.  
**Status:** static/source audit completed; full browser/production visual coverage **not yet collected**. No production changes authorized by this document.

## Executive decision

The application uses one Next.js app and a consistent Candy palette, but its **presentation rules have drifted** through route-by-route fixes. The biggest friction is a *design-system consistency problem*, not missing PDF conversion features or a need to replace the framework.

**Recommendation:** retain the Candy identity and accepted task-first workflow; standardize the small set of shared presentation primitives, then improve layout and regression coverage across all existing routes. Prioritize the multi-input selected-file row, readable copy, file intake proportions, and reusable primary/secondary actions.

Do **not** start with a wholesale Next.js-to-Astro migration, another UI library, a massive file rewrite, or production deployment. Do not change authorization, job states, file selection behavior, API contracts, or storage semantics to address cosmetic findings.

## Evidence and findings (source-confirmed)

| ID | Priority | Source | Finding | User effect | Proposed treatment |
| --- | --- | --- | --- | --- | --- |
| A-01 | **P0** | `apps/web/app/components/tool-file-intake.tsx:107-115`; `apps/web/app/app-v3.css:348-369` | The selected-file row reuses the three-column `.v3RecentFile` grid. Multi-input rows can render **four immediate children** (order, filename, up/down control group, remove button). | The remove button can wrap to its own line; seen in the operator's images-to-PDF screenshot. | Dedicated selected-file row layout with correct grid areas/columns and consistent icon buttons. Preserve name, order, and removal behavior. |
| A-02 | **P1** | `apps/web/app/app-v3.css:251-255,290-336` | Intake uses 1.35fr : .65fr (~67.5:32.5) columns, and upload/card minimum heights of 315px. | Oversized vacant upload area next to cramped file names; seen on Office-to-PDF screenshot. | Content-driven dimensions, suitable max-width, review row close to primary CTA; responsive two-to-one columns. |
| A-03 | **P1** | `apps/web/app/app-v3.css:680-698,1166-1278,1394-1409` | The same controls receive baseline tiny type followed by later route-specific overrides. | Button dimensions and typography vary across intake, status, result and Admin screens. | One action scale and component-agnostic CSS contracts (primary, secondary, destructive, icon). |
| A-04 | **P1** | `apps/web/app/app-v3.css` (~1,574 lines, 14 `@media` blocks); `apps/web/app/globals.css`; `apps/web/app/layout.tsx:1-2` | Two stylesheets plus accumulated overrides, breakpoint duplication and globally shared selectors. A static search found 109 `font-size` declarations of 7–12px in `app-v3.css`, many superseded later. | Higher cascade risk and friction keeping layouts visually aligned across pages. | Inventory actual computed styles before consolidating into tokens and shared primitives. **The count is a source metric, not a claim about rendered font sizes.** |
| A-05 | **P1** | `apps/web/app/components/tool-file-intake.tsx:70-117` | Upload, searchable My Files, input review and action live in one composition; actions depend on scrolling and content height. | Tasks are technically correct but controls compete for attention. | Emphasize input acquisition → selected items → primary next action; preserve explicit input confirmation. |
| A-06 | **P1** | `apps/web/tests/e2e/pdf-hub.ui-regression.spec.ts`, `pdf-hub.smoke.spec.ts` | Responsive and functional assertions exist, but no `toHaveScreenshot` or approved snapshot baseline was found in the reviewed suites. | E2E success does not reveal spacing, typography, or alignment drift. | Capture representative states, compare deterministic screenshots and DOM geometry; approve baseline separately. |
| A-07 | **P2** | `apps/web/app/components/tool-file-intake.tsx:81,93,102`; `apps/web/app/components/v3-ui.tsx:47-76,414-467` | `MY FILES`, `REVIEW INPUTS`, `Workspace`, `Files`, `My Jobs` mixed with Thai labels; raw `content_type` MIME visible. | UI feels assembled from unrelated pages; technical jargon competes with task labels. | Thai-first content guide, format file types for users, keep technical names in diagnostics only. |
| A-08 | **P2** | `apps/web/app/components/v3-ui.tsx:29-80`; `apps/web/app/components/my-jobs-screen.tsx`; `apps/web/app/components/job-detail-screen.tsx` | App header, job history and job detail have different heading/actions patterns and information density. | Inconsistent navigation/action placement across stages. | Shared page-header and action conventions without changing durable job/result routes. |
| A-09 | **P2** | `apps/web/app/components/admin-area-nav.tsx`; `apps/web/app/components/pdf-hub-app.tsx:593-656` | Admin is already split into six purpose-specific areas. Visual alignment with user UI is unverified by screenshots. | Potential style inconsistency, **not evidence of broken admin workflow**. | Add role-safe screenshot/keyboard review of each of six Admin areas; do not alter RBAC or privileged actions. |
| A-10 | **P2** | `apps/web/app/components/task-journey.tsx`; `apps/web/app/components/job-result-screen.tsx` | Step indicator, result CTA and secondary links have independent page wrappers. | Visual identity may vary even though flow is consistent. | Align typography/spacing and status visuals, retain job ownership and output access checks. |

**Scope clarification:** source locations refer to the 2026-10-19 baseline, not necessarily future line numbers. Screenshots establish visible layout only for the supplied states. Other findings are *code evidence* and candidates for on-browser confirmation.

## Route-by-route audit inventory

| Route / surface | Source audit | Operator visual evidence | Runtime visual acceptance needed |
| --- | --- | --- | --- |
| `/` — Workspace / tool catalog | inspected: `v3-ui.tsx`, `pdf-hub-app.tsx` | not supplied for current baseline | yes: empty/files-selected states |
| `/tools/[slug]` — intake (13 tools) | inspected shared `ToolFileIntake`, catalog and input rules | **Office → PDF** and **Images → PDF** supplied | yes: all 13 tools incl. 1/2/many inputs, search, empty/error states |
| `/tools/[slug]` — configuration | inspected `ToolPanel` / `ToolWorkspace` | previous flow screenshots only, not current systematic baseline | yes: every tool capability variant |
| `/files` — file library | inspected `FilesScreen` within `v3-ui.tsx` | not supplied | yes: search, pagination, actions, long names |
| `/files/[id]` — individual document | routed through `PdfHubApp` | not supplied | yes: preview/loading/error/expired |
| `/jobs` — My Jobs | inspected `MyJobsScreen` | not supplied | yes: history/filters/empty/running |
| `/jobs/[id]` — job status | inspected `JobDetailScreen` | completed Office conversion screenshot supplied | yes: queued/running/completed/failed |
| `/jobs/[id]/result` — result/download | inspected `JobResultScreen` | not supplied | yes: download/expired/chainable |
| `/admin/login` | inspected login rules and shell | not supplied | yes: unauthenticated + negative path |
| `/admin?section=overview` | inspected shell and overview | not supplied | yes: read-only + role-safe |
| `/admin?section=jobs` | inspected jobs triage references | not supplied | yes: filters + no forbidden actions |
| `/admin?section=access` | inspected role/access structure | not supplied | yes: authorized identity-only |
| `/admin?section=storage` | inspected storage health structure | not supplied | yes: healthy/error/empty |
| `/admin?section=diagnostics` | inspected diagnostics structure | not supplied | yes: service checks/audit |
| `/admin?section=integrations` | inspected integration structure | not supplied | yes: empty/connected/denied |

All 13 tool slugs are registered in `apps/web/app/components/tool-catalog.ts` (OCR, merge, organize, compress, PDF→images, images→PDF, watermark, page numbers, PDF/A, Office→PDF, stamp, signed-link, archive). *Source audit of shared route code does not count as independently rendering all 13 routes.*

## Accepted constraints (do not break)

- **Candy UI** visual identity: soft gradients, rounded cards, pleasant pink/purple accents; adjust hierarchy and density, not a blank monochrome redesign.
- **ADR-0001:** ToolWorkspace owns per-tool settings/payload creation.
- **ADR-0005:** tool-first → explicit input selection → configure/preview → submit → durable job status → result/download/continue. Support file-first and operations-first paths.
- **RBAC + retention:** do not loosen file/job ownership; do not expose admin cross-user mutations or disable audit checks.
- **Deployment:** the user runs production Compose (`docker-compose.yml` plus `docker-compose.prod.yml`); no default Compose redeploy, database migration, storage deletion, or production restart as part of this audit.
- **Implementation scope:** change one area per PR, with screenshot plus functional regression evidence. Do not add a UI package merely to compensate for CSS drift.

## Proposed design foundation (for Phase B, not yet implemented)

| Token / convention | Candidate baseline to validate |
| --- | --- |
| Typography | body ~16px; supportive text 13–14px; control labels 14–16px; headings based on 20/28/36 scale; maintain Thai readability |
| Spacing | 4, 8, 12, 16, 24, 32; use shared gap/padding tokens rather than adding route-specific pixel patches |
| Hit target | primary/secondary/icon interactive controls generally ≥44×44px; icon buttons labeled/accessibly named |
| Surfaces | shared card radius/border/shadow scale; preserve Candy color identity |
| Layout | adaptive upload + library; compact file review; single discoverable primary next action |
| Content | Thai-first user copy; human-readable file type/size; hide MIME/job internals unless contextual and necessary |
| Focus and error | visible keyboard focus; inline field/status errors; responsive empty/loading/error/success states |

The values above are **proposals**. Validate actual computed styles and brand contrast before adopting.

## Baseline and acceptance matrix (Phase A remaining evidence / Phase E release gate)

For each priority route, capture **same deterministic data and fonts** at widths:
- Desktop: **1649×925** (operator screenshot match), **1440×900**, **1366×768**
- Tablet: **768×1024**
- Mobile: **390×844**

Capture: empty, populated, loading, error, selected/review, success or terminal state as applicable. No private personal information should be embedded in committed screenshots; mock realistic Thai filenames and long names.

Checks:
1. No horizontal page overflow at tested viewport widths; no CTA hidden under sticky header or mobile safe area.
2. All primary actions visible and enabled only when valid; main download and next-stage paths remain unchanged.
3. Multiple selected files show index, name, order controls and remove action **on the same row or an intentionally responsive stacked pattern**.
4. Text contrast, focus-visible, status/live regions, meaningful accessible names, keyboard navigation; no visible raw MIME values on end-user screens unless justified.
5. Owner-only access, retention/expiry, job polling and admin negative authorization tests still pass.
6. Visual snapshots reviewed/approved **in addition to** Playwright/TypeScript/CodeQL/Dependency Review. A green functional CI does not imply visual acceptance.
7. No Production deployment without separate operator approval and reproducible rollback instructions.

## Skills used and planned

- Repository `.agents/skills/web-design-guidelines/SKILL.md`: read current upstream rules; apply a11y, form, content, focus, mobile and navigation heuristics.
- `.agents/skills/vercel-react-best-practices/SKILL.md` + Vercel connector skill: review TSX and hook interfaces; no gratuitous state changes.
- `.agents/skills/improve-codebase-architecture/SKILL.md` and `codebase-design`: deepen the presentation interface only where multiple callers benefit. Existing ADR module seams remain.
- `.agents/skills/playwright-testing/SKILL.md`: deterministic visual & functional browser baseline.
- `.agents/skills/diagnosing-bugs/SKILL.md`: reproduce layout and selection bugs with tight pass/fail assertions.

Reference guidelines: https://github.com/vercel-labs/web-interface-guidelines .

## Recommended next action

**Phase A2** — implement *read-only* visual baseline capture and state matrix on mocked browser fixtures, then approve screenshots.  
**Phase B** — consolidate minimal layout/typography/button/file-row tokens behind existing class contracts in a small PR.  
**Phase C** — fix intake and tool configuration across 13 tools; preserve the TaskJourney and ToolWorkspace interfaces.  
**Phase D** — align file/job/result/admin layouts.  
**Phase E** — screenshot and accessibility/functional parity acceptance on all routes, then operator-approved deployment.

Do not mark overall UX unification COMPLETE until all five phases have evidence.