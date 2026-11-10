// GENERATED FROM the audited 40-format backend catalog (2026-11-09).
// Maintained as a literal allowlist; backend remains the final MIME, owner,
// scope, format-signature and feature-flag enforcement authority.
// This module is *not* imported by the legacy 13-card Production catalog.
export type StagedToPdfVariant = {
  operation: string;
  route: string;
  mime: string;
  suffixes: readonly string[];
};

export type StagedToPdfFormat = {
  id: string;
  title: string;
  variants: readonly StagedToPdfVariant[];
  withheld: boolean;
  limit: string;
};

export const STAGED_TO_PDF_FORMATS: readonly StagedToPdfFormat[] = [
  {
    id: "T01", title: "Word (.doc)", withheld: false,
    limit: "OLE legacy format validation limited to signature",
    variants: [
      { operation: "doc-to-pdf", route: "doc", mime: "application/msword", suffixes: [".doc"] },
    ],
  },
  {
    id: "T02", title: "JPG", withheld: false,
    limit: "raster size and color fidelity",
    variants: [
      { operation: "jpg-to-pdf", route: "jpg", mime: "image/jpeg", suffixes: [".jpg"] },
      { operation: "jpeg-to-pdf", route: "jpeg", mime: "image/jpeg", suffixes: [".jpeg"] },
    ],
  },
  {
    id: "T03", title: "PNG", withheld: false,
    limit: "transparency and color fidelity",
    variants: [
      { operation: "png-to-pdf", route: "png", mime: "image/png", suffixes: [".png"] },
    ],
  },
  {
    id: "T04", title: "EPUB", withheld: false,
    limit: "development: EPUB2/3 spine text, lists, tables, local bitmaps and manifest cover; no full CSS/pagination, DRM or remote resources",
    variants: [
      { operation: "epub-to-pdf", route: "epub", mime: "application/epub+zip", suffixes: [".epub"] },
    ],
  },
  {
    id: "T05", title: "DOCX", withheld: false,
    limit: "OOXML fonts, charts and tables",
    variants: [
      { operation: "docx-to-pdf", route: "docx", mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", suffixes: [".docx"] },
    ],
  },
  {
    id: "T06", title: "Excel", withheld: false,
    limit: "workbook print areas and formula/cache semantics",
    variants: [
      { operation: "xls-to-pdf", route: "xls", mime: "application/vnd.ms-excel", suffixes: [".xls"] },
      { operation: "xlsx-to-pdf", route: "xlsx", mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", suffixes: [".xlsx"] },
      { operation: "ods-to-pdf", route: "ods", mime: "application/vnd.oasis.opendocument.spreadsheet", suffixes: [".ods"] },
    ],
  },
  {
    id: "T07", title: "PPT", withheld: false,
    limit: "slide aspect, animations lost and embedded fonts",
    variants: [
      { operation: "ppt-to-pdf", route: "ppt", mime: "application/vnd.ms-powerpoint", suffixes: [".ppt"] },
    ],
  },
  {
    id: "T08", title: "PPTX", withheld: false,
    limit: "slides and embedded font fidelity",
    variants: [
      { operation: "pptx-to-pdf", route: "pptx", mime: "application/vnd.openxmlformats-officedocument.presentationml.presentation", suffixes: [".pptx"] },
      { operation: "odp-to-pdf", route: "odp", mime: "application/vnd.oasis.opendocument.presentation", suffixes: [".odp"] },
    ],
  },
  {
    id: "T10", title: "HTML", withheld: false,
    limit: "staged sanitized content-only, styling and assets intentionally omitted",
    variants: [
      { operation: "html-to-pdf", route: "html", mime: "text/html", suffixes: [".html"] },
    ],
  },
  {
    id: "T11", title: "DjVu", withheld: false,
    limit: "single-page inline DJVU IFF only; bounded patched Debian DjVuLibre subprocess; no multipage, external INCL, exact layout/text fidelity",
    variants: [
      { operation: "djvu-to-pdf", route: "djvu", mime: "image/vnd.djvu", suffixes: [".djvu"] },
    ],
  },
  {
    id: "T12", title: "Pages", withheld: false,
    limit: "Pages 4/5 ZIP full-document index only via libetonyek; other Pages variants and visual/font fidelity unverified",
    variants: [
      { operation: "pages-to-pdf", route: "pages", mime: "application/vnd.apple.pages", suffixes: [".pages"] },
    ],
  },
  {
    id: "T13", title: "TIFF", withheld: false,
    limit: "multi-frame image fidelity",
    variants: [
      { operation: "tiff-to-pdf", route: "tiff", mime: "image/tiff", suffixes: [".tif",".tiff"] },
    ],
  },
  {
    id: "T14", title: "TXT", withheld: false,
    limit: "UTF-8 Thai text and page wrapping",
    variants: [
      { operation: "txt-to-pdf", route: "txt", mime: "text/plain", suffixes: [".txt"] },
    ],
  },
  {
    id: "T15", title: "ODT", withheld: false,
    limit: "OpenDocument fonts and page layout",
    variants: [
      { operation: "odt-to-pdf", route: "odt", mime: "application/vnd.oasis.opendocument.text", suffixes: [".odt"] },
    ],
  },
  {
    id: "T16", title: "SVG", withheld: false,
    limit: "restricted geometry/text only; no CSS, remote links, gradients, filters, images or fonts",
    variants: [
      { operation: "svg-to-pdf", route: "svg", mime: "image/svg+xml", suffixes: [".svg"] },
    ],
  },
  {
    id: "T17", title: "CSV", withheld: false,
    limit: "UTF-8 rows, wide tables and print scaling",
    variants: [
      { operation: "csv-to-pdf", route: "csv", mime: "text/csv", suffixes: [".csv"] },
    ],
  },
  {
    id: "T18", title: "RTF", withheld: false,
    limit: "legacy RTF parser and font fidelity",
    variants: [
      { operation: "rtf-to-pdf", route: "rtf", mime: "application/rtf", suffixes: [".rtf"] },
    ],
  },
  {
    id: "T19", title: "MOBI", withheld: false,
    limit: "restricted DRM-free classic UTF-8 MOBI4-6 text transcript only; no KF8, media, CSS, full typography",
    variants: [
      { operation: "mobi-to-pdf", route: "mobi", mime: "application/x-mobipocket-ebook", suffixes: [".mobi"] },
    ],
  },
  {
    id: "T21", title: "PUB", withheld: false,
    limit: "limited v3 OLE Publisher via LibreOffice; genuine two-page text and ink proof for Apache POI sample; unsupported layouts and fonts may fail",
    variants: [
      { operation: "pub-to-pdf", route: "pub", mime: "application/x-mspublisher", suffixes: [".pub"] },
    ],
  },
  {
    id: "T22", title: "XPS", withheld: false,
    limit: "restricted ZIP FixedDocument/Glyphs Unicode transcript; no vector, image, page-size or original font fidelity",
    variants: [
      { operation: "xps-to-pdf", route: "xps", mime: "application/vnd.ms-xpsdocument", suffixes: [".xps"] },
    ],
  },
  {
    id: "T23", title: "XML", withheld: false,
    limit: "staged plain source-listing only; no XSLT or document styling",
    variants: [
      { operation: "xml-to-pdf", route: "xml", mime: "application/xml", suffixes: [".xml"] },
    ],
  },
  {
    id: "T24", title: "WebP", withheld: false,
    limit: "animation and alpha fidelity",
    variants: [
      { operation: "webp-to-pdf", route: "webp", mime: "image/webp", suffixes: [".webp"] },
    ],
  },
  {
    id: "T26", title: "JFIF", withheld: false,
    limit: "JPEG/JFIF signature and color accuracy",
    variants: [
      { operation: "jfif-to-pdf", route: "jfif", mime: "image/jpeg", suffixes: [".jfif"] },
    ],
  },
  {
    id: "T27", title: "GIF", withheld: false,
    limit: "multi-frame animation page policy",
    variants: [
      { operation: "gif-to-pdf", route: "gif", mime: "image/gif", suffixes: [".gif"] },
    ],
  },
  {
    id: "T28", title: "BMP", withheld: false,
    limit: "raster encoding and color",
    variants: [
      { operation: "bmp-to-pdf", route: "bmp", mime: "image/bmp", suffixes: [".bmp"] },
    ],
  },
  {
    id: "T29", title: "HWP", withheld: false,
    limit: "legacy HWP 3.0/1997 only with exact 30-byte version signature and no password, pinned LibreOffice hwpfilter; HWP5/HWPX excluded",
    variants: [
      { operation: "hwp-to-pdf", route: "hwp", mime: "application/x-hwp", suffixes: [".hwp"] },
    ],
  },
  {
    id: "T31", title: "FB2", withheld: false,
    limit: "development: FB2 body, lists, tables, verse, coverpage and bounded inline illustrations; original typography unsupported",
    variants: [
      { operation: "fb2-to-pdf", route: "fb2", mime: "application/x-fictionbook+xml", suffixes: [".fb2"] },
    ],
  },
  {
    id: "T32", title: "ZIP", withheld: false,
    limit: "staged images-only; other ZIP contents deliberately rejected",
    variants: [
      { operation: "zip-to-pdf", route: "zip", mime: "application/zip", suffixes: [".zip"] },
    ],
  },
  {
    id: "T35", title: "EML", withheld: false,
    limit: "staged plain-text email only; rich HTML/attachments excluded",
    variants: [
      { operation: "eml-to-pdf", route: "eml", mime: "message/rfc822", suffixes: [".eml"] },
    ],
  },
  {
    id: "T36", title: "Markdown", withheld: false,
    limit: "CommonMark safe subset, remote content forbidden",
    variants: [
      { operation: "md-to-pdf", route: "md", mime: "text/markdown", suffixes: [".md"] },
    ],
  },
  {
    id: "T37", title: "DXF", withheld: false,
    limit: "strict ASCII DXF LINE/CIRCLE vectors only; no colors, fonts, XREF, BLOCK or 3D",
    variants: [
      { operation: "dxf-to-pdf", route: "dxf", mime: "image/vnd.dxf", suffixes: [".dxf"] },
    ],
  },
  {
    id: "T38", title: "CBZ", withheld: false,
    limit: "images-only safe comic archive, page order",
    variants: [
      { operation: "cbz-to-pdf", route: "cbz", mime: "application/vnd.comicbook+zip", suffixes: [".cbz"] },
    ],
  },
  {
    id: "T39", title: "AI", withheld: false,
    limit: "PDF-compatible Illustrator subset only; PostScript/EPS and native Illustrator streams blocked",
    variants: [
      { operation: "ai-to-pdf", route: "ai", mime: "application/vnd.adobe.illustrator", suffixes: [".ai"] },
    ],
  },
  {
    id: "T40", title: "CBR", withheld: false,
    limit: "strict single-volume RAR4 *stored* image entries only; RAR5/compressed/encrypted RAR intentionally blocked",
    variants: [
      { operation: "cbr-to-pdf", route: "cbr", mime: "application/vnd.comicbook-rar", suffixes: [".cbr"] },
    ],
  },
] as const;

export const AVAILABLE_STAGED_TO_PDF_FORMATS = STAGED_TO_PDF_FORMATS.filter(
  (item) => !item.withheld
);

// Publisher T21 stays deliberately unavailable while its real fixture has
// visibly blank page 2. Six native/URL prototypes are not in this allowlist.
