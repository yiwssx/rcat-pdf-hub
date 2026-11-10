# RCAT PDF HUB — T90 Engineering-First inventory

**Snapshot:** 2026-11-10, proposed M05 private text-only translation PR (counts become authoritative only after protected merge). This is Engineering source readiness, not live RCAT certification. Canonical registry: [pdf-tools.v1.json](../../contracts/pdf-tools.v1.json).

## Scope and definitions

The original requested deliverable is **90 discoverable user-facing tools**, not 90 independently implemented conversion engines. A shared backend may serve many tools; do not recreate or re-qualify it 90 times.

- **CODE COMPLETE**: existing scoped engine, an existing UI route/workspace interaction and basic code tests for the supported subset; may still be feature-gated OFF and QA PENDING. Does **not** mean deployed or fully format-compatible.
- **PARTIAL**: useful legacy/backend source path exists but the named tool still lacks a distinct selectable user workflow, or advertised feature subset is incomplete. After #339 and #340, 33 guarded To-PDF and all 16 guarded From-PDF choices have a shared user-facing workflow; T21 Publisher remains deliberately withheld for a known blank-page risk.
- **MISSING**: no dedicated usable engine+workflow demonstrated in source audit; proposed adapter alone is not proof of code.
- **BLOCKED**: code prototype exists but production-usable capability needs a genuine external codec/engine, validated license, restricted network/container dependency or other technical prerequisite. F15 has no accepted MOBI output engine. Blockers remain explicit; not 100% delivery claims.

**Dev-only rollup:** CODE COMPLETE **78**, PARTIAL **5**, MISSING **0**, BLOCKED **7** = **90**. This conservative *user-facing workflow readiness* is deliberately different from independent T90 source evidence ledger **40 IMPLEMENTED + 1 STAGED + 49 UNASSESSED** (source credit not yet reconciled for M20). Source evidence counts and tool usability may change independently.

| Family | CODE COMPLETE | PARTIAL | MISSING | BLOCKED | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Manage PDF | 29 | 4 | 0 | 0 | 33 |
| Convert to PDF | 33 | 1 | 0 | 6 | 40 |
| Convert from PDF | 16 | 0 | 0 | 1 | 17 |
| **Total** | **78** | **5** | **0** | **7** | **90** |

## Prioritized engineering leverage

