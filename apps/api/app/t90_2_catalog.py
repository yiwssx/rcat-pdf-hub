"""Authoritative T90-2 40-format engineering inventory.

A staged adapter is NOT evidence of a deployed or visually verified product.
Explicitly blocked items have no callable endpoint, upload handler or worker.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FormatCapability:
    item_id: str
    name: str
    operations: tuple[str, ...]
    priority: str
    risk_or_blocker: str

    @property
    def engineering_state(self) -> str:
        # Independent format acceptance gate: a prototype alone is not STAGED.
        return "STAGED" if self.operations else "BLOCKED"

    @property
    def development_operations(self) -> tuple[str, ...]:
        return self.operations or EXPERIMENTAL_CODE_PATHS.get(self.item_id, ())

    @property
    def code_prepared(self) -> bool:
        # "Prepared" means a guarded source path exists, NOT output fidelity,
        # target-host runtimes, authorized user access or release acceptance.
        return bool(self.development_operations)


# Six individually gated draft pipelines, never included in STAGED routes.
EXPERIMENTAL_CODE_PATHS = {
    "T09": ("heic-to-pdf",),
    "T20": ("dwg-to-pdf",),
    "T25": ("heif-to-pdf",),
    "T30": ("chm-to-pdf",),
    "T33": ("url-to-pdf",),
    "T34": ("wps-to-pdf",),
}


FORMAT_CAPABILITIES: tuple[FormatCapability, ...] = (
    FormatCapability("T01", "Word (.doc)", ("doc-to-pdf",), "P0", "OLE legacy format validation limited to signature"),
    FormatCapability("T02", "JPG", ("jpg-to-pdf", "jpeg-to-pdf",), "P0", "raster size and color fidelity"),
    FormatCapability("T03", "PNG", ("png-to-pdf",), "P0", "transparency and color fidelity"),
    FormatCapability("T04", "EPUB", ("epub-to-pdf",), "P2", "development: EPUB2/3 spine text, lists, tables, local bitmaps and manifest cover; no full CSS/pagination, DRM or remote resources"),
    FormatCapability("T05", "DOCX", ("docx-to-pdf",), "P0", "OOXML fonts, charts and tables"),
    FormatCapability("T06", "Excel", ("xls-to-pdf", "xlsx-to-pdf", "ods-to-pdf",), "P0", "workbook print areas and formula/cache semantics"),
    FormatCapability("T07", "PPT", ("ppt-to-pdf",), "P0", "slide aspect, animations lost and embedded fonts"),
    FormatCapability("T08", "PPTX", ("pptx-to-pdf", "odp-to-pdf",), "P0", "slides and embedded font fidelity"),
    FormatCapability("T09", "HEIC", (), "P2", "development-only bounded multi-image native decoder draft; pinned libheif >=1.23.7 external runtime, sandbox and acceptance absent"),
    FormatCapability("T10", "HTML", ("html-to-pdf",), "P1", "staged sanitized content-only, styling and assets intentionally omitted"),
    FormatCapability("T11", "DjVu", ("djvu-to-pdf",), "P3", "single-page inline DJVU IFF only; bounded patched Debian DjVuLibre subprocess; no multipage, external INCL, exact layout/text fidelity"),
    FormatCapability("T12", "Pages", ("pages-to-pdf",), "P3", "Pages 4/5 ZIP full-document index only via libetonyek; other Pages variants and visual/font fidelity unverified"),
    FormatCapability("T13", "TIFF", ("tiff-to-pdf",), "P0", "multi-frame image fidelity"),
    FormatCapability("T14", "TXT", ("txt-to-pdf",), "P1", "UTF-8 Thai text and page wrapping"),
    FormatCapability("T15", "ODT", ("odt-to-pdf",), "P0", "OpenDocument fonts and page layout"),
    FormatCapability("T16", "SVG", ("svg-to-pdf",), "P1", "restricted geometry/text only; no CSS, remote links, gradients, filters, images or fonts"),
    FormatCapability("T17", "CSV", ("csv-to-pdf",), "P1", "UTF-8 rows, wide tables and print scaling"),
    FormatCapability("T18", "RTF", ("rtf-to-pdf",), "P0", "legacy RTF parser and font fidelity"),
    FormatCapability("T19", "MOBI", ("mobi-to-pdf",), "P3", "restricted DRM-free classic UTF-8 MOBI4-6 text transcript only; no KF8, media, CSS, full typography"),
    FormatCapability("T20", "DWG", (), "P3", "development-only external LibreDWG-to-DXF bounded LINE/CIRCLE 2D PDF bridge; blocked by GPLv3 license review, decoder sandbox, complex CAD semantics"),
    FormatCapability("T21", "PUB", ("pub-to-pdf",), "P3", "bounded v3 OLE Publisher subset via pinned LibreOffice/libmspub; proprietary layout/font fidelity unverified"),
    FormatCapability("T22", "XPS", ("xps-to-pdf",), "P2", "restricted ZIP FixedDocument/Glyphs Unicode transcript; no vector, image, page-size or original font fidelity"),
    FormatCapability("T23", "XML", ("xml-to-pdf",), "P2", "staged plain source-listing only; no XSLT or document styling"),
    FormatCapability("T24", "WebP", ("webp-to-pdf",), "P0", "animation and alpha fidelity"),
    FormatCapability("T25", "HEIF", (), "P2", "development-only bounded native decoder draft; patched pinned codec, licensed plugins and sandbox acceptance absent"),
    FormatCapability("T26", "JFIF", ("jfif-to-pdf",), "P1", "JPEG/JFIF signature and color accuracy"),
    FormatCapability("T27", "GIF", ("gif-to-pdf",), "P1", "multi-frame animation page policy"),
    FormatCapability("T28", "BMP", ("bmp-to-pdf",), "P0", "raster encoding and color"),
    FormatCapability("T29", "HWP", ("hwp-to-pdf",), "P3", "legacy HWP 3.0/1997 only with exact 30-byte version signature and no password, pinned LibreOffice hwpfilter; HWP5/HWPX excluded"),
    FormatCapability("T30", "CHM", (), "P3", "native CHM/LZX reader and offline local cross-links implemented on development branch; blocked until sandbox security, decoder isolation and real-file acceptance"),
    FormatCapability("T31", "FB2", ("fb2-to-pdf",), "P3", "development: FB2 body, lists, tables, verse, coverpage and bounded inline illustrations; original typography unsupported"),
    FormatCapability("T32", "ZIP", ("zip-to-pdf",), "P2", "staged images-only; other ZIP contents deliberately rejected"),
    FormatCapability("T33", "URL", (), "P2", "development-only strict HTTPS textual importer, DNS-pinned TLS, offline PDF, fileless RQ job; blocked pending independent network egress sandbox and tests"),
    FormatCapability("T34", "WPS", (), "P3", "development-only MS Works via wps2odt -> nonblank ODT -> PDF prototype; still blocked; Kingsoft WPS and exact fidelity unsupported"),
    FormatCapability("T35", "EML", ("eml-to-pdf",), "P2", "staged plain-text email only; rich HTML/attachments excluded"),
    FormatCapability("T36", "Markdown", ("md-to-pdf",), "P1", "CommonMark safe subset, remote content forbidden"),
    FormatCapability("T37", "DXF", ("dxf-to-pdf",), "P3", "strict ASCII DXF LINE/CIRCLE vectors only; no colors, fonts, XREF, BLOCK or 3D"),
    FormatCapability("T38", "CBZ", ("cbz-to-pdf",), "P2", "images-only safe comic archive, page order"),
    FormatCapability("T39", "AI", ("ai-to-pdf",), "P3", "PDF-compatible Illustrator subset only; PostScript/EPS and native Illustrator streams blocked"),
    FormatCapability("T40", "CBR", ("cbr-to-pdf",), "P3", "strict single-volume RAR4 *stored* image entries only; RAR5/compressed/encrypted RAR intentionally blocked"),
)

FORMAT_BY_ID = {item.item_id: item for item in FORMAT_CAPABILITIES}
