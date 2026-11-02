# T90-3 F09 — staged backend PDF to multipage TIFF

**Scope:** backend development, default OFF. No public catalog entry, no host
deployment and no `VERIFIED` or `RELEASED` claim.

## Full path

1. `POST /api/v1/pdf/from-pdf/tiff` accepts one previously uploaded,
   owner-matched, nonexpired PDF; validates true PDF MIME, suffix, file budget
   and strictly typed 72–300 DPI.
2. Existing audited `_create_job` persists the request and enforces job
   quotas; the F09 queue class is **heavy** when individually enabled.
3. Worker independently rechecks owner, expiry, MIME, suffix and the original
   PDF file signature before executing `from_pdf_tiff.pdf_to_multipage_tiff`.
4. The converter uses bounded Poppler subprocess and actual multi-frame TIFF
   verification, including page inventory. Job output is stored under
   `image/tiff` with `.tiff`, not falsely advertised as a PDF.
5. Existing artifact storage, malware scan, cancellation, auditing, expiry,
   file owner and output download controls remain unchanged.

## Opt-in stage configuration

```dotenv
PDFHUB_FROM_PDF_TOOLS_ENABLED=false
```

The default remains OFF in Pydantic settings, Compose and environment examples.
Do not activate without a staging acceptance run with real Thai PDFs, source
vs page-image visual comparisons and live owner/download verification. T90-5
#262 governs independent confirmation and release approval.

**Known quality limits:** raster-only output; selectable DPI 72–300,
no preservation of editable text or native PDF vectors; max 40 pages,
24 MiB input, 100 million total rendered pixels and 64 MiB TIFF output.
