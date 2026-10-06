# ADR-0002: Route PDF jobs by workload class

- Status: Accepted
- Date: 2026-10-06

## Context

RCAT PDF Hub previously placed every asynchronous PDF operation on one RQ queue named `pdf`.

That kept deployment simple, but it also meant a long OCR, PDF/A, Office conversion, or large PDF-to-image job could sit ahead of lightweight page operations. The API had no explicit scheduling model beyond one global queue name, so future worker isolation would otherwise require routing logic to be added ad hoc across routers.

## Decision

Classify every supported PDF operation into one of three workload classes:

- `interactive`: organize, split, rotate, watermark, page-numbers, stamp
- `pdf`: merge, compress, images-to-pdf
- `heavy`: ocr, pdfa, office-to-pdf, pdf-to-images

Queue selection is centralized in `app.queue`. Routers submit work through `enqueue_processing_job(operation, job_id)` rather than selecting an RQ queue directly.

The configured queue names are:

- `PDFHUB_RQ_INTERACTIVE_QUEUE=pdf-interactive`
- `PDFHUB_RQ_QUEUE=pdf`
- `PDFHUB_RQ_HEAVY_QUEUE=pdf-heavy`

Queue names must be non-empty and distinct. Unknown operations fail closed instead of silently falling back to a queue.

During Task 6C.1 the existing worker listens to all three queues so routing can be introduced without creating unserved jobs or changing the API contract. Task 6C.2 will replace this transitional worker arrangement with dedicated worker pools.

Retries use the same routing function as newly created jobs, so a retried heavy job cannot accidentally move to the standard queue.

## Consequences

- Scheduling policy has one source of truth.
- The public API and persisted `JobRecord.operation` values remain unchanged.
- Queue depth can be observed per configured queue while the existing aggregate admin field remains available.
- Lightweight jobs are explicitly identifiable before worker-pool isolation is introduced.
- The transitional worker still permits head-of-line blocking inside one worker process; dedicated pools are intentionally deferred to Task 6C.2.

## Validation

Backend tests must cover the complete operation-to-class matrix, unknown-operation fail-closed behavior, configured queue-name selection, enqueue delegation, and distinct queue-name validation.

Compose validation must verify the transitional worker consumes all three configured queues.
