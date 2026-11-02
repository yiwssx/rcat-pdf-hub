# T90-4 M33 — owner-bound AcroForm text filling (staged)

This is an independently gated engineering integration, **not** a verified
production feature. Public OpenAPI, routes and operator UI are absent when the
feature flag is OFF (its default).

## End-to-end job pipeline

1. `POST /api/v1/pdf/advanced/fill-pdf-form` accepts an uploaded PDF
   `file_id` and 1–64 existing `/Tx` text-field name/value pairs.
   `pdf:convert` permission is required (existing RCAT operator role).
2. Router requires exact file owner, unexpired PDF MIME and `.pdf` name,
   24 MiB maximum input and strictly typed field values.
3. Existing `_create_job` enforces job quota, queue audit and owner binding.
   `fill-pdf-form` uses the normal bounded `pdf` RQ class, not legacy adapter
   dynamic dispatch.
4. Worker independently checks **current** flag, source owner, expiry,
   persisted MIME/suffix, size, input signature and exact parameter keys.
5. The dedicated pypdf engine accepts only supported AcroForm text fields,
   rejects signed/XFA/encrypted inputs, verifies values and page count from a
   privately staged PDF candidate, and exclusively publishes the checked PDF.
   Existing output storage, scanning, audit, expiry and authenticated downloads
   remain in the normal job pipeline.

## Activation is separately gated

```dotenv
PDFHUB_PDF_FILLER_TOOLS_ENABLED=false
```

Pydantic, `.env.example`, and shared Docker Compose API/worker settings all
default OFF. Approval requires actual Thai font appearance checks (a correct
`/V` value is not proof that glyphs render visually), owner-download E2E,
malformed files and regression acceptance through T90-5 #262.

**Not implemented/certified:** field designer UI, PDF form flattening, digital
signatures, PDF redaction, signed document modification, XFA, arbitrary font
embedding, or reliable display of all Thai combinations. These are separate
tools and must never be misrepresented by this M33 subset.
