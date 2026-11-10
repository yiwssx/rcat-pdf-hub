# M06 — Follow-up evidence search, Engineering First (source only)

**What users get:** a scoped multi-question evidence-search session for one owner-held PDF. On the staged M03/M06 page, M06 records up to six submitted questions and links to each existing job's authenticated UTF-8 result. The next question may optionally send the immediately preceding question as a **weak lexical context hint**. Switching the PDF clears session history; no transcript is persisted in the application database, and no new persistence/API dependency is introduced.

## Source-grounded behavior

- Existing M06 route `/api/v1/pdf/document-assist/evidence` still submits a normal owner-scoped RQ job with one PDF file ID and a `question` of 3–250 characters. The only new optional field is `previous_question`, also limited to 3–250 characters when supplied; controls, unknown fields and oversized input fail closed.
- The API and worker keep the same owner, expiry, scope, MIME, input-byte cap and default-OFF gates. Worker params are strictly limited to `question` and, optionally, `previous_question`; M03 summary never accepts either field.
- The original PDF's selectable text layer is extracted once per job. The current question's actual lexical matches always rank above any context-only matches. The previous question may break ties and provide a **clearly labeled fallback** if the new question has no direct lexical match. Fallback passages explicitly state that they **do not answer** the new question.
- Every returned passage is verbatim text drawn from the original PDF and includes its physical page number. Empty searches say no matching evidence. Results are a bounded UTF-8 TXT artifact delivered through the existing job authorization/download, never fabricated AI prose.
- Session history is client-side only, no browser storage and no cross-file carry-over. Users can disable context, ask additional questions or clear the visible history.

## Non-goals / truthful limits

This remains a **PARTIAL** implementation of the named "Chat with PDF" tool, not a generative chatbot. It cannot resolve pronouns, perform semantic entailment, synthesize a new answer, translate, extract scans without OCR, or guarantee paragraph context beyond the quoted text. Thai search still relies on literal token matching; complex Thai segmentation and semantic paraphrase search are not claimed. User-supplied text is not sent to a model or external search service.

## Source tests and merge gates

Regression covers direct-match preference, context-only explicit warning, no-context no-match, invalid context, M03 isolation, request schema controls, multi-question owner-only browser flow and context opt-out. Retain four protected checks on the exact PR head. Independent full institutional QA remains under #262/#308, not credited by source CI. Source flags stay OFF; no Production deploy, RBAC, network, DNS, DR, secrets or runner changes.

**Parent:** [#172](https://github.com/yiwssx/rcat-pdf-hub/issues/172). **Snapshot classification:** M06 PARTIAL.
