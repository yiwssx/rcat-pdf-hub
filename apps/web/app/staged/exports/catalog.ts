// Scope-limited, default-OFF T90-3 source-only UI projection, 2026-11-09.
// Exact API routes and owner/scopes remain enforced in from_pdf.py.
export type StagedFromPdfFormat = {
  id: string;
  label: string;
  route: string;
  requiredScope: string;
  fileKind: string;
  limitation: string;
};

export const STAGED_FROM_PDF_FORMATS: readonly StagedFromPdfFormat[] = [
  { id: "F01", label: "PDF OCR", route: "ocr", requiredScope: "pdf:ocr", fileKind: "Searchable PDF", limitation: "OCR language defaults to Thai + English; searchable source with bounded page count" },
  { id: "F02", label: "PDF to Word", route: "word", requiredScope: "pdf:pdf-to-image", fileKind: "DOCX", limitation: "Word-compatible DOCX; NOT a binary .doc or perfect layout copy" },
  { id: "F03", label: "PDF to JPG", route: "jpg", requiredScope: "pdf:pdf-to-image", fileKind: "JPG ZIP", limitation: "One JPG per page in a ZIP, default 96 DPI" },
  { id: "F04", label: "PDF to PNG", route: "png", requiredScope: "pdf:pdf-to-image", fileKind: "PNG ZIP", limitation: "One PNG per page in a ZIP, default 96 DPI" },
  { id: "F05", label: "PDF to EPUB", route: "epub", requiredScope: "pdf:pdf-to-image", fileKind: "EPUB", limitation: "Restricted searchable text extraction only; no original print layout guarantee" },
  { id: "F06", label: "PDF to DOCX", route: "docx", requiredScope: "pdf:pdf-to-image", fileKind: "DOCX", limitation: "Editable DOCX for bounded source layout; complex fonts/geometry excluded" },
  { id: "F07", label: "PDF to Excel", route: "excel", requiredScope: "pdf:pdf-to-image", fileKind: "XLSX", limitation: "Only supported ruled-table PDF content becomes XLSX" },
  { id: "F08", label: "PDF to PPT", route: "ppt", requiredScope: "pdf:pdf-to-image", fileKind: "PPTX", limitation: "Modern PPTX slide export; not a binary .ppt" },
  { id: "F09", label: "PDF to TIFF", route: "tiff", requiredScope: "pdf:pdf-to-image", fileKind: "TIFF", limitation: "Multipage TIFF, default 150 DPI" },
  { id: "F10", label: "PDF to ODT", route: "odt", requiredScope: "pdf:pdf-to-image", fileKind: "ODT", limitation: "Searchable text-focused ODT; original geometry not guaranteed" },
  { id: "F11", label: "PDF to PDF/A", route: "pdfa", requiredScope: "pdf:pdfa", fileKind: "PDF/A", limitation: "PDF/A candidate; archival compliance requires separate validator review" },
  { id: "F12", label: "PDF to SVG", route: "svg", requiredScope: "pdf:pdf-to-image", fileKind: "SVG ZIP", limitation: "One bounded SVG per page in a ZIP" },
  { id: "F13", label: "PDF to CSV", route: "csv", requiredScope: "pdf:pdf-to-image", fileKind: "CSV", limitation: "Bounded ruled-table extraction; unsuitable PDFs are rejected" },
  { id: "F14", label: "PDF to RTF", route: "rtf", requiredScope: "pdf:pdf-to-image", fileKind: "RTF", limitation: "Text-only RTF subset; complex layout not preserved" },
  { id: "F16", label: "PDF to GIF", route: "gif", requiredScope: "pdf:pdf-to-image", fileKind: "Animated GIF", limitation: "PDF pages become GIF frames; default 96 DPI, 1200 ms per frame" },
  { id: "F17", label: "PDF to BMP", route: "bmp", requiredScope: "pdf:pdf-to-image", fileKind: "BMP ZIP", limitation: "One BMP per page in a ZIP, default 96 DPI" },
] as const;

// F15 is intentionally absent: no accepted legitimate PDF-to-MOBI exporter.
// PDF-to-Word/PPT/Excel names are explicitly scoped to DOCX/PPTX/XLSX, not
// misleading binary .doc/.ppt/.xls output.
