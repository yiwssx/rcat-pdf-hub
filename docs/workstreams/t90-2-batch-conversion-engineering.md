# T90-2 conversion engineering — batch 1 (2026-10-28)

Master [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172); execution [#237](https://github.com/yiwssx/rcat-pdf-hub/issues/237).

## Current engineering delta — opt-in only

Five separate **staged HTTP/API/worker operation identities**, implemented without changing any legacy 13-operation adapter:
- T14 TXT: `txt-to-pdf` (UTF-8, Thai Unicode, escaped XHTML via trusted Chromium Gotenberg).
- T17 CSV: `csv-to-pdf` (UTF-8, comma delimiter, escaped table, header repeat CSS).
- T26 JFIF: `jfif-to-pdf` (JPEG image signature and decoder check).
- T27 GIF: `gif-to-pdf` (all frames; strict 64-frame/50MP aggregate bounds).
- T13 TIFF: `tiff-to-pdf` (all frames; no modification to legacy one-image-per-file behavior).

`PDFHUB_TO_PDF_TOOLS_ENABLED=false` by default; new endpoint paths are absent from production OpenAPI. Isolated staging opt-in endpoints live under `/api/v1/pdf/to-pdf/{txt,csv,jfif,gif,tiff}`; TXT/CSV require existing `pdf:convert` scope; JFIF/GIF/TIFF require existing `pdf:image-to-pdf` scope and owner-verified persisted input MIME/extension, quota, job, queue, worker owner/expiry and revalidation, scan and artifact handling. No arbitrary URL/HTML/JS/archive conversion. This is NOT five end-user features released or deployed, and no UI card, migration or production config was changed.

### Defensive limits

- TXT/CSV max 2 MiB UTF-8, 200k characters; ASCII controls except LF, CR, TAB rejected.
- CSV comma-only (explicit, not auto-detected), max 1000 rows, 20 columns, 2000 chars/cell; formulas displayed as literal strings, not interpreted.
- GIF/TIFF/JFIF max 30 MiB, 64 frames, 20 MP/frame, 50 MP aggregate; all decoded images staged in a disposable sandbox directory. GIF uses composed frames produced by Pillow and flattens alpha to white. A 40 MiB PDF output cap applies.
- Gotenberg HTML produced only by backend, escaping every user-originated cell/text. No HTTP remote fetch requested, no external CSS/image URLs, no user supplied JavaScript/HTML.
- Decode/output signatures and PDF page count independently parsed; original content immutable. Staging flag can be revoked between enqueue and execution.

### Outstanding to call individual tools VERIFIED

- Actual font-golden PDF corpus against Thai Sarabun/Noto Sans Thai, text extraction, combining-character shape, layout, line wraps, font/substitution and visual diff on production-equivalent Gotenberg image.
- Deployed isolated Compose journey (auth/upload/queue/RQ/postgres/Valkey/S3/download/cancel/expiry), malware, concurrent load and malicious input coverage; UI browser keyboard/mobile parity.
- Additional P0 T01/02/03/05/06/07/08/15/18/24/28 and all other P1/P2/P3 conversion families require separate concrete implementation/evidence. Never infer 40/40 from generic Office or image adapter.
- P2 archive/URL/XML/EML requires licensed bounded decoders, SSRF/DNS-rebinding/XXE controls, no unsafe decompression; P3 specialist executables require documented license/format support. No enablement or installer in this batch.
- Master matrix remains 0/90 RELEASED until T90-5 production signoff. T90-1 acceptance remains independent (#225).

### Rollback

Keep `PDFHUB_TO_PDF_TOOLS_ENABLED=false`. If engineering regression appears, revert the reviewed PR; no existing input/output contracts or migrations need rollback. Do not enable on production or claim users can access the five staged endpoints until deployment and acceptance.
