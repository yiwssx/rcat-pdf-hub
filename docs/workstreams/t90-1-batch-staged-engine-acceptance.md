# T90-1 batch engineering: M11/M28, M08/M09, M18/M30 (STAGED, not released)

## Delivery boundary
This PR introduces **only six static internal engines and deterministic binary tests**.
It does not mount a new API route, register a new worker operation, modify the
reviewed 13 legacy tools, enable any environment flag, alter user scopes,
change Docker topology or introduce a new artifact storage contract.

| Tracker | Engine | Demonstrated engineering evidence | Outstanding for VERIFY/RELEASE |
| --- | --- | --- | --- |
| T90-1.5 | M11 Crop | Select 1-based pages; cropped CropBox vs preserved MediaBox; mixed size/rotation; immutable source; reject unsafe rectangles | Browser selection and preview, rotated-screen coordinate conversion, annotations/visual review, authenticated Compose |
| T90-1.5 | M28 Resize | Exact output page dimensions, resized content and mixed geometry; immutable source | Aspect-ratio-preserving modes, safe print fidelity, annotations, browser/API/worker |
| T90-1.6 | M08 Unlock | Correct user/owner password only, reject incorrect password, decrypt to valid PDF | **Secret transport without persisting credentials to DB/RQ/audit**, signed downloads, authenticated lifecycle, service threat review |
| T90-1.6 | M09 Protect | User + distinct owner password, PDF AES-256 (/V=5, /R=6), correct-password round trip | Secret handoff, password UX/validation, output permission review, live stack |
| T90-1.7 | M18 Extract images | Original embedded XObject image bytes in deterministic ZIP; not screenshots | Limits on image decompression, color profiles/unsupported image formats, multi-artifacts/ZIP UX |
| T90-1.7 | M30 Grayscale | Real Ghostscript generated PDF, text and gray raster visual proof | Form/signature warning, complex Thai/glyph/vector fidelity and visual QA, worker/API/UI |

All outputs are written atomically, no source is overwritten, and encrypted
inputs fail closed except in the dedicated password-verified unlock routine.
Tests live in the pinned API image and run in Core API CI.

## Security / wording constraints

- **Crop is not redaction**: hidden text remains in original page streams.
- **Resize exact-size is not aspect-ratio preserving**: independent X/Y scaling
  can visibly stretch the document.
- **Unlock is not a password bypass**. No attempt with empty/default guessed
  credentials. Valid user/owner password required. Do not persist secrets.
- **Native image extraction is not page-to-image conversion**.
- **Grayscale conversion may drop digital signatures, forms or annotations**;
  it must not be offered as a preservation-verified workflow.
- Do not claim six tools are VERIFIED/RELEASED from these tests.
  No production deployment, user-facing activation, or T90-1 task closure.

## Next integrated gates

1. Review secret-safe credential handoff for M08/M09; do **not** reuse
   JobRecord.params_json or RQ arguments for passwords.
2. Add owner-authenticated separate staging routes, worker cleanup, storage
   quota, AV, expiry, cancellation and output ZIP MIME as explicit reviewed contracts.
3. Add keyboard/mobile user workflow, Thai golden PDF suite, signed-download and
   live Docker Compose/Valkey/RQ/PostgreSQL/storage evidence.
4. Inspect PR CI (Core API, Web, CodeQL, Dependency Review) and attach the result
   to issue #225. T90-5 production authorization remains mandatory.
