# RCAT PDF Hub — Agent Guidance

This repository includes project-local agent skills under `.agents/skills/`.

## Skill routing

- For work under `apps/web/**` that writes, reviews, or refactors React/Next.js code, read and apply `.agents/skills/vercel-react-best-practices/SKILL.md`. For detailed performance rules, use its compiled `AGENTS.md`.
- For architecture reviews or architecture-changing refactors, explicitly read `.agents/skills/improve-codebase-architecture/SKILL.md` and `.agents/skills/codebase-design/SKILL.md` before proposing implementation.
- The architecture skill's supporting workflow is installed locally as `grilling` and `domain-modeling`. Use those only when the architecture skill calls for them.
- Prefer YAGNI. Do not perform architecture churn merely to reduce file count or introduce abstractions.
- If `GLOSSARY.md` or ADRs under `docs/adr/` exist, treat them as domain/decision constraints and do not silently re-litigate them.

## Project execution rules

- Preserve existing product behavior unless the task explicitly changes it.
- For web changes, prioritize eliminating async waterfalls and unnecessary client bundle work before micro-optimizations.
- Keep module interfaces smaller than their implementations; introduce a seam only when variation or testing leverage justifies it.
- Validate through the repository's existing CI and tests before merging.
- Third-party skills are guidance for development agents only; they are not part of the production runtime or application bundle.

See `.agents/README.md` for provenance and update commands.
