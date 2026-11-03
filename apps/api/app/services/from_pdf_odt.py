"""F10: conservatively export editable text-only PDF pages as ODF text (.odt).

Uses the same strict single-column selectable text subset as F14 RTF. Does not
claim to reconstruct complex tables, fonts, images, vectors or page geometry.
"""
from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from pypdf import PdfReader

from app.services.from_pdf_rtf import (
    _extract_plain_lines, MAX_CHARS, MAX_PAGES, MAX_SOURCE_BYTES,
)

MIMETYPE = "application/vnd.oasis.opendocument.text"
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
O = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
T = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
S = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
F = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
M = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
for prefix, namespace in (("office", O), ("text", T), ("style", S),
                          ("fo", F), ("manifest", M)):
    ET.register_namespace(prefix, namespace)


def _attr(namespace: str, local: str) -> str:
    return f"{{{namespace}}}{local}"


def _xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def pdf_to_editable_text_odt(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("ODT source and destination must be independent files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds strict ODT text-only input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")

    root = ET.Element(_attr(O, "document-content"), {_attr(O, "version"): "1.2"})
    styles = ET.SubElement(root, _attr(O, "automatic-styles"))
    page_break = ET.SubElement(styles, _attr(S, "style"), {
        _attr(S, "name"): "PageBreak", _attr(S, "family"): "paragraph",
    })
    ET.SubElement(page_break, _attr(S, "paragraph-properties"), {
        _attr(F, "break-before"): "page",
    })
    body = ET.SubElement(ET.SubElement(root, _attr(O, "body")), _attr(O, "text"))

    total_chars = 0
    for number, page in enumerate(pdf.pages):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(width) or not math.isfinite(height)
                or not 1 <= width <= 4000 or not 1 <= height <= 4000):
            raise ValueError("Invalid PDF text-only page dimensions")
        lines = _extract_plain_lines(page, pdf)
        total_chars += sum(len(line) for line in lines)
        if total_chars > MAX_CHARS:
            raise ValueError("Too many text characters for the ODT subset")
        for line_no, text in enumerate(lines):
            attrs = {_attr(T, "style-name"): "PageBreak"} if number and not line_no else {}
            paragraph = ET.SubElement(body, _attr(T, "p"), attrs)
            paragraph.text = text

    styling = ET.Element(_attr(O, "document-styles"), {_attr(O, "version"): "1.2"})
    ET.SubElement(styling, _attr(O, "styles"))
    manifest = ET.Element(_attr(M, "manifest"), {_attr(M, "version"): "1.2"})
    for filename, mime in (
        ("/", MIMETYPE), ("content.xml", "text/xml"), ("styles.xml", "text/xml")
    ):
        ET.SubElement(manifest, _attr(M, "file-entry"), {
            _attr(M, "full-path"): filename, _attr(M, "media-type"): mime,
        })

    with TemporaryDirectory(prefix="pdfhub-frompdf-odt-") as temp:
        stage = Path(temp) / "result.odt"
        with ZipFile(stage, "w", allowZip64=False) as archive:
            archive.writestr("mimetype", MIMETYPE.encode("ascii"), compress_type=ZIP_STORED)
            archive.writestr("content.xml", _xml(root), compress_type=ZIP_DEFLATED)
            archive.writestr("styles.xml", _xml(styling), compress_type=ZIP_DEFLATED)
            archive.writestr(
                "META-INF/manifest.xml", _xml(manifest), compress_type=ZIP_DEFLATED
            )
        if not 256 <= stage.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("ODT output size violates text-only budget")
        with ZipFile(stage) as proof:
            if (proof.namelist() != [
                "mimetype", "content.xml", "styles.xml", "META-INF/manifest.xml",
            ] or proof.testzip() is not None
                    or proof.getinfo("mimetype").compress_type != ZIP_STORED
                    or proof.read("mimetype") != MIMETYPE.encode("ascii")):
                raise ValueError("ODT package manifest or content integrity invalid")
        with stage.open("rb") as original, output.open("xb") as destination:
            while chunk := original.read(1024*1024):
                destination.write(chunk)