1. **DONE — shared To-PDF Web workflow PR #339:** 33 selectable source-code formats (T21 Publisher withheld). Existing upload, queue, worker, result/download reused; default OFF and not certified.
2. **DONE — shared From-PDF Web workflow PR #340:** 16 selectable guarded exporter source-code tools using existing scopes and queues. No F15 MOBI claim, default OFF.
3. **Manage progress:** Existing workflows reconciled; genuine engines for M21/M24/M25/M26/M29/M32 and guarded UI for M08/M09 plus eight previously partial Manage tools. New M03 extractive summary and limited M06 evidence search. M01 supports a strictly bounded Courier text-object edit (PARTIAL), M12 visual e-signature is PARTIAL (no certificate-backed signature), and M05 private-model text-only translation is PARTIAL (local model not provisioned and no translated PDF layout).
4. **True technical blockers:** six native/URL T formats, F15 MOBI, and T21 publisher incomplete page source fidelity. Record honest scope/requirements and only revisit after ordinary capabilities.
5. **QA/Operations parked:** R1 negative identity/owner tests, native/SSRF host tests, Thai physical/visual goldens, load/DR and independent RELEASED proof stay in [QA #262](https://github.com/yiwssx/rcat-pdf-hub/issues/262), [R1 #308](https://github.com/yiwssx/rcat-pdf-hub/issues/308), [CI #195](https://github.com/yiwssx/rcat-pdf-hub/issues/195), [DR #323](https://github.com/yiwssx/rcat-pdf-hub/issues/323). These do NOT block closing an otherwise complete engineering subtask.

## All 90 tools — current development snapshot (source only)

| ID | Tool | Dev status | Engine/source evidence | Next engineering work |
| --- | --- | --- | --- | --- |
| M01 | Edit PDF | **PARTIAL** | Real, bounded same-length Courier text-object replacement in [M01 source workflow](t90-m01-text-editor-engineering-first.md) | Existing Tj text edited, but not a general PDF/Thai/layout editor; no Production activation |
| M02 | Compress PDF | **CODE COMPLETE** | Legacy `compress` | Defer independent QA; preserve code/CI |
| M03 | PDF Summarizer | **CODE COMPLETE** | Genuine bounded extractive PDF summary, quoted page-cited TXT [PR #353](https://github.com/yiwssx/rcat-pdf-hub/pull/353) | No abstraction, OCR or generative inference; QA deferred, flags OFF |
| M04 | Merge PDF | **CODE COMPLETE** | Legacy `merge` | Defer independent QA; preserve code/CI |
| M05 | PDF Translator | **PARTIAL** | Selectable text PDF, private model transport, owner API→RQ→worker→TXT or newly typeset PDF via Thai-capable Chromium; guarded Web [M05 workflow](t90-m05-private-translator-engineering-first.md) | Model not yet provisioned or Thai quality validated; PDF is re-layout, not original geometry; flags OFF |
| M06 | Chat with PDF | **PARTIAL** | Actual quoted PDF evidence search [PR #353](https://github.com/yiwssx/rcat-pdf-hub/pull/353) | Question-to-excerpt with page numbers; generative conversational chat still unavailable |
| M07 | Split PDF | **CODE COMPLETE** | PR [#300](https://github.com/yiwssx/rcat-pdf-hub/pull/300) bounded ZIP engine + [#344](https://github.com/yiwssx/rcat-pdf-hub/pull/344) guarded owner-scoped Web input/submit/results | Supports non-encrypted, unsigned, non-form, non-annotated PDF ≤16 MiB/200 pages; up to 80 unique pages; all gates OFF; QA deferred |
| M08 | Unlock PDF | **CODE COMPLETE** | Pre-existing AES-GCM one-use password handoff, typed owner API/worker + separate institutional Web [PR #352](https://github.com/yiwssx/rcat-pdf-hub/pull/352) | No persistent passwords, external activation/QA deferred |
| M09 | Protect PDF | **CODE COMPLETE** | Pre-existing AES-256 protected PDF engine, distinct AEAD handoff + scoped institutional Web [PR #352](https://github.com/yiwssx/rcat-pdf-hub/pull/352) | No credential logging/storage in jobs; activation/QA deferred |
| M10 | Rotate PDF | **CODE COMPLETE** | Legacy `rotate` | Defer independent QA; preserve code/CI |
| M11 | Crop PDF | **CODE COMPLETE** | PR [#236](https://github.com/yiwssx/rcat-pdf-hub/pull/236) · bounded engine | Defer independent QA; preserve code/CI |
| M12 | Sign PDF | **PARTIAL** | Real drawn/PNG visual signature uses owner-bound M23 PDF image overlay and [M12 workflow](t90-m12-visual-signature-engineering-first.md) | Image signature only; no certificate-backed CMS/PAdES cryptographic signature, QA deferred |
| M13 | Edit metadata | **CODE COMPLETE** | PR [#235](https://github.com/yiwssx/rcat-pdf-hub/pull/235) · bounded engine | Defer independent QA; preserve code/CI |
| M14 | Delete pages | **CODE COMPLETE** | Guarded owner-bound delete-pages backend + shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | Limited source types, QA deferred |
| M15 | Rearrange pages | **CODE COMPLETE** | Guarded reorder-pages backend + shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | Limited source types, QA deferred |
| M16 | Extract pages | **CODE COMPLETE** | PDF page extraction backed by genuine PDF/ZIP engines and shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | Limited source types, QA deferred |
| M17 | Extract text | **CODE COMPLETE** | PR [#235](https://github.com/yiwssx/rcat-pdf-hub/pull/235) · bounded engine | Defer independent QA; preserve code/CI |
| M18 | Extract images | **CODE COMPLETE** | Genuine embedded-image extractor and shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | Extracts embedded images, not visual snapshots; QA deferred |
| M19 | Add page numbers | **CODE COMPLETE** | Legacy `page-numbers` | Defer independent QA; preserve code/CI |
| M20 | PDF Viewer | **CODE COMPLETE** | Existing authenticated page-count/PNG preview/download APIs + [#343](https://github.com/yiwssx/rcat-pdf-hub/pull/343) Web route | Owner-scoped active PDF selector, page navigation, bounded page index/preview resolution and original download; default-OFF stage UI; no PDF edit; QA deferred |
| M21 | Add watermark | **CODE COMPLETE** | Legacy text watermark plus genuine opacity-controlled image watermark [PR #351](https://github.com/yiwssx/rcat-pdf-hub/pull/351) | No cryptographic signing; backend/Web default OFF |
| M22 | Add text | **CODE COMPLETE** | Actual one-page text overlay engine plus shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | Adds overlay only; does not replace embedded PDF text |
| M23 | Add image to PDF | **CODE COMPLETE** | Genuine JPEG/PNG image overlay + guarded Web [PR #341](https://github.com/yiwssx/rcat-pdf-hub/pull/341) | Defer real-host QA; keep stage flags OFF |
| M24 | Flatten PDF | **CODE COMPLETE** | Genuine bounded raster visual flatten engine + owner Web [PR #347](https://github.com/yiwssx/rcat-pdf-hub/pull/347) | Visual image-only output; original text layer not preserved |
| M25 | Annotate PDF | **CODE COMPLETE** | Real PDF FreeText annotations, restricted to ASCII + Web [PR #348](https://github.com/yiwssx/rcat-pdf-hub/pull/348) | Not arbitrary existing text editing; QA deferred |
| M26 | Highlight PDF | **CODE COMPLETE** | Real PDF Highlight annotation + Web [PR #348](https://github.com/yiwssx/rcat-pdf-hub/pull/348) | Visual rectangle annotation; QA deferred |
| M27 | Remove metadata | **CODE COMPLETE** | PR [#235](https://github.com/yiwssx/rcat-pdf-hub/pull/235) · bounded engine | Defer independent QA; preserve code/CI |
| M28 | Resize pages | **CODE COMPLETE** | PR [#236](https://github.com/yiwssx/rcat-pdf-hub/pull/236) · bounded engine | Defer independent QA; preserve code/CI |
| M29 | Whiteout PDF | **CODE COMPLETE** | Real visible white overlay + Web [PR #348](https://github.com/yiwssx/rcat-pdf-hub/pull/348) | NOT secure redaction: original content remains recoverable |
| M30 | Grayscale PDF | **CODE COMPLETE** | Existing genuine grayscale engine + shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | QA deferred, flags OFF |
| M31 | Header and footer | **CODE COMPLETE** | Existing genuine header/footer engine + shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | QA deferred, flags OFF |
| M32 | Repair PDF | **CODE COMPLETE** | Genuine qpdf bounded structural repair engine + owner Web [PR #349](https://github.com/yiwssx/rcat-pdf-hub/pull/349) | Cannot recover irretrievably lost pages; QA deferred |
| M33 | PDF Filler | **CODE COMPLETE** | Existing AcroForm text filler + shared Web [PR #346](https://github.com/yiwssx/rcat-pdf-hub/pull/346) | Text fields only, not signature; QA deferred |
| T01 | Word to PDF | **CODE COMPLETE** | `doc-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T02 | JPG to PDF | **CODE COMPLETE** | `jpg-to-pdf, jpeg-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T03 | PNG to PDF | **CODE COMPLETE** | `png-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T04 | EPUB to PDF | **CODE COMPLETE** | `epub-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T05 | DOCX to PDF | **CODE COMPLETE** | `docx-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T06 | Excel to PDF | **CODE COMPLETE** | `xls-to-pdf, xlsx-to-pdf, ods-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T07 | PPT to PDF | **CODE COMPLETE** | `ppt-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T08 | PPTX to PDF | **CODE COMPLETE** | `pptx-to-pdf, odp-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T09 | HEIC to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T10 | HTML to PDF | **CODE COMPLETE** | `html-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T11 | DjVu to PDF | **CODE COMPLETE** | `djvu-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T12 | PAGES to PDF | **CODE COMPLETE** | `pages-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T13 | TIFF to PDF | **CODE COMPLETE** | `tiff-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T14 | TXT to PDF | **CODE COMPLETE** | `txt-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T15 | ODT to PDF | **CODE COMPLETE** | `odt-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T16 | SVG to PDF | **CODE COMPLETE** | `svg-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T17 | CSV to PDF | **CODE COMPLETE** | `csv-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T18 | RTF to PDF | **CODE COMPLETE** | `rtf-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T19 | MOBI to PDF | **CODE COMPLETE** | `mobi-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T20 | DWG to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T21 | PUB to PDF | **PARTIAL** | `pub-to-pdf` (guarded) | Known Publisher page 2 blank risk; keep subset under review |
| T22 | XPS to PDF | **CODE COMPLETE** | `xps-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T23 | XML to PDF | **CODE COMPLETE** | `xml-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T24 | WebP to PDF | **CODE COMPLETE** | `webp-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T25 | HEIF to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T26 | JFIF to PDF | **CODE COMPLETE** | `jfif-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T27 | GIF to PDF | **CODE COMPLETE** | `gif-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T28 | BMP to PDF | **CODE COMPLETE** | `bmp-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T29 | HWP to PDF | **CODE COMPLETE** | `hwp-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T30 | CHM to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T31 | FB2 to PDF | **CODE COMPLETE** | `fb2-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T32 | ZIP to PDF | **CODE COMPLETE** | `zip-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T33 | URL to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T34 | WPS to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T35 | EML to PDF | **CODE COMPLETE** | `eml-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T36 | MD to PDF | **CODE COMPLETE** | `md-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T37 | DXF to PDF | **CODE COMPLETE** | `dxf-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T38 | CBZ to PDF | **CODE COMPLETE** | `cbz-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T39 | AI to PDF | **CODE COMPLETE** | `ai-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| T40 | CBR to PDF | **CODE COMPLETE** | `cbr-to-pdf` (guarded) | Shared gated To-PDF UI [PR #339](https://github.com/yiwssx/rcat-pdf-hub/pull/339); QA deferred, flags OFF |
| F01 | PDF OCR | **CODE COMPLETE** | PR [#292](https://github.com/yiwssx/rcat-pdf-hub/pull/292) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F02 | PDF to Word | **CODE COMPLETE** | PR [#286](https://github.com/yiwssx/rcat-pdf-hub/pull/286) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F03 | PDF to JPG | **CODE COMPLETE** | PR [#291](https://github.com/yiwssx/rcat-pdf-hub/pull/291) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F04 | PDF to PNG | **CODE COMPLETE** | PR [#291](https://github.com/yiwssx/rcat-pdf-hub/pull/291) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F05 | PDF to EPUB | **CODE COMPLETE** | PR [#289](https://github.com/yiwssx/rcat-pdf-hub/pull/289) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F06 | PDF to DOCX | **CODE COMPLETE** | PR [#286](https://github.com/yiwssx/rcat-pdf-hub/pull/286) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F07 | PDF to Excel | **CODE COMPLETE** | PR [#287](https://github.com/yiwssx/rcat-pdf-hub/pull/287) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F08 | PDF to PPT | **CODE COMPLETE** | PR [#290](https://github.com/yiwssx/rcat-pdf-hub/pull/290) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F09 | PDF to TIFF | **CODE COMPLETE** | PR [#269](https://github.com/yiwssx/rcat-pdf-hub/pull/269) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F10 | PDF to ODT | **CODE COMPLETE** | PR [#285](https://github.com/yiwssx/rcat-pdf-hub/pull/285) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F11 | PDF to PDF/A | **CODE COMPLETE** | PR [#292](https://github.com/yiwssx/rcat-pdf-hub/pull/292) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F12 | PDF to SVG | **CODE COMPLETE** | PR [#282](https://github.com/yiwssx/rcat-pdf-hub/pull/282) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F13 | PDF to CSV | **CODE COMPLETE** | PR [#283](https://github.com/yiwssx/rcat-pdf-hub/pull/283) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F14 | PDF to RTF | **CODE COMPLETE** | PR [#284](https://github.com/yiwssx/rcat-pdf-hub/pull/284) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F15 | PDF to MOBI | **BLOCKED** | No accepted MOBI exporter | Find legitimate output engine; do not fake MOBI |
| F16 | PDF to GIF | **CODE COMPLETE** | PR [#278](https://github.com/yiwssx/rcat-pdf-hub/pull/278) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |
| F17 | PDF to BMP | **CODE COMPLETE** | PR [#280](https://github.com/yiwssx/rcat-pdf-hub/pull/280) · guarded exporter | Shared gated From-PDF UI [PR #340](https://github.com/yiwssx/rcat-pdf-hub/pull/340); QA deferred, flags OFF |

## Rules

- Source mapping is a conservative point-in-time engineering audit, not runtime inspection. A row must change to CODE COMPLETE only after a usable selected UI→API→queue/worker→owned-result pathway exists and basic tests pass for its stated subset.
- Reuse authentic original source and generated output; no stub output, renamed file extension, or false promise of format coverage.
- CI and essential source/unit tests remain mandatory for a merge. Expensive full Compose/real RCAT Workspace E2E, Thai golden documents, independent security/DR/rollout tests are **deferred**, never shown as PASS.
- Never deploy Production, flip an existing/new T90 feature flag, broaden RBAC or close the QA/Infrastructure issues by source-only work.

