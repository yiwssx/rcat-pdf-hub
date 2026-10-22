# RCAT PDF HUB — T90 Master Capability Tracker (Planning Only)

> **Status:** PLANNING / NOT IMPLEMENTED | **Date:** 2026-10-22 | **Main issue:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172) | **Code audit baseline:** `main@1d6aa41bd128500c1686c19b637670bad61b441b`  
> **Scope:** **90 user-facing PDF tools = 33 Manage + 40 Convert to PDF + 17 Convert from PDF**. This document is a **proposed capability matrix**, not proof of functioning tools. No release/deployment approved.

## Basis, counting policy and constraints

- Benchmark: [PDF Candy](https://pdfcandy.com/) homepage tool lists checked 2026-10-22; vendor homepage states **98** total. Product counts and categories can evolve. Follow its *functional coverage*, not proprietary code, branding, UI, assets or implied licensing.
- Starting from its **36 + 44 + 18 = 98** grouped entries, fold eight overlaps/umbrella views into canonical destinations: `Edit PDF Text → Edit PDF`, `Create PDF → creation/conversion tools`, `Organize Pages → Rearrange Pages`, `PDF Converter → specific conversions`, `Convert to PDF → specific conversions`, `Image to PDF → format-specific conversions`, `eBook to PDF → ebook-specific conversions`, `PDF to Image → format-specific export`. Remaining **33 + 40 + 17 = 90** entries are specified below.
- Some dedicated routes have deliberately shared backends (e.g., Word/DOCX and PDF/JPG/PNG); **90 counts discoverable end-user tools, not 90 independent engines**. For public claims, disclose shared format functionality instead of implying unrelated algorithms.
- RCAT existing UI catalog contains **13 cards**: **11 processing entry points** + `signed-link` and `archive` support features; backend queue supports **13 operations**. This does **not** establish live successful execution on production.
- Historical source: `apps/web/app/components/tool-catalog.ts`, `tool-input-rules.ts`, `tool-workspace-state.ts`, `tool-panel.tsx`; `apps/api/app/routers/pdf.py`, `routers/jobs.py`, `queue.py`, `worker_tasks.py`, `services/pdf_tools.py`, `config.py`; `README.md`; ADR-0001/0002/0003/0005.
- Retain Candy UI v3 identity, task-first intake/configure/job/result flow, self-hosting, no new paid-cloud dependency, owner-scoped access, RBAC, audits, privacy/retention, quotas, isolated worker pools and existing production Compose overrides.
- Separate this feature workstream from [Candy UI unification tracker](candy-ui-unification-tracker.md). Do not bypass/overwrite its design signoff or introduce 90 inconsistent custom tool panels.

## Status semantics

| State | Meaning | Counts toward 90/90 released? |
| --- | --- | --- |
| `PLANNED` | Missing dedicated capability; feasibility/engine proposal only | No |
| `PARTIAL` | Some backend/UI primitive exists, but parity/input-output/UX contract incomplete | No |
| `BASELINE` | Existing repository code path supports all or part of named purpose; **not re-validated in this tracker** | No |
| `IMPLEMENTED` | Feature delivered on a PR/branch with scoped automated tests | No |
| `VERIFIED` | API, UX, security, real-runtime and document-fidelity evidence recorded | No |
| `RELEASED` | Approved production rollout with verified download/rollback/monitoring evidence | **Yes** |

Only advance states with links to PR, CI run, test report and any operational evidence. No mass state transitions.

## Rollup

| Metric | Value |
| --- | ---: |
| Manage/modify PDF | **33** |
| Convert **to** PDF | **40** |
| Convert **from** PDF | **17** |
| **Total target** | **90** |
| Released validated by T90 | **0 / 90** *(not a claim that existing production features are broken; they have not been re-certified here)* |
| Baseline code / Partial / Planned | **18 / 9 / 63** |

## Full inventory — 90 tracked items

Each row's acceptance condition is a *minimum additional* check. Universal acceptance gates at the end always apply. The status is **code-audit baseline**, not release state.

### Manage PDF — 33

| ID | Tool / public slug | State | Priority | Proposed adapter | Minimum tool-specific acceptance |
| --- | --- | --- | --- | --- | --- |
| M01 | **Edit PDF** `edit-pdf` | `PLANNED` | P2 | PDF editor / PyMuPDF + UI | Text/image edits persist; fonts and page geometry visually reviewed |
| M02 | **Compress PDF** `compress-pdf` | `BASELINE` | P0 | Ghostscript | Compression presets; smaller-size check without silent fidelity loss |
| M03 | **PDF Summarizer** `pdf-summarizer` | `PLANNED` | P3 | Isolated OCR + local AI | Grounded citations, sensitive-data controls, no invented claims |
| M04 | **Merge PDF** `merge-pdf` | `BASELINE` | P0 | qpdf | Reordering, mixed sizes, password/input validation |
| M05 | **PDF Translator** `pdf-translator` | `PLANNED` | P3 | OCR + translation adapter | Thai/English text and layout QA; preserve source |
| M06 | **Chat with PDF** `chat-with-pdf` | `PLANNED` | P3 | Isolated extraction + local retrieval/LLM | Answers grounded with page references, tenant isolation |
| M07 | **Split PDF** `split-pdf` | `PARTIAL` | P0 | qpdf + multi-output | Ranges and per-page outputs; individual files / ZIP |
| M08 | **Unlock PDF** `unlock-pdf` | `PLANNED` | P1 | qpdf / pypdf | Requires valid supplied password and legitimate access |
| M09 | **Protect PDF** `protect-pdf` | `PLANNED` | P1 | qpdf AES-256 | Encrypted output, permissions and password tests |
| M10 | **Rotate PDF** `rotate-pdf` | `BASELINE` | P0 | qpdf | Selected/all pages preserve page content |
| M11 | **Crop PDF** `crop-pdf` | `PLANNED` | P0 | pypdf / PyMuPDF | Visual crop rectangle and MediaBox/CropBox QA |
| M12 | **Sign PDF** `sign-pdf` | `PLANNED` | P2 | Visible signature + reviewed pyHanko | Explicit visual signature versus cryptographic signature distinction |
| M13 | **Edit metadata** `edit-metadata` | `PLANNED` | P0 | pypdf | Round-trip title/author/subject/keywords |
| M14 | **Delete pages** `delete-pages` | `PARTIAL` | P0 | Existing organize pipeline | Multi-page remove UX; must reject empty result |
| M15 | **Rearrange pages** `rearrange-pages` | `BASELINE` | P0 | Existing organize pipeline | Drag/drop, exact page order after download |
| M16 | **Extract pages** `extract-pages` | `PARTIAL` | P0 | qpdf + multi-output | Select ranges, individual PDFs/ZIP |
| M17 | **Extract text** `extract-text` | `PLANNED` | P0 | Poppler/pypdf + optional OCR | UTF-8 Thai ordering and searchable/scanned cases |
| M18 | **Extract images** `extract-images` | `PLANNED` | P1 | pdfimages / PyMuPDF | Original image objects exported rather than rasterized pages |
| M19 | **Add page numbers** `add-page-numbers` | `BASELINE` | P0 | ReportLab + pypdf | Thai fonts, start/page numbering and positions |
| M20 | **PDF Viewer** `pdf-viewer` | `PARTIAL` | P0 | Existing preview + PDF.js or equivalent | Full multi-page zoom/search/navigation without mutation |
| M21 | **Add watermark** `add-watermark` | `PARTIAL` | P0 | Existing text watermark + image mode | Thai text/image watermark opacity/rotation/selection |
| M22 | **Add text** `add-text` | `PLANNED` | P1 | ReportLab overlay | Thai text selectable and positioned |
| M23 | **Add image to PDF** `add-image-to-pdf` | `PLANNED` | P1 | pypdf / PyMuPDF overlay | Place PNG/JPEG with transparent images |
| M24 | **Flatten PDF** `flatten-pdf` | `PLANNED` | P1 | pypdf / Ghostscript reviewed | Form/annotation appearance persists; no unexpected loss |
| M25 | **Annotate PDF** `annotate-pdf` | `PLANNED` | P2 | PDF.js editor + PyMuPDF | Comments/shapes retained in readers |
| M26 | **Highlight PDF** `highlight-pdf` | `PLANNED` | P2 | PDF text selection + annotation | Highlight anchors to text accurately |
| M27 | **Remove metadata** `remove-metadata` | `PLANNED` | P0 | pypdf + verify | No retained sensitive metadata where removal is promised |
| M28 | **Resize pages** `resize-pages` | `PLANNED` | P1 | pypdf transformations | Correct page dimensions, content fit and orientation |
| M29 | **Whiteout PDF** `whiteout-pdf` | `PLANNED` | P2 | Whiteout overlay + explicit labeling | Do not claim secure redaction; test underlying text remains |
| M30 | **Grayscale PDF** `grayscale-pdf` | `PLANNED` | P1 | Ghostscript | Preserve content and legibility, verify color space |
| M31 | **Header and footer** `header-and-footer` | `PARTIAL` | P1 | ReportLab overlay | Text/date/page token formatting and placement |
| M32 | **Repair PDF** `repair-pdf` | `PLANNED` | P2 | qpdf / Ghostscript recovery | Best effort only; immutable original and failure disclosure |
| M33 | **PDF Filler** `pdf-filler` | `PLANNED` | P2 | AcroForm fill + UI | Interactive fields filled, flattened optional, owner-safe |

### Convert to PDF — 40

| ID | Tool / public slug | State | Priority | Proposed adapter | Minimum tool-specific acceptance |
| --- | --- | --- | --- | --- | --- |
| T01 | **Word to PDF** `word-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | DOC/DOCX text, tables, Thai font fidelity |
| T02 | **JPG to PDF** `jpg-to-pdf` | `BASELINE` | P0 | Pillow + ReportLab | Dedicated JPG input, ordering, output PDF |
| T03 | **PNG to PDF** `png-to-pdf` | `BASELINE` | P0 | Pillow + ReportLab | Alpha, page sizing and DPI verified |
| T04 | **EPUB to PDF** `epub-to-pdf` | `PLANNED` | P2 | Calibre / ebook engine review | Chapter hierarchy, images, font license/limits |
| T05 | **DOCX to PDF** `docx-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | Explicit DOCX route, Thai fonts and sections |
| T06 | **Excel to PDF** `excel-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | XLS/XLSX sheets, print area and page breaks |
| T07 | **PPT to PDF** `ppt-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | Legacy slides and fonts |
| T08 | **PPTX to PDF** `pptx-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | Slide geometry, text, embedded visuals |
| T09 | **HEIC to PDF** `heic-to-pdf` | `PLANNED` | P2 | libheif/Pillow plugin | Color profiles, multipage, dependency review |
| T10 | **HTML to PDF** `html-to-pdf` | `PLANNED` | P1 | Gotenberg Chromium | Sanitized input, no remote fetch by default, Thai font |
| T11 | **DjVu to PDF** `djvu-to-pdf` | `PLANNED` | P3 | DjVuLibre adapter | Scanned-page fidelity + file sandbox |
| T12 | **PAGES to PDF** `pages-to-pdf` | `PLANNED` | P3 | Specialized adapter feasibility | Proprietary Apple formats; disclose unsupported variants |
| T13 | **TIFF to PDF** `tiff-to-pdf` | `BASELINE` | P0 | Pillow + ReportLab | Multi-frame TIFF pages and order |
| T14 | **TXT to PDF** `txt-to-pdf` | `PLANNED` | P1 | ReportLab/HTML renderer | UTF-8 Thai wrapping and page breaks |
| T15 | **ODT to PDF** `odt-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | ODT style and page-fidelity regression |
| T16 | **SVG to PDF** `svg-to-pdf` | `PLANNED` | P1 | CairoSVG / renderer | No external references, preserve vectors where feasible |
| T17 | **CSV to PDF** `csv-to-pdf` | `PLANNED` | P1 | Tabular renderer | Encoding, delimiter, long tables, Thai glyphs |
| T18 | **RTF to PDF** `rtf-to-pdf` | `BASELINE` | P0 | Gotenberg LibreOffice | Styles and text encoding |
| T19 | **MOBI to PDF** `mobi-to-pdf` | `PLANNED` | P3 | Calibre feasibility | DRM-free only, chapter/cover fidelity |
| T20 | **DWG to PDF** `dwg-to-pdf` | `PLANNED` | P3 | CAD conversion feasibility | Licensing, layers, scale and fonts |
| T21 | **PUB to PDF** `pub-to-pdf` | `PLANNED` | P3 | Publisher import feasibility | Page geometry and compatibility matrix |
| T22 | **XPS to PDF** `xps-to-pdf` | `PLANNED` | P2 | GhostXPS / mutool evaluation | Fonts/transparency validation |
| T23 | **XML to PDF** `xml-to-pdf` | `PLANNED` | P2 | Safe XML renderer | Schema/template choice and XXE disabled |
| T24 | **WebP to PDF** `webp-to-pdf` | `BASELINE` | P0 | Pillow + ReportLab | Alpha and multipage/animation policy |
| T25 | **HEIF to PDF** `heif-to-pdf` | `PLANNED` | P2 | libheif / Pillow plugin | Frames, color profile and resource limits |
| T26 | **JFIF to PDF** `jfif-to-pdf` | `PLANNED` | P1 | Pillow | JPEG/JFIF signature, EXIF orientation |
| T27 | **GIF to PDF** `gif-to-pdf` | `PLANNED` | P1 | Pillow | Frame selection policy documented; transparencies |
| T28 | **BMP to PDF** `bmp-to-pdf` | `BASELINE` | P0 | Pillow + ReportLab | Large BMP resource bounds and correct page sizing |
| T29 | **HWP to PDF** `hwp-to-pdf` | `PLANNED` | P3 | Hancom adapter feasibility | Version support and licensing proof |
| T30 | **CHM to PDF** `chm-to-pdf` | `PLANNED` | P3 | Sandboxed CHM extraction | Archive exploit protections, navigation ordering |
| T31 | **FB2 to PDF** `fb2-to-pdf` | `PLANNED` | P3 | Calibre feasibility | Books and illustrations, no external fetch |
| T32 | **ZIP to PDF** `zip-to-pdf` | `PLANNED` | P2 | Archive validator + conversion pipeline | Prevent zip bombs/path traversal; explicit chosen documents |
| T33 | **URL to PDF** `url-to-pdf` | `PLANNED` | P2 | Gotenberg Chromium + egress controls | Block SSRF/private IP, DNS rebinding, timeouts |
| T34 | **WPS to PDF** `wps-to-pdf` | `PLANNED` | P3 | LibreOffice compatibility feasibility | Legacy WPS text accuracy |
| T35 | **EML to PDF** `eml-to-pdf` | `PLANNED` | P2 | MIME parser + HTML renderer | Sanitize HTML, block remote images, attachments policy |
| T36 | **MD to PDF** `md-to-pdf` | `PLANNED` | P1 | Gotenberg Markdown/HTML | Code, tables, Thai fonts, escaping |
| T37 | **DXF to PDF** `dxf-to-pdf` | `PLANNED` | P3 | ezdxf + renderer feasibility | Units, layers, vector scaling |
| T38 | **CBZ to PDF** `cbz-to-pdf` | `PLANNED` | P2 | Safe ZIP image pipeline | Natural page ordering and decompression limits |
| T39 | **AI to PDF** `ai-to-pdf` | `PLANNED` | P3 | Vector/Illustrator file adapter feasibility | Adobe Illustrator AI files, not generative AI |
| T40 | **CBR to PDF** `cbr-to-pdf` | `PLANNED` | P3 | Sandboxed RAR extraction | Archive security, rights, ordering |

### Convert from PDF — 17

| ID | Tool / public slug | State | Priority | Proposed adapter | Minimum tool-specific acceptance |
| --- | --- | --- | --- | --- | --- |
| F01 | **PDF OCR** `pdf-ocr` | `PARTIAL` | P0 | OCRmyPDF / Tesseract | Searchable PDF exists; add TXT extraction path where required |
| F02 | **PDF to Word** `pdf-to-word` | `PLANNED` | P1 | Layout-aware DOC/DOCX converter | Editable content, Thai paragraphs and tables |
| F03 | **PDF to JPG** `pdf-to-jpg` | `PARTIAL` | P0 | Poppler PDF raster -> ZIP | Dedicated JPG flow, individual/ZIP outputs and DPI |
| F04 | **PDF to PNG** `pdf-to-png` | `PARTIAL` | P0 | Poppler PDF raster -> ZIP | Dedicated PNG flow, transparent/white background policy |
| F05 | **PDF to EPUB** `pdf-to-epub` | `PLANNED` | P2 | Extraction + ebook generator | Reflow quality, images and page-reference QA |
| F06 | **PDF to DOCX** `pdf-to-docx` | `PLANNED` | P1 | Layout-aware DOCX converter | True selectable editable text, not page screenshots |
| F07 | **PDF to Excel** `pdf-to-excel` | `PLANNED` | P2 | Table extraction / XLSX writer | Table cell accuracy, merged cells and numeric typing |
| F08 | **PDF to PPT** `pdf-to-ppt` | `PLANNED` | P2 | Slide writer / layout extraction | Slides retain correctly positioned editable content |
| F09 | **PDF to TIFF** `pdf-to-tiff` | `PLANNED` | P1 | Poppler + Pillow | Multi-page TIFF, DPI and file sizing |
| F10 | **PDF to ODT** `pdf-to-odt` | `PLANNED` | P2 | Structured extraction + ODT writer | Editable paragraphs, fonts, page fidelity |
| F11 | **PDF to PDF/A** `pdf-to-pdfa` | `BASELINE` | P0 | OCRmyPDF/PDF-A pipeline + veraPDF gate | Independent ISO conformance validation |
| F12 | **PDF to SVG** `pdf-to-svg` | `PLANNED` | P2 | Poppler SVG renderer | Vector/bitmap policy and per-page output |
| F13 | **PDF to CSV** `pdf-to-csv` | `PLANNED` | P1 | Table extraction | CSV delimiter/encoding with manually validated examples |
| F14 | **PDF to RTF** `pdf-to-rtf` | `PLANNED` | P2 | Text/layout extractor + RTF writer | Thai formatting and valid RTF |
| F15 | **PDF to MOBI** `pdf-to-mobi` | `PLANNED` | P3 | Ebook conversion feasibility | DRM-free, reflow/coverage disclosure |
| F16 | **PDF to GIF** `pdf-to-gif` | `PLANNED` | P1 | Poppler + Pillow | Page-to-frame choice, resolution and animation policy |
| F17 | **PDF to BMP** `pdf-to-bmp` | `PLANNED` | P1 | Poppler + Pillow | Page range, depth, resource guard |

## Delivery workstreams and gates

| Workstream | Dependency | Scope | Gate / expected evidence | State |
| --- | --- | --- | --- | --- |
| **T90-0** Contract & feasibility | none | 90 registry records, canonical slug/aliases, typed param/input/output schema, status, classes, scopes; 8 consolidations; license/threat/risk matrix; multi-output artifacts design | Single source of truth; contract round-trip; existing 13 operations unchanged; baseline E2E PASS | `TODO` |
| **T90-1** Core PDF | T90-0 | Manage basics: M02/M04/M07–M11/M13–M21/M27–M28/M30–M31 and viewer quality | API/error paths + PDF binary integrity; desktop/mobile screenshots, Thai text; no elevated privileges | `TODO` |
| **T90-2** Convert to PDF | T90-0 | T01–T40 split by engine/format complexity, P0→P3 | Supported magic type checked; fonts, page geometry and print area QA; source not overwritten | `TODO` |
| **T90-3** Convert from PDF | T90-0, multi-output | F01–F17: raster, structured tables/text, editable Office and ebook | Real editability/layout assertions; JPG/PNG multi-files per page or ZIP; valid MIME/result | `TODO` |
| **T90-4** Advanced and isolated workers | T90-0, T90-1 | Editor, form, annotations, signature, URL/archive/CDR/special format, AI (M01/M03/M05/M06/M12/M25/M26/M29/M32/M33 etc.) | Threat model, exploit fixtures, sandbox, license review, resource envelope, optional enablement | `TODO` |
| **T90-5** Production release | T90-1–T90-4 | Per-tool E2E/monitoring/rollback/rollout; admin operability | Production-mode readiness, backup/DR, explicit operator approval, 90 evidence records | `TODO` |

### T90-0 design decisions required before code expansion

- [ ] Inventory the **90 definitions** as canonical IDs with slug aliases and localizations; establish whether tool and operation registry can be generated from one reviewed source **without unsafe dynamic execution**.
- [ ] Maintain **separate** conceptual fields: UI entry ID; backend operation; accepted MIME/signatures; parameter schema; output artifact type and cardinality; required scopes; queue class; latency/size limits; runtime feature flag; license/adapter readiness.
- [ ] Preserve existing public slugs and legacy API contracts. Introduce aliases/redirects deliberately and test client backwards compatibility.
- [ ] Introduce **multi-output artifact manifest** with per-item secure download plus optional ZIP, not only fixed `.pdf`/`.zip`; owner-scope every artifact, retention and signed links.
- [ ] Refactor `worker_tasks.process_job` and `tool-panel.tsx` away from ever-expanding conditional dispatch toward bounded capability adapters; preserve ADR-0001 ToolWorkspace seam.
- [ ] Define input magic signature checks, encrypted-document handling, per-format file count/size/pages, zip bomb bounds, malicious ZIP paths, XML entities, remote resource prohibition, SSRF and URL-to-PDF network egress controls.
- [ ] Mark `Whiteout` as **visual masking, not secure redaction**; never advertise irreversible redaction without verified object removal. Distinguish **image/visual signature vs PKI digital signature**.
- [ ] Isolate AI inference and specialized converters as **optional**, resource-bounded services/workers; no automatic outgoing document disclosure.
- [ ] Verify dependency licenses and current-maintenance/security posture *before* adding engines (e.g., PyMuPDF AGPL/commercial tradeoffs, archive/CAD/eBook tools); do not equate availability with redistribution rights.
- [ ] Define Thai golden corpus including scanned Thai, text-layer Thai, Thai government forms, tables, embedded fonts, rotated/mixed page sizes, large PDFs and malformed/locked documents.
- [ ] Inventory baseline CI and functional acceptance before implementation; do not start feature rollout while critical Candy UI regressions remain unresolved.

## Universal acceptance criteria (each of 90)

1. **Functionality:** real API operation, typed validated inputs/options, deterministic output, correct content type; no static placeholder or unimplemented CTA.
2. **Security:** input signature + scanner, scoped file/job ownership (including child artifacts), fail-closed auth/audit where applicable, quotas, path/URL/archive controls; no secret logging.
3. **Fidelity:** independently inspect source vs output (page count, extracted text and/or visual comparison, Thai font, tables, links, forms as applicable). Provide honest warning for lossy/unsupported features.
4. **UX:** Candy UI v3 common patterns, search/categorization, accessible keyboard, Thai copy; test **1649×925, 1440×900, 1366×768, 768×1024, 390×844**, long Thai filenames, empty/error/running/completed/expired states.
5. **Workflow:** upload/select → configure/preview → submit → durable job → authorized result → download/next-tool; retry/cancel rules and multi-output checked.
6. **Quality gates:** scoped unit + integration + browser E2E; OpenAPI/frontend contract; CodeQL, dependency/license review, performance and resource limits; real Compose runtime E2E at release.
7. **Evidence:** row-specific PR, passing checks, downloadable example/golden test, accepted visual before/after, date, reviewed engine and deployment/rollback evidence; change state manually on proven evidence.

## Release controls

- **Planning only in this PR**. No changes to Next.js, FastAPI, auth, schema migrations, Docker, workers, UI CSS, production environment or existing production release tags.
- Work in independent feature branches/PRs by engine family and risk tier; avoid a 90-tools mega-PR. Each PR explicitly reports affected IDs.
- Do not auto-merge, reinterpret previous Phase 7 completion, or rewrite existing Candy UI tracker.
- Merge of this *planning document* is distinct from authorizing any implementation, production deployment, migration or enabling of AI/specialized converters.
- Actual resource sizing follows load testing and deployment hardware; **90 UI tools ≠ capacity for 90 concurrent heavy tasks**.
- Maintain a current decision log for each unsupported format; if any named tool proves impractical or unlicensable, propose scope replacement with explicit owner approval **while preserving honest 90/90 accounting**.

## Progress log

| Date | Event | Evidence | Outcome |
| --- | --- | --- | --- |
| 2026-10-22 | Planning matrix created; 90 IDs/unique slugs reconciled, no code changed | [Issue #172](https://github.com/yiwssx/rcat-pdf-hub/issues/172); repo audit at `1d6aa41`; [PDF Candy tool catalog](https://pdfcandy.com/) | `PLANNING` |
