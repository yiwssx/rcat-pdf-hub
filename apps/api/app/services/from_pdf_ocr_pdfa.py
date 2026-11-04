"""F01 searchable OCR and F11 PDF/A-2 conversion: bounded source/output checks.

Reuse the established OCRmyPDF/Tesseract backend. Do not claim independent
ISO PDF/A conformance: veraPDF and institutional corpus checks remain T90-5.
"""
from __future__ import annotations

import math
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream

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




def _require_scanned_image_only(reader: PdfReader) -> None:
    """Do not force-rasterize original text, annotations, forms or vector art."""
    root = reader.trailer["/Root"]
    if root.get("/AcroForm"):
        raise ValueError("PDF/A scanned-only mode refuses interactive PDF forms")
    forbidden_paint = {
        b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*",
        b"sh", b"BI", b"ID", b"EI",
    }
    text_show = {b"Tj", b"TJ", b"'", b'"'}
    for page in reader.pages:
        if int(page.get("/Rotate", 0)) % 360 or page.get("/Annots"):
            raise ValueError("PDF/A scanned-only mode refuses rotation/annotations")
        if (page.extract_text() or "").strip():
            raise ValueError("PDF/A scanned-only mode refuses selectable PDF text")
        resources = page.get("/Resources")
        objects = resources.get("/XObject") if resources else None
        if objects is None:
            raise ValueError("PDF/A requires image-only PDF pages")
        images = objects.get_object()
        image_names = {
            str(name) for name, obj in images.items()
            if obj.get_object().get("/Subtype") == "/Image"
        }
        if not image_names or len(image_names) != len(images):
            raise ValueError("PDF/A requires image-only PDF XObjects")
        referenced_images = set()
        for args, operation in ContentStream(page.get_contents(), reader).operations:
            if operation in forbidden_paint or operation in text_show:
                raise ValueError("PDF/A scanned-only mode refuses text/vector painting")
            if operation == b"Do":
                if not args or str(args[0]) not in image_names:
                    raise ValueError("PDF/A scanned-only mode refuses nonimage calls")
                referenced_images.add(str(args[0]))
        if not referenced_images:
            raise ValueError("PDF/A source page must contain a drawn scan image")

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
    if kind == "pdfa-2":
        # The pinned Debian Bookworm Ghostscript 10.0.0 corrupts or refuses
        # OCRmyPDF --skip-text PDF/A conversions. Do NOT discard existing
        # selectable text with --force-ocr; accept image-only sources instead.
        reader = PdfReader(str(source), strict=True)
        _require_scanned_image_only(reader)
    try:
        if kind == "ocr":
            # Explicit --output-type pdf bypasses the Ghostscript PDF/A
            # regression without changing the legacy /api/v1/pdf/ocr flow.
            args = ["ocrmypdf", "--skip-text", "--output-type", "pdf",
                    "--optimize", "1", "-l", languages]
            if deskew:
                args.append("--deskew")
            if rotate_pages:
                args.append("--rotate-pages")
            args.extend([str(source), str(output)])
        else:
            if deskew or rotate_pages:
                raise ValueError("PDF/A accepts only explicit language setting")
            # Force mode only for PDFs where we just proved no selectable
            # text can be destroyed. Produces real PDF/A-2 identified XMP.
            args = ["ocrmypdf", "--force-ocr", "--output-type", "pdfa-2",
                    "-l", languages, str(source), str(output)]
        pdf_tools._run(args, timeout=600)
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
            parts = []
            for node in xmp_xml.iter():
                if node.tag == pdfa_namespace + "part":
                    parts.append((node.text or "").strip())
                # RDF descriptions commonly encode pdfaid:part="2" as
                # a namespace-qualified attribute, not a child element.
                for name, value in node.attrib.items():
                    if name == pdfa_namespace + "part":
                        parts.append(value.strip())
            if not parts or set(parts) != {"2"}:
                raise ValueError("PDF/A-2 XMP identification is absent or ambiguous")
    except Exception:
        if output.exists() and not output.is_symlink():
            output.unlink()
        raise
