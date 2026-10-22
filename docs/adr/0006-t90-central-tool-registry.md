# ADR-0006: T90 central capability registry, planning seam and compatibility gates

- **Status:** Proposed / design and contract groundwork only (2026-10-22)
- **Scope:** T90-0 under [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172)
- **Related:** ADR-0001 ToolWorkspace, ADR-0002 queue classes, ADR-0003 worker pools, ADR-0005 task-first journeys, [T90 inventory](../workstreams/pdf-90-tools-master-tracker.md)
- **Out of scope:** enabling new tools, shipping 90 tool cards, replacing the job executor, migrating the DB, altering auth/production Compose, deploying

## Decision

Establish `contracts/pdf-tools.v1.json` as the **authoritative planning inventory** for 90 canonical tool IDs and slugs (M01–M33, T01–T40, F01–F17). Every entry describes:

- canonical ID, slug and English title, category, priority, maturity, adapter proposal, row-specific acceptance;
- known existing UI route(s) and backend operation(s), without assuming parity;
- explicitly **proposed**, non-executable input MIME/count, output MIME/cardinality, queue workload hint and security-review flag;
- `runtime_enabled=false` on all 90 entries.

Preserve 13 user-facing legacy cards and 13 existing backend operations, with current UI and job routing code remaining authoritative. `scripts/validate-tool-registry.py` compares the registry to the human-readable T90 tracker and to concrete legacy frontend/worker sets; `scripts/tests/test_tool_registry.py` asserts fail-closed behavior for drift, duplicate identity, unsafe activation and missing/malformed contracts.

**No runtime reads or executes registry adapters** at this stage. This prevents unverified routes and permissions from appearing before a future adapter seam is implemented and tested.

## Deep module design (next independent PR)

A future `ToolCapability` module should hide discovery and parameter normalization behind a small reviewed interface rather than layering conditional checks across Web, routers, queue and workers:

1. Lookup by canonical tool ID/slug (with explicit aliases for legacy routes), returning approved metadata and capability state.
2. Validate an authorized request against per-tool input signature, count, encrypted-file policy, page/file limits and typed options before queue submission.
3. Plan the execution using an **approved** engine adapter mapping and queue class. Never dispatch shell arguments or Python imports derived from user-controlled registry strings.
4. Record output artifacts (including multiple outputs and optional ZIP) under existing owner-scoped file/job security, quotas, expiry and audit semantics.
5. Publish a tool only after independently reviewed implementation + functional/Thai document fidelity/security/accessibility/runtime acceptance and explicit release approval.

A single source of truth can generate read-only language-specific bindings later; do **not** change container build contexts or duplicate runtime policy tables before the executable seam is agreed. Proposed MIME/workload fields are deliberately not authoritative validators.

## Guardrails and risks

- Existing route slugs and /api/v1/pdf contracts must remain stable; old `split-rotate`, `office-to-pdf` etc. may serve multiple future task entries without claiming each variant is fully implemented.
- Avoid confusing `BASELINE` (source code exists) with `VERIFIED` or `RELEASED`. Public tool count remains based on the unchanged 13-card catalog, **not** the 90 planning records.
- Read-only, fail-closed planning guard has no side effects. Registry proposals with generic `application/octet-stream`, one-file bounds or MIME differences require focused engine review before implementation.
- Maintain strict tenant ownership and scopes, auditable actions, short-lived downloads, ClamAV scanning, resource ceilings and all CI/release gates.
- Treat URL-to-PDF as SSRF risk, archives as decompression/path-traversal risk, PDF whiteout as **not redaction**, and visual stamps as **not cryptographic signing**.
- Verify third-party tool licenses (including potential copyleft/commercial obligations) and Thai-fidelity tests before selecting a new adapter.
- Keep existing Candy UI v3 styling and UI-unification tracker independent. Reuse ToolWorkspace and existing job journey seams rather than a UI rewrite.

## T90-0 acceptance and outstanding actions

- [x] 90 unique canonical IDs/slugs, 33/40/17 sections and exact alignment with human-readable tracker.
- [x] Record existing 13 routes and 13 operations, with explicit compatibility validation.
- [x] Each tool has proposed input/output/workload and separate security-review flag.
- [x] Fail closed on attempts to activate planned entries; no deploy/migrations or new runtime capabilities.
- [x] Pure standard-library validator and negative mutation tests integrated with development validation.
- [ ] Approve detailed, type-safe parameter schema **per tool** and per-format signature rules.
- [ ] Approve multi-output artifact manifest/schema and owner-scoped download migration path.
- [ ] Decide executable adapter interface and runtime source generation strategy after integration tests.
- [ ] Perform baseline CI and runtime acceptance; validate current PR against latest main and separately merge the upstream tracker PR.
- [ ] Production release approval remains separate and is **not** implied by this ADR.
