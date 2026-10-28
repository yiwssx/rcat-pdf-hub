# T90-1.1 — M04 Merge PDF: binary and API security acceptance

Tracker: [T90-1 #225](https://github.com/yiwssx/rcat-pdf-hub/issues/225) · Parent: [T90 #172](https://github.com/yiwssx/rcat-pdf-hub/issues/172)

## Scope of this bounded change

This change **adds regression tests only** to the existing `merge` API, `qpdf` engine and static worker adapter. No new PDF operation, output type, UI route, entitlement, database schema, dependency, infrastructure, or feature activation.

### Binary acceptance: `test_t90_1_merge_acceptance.py`

- Exercise the **real qpdf executable** (not a mocked response) against 2 input PDFs with 3 differently sized output pages. Verify PDF header, strict pypdf parsing, exact source page order, extractable page labels, mixed MediaBox geometry and original byte-for-byte immutability.
- Reject a deliberately corrupt PDF and an encrypted/password-protected PDF when no password is supplied. A failure must not be reported as a completed merge.
- The binary tests deliberately **skip on host machines without qpdf**; they must actually **run, not skip** in the pinned API CI container, which includes qpdf.

### Authenticated API acceptance

- Exercise the real FastAPI request schema, scope dependency, persisted FileRecords and JobRecord; only external RQ queue dispatch is replaced by a test double.
- Confirm a principal lacking `pdf:merge` receives 403 before enqueue.
- Confirm cross-owner files receive 403 and disguised non-PDF uploads receive 415 before enqueue.
- Confirm allowed two-file request returns 202 and creates a `merge` job owned by its requester.
- Confirm foreign requesters cannot read the new job through the normal `GET /api/v1/jobs/{job_id}` route.

## CI and release decisions

- Required: Core API CI including actual qpdf tests, Python/backend, Gotenberg/Thai image, PostgreSQL and real storage/worker rehearsals; Web CI/CodeQL/Dependency Review must remain healthy where applicable.
- This is a **first engineering regression gate**, not an end-to-end downloadable output test, browser visual acceptance or Production signoff.
- Do **not** transition M04 from `BASELINE` to `VERIFIED` or `RELEASED` on this PR alone. Remaining M04 acceptance: authenticated real Compose worker-to-S3 result and download, cancellation/expiry, actual UI ordering and Thai/desktop/mobile visual checks, performance and release signoff.
- No merge before CI verification; no production deployment, database migration, feature flags, hidden security bypass or tool count increase.
