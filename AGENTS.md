# RCAT PDF Hub — Agent Guidance

This repository includes project-local agent skills under `.agents/skills/`.

## Skill routing

Use the smallest set of skills that fits the task. Do not activate every skill for every change.

### React / Next.js

- For work under `apps/web/**` that writes, reviews, or refactors React/Next.js code, read and apply `.agents/skills/vercel-react-best-practices/SKILL.md`. For detailed performance rules, use its compiled `AGENTS.md`.
- When a React module is becoming configurable through many booleans, has unclear state ownership, or needs a reusable interface, also apply `.agents/skills/vercel-composition-patterns/SKILL.md` and its compiled `AGENTS.md`.
- For visible UI/UX work — layout, typography, forms, responsive behavior, navigation, interaction states, or accessibility — also apply `.agents/skills/web-design-guidelines/SKILL.md`.

### Bugs and regressions

- When the user reports something broken, failing, flaky, or slow, start with `.agents/skills/diagnosing-bugs/SKILL.md`. Establish a reproducible pass/fail signal and root cause before changing production code.
- Once the failure is reproducible and the behavior has a suitable public seam, use `.agents/skills/tdd/SKILL.md` for the red → green implementation loop.
- For Python/FastAPI tests under `apps/api/**`, pair TDD with `.agents/skills/pytest-patterns/SKILL.md`.
- For browser-visible behavior under `apps/web/**`, pair TDD with `.agents/skills/playwright-testing/SKILL.md`. Prefer a regression test for responsive/layout bugs when the failure can be expressed through DOM, viewport, network, console, or screenshot assertions.

### Architecture

- For architecture reviews or architecture-changing refactors, explicitly read `.agents/skills/improve-codebase-architecture/SKILL.md` and `.agents/skills/codebase-design/SKILL.md` before proposing implementation.
- The architecture workflow's supporting skills are installed locally as `grilling` and `domain-modeling`. Use them only when the architecture workflow calls for them.
- Prefer YAGNI. Do not perform architecture churn merely to reduce file count or introduce abstractions.
- If `GLOSSARY.md` or ADRs under `docs/adr/` exist, treat them as domain/decision constraints and do not silently re-litigate them.

### Review before merge

- For non-trivial changes, run `.agents/skills/code-review/SKILL.md` after implementation and tests, before merge.
- Keep review findings separate from automated CI/security results. A green CI run does not replace code review.

## Active workstream continuity

- For Phase 6 work, read `docs/workstreams/phase6-production-hardening-tracker.md` before implementation.
- Treat its task table and activity log as the canonical continuation state across sessions.
- Update the tracker in the same PR when a Phase 6 task changes status, scope, acceptance evidence, or next action.
- Never repeat a task marked `COMPLETE` solely because conversational context is missing; verify repository evidence first.

### Phase 7 — Experience & Workflow

- Read `PHASE7.md`, `docs/workstreams/phase7-experience-workflow-tracker.md` and ADR-0005 before implementing User or Admin journeys.
- Treat the Phase 7 Master Tracker as the canonical state; update its task table and activity log with exact PR/CI evidence in every P7 implementation PR.
- A merged P7 planning PR is **not** authorization to begin code implementation. Stop at the planning gate until the project owner explicitly instructs execution.
- Preserve ADR-0001 ToolWorkspace ownership, ADR-0004 RBAC, Phase 6 production safeguards and the published `v0.6.0` tag.

## Project execution rules

- Preserve existing product behavior unless the task explicitly changes it.
- For web changes, prioritize eliminating async waterfalls and unnecessary client bundle work before micro-optimizations.
- Keep module interfaces smaller than their implementations; introduce a seam only when variation or testing leverage justifies it.
- Diagnose before patching. Prefer evidence from a failing test, HTTP request, browser reproduction, trace, or minimal harness over guesswork.
- Test user-visible behavior at the highest practical seam. Avoid tests coupled to private implementation details.
- Validate through the repository's existing CI and tests before merging.
- Third-party skills are guidance for development agents only; they are not part of the production runtime or application bundle.

See `.agents/README.md` for provenance and update commands.
