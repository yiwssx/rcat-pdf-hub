# Office → PDF font fidelity

Gotenberg uses LibreOffice, **not Microsoft Office**. When the container lacks
an exact source-document font, LibreOffice substitutes a different font. This
changes line wrapping, table heights, page breaks, and pagination, especially
with Thai government forms.

The custom Gotenberg image uses the pinned upstream Gotenberg 8.34.0 and adds
the Debian `fonts-thai-tlwg` fallback package. The base image includes other
general-purpose fonts. **Neither package guarantees matching TH Sarabun or
other installed Windows fonts.**

## Install exact source-document fonts

1. Identify the font family and version used in the Office document (e.g.
   `TH Sarabun New`, `THSarabunPSK`, or `TH SarabunPSK`). These are not
   always the same family and may have different layout metrics.
2. Obtain the permitted .ttf/.otf font files from the institution's
   approved distribution or an authoritative rights-compliant source.
3. Copy the font files to `ops/gotenberg/fonts/` **on the Docker build host**.
   Do not commit or upload font binaries to Git; `.gitignore` excludes them.
4. Rebuild **only** Gotenberg and restart it:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
     up -d --build --no-deps gotenberg
   ```

   For non-production Compose, omit `-f docker-compose.prod.yml`. Production
   also works with the NAS override as needed.
5. Verify the exact family name and its loaded face:

   ```bash
   PDFHUB_COMPOSE_MODE=prod bash scripts/check-office-fonts.sh "TH Sarabun New"
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
     exec -T gotenberg fc-match "TH Sarabun New"
   ```

   `fc-match` *always* returns a fallback even when the desired font is absent;
   the doctor checks exact installed family names using `fc-list`.

## Acceptance testing

Test at least one real DOCX, XLSX, and PPTX containing Thai fonts, tables,
headers/footers, page numbering, and page breaks. Compare the generated PDF
against **PDF exported by Microsoft Office using the same source file and font
versions**. Check A4 page size, page count, line wrapping, table overflow,
Thai glyphs, merged cells and images. A conversion returning HTTP 200 does not
prove layout fidelity.

Gotenberg/LibreOffice cannot guarantee byte-for-byte or pixel-identical PDF
output for every Microsoft Office document, even with exact fonts. For
complex proprietary Office features, use Microsoft Office's own PDF export
when exact rendering is legally or operationally required. Installing the
font in the *API* container or Ubuntu host does **not** install it in Gotenberg.

See https://gotenberg.dev/docs/convert-with-libreoffice/convert-to-pdf
and https://gotenberg.dev/docs/configuration .
