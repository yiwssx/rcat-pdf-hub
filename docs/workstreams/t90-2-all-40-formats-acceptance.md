# T90-2 consolidated 40-format delivery ledger (2026-10-29)

> **CURRENT ENGINEERING SNAPSHOT (2026-11-02):** [40-format code-only completion and deferred physical QA](t90-2-code-only-completion-2026-11-02.md) supersedes older dated summary paragraphs below. **40/40 guarded source paths prepared (34 restricted STAGED backends + 6 default-OFF experimental engines), not 40/40 operational approvals.** The six previously missing endpoints exist only behind individual developer flags; they are still **BLOCKED FOR ACCEPTANCE** pending actual RCAT host/licensing/file quality proof. T21 Publisher page 2 was observed visually blank; source-reference fidelity remains unresolved. **0 tools VERIFIED/RELEASED.** Historical sections are preserved for chronology only.\n\n> Governance: **40/40 enumerated and adjudicated** is not **40/40 independently implemented, VERIFIED or RELEASED**. Release count remains **0/90**. Technical gates are enforced in code, and the six dangerous formats have **default-OFF experimental routes/queue/service prototypes** that are **not independently accepted or released**. T90-2 issue [#237](https://github.com/yiwssx/rcat-pdf-hub/issues/237); parent [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172).

## Current engineering tally

- **34 canonical formats STAGED** via **38 guarded format-specific variants** (31 baseline plus CBR RAR4 stored images, Apple Pages4/5 and HWP3/1997 genuine imports). This means version-controlled backend code is present but default disabled, not that all test/visual/fidelity/production gates have passed.
- **6 formats BLOCKED** pending vetted decoders, licensing, conversion-scope clarity or safety/egress isolation. Never expose dummy routes or re-label them as implemented.
- No new Web catalog/UX released; existing 13 operation adapters are unchanged; T90-1 #225 independently pending.

## Exhaustive canonical format decisions

| ID | Canonical format/tool | Tier | Engineering state | Explicit backend variants | Minimum unresolved fidelity or security gate |
|:---|:---|:---|:---|:---|:---|
| T01 | Word (.doc) | P0 | **STAGED (flag OFF)** | `doc-to-pdf` | OLE legacy format validation limited to signature |
| T02 | JPG | P0 | **STAGED (flag OFF)** | `jpg-to-pdf`, `jpeg-to-pdf` | raster size and color fidelity |
| T03 | PNG | P0 | **STAGED (flag OFF)** | `png-to-pdf` | transparency and color fidelity |
| T04 | EPUB | P2 | **STAGED (flag OFF); illustration FEATURE IN DEVELOPMENT** | `epub-to-pdf` | XHTML spine plus bounded local PNG/JPEG/WebP/GIF illustration draft on development branch; no CSS/original pagination, remote fetch, DRM, or completed acceptance |
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
| T21 | PUB | P3 | **STAGED (flag OFF)** | `pub-to-pdf` | Strict size/CFB v3 FAT-directory preflight; pinned real Gotenberg/libmspub Publisher sample yields 2 A4 pages (page 1 nonblank, page 2 visibly blank; original source page-2 reference pending); arbitrary Publisher page/font fidelity unverified |
| T22 | XPS | P2 | **STAGED (flag OFF)** | `xps-to-pdf` | Restricted ZIP/XML Glyphs Unicode-only **text transcription** onto A4; rejects images/vectors; original XPS page geometry/fonts not preserved |
| T23 | XML | P2 | **STAGED (flag OFF)** | `xml-to-pdf` | staged plain source-listing only; no XSLT or document styling |
| T24 | WebP | P0 | **STAGED (flag OFF)** | `webp-to-pdf` | animation and alpha fidelity |
| T25 | HEIF | P2 | **BLOCKED** | — | licensed bounded HEIF codec absent |
| T26 | JFIF | P1 | **STAGED (flag OFF)** | `jfif-to-pdf` | JPEG/JFIF signature and color accuracy |
| T27 | GIF | P1 | **STAGED (flag OFF)** | `gif-to-pdf` | multi-frame animation page policy |
| T28 | BMP | P0 | **STAGED (flag OFF)** | `bmp-to-pdf` | raster encoding and color |
| T29 | HWP | P3 | **STAGED (flag OFF)** | `hwp-to-pdf` | HWP3/97 exact magic and password/protection rejection, Korean text A4 native LibreOffice; HWP5/HWPX excluded |
| T30 | CHM | P3 | **BLOCKED** | — | CHM extraction sandbox and HTML cross-links |
| T31 | FB2 | P3 | **STAGED (flag OFF); illustration FEATURE IN DEVELOPMENT** | `fb2-to-pdf` | FictionBook body, coverpage and bounded referenced bitmap draft on development branch; visual fidelity and acceptance pending |
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

## 2026-10-30 — real Hangul 97/HWP 3.0 nonblank document acceptance

- Authentic upstream LibreOffice `hwpfilter/qa/cppunit/data/pass/hangul97-3.0.hwp` (immutable core revision `fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4`, git blob SHA `68ff2f51269f3ab619f6465073518cd84694300c`, 11,537 bytes) converted with actual pinned Gotenberg LibreOffice/hwpfilter to **1 nonblank A4 page** with successfully extracted **'Hello OpenOffice.org!' and '안녕하세요 오픈오피스!'**. Source SHA-256 remains unchanged. This is meaningful file import; not a blank fallback.
- Implemented **HWP V3.00 1997 *only***, from public Hangul 3.0 on-disk spec: exact 30-byte magic `HWP Document File V3.00 ` followed by `0x1A0102030405`; 30+128+1008 minimum source and ≤8MiB; Document Info +24 document-protection dword=0 and +96 password flag=0. Reject HWP5 OLE, HWPX ZIP, modern variants, passworded/protected files. Static `POST /api/v1/pdf/to-pdf/hwp` requires `pdf:convert`, owner/expiry and exact `.hwp` / `application/x-hwp`. Existing worker rechecks at dispatch; forwards temporary `document.hwp` to pinned LibreOffice and validates resulting PDF. No new decoder/dependency needed.
- STAGED only, default `PDFHUB_TO_PDF_TOOLS_ENABLED=false`, no public/production rollout. HWP3 fonts, tables, print geometry and larger complex Korean documents remain unverified, no HWP5 or HWPX support. Security, AV/fuzz/native converter isolation and independent full Compose acceptance pending.
- Engineering count on standalone branch: 34 STAGED / 6 BLOCKED / 38 guarded variants; reconcile with concurrent Pages/CBR PRs before merging. Never count it as VERIFIED/RELEASED.

## 2026-11-01 — EPUB/FB2 image feature development (NOT YET TESTED OR MERGED)

- Development branch: `feature/t90-2-epub-fb2-embedded-images-20261101`. This branch is deliberately **not submitted to PR CI** because the project owner requested feature implementation before testing. Do not interpret documentation here as a verified converter outcome.
- Added bounded local raster resource resolution for EPUB XHTML spine images and FB2 embedded binary/coverpage references. Only declared bitmap MIME PNG/JPEG/WebP/GIF, per-image 4 MiB / 8 Mpixel, total 12 MiB / 32 images and 20 MiB rendered HTML cap. Multi-frame images, unsupported formats and malformed source fail explicitly; HTTP and network fetches remain prohibited by CSP and source resolution.
- EPUB local chapter image references are resolved against the ZIP root without filesystem extraction. External resource links are suppressed, never fetched. FB2 `#id` references resolve only to declared inline `<binary>` payloads; book coverpage can now precede chapter body.
- The browser HTML renderer permits **only data: bitmap URLs**, never remote `http(s):`, filesystem or network access, and constrains print image geometry. Original ebook CSS, typography, complex vector/SVG artwork, scripts, full EPUB/FB2 features and arbitrary DRM are still not supported; these items must not be labeled full compatibility.
- **No tests, CI, PR, merge, runtime activation or Production deployment** have been performed for this feature branch. The authoritative `main` tally remains 34 STAGED / 6 BLOCKED / 38 guarded variants / 0 independently VERIFIED/RELEASED; T90-2 issue #237 remains open.

## 2026-11-01 — continued ebook FEATURE DEVELOPMENT (NO TESTS / CI)

- On the same unpublished branch `feature/t90-2-epub-fb2-embedded-images-20261101`, replaced the former paragraph-only extraction with a bounded, ordered EPUB/FB2 book-block renderer: heading hierarchy, nested section/div prose, ordered/unordered list item markers, blockquotes, verse/poem lines, HTML tables/captions and original-position inline raster illustrations. All output markup is synthesized from a fixed allowlist; no source scripts, styles, links or arbitrary attributes are passed through to Chromium.
- Added EPUB2 `<meta name="cover" content="image-id">` and EPUB3 `properties="cover-image"` bitmap recognition. The cover is prepended only when its declared image resource was not already used in spine content; ambiguity, non-bitmap resources and size limits fail closed. FB2 coverpage support remains in place.
- A chapter image may appear between two text spans without disappearing; the renderer segments printable text around the image instead of flattening its containing paragraph. 500-row / 24-column table bounds, table captions, ordered list text and direct paragraphless `div` prose are added; image byte/pixel/count caps remain unchanged.
- This work is **development code only**. No test execution, CI, PR, merge, deployment, production flag change or independent acceptance was performed. Pending limitations: exact ebook CSS and typography, complex nested HTML tables, vector/SVG artwork, footnote linking, EPUB DRM, chapter print-layout goldens and complete image fidelity. Main tally remains 34 STAGED / 6 BLOCKED / 0 VERIFIED / 0 RELEASED. The six blocked types remain HEIC, HEIF, DWG, CHM, URL, WPS.

## 2026-11-01 — native T30 CHM and T09/T25 HEIC/HEIF FEATURE DEVELOPMENT (NO TESTS / CI)

**Branch:** `feature/t90-2-epub-fb2-embedded-images-20261101`. This is **code only**: no tests, CI, PR, merge, deployment or runtime activation were requested/performed.

### T30 CHM: implemented internal read-only LZX reader and offline print renderer

- New `apps/api/app/services/to_pdf_chm_worker.py`: fixed-layout ctypes binding to upstream `libchm.so.1` (`chm_enumerate`, `chm_retrieve_object`). Enumerates bounded normal CHM file members and reads them **directly into memory without extracting untrusted archive paths to disk**. Restricts member names, count, length, HTML/character budgets and embedded bitmap image size/count/pixels.
- Processes TOC (`.hhc`) and printable HTML chapters, creates local chapter anchors and *internal-only* cross-links, sanitizes source HTML through an output allowlist, and reconstructs limited tables, lists, headings, images and paragraph content. UTF-8/explicitly declared supported legacy encodings only; rejects undecodable unknown charsets.
- New `apps/api/app/services/to_pdf_chm_native.py`: launches native worker through fixed argv without shell, resource/CPU/memory/core/FD limits and a short timeout, parses bounded JSON, and sends sanitized **offline** markup to existing guarded Gotenberg/PDF checker. `apps/api/Dockerfile` includes Debian Bookworm `libchm1` read-only shared library, **not** archive extraction executables.
- `PDFHUB_CHM_NATIVE_DEV_ENABLED=false` default and no upload/route/operation registration. **BLOCKED** until a separately **network-denied and file-isolated native decoder sandbox**, AV/fuzz and real CHM LZX/image/TOC/Thai fidelity acceptance. Resource caps do not themselves establish sandbox security. Original HTML/CSS layout, JavaScript, rich CHM navigation and unsupported image assets are not yet faithfully reproduced.

### T09 / T25 HEIC/HEIF: patched native decoder interface prototype

- New `apps/api/app/services/to_pdf_heif_native.py` preflights ISO BMFF `ftyp` HEIF brands/size, checks **the specific installed libheif runtime** for `>=1.23.7`, requires both `/opt/pdfhub/heif/lib/libheif.so.1` and `/opt/pdfhub/heif/bin/heif-dec`, then runs the CLI with bounded CPU, RAM, timeout, private temporary output directory and no shell. Native decoder PNG outputs are counted, ordered, pixel/byte/binary-validated and rendered to a PDF with matching image pages.
- Version 1.23.7 is mandatory because upstream identified critical/high security issues in older libheif versions. This project deliberately **does not add old Bookworm libheif packages, a vulnerable wheel or unverified binary**, and has not provisioned patched independent codecs yet.
- `PDFHUB_HEIF_NATIVE_DEV_ENABLED=false` default and **no API upload/worker/public route**. HEIC/HEIF remain **BLOCKED** until patched decoder supply-chain/hash/license audit, native process isolation with no network or unnecessary filesystem access, codec interoperability, complete multi-image/metadata/orientation color fidelity, AV/fuzz and real acceptance.

**Engineering inventory on `main` remains:** 34 STAGED, 6 BLOCKED (T09 HEIC, T20 DWG, T25 HEIF, T30 CHM, T33 URL, T34 WPS), 38 guarded operation variants, 0 independently VERIFIED/RELEASED. Native prototypes do **not** change this tally; no production flag has been enabled and T90-2 tracker #237 remains OPEN.

## 2026-11-01 — T33 URL / T34 WPS / T20 DWG FEATURE DEVELOPMENT (NO TESTS / CI)

All changes are on `feature/t90-2-epub-fb2-embedded-images-20261101` only. Work is **not tested, not CI-validated, not merged and not deployed** per project owner request. 40-format release gates are not satisfied.

### T33 — URL → PDF

- New `to_pdf_url.py`: HTTPS-only, fully qualified domain, no credentials, URL parameters, fragments, nonstandard ports, redirects or IP-literal hosts. Resolve all DNS A/AAAA answers and reject any non-global or private result. Pick a validated numerical IP, connect to that numeric address **without re-resolving the original hostname**, and preserve hostname in TLS SNI/certificate and HTTP Host. No environment proxy, redirects, cookies or source JS allowed. Strict finite content, response types, encodings, timeouts and character limits.
- Import only one public HTML/text response; synthesize a sanitized, attribute-free HTML transcription before Gotenberg. Chromium processes only the sanitized local HTML and does **not** visit the remote URL or fetch its CSS, images, JavaScript or third-party content. This is a content-first URL reader, **NOT pixel-identical screenshot/web print**.
- New `POST /api/v1/pdf/to-pdf/url` accepts URL directly when **both** `PDFHUB_TO_PDF_TOOLS_ENABLED=true` and `PDFHUB_URL_TO_PDF_DEV_ENABLED=true`. It constructs a **zero-input-file** owner/quotas-governed job; heavy RQ worker rechecks disabled flags, zero files and exact job parameters at dispatch.
- **Default OFF** and still **BLOCKED**: no production egress isolation or DNS-rebinding/redirect/SSRF penetration proof, no browser visual-fidelity signoff, no tests. Deploy an independently egress-enforced URL fetch container before rollout and never give the standard API unrestricted internal network access.

### T34 — Microsoft Works WPS → ODT → PDF

- New `to_pdf_wps_native.py`: execute Debian Bookworm `wps2odt` from WriterPerfect as a bounded, no-shell dedicated Microsoft Works importer. Validate actual ODF text package, MIME, XML complexity and nonblank document text; then send ODT through existing Gotenberg LibreOffice conversion and nonblank PDF validation.
- Add Debian `wps2odt` package to API Docker image. Its dedicated writerperfect conversion path differs from the previously failed **direct** LibreOffice .wps import, which produced blank PDF from authentic Works 3–6 samples.
- **Default OFF** via `PDFHUB_WPS_NATIVE_DEV_ENABLED=false`; no upload/route. It is NOT a Kingsoft WPS format converter. Dedicated native parser isolation, authentic Works and text/layout font comparisons, password/protected-file screening, package-security review and cross-version acceptance remain mandatory.

### T20 — DWG → DXF → PDF (restricted 2D)

- New `to_pdf_dwg_native.py`: requires an externally provisioned `/opt/pdfhub/cad/bin/dwgread` binary, known DWG AC10xx header and strict source size. Invokes `dwgread -O DXF -o ...` with memory/CPU/file/time limits, projects **only** bounded 2D `LINE` and `CIRCLE` entities, rejects other CAD object kinds, then invokes the existing strict DXF line/circle PDF vector renderer.
- Binary **not installed** in API image: GNU LibreDWG is GPL-3.0-or-later, requiring independent review of licensing/redistribution obligations before deployment. No DWG API/upload/queue route is exposed. `PDFHUB_DWG_NATIVE_DEV_ENABLED=false` default.
- Original layer/color/linetype/print scale/3D/BLOCK/XREF fidelity, decoder-sandbox, version/feature coverage and real CAD sample signoff remain unsupported. This limited 2D prototype is **not** a full DWG converter.

### Status boundary

Although initial native, network and dedicated legacy import prototypes now exist for all six historically blocked IDs, **every one remains BLOCKED** until proven functional and safe; T09/T25 HEIC/HEIF still lack patched decoder installation, CHM lacks isolated sandbox, and T20/T33/T34 lack production signoff. No changes to main: **34 STAGED / 6 BLOCKED / 38 guarded variants / 0 independently VERIFIED or RELEASED**. Tracker #237 and master #172 remain OPEN. Never mark a placeholder endpoint or drafted decoder as a passed format.

## 2026-11-01 — native-engine hardening while FEATURE TESTS DEFERRED

Additional *implementation-only* changes on `feature/t90-2-epub-fb2-embedded-images-20261101`. These changes have **not** been executed or tested, do not alter public format counts, and do not waive runtime/sandbox/licensing or independent acceptance gates.

- **Native subprocess memory safety**: CHM's JSON-producing helper no longer uses unbounded `subprocess.run(capture_output=True)`; its parent opens a controlled temporary stdout file, imposes child `RLIMIT_FSIZE`, discards stderr and bounds bytes read before JSON parsing. HEIC/HEIF, WPS and DWG subprocesses whose documented outputs are files now discard stdout/stderr rather than buffering arbitrary native-process logs.
- **DWG visual/source integrity**: The restricted `LINE`/`CIRCLE` bridge now refuses non-default entity layer, color, line type, line weight, visibility and model/paper-space choices rather than quietly producing incorrect all-black geometry. It accepts only inert object identifiers/default boilerplate; complex CAD semantics still BLOCKED and not advertised as supported.
- **CHM malformed HTML fidelity**: The native reader's chapter sanitizer now matches source tag identities, handles local anchors without closing unrelated elements, enforces nesting and tag-count budgets, and rejects unterminated/misnested executable-content subtrees; it does not forward source scripts/styles/attributes. Original CHM layout fidelity and native decoding sandbox remain unverified.
- **HEIC/HEIF completeness**: ISO BMFF `ftyp` parsing now distinguishes `major_brand` at bytes 8–11, `minor_version` at 12–15 and `compatible_brands` beginning at 16 (a set-discard approach could erroneously erase a valid major brand). Generated image pages are first written to an internal PDF candidate; the common strict PDF validator enforces exact page count, size and visible content before final artifact write. Separately pinned patched native decoder still not provisioned.
- **Source checks only**: no Python execution, no test suite, no CI run, no PR/merge, no container build/deploy, no feature-flag activation. Main remains 34 STAGED / 6 BLOCKED / 0 independently VERIFIED or RELEASED; T90-2 tracker #237 remains OPEN.

Next implementation priorities before a separate testing phase: OS-enforced network isolation for native readers and URL fetcher, externally pinned patched HEIF runtime and provenance, native Works and LibreDWG compatibility/licensing review, and broader actual 2D/3D CAD, URL and ebook layout feature coverage.

## 2026-11-01 — Mandatory native network isolation added (DEVELOPMENT, NO TESTS)

- New `apps/api/app/services/native_sandbox.py` constructs one **mandatory** Bubblewrap `bwrap` invocation for CHM, HEIC/HEIF, Microsoft Works WPS and restricted DWG native decoders. The child is configured with user/net/IPC/PID/UTS namespaces; a private temp/proc/dev tree; read-only runtime/code mounts; a single read-only `/input/source`; and an optional task-owned writable `/output` directory. The parent passes only fixed executable argv and a scrubbed environment. There is **no unsandboxed fallback**: if Bubblewrap cannot start or namespaces are blocked by the actual Docker host, the conversion fails closed.
- Changed the CHM, HEIC/HEIF, WPS and DWG entry points to use the same sandbox builder, with their existing CPU/memory/file/timeout limits. API Dockerfile now lists Debian `bubblewrap` as a runtime dependency. No `privileged: true`, broad capabilities, weakened seccomp or host AppArmor bypass were introduced.
- Fixed CHM `.hhc` relative chapter-path handling: TOC links resolve against the actual TOC member path, not a fabricated root-level TOC name.
- Limited aggregate native HEIC/HEIF decoded PNG output bytes *before* each Pillow image read, in addition to earlier per-frame/pixel/page caps.
- Improved URL→PDF HTML sanitization to correctly distinguish HTML5 void elements (`meta`, `link`, `base`, `source`) from paired executable nodes; normal head metadata should not accidentally keep all printable body content hidden. Upstream `Content-Length` mismatches now fail instead of emitting a truncated document. **URL remains BLOCKED** until a *separate network-enabled but public-only egress sandbox* exists; the native **no-network** sandbox intentionally cannot be reused for URL acquisition.
- Added dedicated contract at `docs/workstreams/t90-2-native-sandbox-contract.md`, including non-root namespace, security, real input corpus, licensing and deployment acceptance gates. Kernel/container namespace compatibility is UNKNOWN because **no tests or builds were performed**. Native engines remain disabled by default.
- **No tests, CI, PR, merge, deployment or Production feature flag changes** in this increment. On `main`, 34 STAGED / 6 BLOCKED / 38 guarded variants / 0 VERIFIED or RELEASED remains unchanged; T90-2 #237 remains OPEN.

## 2026-11-01 — T33 URL egress sidecar architecture implementation (NO TESTS/CI)

Development-only work on `feature/t90-2-epub-fb2-embedded-images-20261101`. No tests, builds, CI, PR, merge, deploy, firewall installation or active feature flags.

- **Critical trust-boundary improvement:** the heavy RQ PDF worker **no longer performs Internet URL fetching**. `apps/api/app/services/to_pdf_url.py` now signs each bounded, independently validated original URL request with a high-entropy shared HMAC secret, timestamp and random nonce; calls only a hardcoded `url-fetcher:8099` private-network endpoint; and verifies the returned HTML payload, response signature, size, type and completeness before calling Gotenberg's offline HTML-to-PDF converter. The original DNS-pinned HTTPS reader/sanitizer lives in independent pure-stdlib `url_fetch_core.py`, imported by the sidecar.
- **Dedicated low-trust sidecar:** `ops/url-fetcher/server.py` is a standalone HTTP service using only stdlib, independently authenticated, replay-nonce-checked, limited to 2 active outbound fetches / 8 HTTP connection threads, with bounded headers/body/time, no original URL logs, a no-redirect public HTTPS/443 importer, strict DNS-global-IP checks and pinned TLS to a public IPv4 address. `ops/url-fetcher/Dockerfile` copies just server and fetch core, no PDF Hub database, queue, files, app secrets or Web Console code.
- **Optional Compose overlay:** `compose.url-fetcher.yaml` adds default-off `url-import-dev` profile, a private internal worker/sidecar bridge, and an external IPv4-only fetcher bridge (`br-pdfhub-url`, static IP `172.30.243.2`). Fetcher has a read-only filesystem, unprivileged UID, no capabilities, no published host ports, PID/memory limits and minimal tmpfs. Both application/global feature flags remain OFF by default; URL fetcher secret must be supplied separately and is shared only with the heavy worker and sidecar in the overlay.
- **Host-side egress controls:** manual, **unexecuted** `ops/url-fetcher/install-host-egress-firewall.sh` adds iptables `DOCKER-USER` **FORWARD** and `INPUT` protections matching the dedicated bridge interface, prohibits non-public/multicast/link-local/meta addresses, permits only remaining public TCP/443, rejects other outbound traffic, and checks that FORWARD actually jumps into DOCKER-USER. It writes a host **boot-specific** operator attestation file only after installing rules. Sidecar fails to start without matching host-boot attestation; reboot stales the marker. An attestation is not firewall proof and **rules are not automatically persistent**. This script supports only hosts using Docker's iptables backend; Docker's nftables backend requires a separately reviewed native policy, not a bypass. Docker Compose **2.33.1+** is required for `gw_priority`.
- **Implementation contract:** `docs/workstreams/t90-2-url-fetcher-egress.md` records threat boundary, admin-only future rollout steps, configuration conflicts and strict negative/positive acceptance criteria. No live network validation or security testing has been performed; `T33 URL` remains **BLOCKED** until host enforcement, HMAC replay, SSRF, DNS manipulation, HTML fidelity, failure modes and target Docker implementation are independently accepted.
- All other prototypes remain development-only; neither 6 blocked formats nor their status on main changes. **Main: 34 STAGED / 6 BLOCKED / 38 guarded operations / 0 independently VERIFIED/RELEASED.** Keep tracker #237 and parent #172 OPEN.

## 2026-11-01 — T33 offline HTML and firewall liveness hardening (development-only)

- Added `apps/api/app/services/url_html_boundary.py`, an independent strict HTML verifier that runs in the trusted PDF worker **after signed URL-fetcher response verification and before Gotenberg**. It rejects active/unknown tags and all attributes (including URLs and event handlers), comments and declarations, caps depth/size/tags, requires matching element boundaries, escapes text a second time and requires nonblank printable content. HMAC authenticates the lower-trust fetcher; it does not authorize its HTML to control the renderer.
- Added `ops/url-fetcher/verify-host-egress-firewall.sh` to inspect the installed **actual ordered** iptables FORWARD/DOCKER-USER/INPUT and egress chain. It refuses unknown or changed rules, invalidates the attestation marker on failure and refreshes a host-boot-bound short-lived lease only after successful verification. The manual install script now calls the verifier rather than issuing an indefinite marker.
- Added opt-in host `systemd` unit/timer files for 30-second firewall audits. The URL sidecar rechecks the 120-second lease at startup, on health probes and twice per fetch request. Stale/absent leases cause 503, but periodic checking **cannot guarantee instantaneous revocation** if firewall is removed between audits; host firewall is mandatory.
- Runbook `docs/workstreams/t90-2-url-fetcher-egress.md` updated with operator installation and outstanding security conditions. The host-side scripts and systemd units are source artifacts: **none has been run/installed**.
- **NO tests, CI, builds, PR, merge, deploy or feature flags. T33 URL remains BLOCKED**, as do T09/T20/T25/T30/T34. `main` stays 34 STAGED / 6 BLOCKED / 38 guarded variants / 0 VERIFIED/RELEASED. Tracker #237 and parent #172 remain OPEN.

## 2026-11-01 — Five experimental Native API-to-Worker paths connected; actual PASS still pending

- Added `NATIVE_DEV_TO_PDF_INPUTS` / `NATIVE_DEV_TO_PDF_OPERATIONS` and a separate guarded native dispatcher in `staged_to_pdf_adapters.py`, **not** in the 38 STAGED variants.
- Added upload preflight for **HEIC, HEIF, DWG, CHM and Microsoft Works WPS** gated on both `PDFHUB_TO_PDF_TOOLS_ENABLED` and each independent native flag; DWG/HEIF/CHM validate size/magic before native access; Works native parser must validate content before PDF output.
- Added independent `/to-pdf/heic`, `/heif`, `/dwg`, `/chm`, `/wps` routes, compiled **only** when the matching native development flag and global T90-2 flag are enabled at startup. Standard scope, file-owner, expiry and MIME requirements apply.
- Added gated heavy queue routes and worker dispatch, repeating ownership/expiry/input count/signature checks before entering the native sandbox; output remains standard owner-bound PDF job artifact.
- Hardened HEIF native runtime validation: `ctypes.CDLL` and `heif_get_version` now run in a resource-capped, no-network Bubblewrap subprocess (`to_pdf_heif_version_worker.py`), rather than loading native shared library in the trusted RQ worker before sandboxing. The external pinned runtime and real decoder have **not** been installed.
- Added source-only regression cases: `test_t90_2_native_dev_integrations.py` (all 5 format gates, upload signatures, heavy queue routing, bad jobs) and `test_t90_2_url_offline_boundaries.py` (URL denial, Unicode Thai paths, ordinary HTML heads, second-stage Chromium HTML rejection). These are **NOT EXECUTED** and do not certify any runtime.
- Added `docs/workstreams/t90-2-native-end-to-end-integration.md` with per-format, legally and technically concrete acceptance gates. A source-level cross-file presence check confirms mapping/routes/queue/worker/hooks exist but **is not a test PASS**.
- **Blockers still prevent certification:** target Docker/OS network/namespace proof, external **libheif >=1.23.7** decoder and plugins, LibreDWG pin/license, genuine Works/CHM/HEIC/HEIF/DWG corpora, public-only URL SSRF firewall audit, and full source-vs-PDF fidelity review.
- **No tests, CI, PR, merge, deployment, or feature-flag activation** in this increment. On main, the catalog remains **34 STAGED / 6 BLOCKED / 38 guarded operation variants / 0 independently VERIFIED or RELEASED**. Keep tracker #237 / parent #172 OPEN until independent acceptance.

## 2026-11-01 — Native output promotion and CHM rendering trust boundary (implementation only)

This increment fixes security and visual correctness flaws without promoting any blocked format.

- **T34 Works WPS:** native `wps2odt` writes only into Bubblewrap's low-trust task directory. Its produced ODT is copied through `copy_native_regular_output` into a **separate trusted temporary directory**, then inspected as a bounded nonblank ODF package and passed to Gotenberg. This prevents follow-on rendering from reopening a mutable native-output path.
- **T20 DWG:** `dwgread` emits DXF into a low-trust directory; the DXF bytes are promoted to a separate trusted directory **before** the restricted 2D parser sees them. The canonical restricted DXF and final vector-PDF generation are outside the native decoder's writable mount.
- **T09/T25 HEIC/HEIF:** native PNG frames are copied individually to an independent trusted directory before Pillow/ReportLab use them, enforcing original per-frame and aggregate byte/pixel caps. Alpha-containing frames are composited onto white (rather than converting RGBA to RGB and accidentally exposing black transparent pixels).
- **Shared guard:** `apps/api/app/services/native_output_guard.py` uses Linux `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC` and `fstat` on an open descriptor to reject symlinks, hardlinks, pipes/devices and oversized/changing native output; uses exclusively-created files in separately provisioned task directories.
- **T30 CHM second HTML trust boundary:** a sandboxed native reader's JSON/HTML is not considered authorized simply because it decoded. New `app/services/chm_html_boundary.py` reconstructs HTML in the trusted worker: only plain document structure, bounded matching `chm-topic-N` links and internally embedded, revalidated PNG/JPEG/GIF/WebP images may reach Gotenberg; JavaScript, CSS, external URLs, arbitrary attributes and mismatched tags are denied. CHM source fidelity remains unverified.
- **T33 URL firewall rule identity:** installer and ordered host auditor now declare the specific IPv4 `REJECT --reject-with icmp-port-unreachable` behavior explicitly rather than relying on backend default-rendered target options. Kernel/backend compatibility and packet-level tests still pending.
- Added **source-only (NOT RUN)** regression modules `test_t90_2_native_output_boundary.py` (regular-file promotion vs symlink, hardlink, FIFO, oversized, preexisting target) and `test_t90_2_chm_html_boundary.py` (safe chapter links/inline image vs unsafe HTML). The earlier native routing and URL HTML tests also remain unexecuted.
- Cross-referenced external documentation: LibreDWG `dwgread -O DXF -o FILE INPUT` and writerperfect `wps2odt INPUT OUTPUT` CLI forms were checked against published project/manual references; no native binary was executed. Runtime/compiler/version/provenance remain independently unverified.

**Unchanged acceptance state:** `main` 34 STAGED / 6 BLOCKED / 38 guarded variants / 0 independently VERIFIED/RELEASED. CHM/HEIC/HEIF/DWG/WPS/URL remain blocked pending genuine-format source-vs-PDF acceptance and target host sandbox/egress proof. No tests/CI, PR, merge, deployment, firewall installation or feature flag activation were performed this increment.

## 2026-11-01 — Native Bubblewrap mount ordering corrected (still BLOCKED)

- **Actual source correctness bug identified:** private `--tmpfs /tmp` was previously ordered before binding host input/output paths. Native source and scratch directories often reside under host `/tmp` and may be hidden before mount resolution. Moved source RO and per-job output RW `--bind` before replacing sandbox `/tmp`, preserving access under `/input/source` and `/output`.
- Restricted native decoder read-only runtime exposure from all of `/app` and `/opt` to `/app/app`, `/opt/venv`, and optional separately provisioned vetted `/opt/pdfhub/heif` and `/opt/pdfhub/cad`. No user data/secrets mounts are intentionally shared.
- Added `app/services/t90_2_sandbox_selftest.py`: an explicitly opt-in, read-only container-level Bubblewrap runtime probe for actual user/net namespaces, source readability and non-access to data/NAS/secrets/public TCP. It has **NOT been executed on RCAT host**, and does not certify file-to-PDF fidelity.
- Added `tests/test_t90_2_native_sandbox_mounts.py` (NOT RUN) for ordering and minimal mount regressions. Connected GitHub source-contract inspection: **8/8 assertions present** (static, not actual Bubblewrap execution). Existing local two-module security smoke rerun: **24/24 PASS**; covers older native-output and URL-HTML modules only.
- **NO changes to status or production.** All 6 formats remain BLOCKED; `main` remains 34 STAGED / 6 BLOCKED / 0 independently VERIFIED or RELEASED. No CI, Docker build, flags, PR, merge or deployment.
