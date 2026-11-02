# T90-2 code-only completion / physical acceptance deferred (2026-11-02)

**Goal:** finish safe, bounded engineering paths for all 40 canonical Convert-to-PDF entries. The owner has explicitly deferred physical / operator / actual school-server / restricted real-source-file tests. **DO NOT mark deferred checks PASS.**

## Code versus acceptance

- **40/40 canonical IDs have guarded source-code paths prepared**: 34 restricted formats have a STAGED backend path in the ordinary opt-in router, and the remaining 6 have dedicated **experimental**, individually disabled paths/sidecars.
- **34 STAGED / 6 BLOCKED** remains the independent *format-acceptance* tally, not a claim that 6 lack all source code.
- **0 T90-2 independently VERIFIED or RELEASED.** T90-5 evidence remains more restrictive; its ledger must never be mass-updated to STAGED from this inventory.
- Feature flags stay OFF by default, native services are Compose opt-in profiles, remote URL importer requires a separate signed fetcher plus host egress proof, and the existing 13 legacy operations stay unchanged.
- A source-path smoke or binary PDF check does **not** establish correct Thai typography, fidelity across real source variants, or authorization in production.

## Deferred for physical, original-file or target-infrastructure acceptance (not failures / not passes)

| ID | Development code available | Still deferred before acceptance |
| --- | --- | --- |
| T09 HEIC | Pinned patched libheif decoder + native sidecar + genuine upstream HEVC test | Phone/camera HEIC corpus, orientation/ICC, all-frame semantics, deployed isolated runtime & RCAT owner session |
| T25 HEIF | Pinned decoder, generated lossless HEIF→PDF native smoke | Externally produced HEIF variant corpus, alpha/depth frames and fidelity, target runtime/codec license review |
| T20 DWG | Fail-closed LibreDWG native 2D bridge | Rights-cleared genuine DWG versions, layers/fonts/units/scale, licensing signoff, real CAD comparison |
| T30 CHM | Bounded CHM offline extraction and sanitization | Genuine CHM/LZX language/TOC cases, malformed binary corpus, target isolation/AV proof |
| T33 URL | HTTPS/TLS DNS-pinned signed URL-fetch sidecar, sanitized text-only HTML | RCAT host firewall/egress verification, DNS rebinding and private endpoint adversarial probe on intended host |
| T34 WPS | Microsoft Works native writerperfect WPS→ODT→PDF prototype | Genuine Microsoft Works generations, nonblank content + source layout, font fidelity, licensing and institutional runtime |

**Also deferred across all 40:** real RCAT Workspace SSO accounts; permission/expiry/owner upload→queue→worker→signed-download; real school typography and PDF page-to-page source goldens (including the known **T21 Publisher second page visibly blank** question); AV, firewall, load, monitoring, rollback and operator signoff. These remain open in issues #237/#262.

## Evidence already available without physical RCAT access

1. T09 pinned developer-authored real external `.heic` went through actual nonroot/no-network/read-only Docker native→PDF with 1 rendered visible page, source/output SHA-256 in [GitHub Actions #41424284804](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41424284804). This is **not** a phone-camera golden.
2. T25 generated lossless HEIF→PDF actual decoder smoke passed in the same pinned native Docker job (not an independent external HEIF corpus).
3. T21 publisher `fdo59355-1.pub` is independently STAGED by [PR #275](https://github.com/yiwssx/rcat-pdf-hub/pull/275), but a second-page raster inspection in [PR #276](https://github.com/yiwssx/rcat-pdf-hub/pull/276) found page 2 visually blank; acceptance needs source comparison.
4. 34 restricted staged entries have bounded API/worker paths and automated negative tests. Each has a restricted supported subset, not universal format compatibility.

## Software merge rule (does not confer pilot release)

- Commit and PR must be based on up-to-date `main`, preserve institutional SSO, F09 TIFF/M33 form engines and existing default-OFF guards.
- Exact PR head: Core API CI, Web CI, CodeQL, Dependency Review **and** dedicated native Docker isolation workflow PASS; zero unresolved code reviews.
- CI must prove all 40 canonical IDs have a code path and that the five native formats and one URL format remain distinct from the 34 STAGED acceptance paths.
- Merge engineering code behind disabled switches if all software checks pass. Do **not** activate, deploy, re-label as VERIFIED, or close the acceptance issue.
- Work that inherently requires RCAT's target host, real institutional fixture, human source-vs-PDF visual inspection, license approval or firewall control remains parked, visibly unchecked, for later.

Source map: `apps/api/app/t90_2_catalog.py` (`EXPERIMENTAL_CODE_PATHS`, `code_prepared`), `app/native_format_policy.py`, `app/staged_to_pdf_adapters.py`, `app/routers/to_pdf.py`, `app/worker_tasks.py`, `compose.native-sidecar.yaml`, `compose.url-fetcher.yaml`, and `apps/api/tests/test_t90_2_native_dev_integrations.py`.
