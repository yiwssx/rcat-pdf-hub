# M05 — private PDF text translator (Engineering First)

**Classification: PARTIAL, no deployment authorization.**

This source implements a bounded PDF selectable-text extraction pipeline, actual
LibreTranslate-compatible HTTP translation requests, typed owner-scoped API,
heavy RQ worker, private UTF-8 output and guarded Web UI. It is not a dictionary
mock, online API or translated-layout PDF.

## Current capability and restrictions

- Only selectable PDF text; scanned pages need OCR separately.
- Translation pairs: English to Thai and Thai to English.
- Source: one PDF of at most 8 MiB and 20 pages, maximum 3,000 characters
  per page and 30,000 characters total. Strict source and output budgets.
- Output: page-marked UTF-8 TXT, NOT a translated PDF and NOT layout-preserving.
- Private provider: fixed HTTP address http://pdf-translate:5000/translate;
  compatible with self-hosted LibreTranslate REST translation endpoint.
- The translator model and Thai/English language packages are NOT included or
  deployed by this code. It will fail closed when the server is absent.
- Before authorization an operator must provision an approved locally hosted
  translation model, verify bilingual quality and licenses, restrict Docker
  networking without internet egress, forbid plaintext request logging and
  outbound data transfer, and validate system retention and RBAC.
- No arbitrary user-controlled URL, no proxy environment, no HTTP redirects;
  strict provider body size and schema, whole-job atomic output, immutable source
  verified by SHA-256, existing owner job/download and file expiry.
- Feature flags PDFHUB_PDF_TRANSLATION_TOOLS_ENABLED and
  PDFHUB_STAGED_TRANSLATION_WEB_ENABLED default OFF.
- Existing pdf:extract-text permission required, not broadened here.
- The R1 host preflight refuses a new backend gate set true.

Required CI and small service/queue/browser tests are the development gate.
No integrated model QA, Thai golden-document tests or production acceptance.
Independent QA and Production remain deferred.

**Next:** deploy and validate a licensed on-premise model only after explicit
operator authorization; add translated PDF output with visually reviewed Thai
typesetting before declaring this tool CODE COMPLETE.
