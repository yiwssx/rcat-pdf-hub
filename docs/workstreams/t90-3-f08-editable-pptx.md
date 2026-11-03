# T90-3 F08 — PDF to editable PowerPoint PPTX (bounded text-only)

This is an **actual** PowerPoint OOXML presentation. Each accepted source
PDF page becomes one slide with editable text shapes, not a slide screenshot.
The API route is named \`/ppt\` to match the canonical F08 public tool;
the output is honestly \`.pptx\`, **not** an old binary \`.ppt\` file.

- Input: strict, unencrypted, owner-bound and unexpired PDF; <=16 MiB,
  <=12 pages and <=150,000 selectable characters. A PDF page must contain
  one unambiguous left-aligned text column. No scanned PDFs, images,
  vector drawings, tables, rotated/transformed text, multiple columns,
  or unsupported geometry.
- Each page is rebuilt as one editable text box with DrawingML AutoFit.
  Maximum 20 lines and 96 Unicode codepoints per source line per slide;
  exceeding that limit fails rather than silently clipping text.
  Output uses a common 4:3 slide geometry, not the PDF's original page
  size, font metrics or exact layout. **Visual fidelity is not guaranteed.**
- OOXML package: \`[Content_Types].xml\`, \`_rels/.rels\`,
  \`ppt/presentation.xml\`, presentation relationships and each individual
  \`ppt/slides/slideN.xml\`. Fixed text and geometry parts; XML escaping
  through ElementTree; no remote assets or executable content.
- Output \`.pptx\` /
  \`application/vnd.openxmlformats-officedocument.presentationml.presentation\`,
  <=4 MiB, ordered slide/ZIP integrity and CRC; source remains immutable,
  output exclusively created.
- Route \`POST /api/v1/pdf/from-pdf/ppt\`, exact \`file_id\`,
  \`pdf:pdf-to-image\` authorization; original source owner/MIME/expiry
  and PDF signature rechecked in worker, heavy queue, default-disabled
  \`PDFHUB_FROM_PDF_TOOLS_ENABLED\`.
- Functional tests: actual selectable PDF pages => editable PowerPoint
  XML text per slide, ordered pages, package CRC and content types;
  optional real reader check via python-pptx / LibreOffice PDF export;
  negative tests for excess lines, graphics, multicolumn, encrypted input,
  symlinks, existing output and unauthorized/expired/MIME-mismatch source.

**Excluded:** arbitrary PDF visual reconstruction, legacy binary PPT,
original diagrams, images, animation or original Thai font positioning.
Physical RCAT Thai/Workspace OIDC/target-host AV, source-output comparison
and operator rollout remain separately gated by T90-5. No feature is
enabled or counted as VERIFIED/RELEASED based on code implementation alone.
