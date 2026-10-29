# T90-2 — Batch 2: Markdown converter + P0 image binary acceptance

Tracks [#237](https://github.com/yiwssx/rcat-pdf-hub/issues/237). Parent [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172).

## Scope and actual guarantees

- **T36 Markdown → PDF**: explicit `md-to-pdf` static backend adapter under the existing `PDFHUB_TO_PDF_TOOLS_ENABLED=false` default-off gate; POST `/api/v1/pdf/to-pdf/md` uses existing `pdf:convert` authorization, typed `file_id`, owner and expiry checks before enqueue and worker execution, standard PDF output custody.
- UTF-8-only `.md` upload classified as `text/markdown` when explicitly opted in. Reuses bounded 2 MiB/200k-character TXT/CSV intake, control-character and wrong-MIME rejection.
- MarkdownIt 4.2.0 (already hash-locked through Rich, now explicitly a direct pinned dependency) renders **CommonMark + pipe tables** into trusted Gotenberg Chromium HTML. Markdown raw HTML is escaped. Link, autolink, image and linkify rules are disabled; attempted network references display as text, not browser-resource elements. An HTML CSP forbids all network loads, browser script and untrusted resources. No arbitrary user HTML, URL converter, shell or dynamic module loading.
- **P0 regression evidence**: existing `images-to-pdf` legacy engine is exercised with actual JPEG, PNG, WebP, BMP, single-frame TIFF PDFs: MIME signature checks, preserved source hash, page geometry, order, JPEG images re-embedded and sampled colors, transparent PNG/WebP flattening, invalid-header rejection. Legacy operation behavior is untouched; multiframe TIFF is already handled by the **separate opt-in T13** converter from prior PR #238.

## Safety and testing boundaries

- Test includes fake Gotenberg HTTP response for Markdown PDF signature/page count, malicious input/cross-owner/scope/queue and genuine worker DB/file artifact persistence; it is **not** a production-like Gotenberg font golden proof.
- No change to 13 legacy queue identities, auth scopes, RBAC, retention, quotas, Docker Compose topology, databases/migrations or Web public catalog. Do not claim Markdown released to end users.
- Still required: Thai/Sarabun/Noto text shaping, copied text + searchable content, long tables and page breaks in actual Gotenberg image; true Composer API/RQ/Postgres/S3/download/cancel/expiry E2E, CORS/CSP/egress isolation check, large input limits and malware behavior, responsive UI/accessibility. All formats require independent T90-5 certification.
- Rollback: keep `PDFHUB_TO_PDF_TOOLS_ENABLED=false`; if new Markdown code regresses, revert scoped PR without touching active legacy image converter.

## Delivery gates

- Full exact-HEAD Core API CI 6/6, Web CI, CodeQL both languages, Dependency Review.
- Explicit protected-main head/required checks verification before merge.
- **0/90 RELEASED remains true**; status of tools without complete end-to-end proof stays below VERIFIED.
