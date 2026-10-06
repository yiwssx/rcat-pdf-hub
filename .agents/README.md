# Project-local agent skills

These skills are vendored for development-agent guidance. They do not run in production and are not application dependencies.

## Primary requested skills

1. **vercel-react-best-practices**
   - Source: https://github.com/vercel-labs/agent-skills
   - Upstream ref: `063bee94c3f4df8453406c830b0a7df0f2860278`
   - Installed files: `SKILL.md` and the full compiled `AGENTS.md`.
   - Use for React/Next.js implementation, review, performance, data fetching, rendering, and bundle decisions.

2. **improve-codebase-architecture**
   - Source: https://github.com/mattpocock/skills
   - Upstream ref: `4588b32ecab9ecc9fc8cc6b6c5e7d675b6004b0d`
   - Installed with `HTML-REPORT.md`.
   - Use for architecture review and deepening opportunities.

## Supporting skills

The architecture skill explicitly depends on the following vocabulary/workflow skills, so they are vendored as support:

- `codebase-design`
- `grilling`
- `domain-modeling`

## Updating

To refresh from upstream in a local checkout, run:

```bash
npx skills add https://github.com/vercel-labs/agent-skills --skill vercel-react-best-practices
npx skills add https://github.com/mattpocock/skills --skill improve-codebase-architecture
npx skills add https://github.com/mattpocock/skills --skill codebase-design
npx skills add https://github.com/mattpocock/skills --skill grilling
npx skills add https://github.com/mattpocock/skills --skill domain-modeling
```

Review upstream changes before committing an update, because agent skills are executable instructions for privileged development agents.
