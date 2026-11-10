# T90: Minimum Acceptable Capability (MAC) for five PARTIAL tools

**Decision date:** 2026-11-10. **Workstream:** Engineering First Issue #172. **Scope:** development-source only; NOT QA, release, Production activation or a permission grant. Credit status changes only after the exact protected-head PR checks pass.

## Acceptance rule

CODE COMPLETE (MAC-scoped) requires a discoverable guarded Web operation, actual owner/scope/type checks, API -> queue -> worker execution, an authentic retrievable artifact, and source-level regression. Unsupported subsets must be visible at the UI. A mock, a relabel or a green CI alone cannot fulfill a missing feature. Status cannot mean unrestricted format support or RELEASED.

| ID | Minimum accepted function | Evidence and excluded scope | Decision |
| --- | --- | --- | --- |
| M01 - Edit PDF | Replace one unambiguous, same-length span of original PDF text on a selected page; use verified existing glyphs and mappings, preserve text positioning, source immutable, return new PDF | Bounded ASCII/Thai non-combining glyph edits in real original text object; owner-bound job, guarded UI and PDF tests. No arbitrary editing, Thai marks/complex shaping, CID, scanned PDFs, annotation, forms, redaction or layout reflow | **CODE COMPLETE for literal-text replacement MAC only**, NOT generic PDF editing |
| M05 - PDF Translator | Produce actual non-echoing English-to-Thai and Thai-to-English translation from selectable PDF text and real TXT or newly composed PDF | Typed owner-bound worker and bilingual PDF already implemented, but approved live local model and quality proof not installed. Existing worker-side isolated bilingual model probe is available, but no approved model is provisioned; mock provider cannot fulfill MAC. No scanned OCR or source geometry | **PARTIAL: MAC NOT MET until licensed model and real bilingual proof exist** |
| M06 - Chat with PDF | Multiple questions about an owned PDF, verbatim cited evidence passages, optional prior-query context and per-question job links | Source-grounded search and six-turn UI work; no generative answers, semantic inference, pronoun reasoning or OCR. Must be advertised as question-based evidence lookup only | **CODE COMPLETE for evidence-only inquiry MAC**, NOT generative AI chat |
| M12 - Sign PDF | Draw or upload a PNG visual signature and position on an owner-held PDF page; output a new PDF with visible image | Real M23 PDF image overlay, PNG upload, owner/scope/geometry checks, guarded signature pad and tests. No certificate-backed identity/integrity, CMS/PAdES, timestamps or legal guarantee | **CODE COMPLETE for visual-signature MAC**, NOT cryptographic signing |
| T21 - PUB to PDF | Genuine import of supported v3 CFB Publisher document with visible preserved pages and authentic PDF | Pinned native LibreOffice + strict CFB parser; second authentic Apache POI `Sample.pub` retains page-1/page-2 *source-referenced* text from Apache POI `Sample.txt`, both pages raster visibly nonblank in real disposable CI. Publisher-only every-page PDFium ink guard rejects unreliable blank output. No universal layout/font proof | **CODE COMPLETE for explicitly bounded Publisher input subset**, NOT universal .pub compatibility; flags OFF |

## Minimal remaining unblockers

**M05:** Provision an approved immutable private translator image with licensed installed English-Thai/Thai-English model packages in the existing isolated opt-in network. Pass real two-direction model readiness with fixed public sentences and verify Thai quality and reflow. The existing fixed-public-sentence model probe runs from worker-heavy on its isolated network and sends no institutional PDF. The API is not attached to that private network, so an API-side readiness check would give false negatives; no such endpoint or widened network permission is introduced. No software-only change may substitute for the genuine model.

**T21:** The alternative approved evidence path is now met for the bounded subset: real Apache POI `Sample.pub` and its independently published `Sample.txt` show both original page contents, and actual disposable Gotenberg output contains both matching page passages and nonblank rasters. The distinct LibreOffice `fdo59355-1.pub` fixture still has an ambiguous blank second page and continues to fail closed. Do not claim all Publisher variants, Thai typography or visual geometry fidelity.

**M01 / M06 / M12:** Already merged engines and typed guarded Web flows meet these deliberately limited MACs. Engineering scope may close after checks; broader feature promises remain explicitly unsupported. No feature flag is enabled merely because an inventory row is CODE COMPLETE.

**Release separation:** 0 VERIFIED / 0 RELEASED in independent T90 QA. Production deployment, OIDC, Thai physical/visual QA, security and DR acceptance remain outside this change (QA #262/#308 and infra #195/#323). No model weights, signing keys, external dependency, secret, runtime deployment or networking changes.

**Updated after T21 PR #367:** 82 CODE COMPLETE (MAC-scoped) / 1 PARTIAL (M05) / 0 MISSING / 7 BLOCKED = 90; only when protected exact-head checks pass and PR merges. No Production activation or independent QA claimed.
