# RCAT PDF HUB — T90 Engineering-First inventory

**Snapshot:** 2026-11-09; based on tracked source at `main` (before any new UI work in this workstream). Canonical 90 IDs: [PDF tool registry](../../contracts/pdf-tools.v1.json). Independent code evidence: [T90 ledger](../../contracts/t90-rcat-pilot-acceptance.v1.json). Convert-to-PDF prepared format map: [T90-2 catalog](../../apps/api/app/t90_2_catalog.py). **This is NOT production certification.**

## Scope and definitions

The original requested deliverable is **90 discoverable user-facing tools**, not 90 independently implemented conversion engines. A shared backend may serve many tools; do not recreate or re-qualify it 90 times.

- **CODE COMPLETE**: existing scoped engine, an existing UI route/workspace interaction and basic code tests for the supported subset; may still be feature-gated OFF and QA PENDING. Does **not** mean deployed or fully format-compatible.
- **PARTIAL**: useful legacy/backend source path exists but the named tool still lacks a distinct selectable user workflow, or advertised feature subset is incomplete. Especially, the 34 T90-2 staged converters and 16 F exports must get shared Web UI rather than 50 one-off frontends.
- **MISSING**: no dedicated usable engine+workflow demonstrated in source audit; proposed adapter alone is not proof of code.
- **BLOCKED**: code prototype exists but production-usable capability needs a genuine external codec/engine, validated license, restricted network/container dependency or other technical prerequisite. F15 has no accepted MOBI output engine. Blockers remain explicit; not 100% delivery claims.

**Dev-only rollup:** CODE COMPLETE **9**, PARTIAL **63**, MISSING **11**, BLOCKED **7** = **90**. This conservative *user-facing workflow readiness* is deliberately different from independent T90 source evidence ledger **40 IMPLEMENTED + 1 STAGED + 49 UNASSESSED**. Source evidence counts and tool usability may change independently.

| Family | CODE COMPLETE | PARTIAL | MISSING | BLOCKED | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Manage PDF | 9 | 13 | 11 | 0 | 33 |
| Convert to PDF | 0 | 34 | 0 | 6 | 40 |
| Convert from PDF | 0 | 16 | 0 | 1 | 17 |
| **Total** | **9** | **63** | **11** | **7** | **90** |

## Prioritized engineering leverage

