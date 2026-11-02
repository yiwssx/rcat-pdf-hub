# T90-3 F16 — PDF to animated GIF (source-code stage)

- **End-user contract**: one uploaded owner-bound PDF becomes **one animated GIF**. Each accepted PDF page is one 256-color raster frame, at 72–150 DPI; frame duration 300–5000 milliseconds.
- **Not an editable conversion**: output is lossy raster animation, not PDF text/links/vector reconstruction; no alpha or ICC fidelity guaranteed.
- **API**: `POST /api/v1/pdf/from-pdf/gif` with `file_id`, `dpi` (default 96), `frame_ms` (default 1200); authorized `pdf:pdf-to-image` role; owner and expiry checked both on submit and in the worker.
- **Queue**: `pdf-to-gif` heavy, output `.gif` / `image/gif`; existing artifact retention, malware scan, quota and owner-bound downloads reused.
- **Security/abuse limits**: independent `PDFHUB_FROM_PDF_TOOLS_ENABLED=false` default, strict PDF parser, no encrypted documents, ≤24 MiB, ≤20 pages, ≤6M pixels/page, ≤40M pixels total, 72–150 DPI, 75s Poppler deadline, non-shell subprocess with CPU/AS/NOFILE/FSIZE limits, fixed temp page filenames, no symlinks, exact sequential frame and page count, exclusive destination creation, ≤48 MiB GIF.
- **Behavior on repeated identical pages**: GIF encoding can collapse identical frames; this converter **fails closed** if the saved GIF has fewer frames than the source PDF, rather than silently claiming 1:1 page fidelity.
- **Generated fixture test**: ReportLab two visibly different colored pages → actual Poppler → animated GIF with two independent frames, explicit frame duration, signed binary header, immutable input.
- **Still required for independent release**: real RCAT PDFs, Thai font/layout checks, owner-scoped institutional OIDC upload/queue/download, AV/load, operator staging deployment and source-vs-raster comparisons.

This is a narrowly scoped engineering implementation, not a new enabled production tool or a T90-5 VERIFIED / RELEASED approval.
