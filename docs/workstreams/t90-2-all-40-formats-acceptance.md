# T90-2 consolidated 40-format delivery ledger (2026-10-29)

> Governance: **40/40 enumerated and adjudicated** is not **40/40 independently implemented, VERIFIED or RELEASED**. Release count remains **0/90**. Technical gates are enforced in code, and the dangerous formats below have **no upload route, no queue operation, and no engine stub**. T90-2 issue [#237](https://github.com/yiwssx/rcat-pdf-hub/issues/237); parent [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172).

## Current engineering tally

- **26 canonical formats STAGED** via **30 real format-specific variants**, including 12 P0 (Office/Images), 6 P1 (safe text/Markdown/GIF/JFIF/HTML/CSV) and 4 P2 constrained subsets. This means version-controlled backend code is present but default disabled, not that all test/visual/fidelity/production gates have passed.
- **14 formats BLOCKED** pending vetted decoders, licensing, conversion-scope clarity or safety/egress isolation. Never expose dummy routes or re-label them as implemented.
- No new Web catalog/UX released; existing 13 operation adapters are unchanged; T90-1 #225 independently pending.

## Exhaustive canonical format decisions

| ID | Canonical format/tool | Tier | Engineering state | Explicit backend variants | Minimum unresolved fidelity or security gate |
|:---|:---|:---|:---|:---|:---|
| T01 | Word (.doc) | P0 | **STAGED (flag OFF)** | `doc-to-pdf` | OLE legacy format validation limited to signature |
| T02 | JPG | P0 | **STAGED (flag OFF)** | `jpg-to-pdf`, `jpeg-to-pdf` | raster size and color fidelity |
| T03 | PNG | P0 | **STAGED (flag OFF)** | `png-to-pdf` | transparency and color fidelity |
| T04 | EPUB | P2 | **STAGED (flag OFF)** | `epub-to-pdf` | text-only XHTML spine; no images, styles, DRM, or remote resources |
| T05 | DOCX | P0 | **STAGED (flag OFF)** | `docx-to-pdf` | OOXML fonts, charts and tables |
| T06 | Excel | P0 | **STAGED (flag OFF)** | `xls-to-pdf`, `xlsx-to-pdf`, `ods-to-pdf` | workbook print areas and formula/cache semantics |
| T07 | PPT | P0 | **STAGED (flag OFF)** | `ppt-to-pdf` | slide aspect, animations lost and embedded fonts |
| T08 | PPTX | P0 | **STAGED (flag OFF)** | `pptx-to-pdf`, `odp-to-pdf` | slides and embedded font fidelity |
| T09 | HEIC | P2 | **BLOCKED** | — | licensed bounded HEIF image codec absent |
| T10 | HTML | P1 | **STAGED (flag OFF)** | `html-to-pdf` | staged sanitized content-only, styling and assets intentionally omitted |
| T11 | DjVu | P3 | **BLOCKED** | — | untrusted native decoder and compression safety |
| T12 | Pages | P3 | **BLOCKED** | — | proprietary Apple container and layout converter |
| T13 | TIFF | P0 | **STAGED (flag OFF)** | `tiff-to-pdf` | multi-frame image fidelity |
| T14 | TXT | P1 | **STAGED (flag OFF)** | `txt-to-pdf` | UTF-8 Thai text and page wrapping |
| T15 | ODT | P0 | **STAGED (flag OFF)** | `odt-to-pdf` | OpenDocument fonts and page layout |
| T16 | SVG | P1 | **STAGED (flag OFF)** | `svg-to-pdf` | allowlisted vector/text geometry only; no gradients, CSS, image assets, transforms or fonts |
| T17 | CSV | P1 | **STAGED (flag OFF)** | `csv-to-pdf` | UTF-8 rows, wide tables and print scaling |
| T18 | RTF | P0 | **STAGED (flag OFF)** | `rtf-to-pdf` | legacy RTF parser and font fidelity |
| T19 | MOBI | P3 | **BLOCKED** | — | licensed native reader and DRM |
| T20 | DWG | P3 | **BLOCKED** | — | CAD binary licensing, layers and model scale |
| T21 | PUB | P3 | **BLOCKED** | — | Publisher proprietary parser and layouts |
| T22 | XPS | P2 | **BLOCKED** | — | ZIP/XML font resource sandbox and converter |
| T23 | XML | P2 | **STAGED (flag OFF)** | `xml-to-pdf` | staged plain source-listing only; no XSLT or document styling |
| T24 | WebP | P0 | **STAGED (flag OFF)** | `webp-to-pdf` | animation and alpha fidelity |
| T25 | HEIF | P2 | **BLOCKED** | — | licensed bounded HEIF codec absent |
| T26 | JFIF | P1 | **STAGED (flag OFF)** | `jfif-to-pdf` | JPEG/JFIF signature and color accuracy |
| T27 | GIF | P1 | **STAGED (flag OFF)** | `gif-to-pdf` | multi-frame animation page policy |
| T28 | BMP | P0 | **STAGED (flag OFF)** | `bmp-to-pdf` | raster encoding and color |
| T29 | HWP | P3 | **BLOCKED** | — | Hangul proprietary parser and Korean fonts |
| T30 | CHM | P3 | **BLOCKED** | — | CHM extraction sandbox and HTML cross-links |
| T31 | FB2 | P3 | **STAGED (flag OFF)** | `fb2-to-pdf` | text-only FictionBook body; no embedded images or exact typography |
| T32 | ZIP | P2 | **STAGED (flag OFF)** | `zip-to-pdf` | staged images-only; other ZIP contents deliberately rejected |
| T33 | URL | P2 | **BLOCKED** | — | SSRF, DNS rebinding and egress infrastructure unavailable |
| T34 | WPS | P3 | **BLOCKED** | — | proprietary WPS/Kingsoft parser and licensing |
| T35 | EML | P2 | **STAGED (flag OFF)** | `eml-to-pdf` | staged plain-text email only; rich HTML/attachments excluded |
| T36 | Markdown | P1 | **STAGED (flag OFF)** | `md-to-pdf` | CommonMark safe subset, remote content forbidden |
| T37 | DXF | P3 | **STAGED (flag OFF)** | `dxf-to-pdf` | restrictive ASCII ENTITIES LINE/CIRCLE 2D only; no XREF/BLOCK/text/units/color/layer fidelity |
| T38 | CBZ | P2 | **STAGED (flag OFF)** | `cbz-to-pdf` | images-only safe comic archive, page order |
| T39 | AI | P3 | **BLOCKED** | — | Illustrator AI/PDF dual-mode licensing and embedded resources |
| T40 | CBR | P3 | **BLOCKED** | — | RAR decoder licensing, archive bombs and extraction isolation |

## Acceptance criteria before individual VERIFIED promotion

**Cross-cutting functional**: authenticated API through queue and worker; persisted upload MIME/signature consistency; identical uploader/worker owner and expiry checks; quotas and cancellation; clean AV scans; immutable input SHA-256; successful signed download; correct PDF magic and strict parse; page order, page count, requested geometry, extracted text and page images; output size and stable SHA regression. Upload and conversion support only explicit white-listed commands/data types, with no shell, arbitrary filenames, non-frozen libraries or user-provided remote URLs.

**Thai + typography**: Sarabun/Noto Sans Thai licensed fonts present inside the actual pinned Gotenberg container, not only on the API host; complex Thai grapheme shaping/combining characters; no missing glyphs, text cut-off or swapped glyphs; DOCX/XLSX/PPTX layout goldens; spreadsheet print areas/page breaks/formula fidelity; markdown table wrapping and plain-text line breaks; comparison against source through actual files, not mocks.

**Dangerous or proprietary formats**: URL tool requires a separate design for pinned resolver, SSRF/DNS rebinding, private-network and metadata-IP blocks, proxy enforcement, redirect refusal, rate limits and egress firewall; ZIP/CBZ strictly images-only with no filesystem extraction and anti-bomb limits; SVG is a closed-schema, regenerated vector subset; rich SVG still needs dedicated secure rendering acceptance; XPS/CHM/DjVu/MOBI/WPS/HWP/DWG/DXF/PUB/AI/CBR/PAGES/HEIF/HEIC require decoder/license and representative binary goldens before enabling. Do not accept blind ZIP extraction/LibreOffice "try everything" as an implementation.

**Rollout/operations**: production flag `PDFHUB_TO_PDF_TOOLS_ENABLED=false` until signed T90-5 activation; preserve previous routes and Docker networks; no silent DB migration; exact-HEAD CI six Core API jobs, Web CI, CodeQL Python/JS, Dependency Review; Compose integration in an isolated stack; page-by-page manual and automated document-quality acceptance; T90-5 release checklist and rollback test. A merged PR is engineering only.

## Reproduction and evidence

- Static registry: `apps/api/app/t90_2_catalog.py`, tested against the actual staged dispatch/route map to disallow phantom or unaccounted operations.
- Typed guarded upload/endpoint/adapter: `apps/api/app/filetypes.py`, `app/routers/to_pdf.py`, `app/staged_to_pdf_adapters.py`.
- Engines: `app/services/to_pdf_engine.py` (validated Office MIME, original filename preserved into Gotenberg; real raster page count; sanitized HTML; UTF-8 XML source listing; text-only EML; image-only ZIP/CBZ; bounded text-only EPUB/FB2).
- Tests: `apps/api/tests/test_t90_2_40_registry.py`, `test_t90_2_multi_format_batch.py`, previous image fidelity, worker owner and Markdown security tests.
- Meaningful rollback: keep flag OFF (default). Partial batch may be reverted from PR; the 13 legacy core adapters must remain operational.

## Scope limitations on four staged P2 conversion paths

- **XML** intentionally prints escaped XML source listing, not arbitrary XSLT/stylesheet transforms.
- **ZIP** accepts image-only archives, not arbitrary collections of Office/HTML/metadata.
- **EML** accepts text/plain email body only; attachments and HTML-only emails are excluded.
- **CBZ** accepts image comic pages and ignores allowed `ComicInfo.xml` metadata; no CBR/RAR fallback.

"STAGED" here is a narrow, accurately labeled backend subset. It does not imply feature parity with every source-format or commercial PDF service.

## 2026-10-29 follow-on: opt-in text-only ebook subset

- T04 EPUB: strict ZIP entries/paths/duplicates/mode/compression/encryption/size ratios; mandatory `mimetype` and `META-INF/container.xml`; rootfile OPF with bounded manifest/spine; exact XHTML chapters parsed with `defusedxml`; chapter order follows OPF spine. Only heading and paragraph text is printed through existing CSP-restricted Gotenberg HTML renderer. No scripts, CSS, images, links, fonts, remote network access, arbitrary ZIP extraction, DRM, or external entities.
- T31 FB2: bounded `FictionBook` XML with `defusedxml` refusing DTD and entities; book title and section paragraphs are escaped and printed. Embedded images, covers, styling, poetry/footnotes and original layout intentionally omitted.
- Both use existing `pdf:convert` scope, owner/expiry/MIME checks, worker artefact retention, strict PDF parser, feature flag OFF and immutable input. The new code must pass CI and owner-bound worker tests; these formats remain **STAGED, not VERIFIED or RELEASED** without real Thai font and document-fidelity acceptance.
- Added `tests/test_t90_2_ebooks.py`, worker integration and input abuse tests. Another 16 formats still need vetted engines.

## 2026-10-29 T16 restricted SVG continuation

- **T16 SVG**: A closed-schema `defusedxml` validator reads only UTF-8 SVG XML, allows a bounded set of primitives (`g`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `path`, `text`, `tspan`) and vetted numeric/color attributes; it **creates new SVG markup** instead of passing untrusted source bytes into Chromium.
- All external/network references, namespaced attributes, events, `<script>`, `<style>`, `<foreignObject>`, `<use>`, `<image>`, `<defs>`, gradients, filters, arbitrary transforms, CSS and XML processing instructions/DTD/XXE are refused. Caps: 2 MiB source, 600 elements, depth 20, 20k text characters; strict PDF validation and owner-scoped worker artifact apply.
- **Excluded**: original fonts, complex fill/stroke gradients, filters, rich paths requiring styling, embedded images, external links, transforms and advanced SVG animation. Gotenberg Thai text shaping, vector content comparisons and representative document goldens are still needed before VERIFIED.
- Registry after SVG staged **25 STAGED / 15 BLOCKED / 29 API variants**; production still `PDFHUB_TO_PDF_TOOLS_ENABLED=false`. T90 release count remains **0/90**.

## 2026-10-29 restricted ASCII DXF engineering follow-on

- T37 is a **closed-schema ASCII DXF 2D subset**: one `ENTITIES` section, literal `LINE` and `CIRCLE` geometry, optional strictly bounded layer/handle labels, no file/network access, nested objects, XREF, INSERT, BLOCK, SPLINE, TEXT, 3D, images, proprietary decoders or subprocesses. Unknown groups and sections fail closed instead of silently dropping design elements.
- A bounded 1 MiB/2,000-entity/20,000-pair parser runs at upload and again in the worker. Vector primitives are drawn on one A4 PDF page by pinned ReportLab. Positions are fit-to-page without original engineering units, annotations or color semantics; **not a dimension-accurate CAD plotting tool**. Source immutable and PDF strict-parse checked.
- The new `/api/v1/pdf/to-pdf/dxf` route is authenticated with `pdf:convert`, owner-scoped and behind the existing production-default-off switch. Negative tests cover binary injection, XREF/INSERT, malformed group codes, out-of-range/3D geometry, and disabled upload/worker paths. Does not alter legacy operations or production deployment.
- Engineering inventory: **26 STAGED / 14 BLOCKED / 30 explicit guarded endpoint variants**. Not VERIFIED or RELEASED: representative engineering drawing corpus, page scaling/units, layers and colors, external CAD review, real Compose/auth/download/Thai golden/AV/load proof and full CI are separate gates. `0/90 RELEASED`.

## 2026-10-29 A4 CSS page-size correctness

- Real pinned Chromium/Gotenberg QA exposed a prior output-fidelity defect: the renderer used Gotenberg's Letter-size default even though the bounded HTML template specified `@page { size:A4 }`. The `preferCssPageSize` form parameter defaults to false.
- The shared `_html_to_pdf` adapter now submits `preferCssPageSize=true` alongside the sanitized `index.html`, so bounded TXT/CSV/Markdown/HTML/XML/EML/EPUB/FB2/SVG HTML-based rendering follows the project's own A4 CSS page policy. All call-boundary tests explicitly assert the opt-in parameter.
- No permission, network, public UI, legacy 13-operation dispatch, source content, printer margin, or production feature-flag changes. Real pinned Thai/A4 smoke is independently tracked; print-fidelity goldens remain required.

## T90-2.5 real pinned Gotenberg Thai smoke acceptance

- Added an isolated CI step in the existing converter-image build job. The job starts the **actual pinned, Thai-font-enabled Gotenberg container** on a random loopback port and posts a version-controlled Thai HTML fixture to Chromium. It must return one strictly PDF-signed A4 page, extract all selected Thai phrases without replacement glyphs, and embed a known installed Thai font.
- The container and temporary PDF are disposed after the CI check. The script has no Production credentials, network mounts, database or deployment access. It does not switch on `PDFHUB_TO_PDF_TOOLS_ENABLED`.
- This is a **functional Thai text smoke**, not a pixel-perfect visual golden, and not DOCX/PPTX/XLSX source-layout comparison. Those independent manual and programmatic goldens, owner-signed downloads, browser/accessibility tests, performance and production T90-5 checks remain open before any VERIFIED/RELEASED status.

## 2026-10-29 — real pinned LibreOffice Thai baseline for P0 DOCX/XLSX/PPTX

- A stdlib-only, deterministic OOXML fixture generator builds **one A4 DOCX**, **one landscape A4 XLSX** with Thai text and numeric cells, and a **two-slide 16:9 PPTX**. No runtime dependencies, font files or binaries are committed; generated fixtures are disposable.
- Core API's existing real Gotenberg font job now exercises **LibreOffice `/forms/libreoffice/convert`** using the pinned custom Thai-font converter container (not a mocked response). It checks PDF signature, page count, exact expected page dimensions with point tolerance, Thai extraction, spreadsheet cell values, slide order, embedded Garuda font, and unchanged SHA-256 of source files. Existing Chromium Thai smoke remains in place.
- **Scope:** this proves a narrow, concrete Office baseline for three common formats and exposes regressions across the deployed converter version and font installation. It does **not** establish fidelity for real institutional DOCX/XLSX/PPTX files, Sarabun/THSarabunPSK, workbook formulas/print areas/charts, PowerPoint masters/embedded assets, rich table layout, legacy DOC/XLS/PPT, nor a browser/API/worker/upload/download end-to-end test. Per-format quality golden and T90-5 rollout decisions remain open.
- Feature flag remains `PDFHUB_TO_PDF_TOOLS_ENABLED=false`, no public UI change, no production deployment, **26 STAGED / 14 BLOCKED / 0 VERIFIED or RELEASED** pending independent acceptance.