1. **One shared, disabled-by-default To-PDF Web workflow** for 34 prepared guarded format routes; existing upload, queue, worker, result/download reused. This removes a repeated UI dependency without claiming formats are certified.
2. **One shared From-PDF Web workflow** for 16 prepared guarded exporters. Respect each typed input/parameters and existing scopes. No new engine per format.
3. **Manage gaps:** M21 image-watermark, M20 viewer and eleven MISSING features; use bounded operation-specific adapters and shared UI, not fresh infrastructure.
4. **True technical blockers:** six native/URL T formats, F15 MOBI, and T21 publisher incomplete page source fidelity. Record honest scope/requirements and only revisit after ordinary capabilities.
5. **QA/Operations parked:** R1 negative identity/owner tests, native/SSRF host tests, Thai physical/visual goldens, load/DR and independent RELEASED proof stay in [QA #262](https://github.com/yiwssx/rcat-pdf-hub/issues/262), [R1 #308](https://github.com/yiwssx/rcat-pdf-hub/issues/308), [CI #195](https://github.com/yiwssx/rcat-pdf-hub/issues/195), [DR #323](https://github.com/yiwssx/rcat-pdf-hub/issues/323). These do NOT block closing an otherwise complete engineering subtask.

## All 90 tools — audit baseline

| ID | Tool | Dev status | Engine/source evidence | Next engineering work |
| --- | --- | --- | --- | --- |
| M01 | Edit PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M02 | Compress PDF | **CODE COMPLETE** | Legacy `compress` | Defer independent QA; preserve code/CI |
| M03 | PDF Summarizer | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M04 | Merge PDF | **CODE COMPLETE** | Legacy `merge` | Defer independent QA; preserve code/CI |
| M05 | PDF Translator | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M06 | Chat with PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
| M07 | Split PDF | **PARTIAL** | PR [#300](https://github.com/yiwssx/rcat-pdf-hub/pull/300) · bounded engine | Finish split / multi-output UI and ZIP delivery |
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
| M20 | PDF Viewer | **PARTIAL** | PDF preview primitives | Complete viewer UI controls and page/navigation |
| M21 | Add watermark | **PARTIAL** | Legacy `watermark` | Add image-watermark capability; existing text mode is not full coverage |
| M22 | Add text | **PARTIAL** | PR [#297](https://github.com/yiwssx/rcat-pdf-hub/pull/297) · bounded engine | Finish missing subset / usable Web UI; no full-host QA |
| M23 | Add image to PDF | **MISSING** | No dedicated engine found | Develop scoped adapter + tool workflow |
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
| T01 | Word to PDF | **PARTIAL** | `doc-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T02 | JPG to PDF | **PARTIAL** | `jpg-to-pdf, jpeg-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T03 | PNG to PDF | **PARTIAL** | `png-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T04 | EPUB to PDF | **PARTIAL** | `epub-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T05 | DOCX to PDF | **PARTIAL** | `docx-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T06 | Excel to PDF | **PARTIAL** | `xls-to-pdf, xlsx-to-pdf, ods-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T07 | PPT to PDF | **PARTIAL** | `ppt-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T08 | PPTX to PDF | **PARTIAL** | `pptx-to-pdf, odp-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T09 | HEIC to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T10 | HTML to PDF | **PARTIAL** | `html-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T11 | DjVu to PDF | **PARTIAL** | `djvu-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T12 | PAGES to PDF | **PARTIAL** | `pages-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T13 | TIFF to PDF | **PARTIAL** | `tiff-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T14 | TXT to PDF | **PARTIAL** | `txt-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T15 | ODT to PDF | **PARTIAL** | `odt-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T16 | SVG to PDF | **PARTIAL** | `svg-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T17 | CSV to PDF | **PARTIAL** | `csv-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T18 | RTF to PDF | **PARTIAL** | `rtf-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T19 | MOBI to PDF | **PARTIAL** | `mobi-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T20 | DWG to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T21 | PUB to PDF | **PARTIAL** | `pub-to-pdf` (guarded) | Known Publisher page 2 blank risk; keep subset under review |
| T22 | XPS to PDF | **PARTIAL** | `xps-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T23 | XML to PDF | **PARTIAL** | `xml-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T24 | WebP to PDF | **PARTIAL** | `webp-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T25 | HEIF to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T26 | JFIF to PDF | **PARTIAL** | `jfif-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T27 | GIF to PDF | **PARTIAL** | `gif-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T28 | BMP to PDF | **PARTIAL** | `bmp-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T29 | HWP to PDF | **PARTIAL** | `hwp-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T30 | CHM to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T31 | FB2 to PDF | **PARTIAL** | `fb2-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T32 | ZIP to PDF | **PARTIAL** | `zip-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T33 | URL to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T34 | WPS to PDF | **BLOCKED** | Native/URL prototype only (OFF) | Runtime/license/egress dependency; keep OFF |
| T35 | EML to PDF | **PARTIAL** | `eml-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T36 | MD to PDF | **PARTIAL** | `md-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T37 | DXF to PDF | **PARTIAL** | `dxf-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T38 | CBZ to PDF | **PARTIAL** | `cbz-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T39 | AI to PDF | **PARTIAL** | `ai-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| T40 | CBR to PDF | **PARTIAL** | `cbr-to-pdf` (guarded) | Reuse one Web converter UI + bounded output flow |
| F01 | PDF OCR | **PARTIAL** | PR [#292](https://github.com/yiwssx/rcat-pdf-hub/pull/292) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F02 | PDF to Word | **PARTIAL** | PR [#286](https://github.com/yiwssx/rcat-pdf-hub/pull/286) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F03 | PDF to JPG | **PARTIAL** | PR [#291](https://github.com/yiwssx/rcat-pdf-hub/pull/291) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F04 | PDF to PNG | **PARTIAL** | PR [#291](https://github.com/yiwssx/rcat-pdf-hub/pull/291) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F05 | PDF to EPUB | **PARTIAL** | PR [#289](https://github.com/yiwssx/rcat-pdf-hub/pull/289) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F06 | PDF to DOCX | **PARTIAL** | PR [#286](https://github.com/yiwssx/rcat-pdf-hub/pull/286) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F07 | PDF to Excel | **PARTIAL** | PR [#287](https://github.com/yiwssx/rcat-pdf-hub/pull/287) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F08 | PDF to PPT | **PARTIAL** | PR [#290](https://github.com/yiwssx/rcat-pdf-hub/pull/290) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F09 | PDF to TIFF | **PARTIAL** | PR [#269](https://github.com/yiwssx/rcat-pdf-hub/pull/269) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F10 | PDF to ODT | **PARTIAL** | PR [#285](https://github.com/yiwssx/rcat-pdf-hub/pull/285) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F11 | PDF to PDF/A | **PARTIAL** | PR [#292](https://github.com/yiwssx/rcat-pdf-hub/pull/292) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F12 | PDF to SVG | **PARTIAL** | PR [#282](https://github.com/yiwssx/rcat-pdf-hub/pull/282) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F13 | PDF to CSV | **PARTIAL** | PR [#283](https://github.com/yiwssx/rcat-pdf-hub/pull/283) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F14 | PDF to RTF | **PARTIAL** | PR [#284](https://github.com/yiwssx/rcat-pdf-hub/pull/284) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F15 | PDF to MOBI | **BLOCKED** | No accepted MOBI exporter | Find legitimate output engine; do not fake MOBI |
| F16 | PDF to GIF | **PARTIAL** | PR [#278](https://github.com/yiwssx/rcat-pdf-hub/pull/278) · guarded exporter | Reuse one From-PDF UI + bounded output flow |
| F17 | PDF to BMP | **PARTIAL** | PR [#280](https://github.com/yiwssx/rcat-pdf-hub/pull/280) · guarded exporter | Reuse one From-PDF UI + bounded output flow |

## Rules

- Source mapping is a conservative point-in-time engineering audit, not runtime inspection. A row must change to CODE COMPLETE only after a usable selected UI→API→queue/worker→owned-result pathway exists and basic tests pass for its stated subset.
- Reuse authentic original source and generated output; no stub output, renamed file extension, or false promise of format coverage.
- CI and essential source/unit tests remain mandatory for a merge. Expensive full Compose/real RCAT Workspace E2E, Thai golden documents, independent security/DR/rollout tests are **deferred**, never shown as PASS.
- Never deploy Production, flip an existing/new T90 feature flag, broaden RBAC or close the QA/Infrastructure issues by source-only work.

