# T90-0.16 — Phase-0 Engineering Acceptance and Handoff to T90-1

**Canonical progress issue:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172). **Previous:** [T90-0.15 Draft PR #192](https://github.com/yiwssx/rcat-pdf-hub/pull/192). **This gate is NOT a Production release.**

## Technical decision and evidence

The Phase 0 **engineering design and Draft implementation** is ready to hand off to feature implementation in T90-1 once this stacked branch has passing CI. This is a deliberately narrower claim than "merged", "deployed", "90 tools working" or "Production approved."

| Requirement | Implemented evidence | Phase-0 outcome |
| --- | --- | --- |
| Exactly 90 canonical tools, 33 Manage / 40 to-PDF / 17 from-PDF | `contracts/pdf-tools.v1.json`, validator; IDs and slugs unique, all new runtime flags false | Design covered; **0/90 separately released** |
| Typed contracts and honest legacy projections | Parameter/format planning contract, registry validators and negative tests | Design covered; advanced formats still proposals |
| Multi-output result design and secure job listing | Manifest schema, DB association migration, owner-bound results, 201-item ZIP+200 pages boundary | Opt-in code tested; default feature flag OFF |
| Migration and data durability | PostgreSQL 18 rehearsal, fenced prewrite journal, lease heartbeat and explicit RQ-status-audited operator recovery | CI rehearsal passed; no Production migration signoff |
| Real crash/recovery evidence | Separate Valkey/RQ parent + forked work-horse SIGKILL, SeaweedFS PUT/lost-ACK, durable PostgreSQL journal | Four isolated synthetic scenarios, not a multi-node/outage soak test |
| Input/Office archive threat model | `apps/api/app/filetypes.py`, PDF MIME queue guard, ZIP member limits, malware scanner | Hardened preflight; complex parsers still require engine sandbox |
| Bounded executable adapter boundary | `app.operation_adapters`, 13 explicit handlers and queue/API mapping parity | New tools can be added by reviewed code, not by dynamic eval |
| Independent CI readiness gate | `scripts/validate-t90-phase-zero.py`, negative tests and Core API CI step | Fail closed on scope, unsafe flag activation and schema drift |

**Criterion for starting T90-1:** A reviewed tool ID, explicit API route/scope, signature-aware input, bounded queue and adapter, output contract, owner-safe download and regression evidence. Start with P0 capabilities and validate actual binary outputs; do not equate planning metadata or a passing static contract with functionality.

## Architecture constraints retained

- No arbitrary dynamic plugins, reflection or registry-to-code execution.
- Existing 13-operation API/queue names, owner/role checks, retention, quotas, audit, Thai Office converter integration and Candy UI patterns remain protected.
- No automatic RQ recovery, requeue, deletion of orphan S3 data or unbounded multi-output data migration.
- Whiteout masking must not be described as secure redaction. Visual signatures must not be represented as cryptographically signed PDFs.
- No unsolicited remote URL/XML/HTML fetching, SSRF/private-network access, embedded scripts, externally retrieved document content or optional proprietary converters without reviewed sandbox and license gates.

## Remaining release requirements are tracked in T90-5, NOT hidden as Phase-0 "done"

1. Mainline branch integration and review of the stacked Draft PR series, including parallel competing heartbeat branch [#185](https://github.com/yiwssx/rcat-pdf-hub/pull/185); validate there are no duplicate implementation conflicts. No forced merge.
2. Production-equivalent PostgreSQL backup/restore, safe migration lock/load tests, Multi-output / Journal flag opt-in staging rollout and explicit administrator approval.
3. End-to-end authenticated Compose, golden Thai PDF and Office corpus, visual fidelity, cancellation/retention/expiry, performance/large-file resource budgets and negative security tests across supported formats.
4. Redis outage/partition, RQ-parent kill, S3 intermittent failure, multi-host worker lease contention, CI/DR and recovery operational drills; existing isolated CI is not Production evidence.
5. Per-tool implementation/release accounting: only `RELEASED` with binary output, UX, security and regression acceptance counts. **Current T90 canonical released count remains zero.**

## Scope and explicit signoff

- **Phase-0 engineering / Draft readiness:** complete when static architecture + 90-tool contract + 13-operation dispatch + full backend/real-stack CI are green on this branch.
- **Branch integration/Production signoff:** NOT granted here. Each stacked PR remains Draft/open unless explicitly approved; no deployments, migrations, feature flag activation, data cleanup or auto-merges.
- **Next action after Phase 0:** T90-1 implementation of real end-user capabilities in reviewed batches; do not further expand the Phase 0 research list without a demonstrated blocker.

The Phase-0 tracker may record "engineering complete in Draft branch" after green CI while keeping merge/Production readiness explicitly **blocked pending review and approval**.
