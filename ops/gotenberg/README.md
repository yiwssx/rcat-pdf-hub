# RCAT Office → PDF font fidelity

Gotenberg uses LibreOffice, **not Microsoft Office**. The fonts available
inside Gotenberg determine its substitutions, line wrapping, table sizing and
page breaks. Installing fonts only on the Ubuntu host or in API containers
will not affect Office → PDF.

## 13Fonts.zip — approved local font bundle

The uploaded archive was inspected before preparing the integration:
- 57 valid TrueType (`.ttf`) files; 14 distinct internal font families;
- no identical duplicate file content, no unreadable font payloads;
- includes TH SarabunPSK, TH Sarabun New, and various Thai display families;
- includes special `IT๙` variants; their internal family/style names may
  coincide with normal variants, so file count and content are verified as
  well as Fontconfig registration.

**Only metadata and an integrity fingerprint are committed to Git.** Keep
the original `13Fonts.zip` and installed font binaries on the trusted
Ubuntu server. Follow the applicable licensing terms; some font licenses
are embedded in their TTF metadata.

The `ops/gotenberg/13fonts-manifest.json` content fingerprint is built from
the original filenames and SHA-256 values of all 57 file payloads. Altered,
incomplete, unknown, path-traversal, duplicate-name and non-font ZIP members
are rejected; arbitrary archives must not be treated as substitutes.

## Installation on Ubuntu

1. Transfer **the original file** `13Fonts.zip` to the server, for example
   by WinSCP or PowerShell from the PC where the ZIP exists:

   ```powershell
   scp .\13Fonts.zip rcat_iot_admin@SERVER_IP:/tmp/13Fonts.zip
   ```

   Replace `SERVER_IP` with the server's actual hostname/IP. The archive
   uploaded to a ChatGPT conversation is not automatically copied to Ubuntu.

2. Pull the merged changes and verify the archive *without extraction*:

   ```bash
   cd /opt/rcat-pdf-hub
   git pull --ff-only
   python3 scripts/office_font_bundle.py /tmp/13Fonts.zip --verify-only
   ```

3. Install all 57 files atomically into the custom Docker build context:

   ```bash
   make office-font-install ZIP=/tmp/13Fonts.zip
   find ops/gotenberg/fonts/13fonts -type f -name '*.ttf' | wc -l
   ```

   Expect `57`. The installer does not publish the files or modify any
   database/document records. Git ignores the local binaries.

4. **After draining in-flight Office conversion jobs**, rebuild *only*
   Gotenberg using the same Compose mode already used by the deployment:

   ```bash
   # Production without NAS override:
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
     up -d --build --no-deps gotenberg

   # Standard development mode (alternative):
   # docker compose up -d --build --no-deps gotenberg
   ```

5. Verify that the **running container** contains exactly the 57 expected
   files, all SHA-256 checksums agree, and Fontconfig registered every file:

   ```bash
   PDFHUB_COMPOSE_MODE=prod make office-font-bundle-doctor
   PDFHUB_COMPOSE_MODE=prod bash scripts/check-office-fonts.sh \
     "TH SarabunPSK" "TH Sarabun New"
   ```

   For production with NAS, use `PDFHUB_COMPOSE_MODE=prod-nas`; for normal
   development, omit the mode override. Do not infer font installation from
   `fc-match` alone: it always returns a fallback.

## Acceptance test before closing the incident

Compare real DOCX, XLSX and PPTX files against reference PDFs exported by
Microsoft Office, using the same source files/font versions. Check:

- Thai glyph visibility, text wrapping, styles, baseline/line spacing;
- A4 vs Letter, print area, table widths and rows, merged cells;
- running headers, footers, page numbering and expected page count;
- embedded images, shapes, positions and slide proportions.

A successful Gotenberg response or checksum check **does not demonstrate
pixel-identical page fidelity**. Complex proprietary Office features can
still differ. Missing fonts outside the supplied 13Fonts bundle (e.g. other
Windows/Office fonts) still require separately authorized font installation.

Do not commit or redistribute font binaries unless the rights explicitly
permit it. See https://gotenberg.dev/docs/convert-with-libreoffice/convert-to-pdf .
