# T90: Minimum Acceptable Capability (MAC) for five PARTIAL tools

**Decision date:** 2026-11-10. **Workstream:** Engineering First Issue #172. **Scope:** development-source only; NOT QA, release, Production activation or a permission grant. Credit status changes only after the exact protected-head PR checks pass.

## Acceptance rule

CODE COMPLETE (MAC-scoped) requires a discoverable guarded Web operation, actual owner/scope/type checks, API -> queue -> worker execution, an authentic retrievable artifact, and source-level regression. Unsupported subsets must be visible at the UI. A mock, a relabel or a green CI alone cannot fulfill a missing feature. Status cannot mean unrestricted format support or RELEASED.

| ID | Minimum accepted function | Evidence and excluded scope | Decision |
| --- | --- | --- | --- |
| M01 - Edit PDF | Replace one unambiguous, same-length span of original PDF text on a selected page; use verified existing glyphs and mappings, preserve text positioning, source immutable, return new PDF | Bounded ASCII/Thai non-combining glyph edits in real original text object; owner-bound job, guarded UI and PDF tests. No arbitrary editing, Thai marks/complex shaping, CID, scanned PDFs, annotation, forms, redaction or layout reflow | **CODE COMPLETE for literal-text replacement MAC only**, NOT generic PDF editing |
| M05 - PDF Translator | Produce actual non-echoing English-to-Thai and Thai-to-English translation from selectable PDF text and real TXT or newly composed PDF | Typed owner-bound worker and bilingual PDF already implemented, but approved live local model and quality proof not installed. Added guarded readiness probe and disabled submission when absent; mock provider cannot fulfill MAC. No scanned OCR or source geometry | **PARTIAL: MAC NOT MET until licensed model and real bilingual proof exist** |
| M06 - Chat with PDF | Multiple questions about an owned PDF, verbatim cited evidence passages, optional prior-query context and per-question job links | Source-grounded search and six-turn UI work; no generative answers, semantic inference, pronoun reasoning or OCR. Must be advertised as question-based evidence lookup only | **CODE COMPLETE for evidence-only inquiry MAC**, NOT generative AI chat |
| M12 - Sign PDF | Draw or upload a PNG visual signature and position on an owner-held PDF page; output a new PDF with visible image | Real M23 PDF image overlay, PNG upload, owner/scope/geometry checks, guarded signature pad and tests. No certificate-backed identity/integrity, CMS/PAdES, timestamps or legal guarantee | **CODE COMPLETE for visual-signature MAC**, NOT cryptographic signing |
| T21 - PUB to PDF | Genuine import of supported v3 CFB Publisher document with visible preserved pages and authentic PDF | Pinned LibreOffice importer and real sample exist, but output page 2 appears blank and no trustworthy original page-2 preview exists. Added per-page raster ink rejection to prevent silent success, which also excludes intentionally blank source pages from the narrow supported subset. No page-fidelity credit yet | **PARTIAL: MAC NOT MET; keep T21 withheld in Web** |

## Minimal remaining unblockers

**M05:** Provision an approved immutable private translator image with licensed installed English-Thai/Thai-English model packages in the existing isolated opt-in network. Pass real two-direction model readiness with fixed public sentences and verify Thai quality and reflow. The authenticated model-readiness route never sends a user's document and stays disabled under existing feature flags; when absent, the staged Web prevents knowingly doomed translation jobs. No software-only change may substitute for the genuine model.

**T21:** Compare the true source page 2 of the upstream publisher test document to the blank output. Alternatively provide a trustworthy second real sample with validated nonblank content on all pages; prove actual conversion with preserved content. Keep withheld until credible source-to-output evidence; do NOT silently drop pages, fabricate content or pretend the raster rejection proves geometry fidelity.

**M01 / M06 / M12:** Already merged engines and typed guarded Web flows meet these deliberately limited MACs. Engineering scope may close after checks; broader feature promises remain explicitly unsupported. No feature flag is enabled merely because an inventory row is CODE COMPLETE.

**Release separation:** 0 VERIFIED / 0 RELEASED in independent T90 QA. Production deployment, OIDC, Thai physical/visual QA, security and DR acceptance remain outside this change (QA #262/#308 and infra #195/#323). No model weights, signing keys, external dependency, secret, runtime deployment or networking changes.

**Expected merged inventory:** 81 CODE COMPLETE (MAC-scoped) / 2 PARTIAL / 0 MISSING / 7 BLOCKED = 90. The remaining PARTIAL entries are M05 and T21.
