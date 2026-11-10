# M12 — Visual electronic signature (MAC-scoped development complete, NOT digital certificate signing)

## Genuine source functionality

Provide one separate signed-in M12 workflow to select an owned, active PDF, draw a signature with pointer/touch or provide a PNG image, select its target page and coordinates, and submit that PNG through the existing authenticated image-on-PDF engine delivered in M23. The output is a **new PDF file** with an actual visible image layer. This is not a fake success response.

The signature pad exports a transparent image/png. The same signed-in owner account first uploads the image through the existing file endpoint, then queues M23 with the resulting owned image ID. Both API and Worker check PDF+PNG ownership, MIME, expiry, size and on-page bounds. There is no new PDF parser, queue architecture, database table, secret, external OCR/translation service or native dependency.

## Boundaries and honest classification

- **MAC-scoped CODE COMPLETE M12**, meaning only real visual PNG signing of a PDF through the existing M23 workflow. This is not a cryptographic signature, and is not a release claim.
- A visual signature cannot prove the signer's identity or integrity of the original PDF. It creates no certificate-backed PDF CMS/PAdES signature and should not be described as legally verified.
- The normal upload retention policy also applies to the saved PNG signature image. Its source file can remain in the private library until expiry; it is not public or reusable across accounts by ID.
- The M23 engine rejects encrypted, interactive/signed, annotated or rotated PDFs, and applies source/image, page and geometry limits. The new Web workflow does not bypass those limits.
- The signature pad works with pointer events (touch and mouse), has a clear button and supports file-upload mode as an accessibility alternative. PNG encode callbacks are invalidated on clearing.
- Input page index 1–80 and coordinates in PDF points (bottom-left); setting a target outside the document causes an explicit Worker error, not a misleading success.

## Default-off safety

- M12 Web: PDFHUB_STAGED_SIGNATURE_WEB_ENABLED=false (default).
- Reused M23 API/Worker: PDFHUB_PDF_IMAGE_OVERLAY_TOOLS_ENABLED=false (default).
- Both are required before the stage exists; no Production flags or deployments are changed.
- Existing files:read, files:write, jobs:read and pdf:stamp scopes, no RBAC extension.
- Playwright basic tests cover 404 default OFF, owner filtering, real drawn PNG upload into M23, payload and denied-scope path. M23 already has independent binary engine tests.

Formal cryptographic M12 remains a future independent engineering requirement, not an implied side effect of overlay. Source-only acceptance as visual signature is recorded in the [five-tool MAC decision](t90-five-partial-mac-decision-20261110.md).
