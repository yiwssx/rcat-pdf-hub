# T90-0.15 — Static operation adapters and pre-expansion contract

**Workstream:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Previous:** [Draft PR #191](https://github.com/yiwssx/rcat-pdf-hub/pull/191)

## Change

The current Worker handles **13 actual PDF operations** using one large conditional block. This change extracts only the **conversion invocation** into `app.operation_adapters.execute_operation`; the operation→handler map is an explicit 13-entry static allowlist, not dynamic imports, arbitrary eval, a runtime enabled 90-tool registry, or a plugin-loader permission boundary.

- One adapter per existing operation: `merge`, `organize`, `split`, `rotate`, `compress`, `ocr`, `pdfa`, `office-to-pdf`, `watermark`, `page-numbers`, `stamp`, `images-to-pdf` and `pdf-to-images`.
- Maintain existing argument order, defaults and `pdf_tools` execution engine. Keep `worker_tasks.pdf_tools` module alias for callers/tests that patch the legacy module symbol.
- Reject unknown operation IDs, non-object parameters and invalid input-file count (e.g., merge 2–50; stamp 2; image-to-PDF 1–100) **before** dispatching. Do not trust user-specified function or module names.
- All upload/owner/expiry checks remain at API boundary; Worker still owns job lifecycle, queue, live lease/heartbeat, scanner, per-file quota, journaled S3 compensation, audit, FileRecord and secure manifest commit.
- `queue.SUPPORTED_OPERATIONS`, API `OPERATION_SCOPES` and new `ADAPTERS` must remain exactly equal, enforced by regression. No new operation is enabled.

## Future expansion contract

1. New tool starts in planning-only `contracts/pdf-tools.v1.json`, with reviewed source MIME signature, typed parameter contract, expected output (single/ZIP/multi), required scopes and intended queue class.
2. Implement a bounded engine function, insert an **explicit** reviewed adapter definition, map it to a queue and API scope, and add contract and binary-output tests. Never execute arbitrary callable strings from the planning registry.
3. Add a tested API route and common Candy UI v3 entry point **only after** validated engine and authorizations; don't count a placeholder route as an implemented tool.
4. Preserve job status, fencing, result authorization and independent S3 artifact tests, no direct path or signed URLs in manifests.
5. Each actual tool requires end-to-end acceptance and separate `RELEASED` evidence, not just CI or PR merge.

## Compatibility and release boundaries

Existing file signatures, supported formats, PDF binary processing, `_output_spec` return shape, queue names, FileRecords, endpoints, job-operation values and flags remain unchanged. This task does **not** activate any of the 90 planning-only tools, redesign the frontend, add a dependency, modify DB schema or deploy.

Remaining Phase 0 requirement T90-0.16: independent architecture/sign-off and a bounded acceptance decision: reviewed gaps, known unsupported formats and clear T90-1 start criteria. Backend and real-stack CI are required to pass on the combined Draft branch.
