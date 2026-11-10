# T90-2 T21 Publisher — immutable third-party QA sample

T21 is a **limited** Microsoft Publisher CFB/LibreOffice import adapter,
not universal Publisher compatibility. This note separates evidence stages.

## Engineering MAC evidence — independently referenced second Publisher source (PR #367, 2026-11-10)

- Apache POI `test-data/publisher/Sample.pub` at immutable upstream commit `cdcdcf1833beb8483229be5989db1ee3b98232c2`, expected Git blob `b870168319048c9e8631c2338eb937e6f8f62b5b`.
- Independent upstream reference `test-data/publisher/Sample.txt` at the same commit explicitly describes page 1 and page 2 original Publisher contents; it is not synthesized from the exported PDF.
- Existing pinned disposable Gotenberg native test imported the real source to **2 pages**, found exact source-referenced phrases on both pages with `pdftotext`, rendered both pages with `pdftoppm` and confirmed visible ink. Source SHA-256 was unchanged.
- Exact real CI output from [Lean CI run #42833699424](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/42833699424): `T21_PUBLISHER_POI_EVIDENCE source_sha256=6fefdef46b87c767150878dc384549cb2d2ec2ac54de25f8ddb3a5628301107e output_sha256=fd39fe341fcb3a87a44edc1b67f00fcb077466d74cfb880150f59307676f26a6 pages=2 source_reference=Apache-POI-Sample.txt page2_text_preserved=true both_pages_nonblank=true immutable_source=true`.
- **Engineering MAC met for this explicitly bounded v3 CFB Publisher subset, conditional on merged protected checks.** T21 now selectable in staged Web; deployment flags OFF. Text and ink evidence is not exact color, geometry, fonts, pictures, Thai styles, or universal Publisher fidelity.
- The older LibreOffice `fdo59355-1.pub` still renders blank page 2; no source page-2 reference for that separate sample. Runtime guard rejects it as suspect.

## Existing source and process proof

- Real publisher file: LibreOffice core writerperfect QA `fdo59355-1.pub`.
- Immutable revision: `fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4`
- Exact Git blob: `607a07ae2d362e4a1f6e779dfff88726fe74f910`
- 10,752-byte OLE CFB file; strict parser checks source header/streams.
- Actual pinned disposable Gotenberg/LibreOffice binary import to PDF;
  expected 2 A4 pages; verified nonblank raster of **first page** only.
- Source SHA-256 is checked again after the conversion.

`scripts/test-t90-2-publisher-gotenberg.sh` emits
`T90_2_T21_REAL_PUBLISHER_EVIDENCE` **only after all checks pass** with
the observed source/output SHA-256 values (not pre-filled or invented).
Its job log is public-fixture technical provenance, not an institutional
font or cross-owner release certification.

For any T90-5 `STAGED` credit, use the actual successful run URL, its
observed 64-digit hashes and exact merge commit / PR. Keep the file strictly
bounded to the known OLE subset. Do not mark `VERIFIED` or `RELEASED`
without real RCAT OIDC sessions, Thai font/layout and PDF visible-page
goldens, AV/abuse/sandbox tests, and independent operator signoff.

## Remaining independent checks

- [x] Immutable upstream authentic .pub binary downloaded in ephemeral CI.
- [x] Size/signature and upstream Git SHA checked.
- [x] Native CFB parser + actual pinned LibreOffice converter run.
- [x] Two A4 PDF pages, visible rasterized page 1, source immutability.
- [x] Independent CI rasterizes page 2 and explicitly reports its observed blankness; **this is a known evidence gap, not successful visual fidelity**. See PR #276 and the per-page job log.
- [ ] Historical `fdo59355-1.pub` page-2 intent remains unknown; alternative Apache POI sample has independent page-2 source reference and passes limited MAC.
- [ ] Multiple genuine Publisher generations / fonts / Thai print documents.
- [ ] Production-equivalent owner-bound API→queue→worker→signed download.
- [ ] Independent isolation/AV/recovery and RCAT-only OIDC signoff.

## New factual observation from real CI

During PR #276 preliminary [Core API CI](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41424089415), job 125206365292, Poppler rendered page 1 with nonwhite pixels but **page 2 returned a visually blank raster**. The PDF remains two A4 pages. Without a trustworthy visual reference of the source page 2, this observation cannot distinguish intentional blank-page semantics from a LibreOffice import defect. The corrected QA script records each page's visible/blank status instead of falsely labeling both pages as nonblank. T21 remains **STAGED** for independent QA, distinct from the now source-complete bounded MAC.

## MAC-safe runtime rejection (Engineering First, 2026-11-10)

The existing converter previously accepted a PDF if *any* output page contained visible ink. Publisher output is now independently checked with bounded PDFium rasterization across **every** page (maximum 24 pages and limited dimensions), before delivery. A visually blank page causes an explicit failed job with no delivered PDF. This rejects also intentionally blank source pages, which are outside the narrowly supported source set; it does **not** prove the output geometry or number of source pages matches the original. The historical blank-page fixture still fails closed; Apache POI independently demonstrates a supported nonblank subset, now selectable in staged Web with flags OFF. See the [five-tool MAC decision](t90-five-partial-mac-decision-20261110.md).
