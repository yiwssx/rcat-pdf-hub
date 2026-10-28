# T90-1.2 — M02 Compression, M10 Rotation, M15 Rearrange binary gate

Parent [T90-1 #225](https://github.com/yiwssx/rcat-pdf-hub/issues/225) · predecessor [T90-1.1 Draft #226](https://github.com/yiwssx/rcat-pdf-hub/pull/226).

## Existing behavior tested (no added runtime capability)

- **M02 / Compress:** execute the existing **real Ghostscript** PDF engine, parse the result in strict mode, assert page count/text and per-page physical geometry; assert source SHA-256 unchanged. Do **not** promise output is always smaller, or visually lossless; some compressions can increase size.
- **M10 / Rotate:** run the real **qpdf** command, rotate exactly one selected page, assert unaffected pages and text layers; verify -90° normalizes to 270°; reject bad degrees and injected/malformed page ranges *before* subprocess.
- **M15 / Rearrange:** use actual **pypdf** write/read, assert page order, repeated selections and per-page rotations; reject empty/out-of-bounds/invalid plans and preserve original bytes.
- **API scope/ownership:** for the three existing routes, real FastAPI session and DB enforce specific scope, original FileRecord owner and persisted PDF MIME before enqueue; request creates owner-bound JobRecord when valid. Only external RQ enqueue is stubbed.
- **No UI, queue, engine, database schema, dependency, security or deployment changes.** The retained 13 operation allowlist remains exact.

## CI checks and boundaries

- [ ] Docker Core API host image actually runs (does not skip) Ghostscript/qpdf binary tests; all new tests pass
- [ ] Full Core API CI plus PostgreSQL/Valkey/S3 acceptance green; Web CI, CodeQL and Dependency Review green
- [ ] Classify any binary incompatibility by affected M02/M10/M15 and address within the same PR
- [ ] Independent browser visual QA, Thai golden documents, signed output download/expiry, real Compose full user journey and operational rollback are still pending for T90-1.8/T90-5.
- [ ] Until explicit acceptance, leave canonical tool states as BASELINE and RELEASED counter 0/90.

Keep this a **draft, review-only** change until checked. Do not merge automatically, run production migrations, deploy or turn on any T90 feature flags.
