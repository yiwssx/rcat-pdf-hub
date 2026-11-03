# T90-3 F17 PDF → BMP page ZIP (code-only stage)

The BMP file format does not support a reliable multipage artifact. This
feature produces **one ZIP archive with exactly one BMP image per PDF page**,
named `page-0001.bmp`, `page-0002.bmp`, etc. No first-page-only fallback.

- **Input**: one already-verified, owned, unexpired PDF; max 24 MiB, 20 pages.
- **Output**: `.zip`, `application/zip`, single owner-bound output/download;
  individual BMP page files available **inside** ZIP, not falsely advertised
  as independently signed outputs.
- **Limits**: 72–150 DPI, 6M pixels per page and 40M aggregate; Poppler 75s,
  no shell, CPU/memory/filesystem/no-file limits, 16 MiB PNG intermediates,
  ≤20 MiB BMP per page, ≤128 MiB ZIP total.
- **Safety**: ZIP_STORED with only fixed generated names and checked BMP
  headers, ordered complete inventory, CRC verification, never extract
  uploaded archives or interpolate user paths. Exclusive output file creation.
- **API**: `POST /api/v1/pdf/from-pdf/bmp`, `pdf:pdf-to-image` scope,
  file_id + strict DPI; default-OFF `PDFHUB_FROM_PDF_TOOLS_ENABLED`.
- **Runtime**: heavy queue, persisted MIME/signature and owner checks at
  both API and worker; inherits existing malware scan, quota, audit, expiry,
  retention and authenticated ZIP download.
- **QA**: generated 2-page and 10-page PDF sources tested against real
  Poppler→BMP ZIP, full page order/headers, image pixel differences and
  original source immutability; refuse encrypted, bad DPI, symlinks and
  mismatched owner/persisted MIME.
- **Cross-cutting bug fixed**: Poppler zero-pads generated page names above
  nine pages. F09 TIFF and F16 GIF now accept leading-zero numbering but
  still reject duplicates or missing indices.

Physical release still requires original RCAT files, Thai font/source-page
goldens, institutional SSO end-to-end and target-host AV/operator review.
This is not production activation and does not imply T90-5 VERIFIED/RELEASED.
