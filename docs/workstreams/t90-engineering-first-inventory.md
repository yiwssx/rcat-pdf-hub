# RCAT PDF HUB — T90 Engineering-First inventory

**Snapshot:** 2026-11-09 after protected PRs [#339](https://github.com/yiwssx/rcat-pdf-hub/pull/339), [#340](https://github.com/yiwssx/rcat-pdf-hub/pull/340), [#341](https://github.com/yiwssx/rcat-pdf-hub/pull/341), [#343](https://github.com/yiwssx/rcat-pdf-hub/pull/343) and [#344](https://github.com/yiwssx/rcat-pdf-hub/pull/344) merged; current Engineering First source/workflow readiness. Canonical 90 IDs: [PDF tool registry](../../contracts/pdf-tools.v1.json). Independent code evidence: [T90 ledger](../../contracts/t90-rcat-pilot-acceptance.v1.json). Convert-to-PDF prepared format map: [T90-2 catalog](../../apps/api/app/t90_2_catalog.py). **This is NOT production certification.**

## Scope and definitions

The original requested deliverable is **90 discoverable user-facing tools**, not 90 independently implemented conversion engines. A shared backend may serve many tools; do not recreate or re-qualify it 90 times.

- **CODE COMPLETE**: existing scoped engine, an existing UI route/workspace interaction and basic code tests for the supported subset; may still be feature-gated OFF and QA PENDING. Does **not** mean deployed or fully format-compatible.
- **PARTIAL**: useful legacy/backend source path exists but the named tool still lacks a distinct selectable user workflow, or advertised feature subset is incomplete. After #339 and #340, 33 guarded To-PDF and all 16 guarded From-PDF choices have a shared user-facing workflow; T21 Publisher remains deliberately withheld for a known blank-page risk.
- **MISSING**: no dedicated usable engine+workflow demonstrated in source audit; proposed adapter alone is not proof of code.
- **BLOCKED**: code prototype exists but production-usable capability needs a genuine external codec/engine, validated license, restricted network/container dependency or other technical prerequisite. F15 has no accepted MOBI output engine. Blockers remain explicit; not 100% delivery claims.

**Dev-only rollup:** CODE COMPLETE **61**, PARTIAL **12**, MISSING **10**, BLOCKED **7** = **90**. This conservative *user-facing workflow readiness* is deliberately different from independent T90 source evidence ledger **40 IMPLEMENTED + 1 STAGED + 49 UNASSESSED** (source credit not yet reconciled for M20). Source evidence counts and tool usability may change independently.

| Family | CODE COMPLETE | PARTIAL | MISSING | BLOCKED | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Manage PDF | 12 | 11 | 10 | 0 | 33 |
| Convert to PDF | 33 | 1 | 0 | 6 | 40 |
| Convert from PDF | 16 | 0 | 0 | 1 | 17 |
| **Total** | **61** | **12** | **10** | **7** | **90** |

## Prioritized engineering leverage

1. **DONE — shared To-PDF Web workflow PR #339:** 33 selectable source-code formats (T21 Publisher withheld). Existing upload, queue, worker, result/download reused; default OFF and not certified.
2. **DONE — shared From-PDF Web workflow PR #340:** 16 selectable guarded exporter source-code tools using existing scopes and queues. No F15 MOBI claim, default OFF.
3. **Manage progress:** M23 done in #341, read-only M20 authenticated viewer done in #343, M07 authentic per-page PDF ZIP workspace done in #344. Next focus M21 image watermark, remaining Manage flows and bounded genuinely missing engines. No new infrastructure.
4. **True technical blockers:** six native/URL T formats, F15 MOBI, and T21 publisher incomplete page source fidelity. Record honest scope/requirements and only revisit after ordinary capabilities.
5. **QA/Operations parked:** R1 negative identity/owner tests, native/SSRF host tests, Thai physical/visual goldens, load/DR and independent RELEASED proof stay in [QA #262](https://github.com/yiwssx/rcat-pdf-hub/issues/262), [R1 #308](https://github.com/yiwssx/rcat-pdf-hub/issues/308), [CI #195](https://github.com/yiwssx/rcat-pdf-hub/issues/195), [DR #323](https://github.com/yiwssx/rcat-pdf-hub/issues/323). These do NOT block closing an otherwise complete engineering subtask.

## All 90 tools — current development snapshot (source only)

| ID | Tool | Dev status | Engine/source evidence | Next engineering work |
| --- | --- | --- | --- | --- |
| M01 | Edit PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M02 | Compress PDF | **CODE COMPLETE** | Legacy `compress` | Defer independent QA; preserve code/CI |
| M03 | PDF Summarizer | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M04 | Merge PDF | **CODE COMPLETE** | Legacy `merge` | Defer independent QA; preserve code/CI |
| M05 | PDF Translator | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M06 | Chat with PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M07 | Split PDF | **CODE COMPLETE** | PR [#300](https://github.com/yiwssx/rcat-pdf-hub/pull/300) bounded ZIP engine + [#344](https://github.com/yiwssx/rcat-pdf-hub/pull/344) guarded owner-scoped Web input/submit/results | Supports non-encrypted, unsigned, non-form, non-annotated PDF ≤16 MiB/200 pages; up to 80 unique pages; all gates OFF; QA deferred |
| M08 | Unlock PDF | **PARTIAL** | PR [#302](https://github.com/yiwssx/rcat-pdf-hub/pull/302) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M09 | Protect PDF | **PARTIAL** | PR [#303](https://github.com/yiwssx/rcat-pdf-hub/pull/303) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M10 | Rotate PDF | **CODE COMPLETE** | Legacy `rotate` | Defer independent QA; preserve code/CI |
| M11 | Crop PDF | **CODE COMPLETE** | PR [#236](https://github.com/yiwssx/rcat-pdf-hub/pull/236) · bounded engine | Defer independent QA; preserve code/CI |
| M12 | Sign PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M13 | Edit metadata | **CODE COMPLETE** | PR [#235](https://github.com/yiwssx/rcat-pdf-hub/pull/235) · bounded engine | Defer independent QA; preserve code/CI |
| M14 | Delete pages | **PARTIAL** | PR [#294](https://github.com/yiwssx/rcat-pdf-hub/pull/294) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M15 | Rearrange pages | **PARTIAL** | PR [#294](https://github.com/yiwssx/rcat-pdf-hub/pull/294) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M16 | Extract pages | **PARTIAL** | PR [#301](https://github.com/yiwssx/rcat-pdf-hub/pull/301) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M17 | Extract text | **CODE COMPLETE** | PR [#235](https://github.com/yiwssx/rcat-pdf-hub/pull/235) · bounded engine | Defer independent QA; preserve code/CI |
| M18 | Extract images | **PARTIAL** | PR [#304](https://github.com/yiwssx/rcat-pdf-hub/pull/304) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M19 | Add page numbers | **CODE COMPLETE** | Legacy `page-numbers` | Defer independent QA; preserve code/CI |
| M20 | PDF Viewer | **CODE COMPLETE** | Existing authenticated page-count/PNG preview/download APIs + [#343](https://github.com/yiwssx/rcat-pdf-hub/pull/343) Web route | Owner-scoped active PDF selector, page navigation, bounded page index/preview resolution and original download; default-OFF stage UI; no PDF edit; QA deferred |
| M21 | Add watermark | **PARTIAL** | Legacy `watermark` | Add image-watermark capability; existing text mode is not full coverage |
| M22 | Add text | **PARTIAL** | PR [#297](https://github.com/yiwssx/rcat-pdf-hub/pull/297) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M23 | Add image to PDF | **CODE COMPLETE** | Genuine JPEG/PNG image overlay + guarded Web [PR #341](https://github.com/yiwssx/rcat-pdf-hub/pull/341) | Defer real-host QA; keep stage flags OFF |
| M24 | Flatten PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M25 | Annotate PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M26 | Highlight PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M27 | Remove metadata | **CODE COMPLETE** | PR [#235](https://github.com/yiwssx/rcat-pdf-hub/pull/235) · bounded engine | Defer independent QA; preserve code/CI |
| M28 | Resize pages | **CODE COMPLETE** | PR [#236](https://github.com/yiwssx/rcat-pdf-hub/pull/236) · bounded engine | Defer independent QA; preserve code/CI |
| M29 | Whiteout PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M30 | Grayscale PDF | **PARTIAL** | PR [#305](https://github.com/yiwssx/rcat-pdf-hub/pull/305) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M31 | Header and footer | **PARTIAL** | PR [#306](https://github.com/yiwssx/rcat-pdf-hub/pull/306) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M32 | Repair PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M33 | PDF Filler | **PARTIAL** | PR [#270](https://github.com/yiwssx/rcat-pdf-hub/pull/270) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
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

