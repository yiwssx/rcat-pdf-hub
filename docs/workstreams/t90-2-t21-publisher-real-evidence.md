# T90-2 T21 Publisher — immutable third-party QA sample

T21 is a **limited** Microsoft Publisher CFB/LibreOffice import adapter,
not universal Publisher compatibility. This note separates evidence stages.

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
- [ ] Determine whether page 2 is intentionally blank in the original Publisher source using a trusted source preview/reference before claiming page-fidelity.
- [ ] Multiple genuine Publisher generations / fonts / Thai print documents.
- [ ] Production-equivalent owner-bound API→queue→worker→signed download.
- [ ] Independent isolation/AV/recovery and RCAT-only OIDC signoff.

## New factual observation from real CI

During PR #276 preliminary [Core API CI](https://github.com/yiwssx/rcat-pdf-hub/actions/runs/41424089415), job 125206365292, Poppler rendered page 1 with nonwhite pixels but **page 2 returned a visually blank raster**. The PDF remains two A4 pages. Without a trustworthy visual reference of the source page 2, this observation cannot distinguish intentional blank-page semantics from a LibreOffice import defect. The corrected QA script records each page's visible/blank status instead of falsely labeling both pages as nonblank. T21 remains **STAGED** and this is an unresolved `VERIFIED` gate.
