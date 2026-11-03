"""F02/F06 PDF -> truly editable DOCX (text-only one-column subset).

Word means DOCX, never a binary legacy .doc or screenshot-based Word file.
Selected PDFs with ambiguous typography, tables, drawings or images fail closed.
"""
from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader

from app.services.from_pdf_rtf import (
    _extract_plain_lines, MAX_CHARS, MAX_PAGES, MAX_SOURCE_BYTES,
)

MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W)
TYPES_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
 <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
RELATIONSHIPS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _w(name: str) -> str:
    return f"{{{W}}}{name}"


def pdf_to_editable_text_docx(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("DOCX source and destination must be independent")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds text-only DOCX input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")

    document = ET.Element(_w("document"))
    body = ET.SubElement(document, _w("body"))
    total_chars = 0
    for i, page in enumerate(pdf.pages):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(width) or not math.isfinite(height)
                or not 1 <= width <= 4000 or not 1 <= height <= 4000):
            raise ValueError("Invalid PDF text-only page size")
        lines = _extract_plain_lines(page, pdf)
        total_chars += sum(len(line) for line in lines)
        if total_chars > MAX_CHARS:
            raise ValueError("Too many source PDF text characters")
        if i:
            page_marker = ET.SubElement(body, _w("p"))
            marker_run = ET.SubElement(page_marker, _w("r"))
            ET.SubElement(marker_run, _w("br"), {_w("type"): "page"})
        for line in lines:
            paragraph = ET.SubElement(body, _w("p"))
            run = ET.SubElement(paragraph, _w("r"))
            text = ET.SubElement(run, _w("t"), {
                "{http://www.w3.org/XML/1998/namespace}space": "preserve",
            })
            text.text = line

    contents = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    with TemporaryDirectory(prefix="pdfhub-frompdf-docx-") as temp:
        staged = Path(temp) / "result.docx"
        with ZipFile(staged, "w", compression=ZIP_DEFLATED, allowZip64=False) as archive:
            archive.writestr("[Content_Types].xml", TYPES_XML)
            archive.writestr("_rels/.rels", RELATIONSHIPS_XML)
            archive.writestr("word/document.xml", contents)
        if not 400 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("DOCX output exceeds budget")
        with ZipFile(staged) as proof:
            if (proof.namelist() != [
                "[Content_Types].xml", "_rels/.rels", "word/document.xml",
            ] or proof.testzip() is not None):
                raise ValueError("DOCX XML package inventory/CRC invalid")
        with staged.open("rb") as original, output.open("xb") as destination:
            while chunk := original.read(1024 * 1024):
                destination.write(chunk)
