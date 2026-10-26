# Protected-main required checks verification — 2026-10-26

Related: [Issue #214](https://github.com/yiwssx/rcat-pdf-hub/issues/214) and [Migration tracker #195](https://github.com/yiwssx/rcat-pdf-hub/issues/195).

This is a documentation-only pull-request trigger to prove that all ordinary API/Web/CodeQL/Dependency Review checks run without path filters. The source code, CI workflows, dependency manifests, Docker images, secrets, production server and T90 flags are unchanged.

## Verified baseline

- Protected main commit at creation: `f8bf1969e910744a0685c92bf311b76ba287e023`.
- Active GitHub ruleset: `25837608`, strict updated-to-main policy and zero bypass actors.
- Required checks before administrator's final change: 9 contexts.
- **Still missing from the ruleset**: `Build and check Thai Office converter image` (GitHub Actions App ID `15368`).
- Desired end state: 10 required contexts, with no reduction of existing security gates.

## Acceptance to record in Issue #214

- [ ] Observe CodeQL Python and JavaScript/TypeScript succeeded on this exact PR HEAD.
- [ ] Observe Dependency Review succeeded on the exact PR HEAD.
- [ ] Observe Core API `api`, Thai Office converter build, and Python 3.11–3.14 host-tooling checks succeeded on the exact PR HEAD.
- [ ] Observe Web CI `web` succeeded on the exact PR HEAD.
- [ ] Administrator adds the one missing Thai Office context under Ruleset #25837608 and a fresh read proves 10 contexts with `integration_id: 15368` and `strict_required_status_checks_policy: true`.
- [ ] Re-evaluate a fresh PR HEAD after ruleset becomes 10/10 and confirm all ten checks are required and passing.

No merge is authorized solely by this diagnostic. Keep `runs-on: ubuntu-latest` in primary workflows and distinguish compatibility-probe Ubuntu 26.04 from the actual runner image chosen by GitHub.