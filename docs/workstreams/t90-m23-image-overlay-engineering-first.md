# T90 M23 — Add image to PDF (Engineering First)

**2026-11-09.** Engineering implementation, not a Production release or sign-off. New branch capability: bounded, real JPEG/PNG XObject overlay on a selected page of an ordinary PDF.

## Real source/Output contract

- Input: one owner-bound, MIME-and-signature-verified PDF up to 16 MiB, max 80 pages; one **separate** owned JPEG/PNG up to 8 MiB, max 20 million decoded pixels, unexpired, matching stored MIME and filename suffix.
- User parameters: exact 1-based page number, X/Y coordinates, width and height in PDF points. Origin is bottom-left; position must fit wholly on page. Defaults on Web: page 1, x/y 30, width 120, height 80.
- Backend: `app.services.pdf_image_overlay.add_image_to_pdf` validates actual still-image decoder, no symlinked/overwritten inputs, rejects signed/interactive/encrypted/annotated/rotated/cropped/offset source pages; places the image with ReportLab and pypdf page composition; verifies output is a real PDF with unchanged page count and an image XObject, without mutating source or other page content. Output max 40 MiB.
- Workflow: two owned stored sources `[pdf_id,image_id]` → `POST /api/v1/pdf/advanced/add-image` with `pdf:stamp` → existing quota/audit/queue/worker/artifact pipeline → `/jobs/{id}/result`. Both intake and worker independently check ownership, expiry, MIME, signature, limits and exact params.
- Web: single guarded `/staged/image-overlay` form with existing login/upload/files/job/result and two-source selection; no new queue, database, external converter or paid dependency.

## Deliberately unsupported

This **does not** edit original images/text, preserve digital signatures, perform secure redaction, support arbitrary vector/SVG/GIF/web content, decode encrypted PDFs, handle any annotations, forms or rotation, or guarantee Thai visual fidelity. Image overlay is not a content removal tool. We do not advertise full PDF editor equivalence.

## Independent default-OFF gates

- Backend: `PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED=false` by default; absent from OpenAPI when OFF.
- Web: `PDFHUB_STAGED_IMAGE_OVERLAY_WEB_ENABLED=true` plus backend flag `PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED=true` required by the server-side page. Neither was enabled or deployed in this change.
- Existing four GitHub protected checks + basic real binary tests required before merge.
- Actual RCAT school accounts, Thai source/visual originals, Production Compose, operator approval, performance/AV/DR and staged release remain separate QA [#262](https://github.com/yiwssx/rcat-pdf-hub/issues/262)/[#308](https://github.com/yiwssx/rcat-pdf-hub/issues/308). Code completion must not be called VERIFIED/RELEASED.

Engineering inventory [90-tool baseline](t90-engineering-first-inventory.md) should reclassify M23 from MISSING to CODE COMPLETE **only after Web, worker and basic CI pass**; independent T90 ledger remains a separate QA evidence record.
