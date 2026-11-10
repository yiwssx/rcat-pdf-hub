# M05 — private PDF text translator (Engineering First)

**Classification: PARTIAL, no deployment authorization.**

This source implements a bounded PDF selectable-text extraction pipeline, actual
LibreTranslate-compatible HTTP translation requests, typed owner-scoped API,
heavy RQ worker, private UTF-8 TXT or newly composed PDF output and guarded Web UI. It is not a dictionary
mock, online API or translated-layout PDF.

## Current capability and restrictions

- Only selectable PDF text; scanned pages need OCR separately.
- Translation pairs: English to Thai and Thai to English.
- Source: one PDF of at most 8 MiB and 20 pages, maximum 3,000 characters
  per page and 30,000 characters total. Strict source and output budgets.
- Output: page-marked UTF-8 TXT **or newly composed translated PDF**. The PDF
  is typeset by existing internal Gotenberg Chromium with Thai-capable Noto Sans
  Thai/Sarabun, text escaping, strict content security policy, PDF parse and
  visible-ink checks. No source geometry, tables, images or exact page counts
  are promised; the output is readable re-layout, NOT original-layout editing.
- The PDF render origin is fixed to http://gotenberg:3000 (internal-only), with
  no ambient HTTP proxy, redirects, external HTML references or public API.
- The PDF selection is a separate typed /translation/pdf operation, with
  owner/MIME/expiry/flag checks repeated in the heavy Worker and unchanged
  authorization. The existing TXT route remains available.
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

**Next:** an [offline-model source profile](../../ops/translation/README.md)
and a bilingual API probe now exist on a guarded development branch, but
no actual local models are installed or verified. A separately authorized
operator must validate the license and provision the model, then inspect real
Thai quality and layout. M05 remains PARTIAL.
