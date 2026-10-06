# Project-local agent skills

These skills are vendored for development-agent guidance. They do not run in production and are not application dependencies.

## Installed skills

### React, performance, and UI

1. **vercel-react-best-practices**
   - Source: https://github.com/vercel-labs/agent-skills
   - Upstream ref: `063bee94c3f4df8453406c830b0a7df0f2860278`
   - Installed: `SKILL.md`, compiled `AGENTS.md`
   - Purpose: React/Next.js performance, async waterfalls, bundle size, rendering, re-renders, and server/client data flow.

2. **vercel-composition-patterns**
   - Source: https://github.com/vercel-labs/agent-skills
   - Upstream ref: `063bee94c3f4df8453406c830b0a7df0f2860278`
   - Installed: `SKILL.md`, compiled `AGENTS.md`
   - Purpose: scalable React module interfaces, state ownership, compound modules, and avoiding boolean-prop proliferation.

3. **web-design-guidelines**
   - Source: https://github.com/vercel-labs/agent-skills
   - Upstream ref: `063bee94c3f4df8453406c830b0a7df0f2860278`
   - Installed: `SKILL.md`
   - Purpose: UI/UX, accessibility, responsive behavior, typography, interaction, and interface quality reviews.
   - Note: the upstream skill intentionally fetches the latest Web Interface Guidelines when a review runs.

### Architecture and domain design

4. **improve-codebase-architecture**
   - Source: https://github.com/mattpocock/skills
   - Upstream ref: `4588b32ecab9ecc9fc8cc6b6c5e7d675b6004b0d`
   - Installed with `HTML-REPORT.md`
   - Purpose: architecture review and deepening opportunities.

5. **codebase-design**
   - Supporting architecture vocabulary and interface/seam design.

6. **grilling**
   - Supporting decision workflow used by the architecture skill.

7. **domain-modeling**
   - Supporting glossary and ADR workflow used by the architecture skill.

### Diagnosis, implementation, and review

8. **diagnosing-bugs**
   - Source: https://github.com/mattpocock/skills
   - Upstream ref: `4588b32ecab9ecc9fc8cc6b6c5e7d675b6004b0d`
   - Installed with its HITL loop script.
   - Purpose: reproduce failures, establish a tight pass/fail feedback loop, test hypotheses, and prove root cause before patching.

9. **tdd**
   - Source: https://github.com/mattpocock/skills
   - Upstream ref: `4588b32ecab9ecc9fc8cc6b6c5e7d675b6004b0d`
   - Installed with `tests.md` and `mocking.md`.
   - Purpose: behavior-first red → green development at agreed public seams.

10. **code-review**
    - Source: https://github.com/mattpocock/skills
    - Upstream ref: `4588b32ecab9ecc9fc8cc6b6c5e7d675b6004b0d`
    - Purpose: pre-merge review against repository standards and intended behavior/spec.

### Test specialists

11. **playwright-testing**
    - Source: https://github.com/TerminalSkills/skills
    - Upstream ref: `a021875c0f1bd906248e3784ce470faa65055201`
    - License declared by upstream skill: Apache-2.0
    - Purpose: reliable browser E2E tests, locators, auth reuse, network mocking, responsive coverage, visual regression, accessibility, and CI.

12. **pytest-patterns**
    - Source: https://github.com/hieutrtr/ai1-skills
    - Upstream ref: `d8244c1acdb4e4fac55de84dd49887e91bf7b941`
    - License declared by upstream skill: MIT
    - Installed with referenced FastAPI/pytest templates and coverage script.
    - Purpose: FastAPI endpoint tests, fixtures, async pytest, parametrization, mocking, factories, and coverage practices.

## Routing summary

- UI/UX change → `web-design-guidelines`
- React/Next.js implementation → `vercel-react-best-practices`
- React module/interface design → add `vercel-composition-patterns`
- Broken/failing/slow behavior → `diagnosing-bugs` first
- Behavior change with a testable seam → `tdd`
- FastAPI/Python tests → add `pytest-patterns`
- Browser/E2E/responsive regression → add `playwright-testing`
- Architecture change → `improve-codebase-architecture` + `codebase-design`
- Non-trivial change before merge → `code-review`

## Updating

To refresh from upstream in a local checkout:

```bash
npx skills add https://github.com/vercel-labs/agent-skills --skill vercel-react-best-practices
npx skills add https://github.com/vercel-labs/agent-skills --skill vercel-composition-patterns
npx skills add https://github.com/vercel-labs/agent-skills --skill web-design-guidelines

npx skills add https://github.com/mattpocock/skills --skill improve-codebase-architecture
npx skills add https://github.com/mattpocock/skills --skill codebase-design
npx skills add https://github.com/mattpocock/skills --skill grilling
npx skills add https://github.com/mattpocock/skills --skill domain-modeling
npx skills add https://github.com/mattpocock/skills --skill diagnosing-bugs
npx skills add https://github.com/mattpocock/skills --skill tdd
npx skills add https://github.com/mattpocock/skills --skill code-review

npx skills add https://github.com/TerminalSkills/skills --skill playwright-testing
npx skills add https://github.com/hieutrtr/ai1-skills --skill pytest-patterns
```

Review upstream changes before committing an update, because agent skills are executable instructions for privileged development agents.
