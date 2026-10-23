# T90-0.12 — 200 raster pages + primary ZIP manifest boundary

**Parent:** [Draft PR #184](https://github.com/yiwssx/rcat-pdf-hub/pull/184) · **Master tracker:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) · **Scope:** one bounded correctness fix.

## Root cause

The generated raster ZIP extractor accepts **up to 200 page images** (`MAX_ARTIFACTS=200`). The completed Job records both the **legacy ZIP bundle** (one primary output) and the **individual PNG/JPG parts** (up to 200). At the supported maximum, this yields **201 FileRecord associations**.

Three separate validation boundaries still capped the *whole manifest* at 200, silently misinterpreting the page cap as the overall number of artifacts:

- `GET /api/v1/jobs/{job_id}/artifacts`: `.limit(201)` followed by `len(links) > 200` rejects the full result.
- Pydantic `JobArtifactManifestOut.artifacts`: `max_length=200` would reject the response even if the route check were relaxed.
- `contracts/pdf-output-manifest.v1.schema.json` and the planning-only validator: `maxItems=200` and `MAX_ITEMS=200`.

## Changes and invariants

- Set `MAX_JOB_ARTIFACTS = 201` in the API response schema; route fetches `MAX_JOB_ARTIFACTS + 1` rows and refuses any excess.
- Align planning JSON Schema and stdlib contract validator to 201 manifest items, **without** increasing the maximum ordinal/page count (still **200**).
- Preserve the singular bundle/result primary, part-ordinal contiguous ordering, same-owner check of **every** file, existing authorized download behavior, no stored keys or signed links in the manifest.
- API regression checks 1, 199 and **200 pages** (root + parts), schema refusal of 202 items, and a foreign-owned 200th image; pure contract tests verify both boundary acceptance and 201-page rejection.
- No data migration, queue changes, S3 changes, activation of dormant 90-tool operations, or alteration of the supported PDF-to-images page cap.

## CI acceptance

- [ ] Backend and response-schema regression tests pass.
- [ ] Planning-only artifact contract validator and tests pass.
- [ ] PostgreSQL migration, real Valkey/RQ + self-hosted SeaweedFS test gate remain green.
- [ ] Host Python, Gotenberg, OpenAPI/full backend validation pass.
- [ ] Draft PR, no merge/deploy/Production feature enablement. Stop after this item.

**Availability:** correction is only in this stacked Draft branch until separately reviewed and merged. Existing `PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED=false` and `PDFHUB_ARTIFACT_WRITE_JOURNAL_ENABLED=false` defaults stay OFF.
