"""F01 searchable OCR and F11 PDF/A-2 conversion: bounded source/output checks.

Reuse the established OCRmyPDF/Tesseract backend. Do not claim independent
ISO PDF/A conformance: veraPDF and institutional corpus checks remain T90-5.
"""
from __future__ import annotations

import math
from pathlib import Path

from pypdf import PdfReader

from app.services import pdf_tools

MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_PAGES = 12
LANGUAGES = frozenset({"tha", "eng", "tha+eng", "eng+tha"})


def _pages(path: Path, *, max_bytes: int) -> int:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source/output must be a regular PDF file")
    size = path.stat().st_size
    if not 24 <= size <= max_bytes:
        raise ValueError("PDF file violates the size budget")
    document = PdfReader(str(path), strict=True)
    if document.is_encrypted or not 1 <= len(document.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")
    for page in document.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(w) or not math.isfinite(h)
                or not 1 <= w <= 4000 or not 1 <= h <= 4000):
            raise ValueError("Unsupported PDF geometry")
    return len(document.pages)


def convert_accessible_pdf(
    source: Path, output: Path, *,
    kind: str, languages: str = "tha+eng",
    deskew: bool = False, rotate_pages: bool = False,
) -> None:
    if (kind not in {"ocr", "pdfa-2"}
            or languages not in LANGUAGES
            or type(deskew) is not bool or type(rotate_pages) is not bool):
        raise ValueError("Unsupported OCR/PDF-A request parameters")
    if source.resolve() == output.resolve() or output.exists() or output.is_symlink():
        raise ValueError("OCR destination must not replace another file")
    expected_pages = _pages(source, max_bytes=MAX_SOURCE_BYTES)
    try:
        if kind == "ocr":
            pdf_tools.ocr(
                source, output, languages=languages,
                deskew=deskew, rotate_pages=rotate_pages,
            )
        else:
            if deskew or rotate_pages:
                raise ValueError("PDF/A accepts only explicit language setting")
            pdf_tools.pdfa(source, output, languages=languages)
        actual_pages = _pages(output, max_bytes=MAX_OUTPUT_BYTES)
        if actual_pages != expected_pages:
            raise ValueError("OCR/PDF-A changed source PDF page inventory")
        # PDF/A identification in XMP is a necessary but not sufficient
        # validation. Independent veraPDF testing is deferred to T90-5.
        if kind == "pdfa-2":
            reader = PdfReader(str(output), strict=True)
            from defusedxml import ElementTree
            root = reader.trailer["/Root"]
            metadata = root.get("/Metadata")
            if metadata is None:
                raise ValueError("PDF/A-2 XMP identification metadata missing")
            raw_xmp = metadata.get_object().get_data()
            if not raw_xmp or len(raw_xmp) > 512 * 1024:
                raise ValueError("PDF/A-2 XMP metadata exceeds safety limits")
            xmp_xml = ElementTree.fromstring(raw_xmp)
            pdfa_namespace = "{http://www.aiim.org/pdfa/ns/id/}"
            parts = [
                (node.text or "").strip()
                for node in xmp_xml.iter()
                if node.tag == pdfa_namespace + "part"
            ]
            if parts != ["2"]:
                raise ValueError("PDF/A-2 XMP identification is absent or ambiguous")
    except Exception:
        if output.exists() and not output.is_symlink():
            output.unlink()
        raise
