# T90-2 consolidated 40-format delivery ledger (2026-10-29)

> Governance: **40/40 enumerated and adjudicated** is not **40/40 independently implemented, VERIFIED or RELEASED**. Release count remains **0/90**. Technical gates are enforced in code, and the dangerous formats below have **no upload route, no queue operation, and no engine stub**. T90-2 issue [#237](https://github.com/yiwssx/rcat-pdf-hub/issues/237); parent [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172).

## Current engineering tally

- **33 canonical formats STAGED** via **37 guarded format-specific variants** (31 baseline plus bounded RAR4 stored-image CBR and genuine Apple Pages4/5 document imports). This means version-controlled backend code is present but default disabled, not that all test/visual/fidelity/production gates have passed.
- **7 formats BLOCKED** pending vetted decoders, licensing, conversion-scope clarity or safety/egress isolation. Never expose dummy routes or re-label them as implemented.
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
| T11 | DjVu | P3 | **STAGED (flag OFF)** | `djvu-to-pdf` | 1-page self-contained DJVU IFF (no multipage/INCL) with patched Debian DjVuLibre; native subprocess CPU/AS/FSIZE/no-file limits, 20s timeout; raster-only PDF, not searchable text or full fidelity |
| T12 | Pages | P3 | **STAGED (flag OFF)** | `pages-to-pdf` | Pages4 XML and Pages5 IWA ZIP full-document importer via LibreOffice/libetonyek; preview-only rejected, modern variants/fidelity unverified |
| T13 | TIFF | P0 | **STAGED (flag OFF)** | `tiff-to-pdf` | multi-frame image fidelity |
| T14 | TXT | P1 | **STAGED (flag OFF)** | `txt-to-pdf` | UTF-8 Thai text and page wrapping |
| T15 | ODT | P0 | **STAGED (flag OFF)** | `odt-to-pdf` | OpenDocument fonts and page layout |
| T16 | SVG | P1 | **STAGED (flag OFF)** | `svg-to-pdf` | allowlisted vector/text geometry only; no gradients, CSS, image assets, transforms or fonts |
| T17 | CSV | P1 | **STAGED (flag OFF)** | `csv-to-pdf` | UTF-8 rows, wide tables and print scaling |
| T18 | RTF | P0 | **STAGED (flag OFF)** | `rtf-to-pdf` | legacy RTF parser and font fidelity |
| T19 | MOBI | P3 | **STAGED (flag OFF)** | `mobi-to-pdf` | restricted DRM-free, classic UTF-8 MOBI4–6 BOOKMOBI, compression 1 or bounded PalmDOC compression 2; *text transcript only*; rejects rich HTML/images/CSS/DRM/KF8/HUFF |
| T20 | DWG | P3 | **BLOCKED** | — | CAD binary licensing, layers and model scale |
| T21 | PUB | P3 | **STAGED (flag OFF)** | `pub-to-pdf` | Strict size/CFB v3 FAT-directory preflight; pinned real Gotenberg/libmspub Publisher sample yields 2 nonblank A4 pages; arbitrary Publisher page/font fidelity unverified |
| T22 | XPS | P2 | **STAGED (flag OFF)** | `xps-to-pdf` | Restricted ZIP/XML Glyphs Unicode-only **text transcription** onto A4; rejects images/vectors; original XPS page geometry/fonts not preserved |
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
| T39 | AI | P3 | **STAGED (flag OFF)** | `ai-to-pdf` | PDF-compatible Illustrator file subset only; strict PDF parse+rewrite, no actions/annotations/encryption; native PostScript/EPS .ai rejected |
| T40 | CBR | P3 | **STAGED (flag OFF)** | `cbr-to-pdf` | Only uncompressed RAR4 STORE single-volume image entries, verified CRC & bounds; RAR5, compressed/encrypted/split RAR excluded |

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

## 2026-10-29 — real pinned LibreOffice ODF/RTF acceptance extension

- The same isolated, unprivileged, pinned Gotenberg/LibreOffice CI job now generates and converts four additional **synthetic Thai** documents: ODT (one A4 portrait page), ODS (one A4 landscape page with explicit wide Thai column and numeric cell), ODP (two ordered 16:9 presentation pages), and UTF-16 Unicode escaped RTF (one A4 portrait page). The fixture generator is standard-library only; generated documents are not stored in Git or released as user documents.
- The existing PDF acceptance script now runs **seven actual LibreOffice format conversions** in one disposable container: DOCX, XLSX, PPTX, ODT, ODS, ODP, RTF. It validates PDF magic, pages, sizes with tolerance, extracted Thai title/body, spreadsheet numbers, order of slides, embedded Garuda font and unchanged input SHA-256. The live Chromium Thai/A4 check continues unchanged.
- During local isolated LibreOffice rehearsal, ODS's initial default-width column **clipped Thai text**; synthetic ODS now sets explicit column widths. Local LibreOffice demonstrated one-page ODT, ODS, RTF and two-slide ODP, with extracted Thai. The pinned GitHub CI run is the release-gating evidence, not local host output.
- **Caveat:** baseline smoke is not representative THSarabunPSK/Sarabun or institution's real document fidelity; no DOC/XLS/PPT legacy binary evidence, per-format visual pixel goldens, formula/chart fidelity, real Compose workflow, malware/load/accessibility signoff or production release. States remain 26 STAGED / 14 BLOCKED, 0 independently VERIFIED/RELEASED, flag OFF.

- **CI typography observation:** the actual Gotenberg/LibreOffice Impress converter substituted embedded Loma for explicitly declared Garuda in synthetic ODP/RTF, even though Thai text/slide geometry were intact; checking a recognized embedded Thai font in that one format is NOT a font-fidelity signoff. Dedicated visual golden comparison remains a hard release gate.

## 2026-10-29 — safely restricted AI/XPS decoder feasibility

- **T39 AI**: accepts only Illustrator files explicitly saved in PDF-compatible mode and beginning with a genuine PDF signature; strict bounded PDF parse, no encryption, scripts/actions, attached resources or annotations. Rewrites printable pages via existing pypdf without cloning the original document catalog and validates the resulting PDF. **Does not support** native PostScript/EPS/old Illustrator, editable layer semantics, or original Illustrator project features.
- **T22 XPS**: reads only ZIP-bounded Microsoft XPS FixedDocumentSequence/FixedDocument/FixedPage entries with direct UnicodeString Glyphs. Prevents XML entity expansion, ZIP bombs, traversal, duplicate/case collisions, remote references and unhandled vector/image/canvas/complex text commands. Renders a page-separated **A4 text transcription** through the existing static Chromium renderer. **Does not preserve** original XPS geometric page size, font, vector layout, overlays or embedded images. Unsupported files fail closed.
- Both use the existing opt-in upload/worker revalidation, static authenticated owner/scope-scoped route, standard output custody and retained `PDFHUB_TO_PDF_TOOLS_ENABLED=false` default. They are intentionally **STAGED**, not visually **VERIFIED** or production **RELEASED**; no new dependency, network or deployment topology. The other 12 specialist formats remain blocked pending codec sandbox and licensing proof.
- Original 26/14 status in older dated checkpoint sections is historical, not the current ledger. Pending: representative real AI/XPS golden corpus, all institutional font/layout goldens, Compose E2E, malware/load/accessibility and T90-5 signoff.

## 2026-10-29 — strict legacy MOBI text-only feasibility

- Added `T19 mobi-to-pdf` as a safe limited **classic MOBI4-6 UTF-8 transcript**, not a general Kindle/Mobipocket reader. Pure standard-library PalmDB record parser with `BOOKMOBI` signature, bounded monotonic offsets, exactly one record-0 and 1–64 data records, explicit MOBI header/version and UTF-8, 192 KiB decoded text limit, PalmDOC no-compression or manually bounded LZ77 compression-2. No third-party native decoder or new dependencies.
- **Security gates:** Rejects DRM metadata/encryption, KF8, HUFF/CDIC, EXTH, trailer extension flags, extra media records, invalid UTF-8, HTML resources/scripts/styles/attributes/links and bidi control chars. HTML transcript output is escaped; renders A4 in the existing no-network Chromium path. Synthetic fixture tests prove English/Thai text, LZ77 regression, unmodified upload source, disallowed types, malformed metadata and flag-OFF behavior.
- **Limitations**: No complete original typography, chapters, images, CSS, Amazon Kindle versions or DRM removal. Published as **STAGED** only, default `PDFHUB_TO_PDF_TOOLS_ENABLED=false`. True institutional golden corpus, Gotenberg visual output, full API/worker/download/security/load and T90-5 production signoff are still required. Other **11** specialist formats remain BLOCKED; **0 independently VERIFIED/RELEASED**.

## 2026-10-30 — genuine Publisher binary import acceptance (PR #249)

- T21 Microsoft Publisher `.pub` now has a **real format-specific, default-OFF** route using existing Gotenberg/LibreOffice (libmspub). Source upload + worker both enforce original `.pub` / `application/x-mspublisher`, and the new standard-library restricted CFB v3 parser checks OLE signature, byte order, FAT allocation table, directory chain/UTF-16 names, at least one root and regular stream, ≤7 MiB and sector alignment. Other CFB variants fail closed. Conversion preserves the original suffix when forwarding bytes to pinned Gotenberg; existing auth/owner/expiry and output custody remain unchanged.
- Binary evidence: disposable pinned Gotenberg CI downloads **one 10,752-byte upstream LibreOffice writerperfect/libmspub QA `.pub` test fixture**, pinned to immutable LibreOffice core revision `fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4` and git blob SHA `607a07ae2d362e4a1f6e779dfff88726fe74f910`. It verifies the upstream binary's authenticity, input SHA-256 unchanged, actual Gotenberg LibreOffice PDF response, precisely **2 A4 pages**, and a nonblank first-page raster via Poppler. No binary sample or proprietary font is added to Git; CI fixture retrieved only inside a disposable job.
- Original format support is **not** universal: some Publisher OLE variants and modern proprietary layouts may fail; full text/object/fonts/layout fidelity needs a diverse representative real-document golden corpus, print-area comparisons and further security validation. The OLE structural preflight is not an AV scan. This is STAGED only, not per-format VERIFIED nor production RELEASED. No change to feature toggle `PDFHUB_TO_PDF_TOOLS_ENABLED=false`, existing public UI, production image/network or legacy 13.
- **Current count after PR success:** 30 STAGED / 10 BLOCKED / 34 guarded route variants, 0 independently VERIFIED / RELEASED. Remaining formats: HEIC, HEIF, DjVu, Pages, DWG, HWP, CHM, URL, WPS, CBR.

## 2026-10-30 — DjVuLibre dependency and restricted self-contained single-page DjVu

- Added Debian bookworm `djvulibre-bin` (Debian-security-maintained package 3.5.28-2.2~deb12u1) to the existing non-root API/worker image. Both API upload and background worker check size ≤8 MiB and exact `AT&TFORM`/`DJVU` IFF signature, full declared FORM length, INFO dimensions ≤4096 and ≤8M pixels, limited chunk count/payload, and require a real inline raster data chunk. `DJVM` multipage, nested FORM, `INCL` external dependencies and `DIRM` directory files fail closed; never fetches external resources.
- Decoder `/usr/bin/ddjvu` runs with **fixed argv, no shell, strict 20s wall/12s CPU limit, 768MiB RLIMIT_AS, 40MiB RLIMIT_FSIZE, 32 file descriptors, no core dumps, private temporary working directory**; rechecks source on worker, runs only behind disabled-by-default `PDFHUB_TO_PDF_TOOLS_ENABLED`, validates output with existing strict PDF parser. Debian DjVuLibre binaries remain separate from Python package lock; native code retains residual parser attack surface and this is not a kernel-level network/seccomp sandbox. Separate decoder container, AV adversarial fuzzing and institution's representative files remain mandatory before production.
- CI runs genuine `cjb2` → `ddjvu` one-page raster-to-PDF regression with immutable upload source plus invalid header, indirect/DJVM and geometry rejection. This intentionally **does not** assert full multipage support, searchable/OCR text, font fidelity, page-layout goldens or PDF/A.
- HEIC/HEIF decoder rollout **deferred**: upstream libheif had successive 2026 security releases including v1.23.7 on 26 Oct 2026, while Debian bookworm `libheif-examples` base is 1.15.1. Installing the old native decoder into current API image without patched/sandboxed isolation would bypass safe signoff. Later implement a separately isolated, patched libheif 1.23.7+ decoder with explicit codec allowlist, true real-image tests, licence review and resource limits.
- Count after this merge and CI success only: **31 STAGED / 9 BLOCKED / 35 guarded route variants / 0 independently VERIFIED or RELEASED**; remaining blocked HEIC, HEIF, Pages, DWG, HWP, CHM, URL, WPS, CBR. No production deployment or UI release; T90-2 and master issues remain open.

## 2026-10-30 — CBR genuine RAR4 stored image-only subset

- Added `T40 cbr-to-pdf` as **strict RAR4 stored-only** (method `0x30`) document pages encoded as JPEG, PNG, WebP or BMP. The standard-library RAR4 parser validates the actual archive signature `Rar!\\x1a\\x07\\x00`, CRC16 of all block headers, single-volume nonencrypted main header, exact file-header lengths/CRC32, no splitting/compression/unknown flags, file count ≤64, file ≤12MiB, total images ≤24MiB and archive ≤25MiB. RAR5, compressed RAR4 and password-protected archives are **not** supported and must fail closed.
- Only unique safe ASCII base filenames are allowed, with no path traversal, symlinks or device paths. Image members are copied into a private temporary ZIP and passed to the pre-existing tested CBZ image-to-PDF engine which performs image signature/decompression/pixel/frame and PDF output-page validation. No shell or native/third-party RAR decoder, no archive extraction to user-chosen paths. Synthetic spec-conforming RAR4 archives have also been parsed successfully with an independent `rarfile` implementation (development verification; no runtime reliance).
- STAGED only with explicit `.cbr` and persisted `application/vnd.comicbook-rar`, authenticated owner scope, upload and worker validation, default OFF. Needs representative real CBR corpus, anti-malware/fuzz, production network isolation/security review and visual/comics golden before independent VERIFIED/RELEASED.
- Standalone branch evidence target: 32 STAGED / 8 BLOCKED / 36 guarded variants. When merged with simultaneous Pages PR #251, reconcile counts to 33 STAGED / 7 BLOCKED / 37 guarded variants. No release and T90-5 remains pending.

## 2026-10-30 — real Apple Pages 4/5 and negative Microsoft Works (.wps) libwps corpus

- Authentic pinned LibreOffice upstream `writerperfect/qa/unit/data/writer/libetonyek/pass/Pages_4.pages` (SHA `43c9213922bd26f9242ae93ed6a5aabcc85df11f`, 42,277 B, ZIP `index.xml`) and `Pages_5.pages` (SHA `cd4438a34b451518a8547a8670fc96154255ace8`, 57,362 B, ZIP `Index/Document.iwa`) imported into a real disposable pinned Gotenberg via LibreOffice/libetonyek, produced **nonblank, raster-verified and readable PDF**: Pages 4 = 1 A4 page with expected text 'Document Liberation link', Pages 5 = 2 A5 pages with text 'A5 page'. Both original uploads remain byte-identical and full indexes are present. **An embedded QuickLook preview alone explicitly fails** Pages upload preflight.
- New static `pages-to-pdf` route and bound input worker checks `.pages` and exact `application/vnd.apple.pages`; uploads revalidated in background workers. ZIP package preflight caps input 16MiB, ZIP members 128, expanded totals 32MiB, main index ≤12MiB, performs bounded CRC decompression for all entries and prevents path traversal and symlinks; only one main `index.xml` or `Index/Document.iwa` permitted; other formats fail closed. No new native library required: pinned Gotenberg already ships libetonyek.
- **Negative evidence:** real Microsoft Works `Works_3.0.wps`, `Works_4.5.wps`, `Works_5.0.wps`, `Works_6.0.wps` (immutable pinned git blobs) all returned a **blank first PDF page with no extracted text** on the same Gotenberg, despite upstream libwps claiming import; therefore **T34 WPS stays BLOCKED** and *must not* be routed/staged until nonblank real-file conversion is proven and Works vs Kingsoft WPS families disambiguated. Tests faithfully log unsupported versions without mislabeling the job as general WPS success.
- Staging does NOT mean all versions or complex layout, fonts, table/chart fidelity are verified. Needs real Thai institutional Pages corpus, package malware screening, isolated native LibreOffice converter review, full authorized Compose upload→worker→signed-download and T90-5 approval. Feature flag `PDFHUB_TO_PDF_TOOLS_ENABLED=false` stays OFF, no production deploy.
- If CI and review pass: **33 STAGED / 7 BLOCKED / 37 guarded variants / 0 independently VERIFIED or RELEASED**. Remaining blockers: HEIC, HEIF, DWG, HWP, CHM, URL, WPS, CBR.
