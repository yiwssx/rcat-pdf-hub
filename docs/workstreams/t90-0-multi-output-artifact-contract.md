# T90-0.3 — Multi-output Artifact Contract (design-only)

**Date:** 2026-10-22  
**Parent tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172)  
**Prerequisites (stacked, not necessarily merged):** #173 (90-tool matrix), #174 (planning registry), #175 (typed parameter contract)  
**Status:** Reviewable contract + reference tests. **Not implemented in production.**

## Verified legacy behavior and why a new seam is necessary

- `JobRecord.output_file_id` in `apps/api/app/models.py` is a **single** nullable FileRecord reference; `JobOut` and `routers/jobs.serialize` expose the same.
- `worker_tasks._output_spec` returns `.zip` / `application/zip` **only for** `pdf-to-images`; all other 12 processing operations produce one `.pdf`.
- `pdf_tools.pdf_to_images` places page images into a ZIP, but records **one** output FileRecord, not one FileRecord per page.
- `pdf_tools.split` produces **one selected-page PDF**, not an independent PDF per page.
- Owner and retention checks currently live in `routers/jobs.py` / `routers/files.py`, with files downloaded from `/api/v1/files/{file_id}/download`. We must not weaken them by serving documents merely because an artifact list contains an ID.
- Current `worker_tasks` malware checks, quota checks, output FileRecord creation, audit, webhook, and cleanup are bound to **one output**.

**No claim that the present backend already supports per-page independent downloads or multi-file results.**

## Proposed manifest interface

Canonical proposed schema: [`contracts/pdf-output-manifest.v1.schema.json`](../../contracts/pdf-output-manifest.v1.schema.json). An immutable view of a **completed** job only:

| Field | Meaning |
| --- | --- |
| `schema_version` | Versioned protocol, currently 1.0.0 |
| `job_id` | Existing job UUID |
| `status` | `completed` only; no partial job manifest |
| `requested_by` | Authoritative job owner (do not derive from client request) |
| `generated_at` | Timezone-aware generation timestamp |
| `primary_file_id` | Existing `JobOut.output_file_id` backward-compatible primary link |
| `artifacts[]` | One or more FileRecord-backed results with UUID, `role` (`result`, `part`, `bundle`), safe display name, exact MIME, byte length, SHA-256, owner, expiry and optional part ordinal |

A `bundle` has MIME `application/zip`; a single historical PDF is `role=result`. A current PDF-to-images ZIP is `role=bundle` **with one artifact only**. A future multi-export may have numbered `part` records and an optional `bundle`; the primary is bundle when present, otherwise the first part. Part order is explicit and must be contiguous.

**The manifest must not contain** stored object names, filesystem paths, signed tokens, download URLs, arbitrary renderable HTML, absolute/relative paths or unverified user-supplied metadata. Filenames are display-only; Thai Unicode names are permitted after safe-basename validation. Each file remains available only through the existing independently scoped and time-bounded file-download mechanism.

## Future database/worker implementation design (not in this PR)

1. **Data seam:** create a transactional `job_output_artifacts` linkage (proposed: job_id, file_id, role, ordinal; uniqueness on job/file and per-job ordinal for parts). Keep `JobRecord.output_file_id` as a maintained backcompat primary pointer. Treat FileRecord ownership, quota and expiry as authoritative.
2. **Staged output:** generate each result under unique temporary names; validate MIME signatures and file size; malware-scan **each** result plus compressed-bundle content policy; reject archive bombs/path traversal; calculate hashes and total stored bytes (ZIP + child files count).
3. **Bounded batch:** cap artifact count (initial **design ceiling 200**, subject to resource load tests); enforce storage quotas against **aggregate** bytes before commit, memory/disk/time ceilings per queue and tenant.
4. **Atomic finalize:** within a DB transaction, record all FileRecord rows + job-artifact associations, primary output and completed job state. Cleanup staged/permanent objects on failed/cancelled/retried attempts, including across local/NAS/S3 backends. Reconcile orphaned storage safely after process crash. Ensure repeated execution/retry is idempotent and cannot reveal an incomplete manifest.
5. **Authorization:** authenticate + owner-check job; fetch linked child FileRecords; enforce their source_system and expiry independently **for every item**. Human Admin identity must not inherit cross-tenant result visibility implicitly. A privileged service cross-owner use, if retained, must follow the existing narrowly defined policy and audit path.
6. **Read-only endpoint option:** `GET /api/v1/jobs/{job_id}/artifacts` responds with manifest only after completed, with exact owner+scope check. Existing `GET /api/v1/jobs/{id}` and `GET /api/v1/files/{file_id}/download` stay backward-compatible. Do **not** implement this proposed endpoint before security review.
7. **Telemetry:** log only job/file IDs and bounded metadata; capture per-child download/audit counts and aggregate quota, not file contents, URL secrets or absolute paths. One canonical job completion webhook, not a cascade of misleading independent completions.
8. **Release:** one tenant-isolated operation first, validated locally/CI/Compose with PNG/JPG + PDF + ZIP, Thai names, deletion/retention races, expired files, malware rejection, cancellation, distributed object-store failure recovery, and controlled rollback.

## Planning inventory implications

The 90-tool registry now distinguishes `artifact_contract.current_delivery` from `artifact_contract.target_cardinality`. The current source-mapped distribution is **24 `legacy_pdf`, 2 `legacy_zip`, 64 `none`**. These indicate *code paths*, not user-facing complete tool parity. Four projected multi-output targets have a migration requirement; this flag **never** enables a route or promises actual multi-output functionality.

## Contract acceptance (this PR)

- [x] Versioned strict proposal with exact field names and no signed links/paths.
- [x] Cross-check 90 entries and current `_output_spec` against existing source; enforce 13 operations unchanged.
- [x] Pure reference validator enforces job completion, job-artifact linkage and persisted FileRecord provenance, owner consistency, expiry/timezone, safe Unicode file names, immutable hashes/sizes, primary pointer, ZIP media, part ordinal and uniqueness.
- [x] Regression tests for one PDF, historical ZIP, proposed multi-export, malformed/foreign/expired/unlinked outputs and fake runtime enablement.
- [x] Keep runtime handlers, ORM models, migrations, Docker, and Web untouched; no deployment.
- [ ] Developer review of transaction/linkage model and authorization gates.
- [ ] Real SQL migration, S3 idempotency, artifact storage/retrieval, route and E2E **deferred to a separate, explicitly authorized implementation PR**.
- [ ] Build+CI and owner acceptance evidence before merging this documentation/validation layer.

Tests: `make validate-tool-registry` or `make validate-ops` (after stacked PRs are checked out). A passing *contract* test is **not** proof of runtime multi-download support.
