"""F05: real EPUB 3 for selectable, single-column PDF text only.

One chapter per source PDF page; generated content is reflowable XHTML text,
not screenshot pages. Complex layout, images, scanned pages fail closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile
import math

from pypdf import PdfReader

from app.services.from_pdf_rtf import (
    _extract_plain_lines, MAX_CHARS, MAX_PAGES, MAX_SOURCE_BYTES,
)

MIMETYPE = "application/epub+zip"
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
XHTML = "http://www.w3.org/1999/xhtml"
OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
CONT = "urn:oasis:names:tc:opendocument:xmlns:container"
ET.register_namespace("", XHTML)


def _xhtml(text_lines: list[str], title: str) -> bytes:
    root = ET.Element(f"{{{XHTML}}}html", {"lang": "und"})
    head = ET.SubElement(root, f"{{{XHTML}}}head")
    ET.SubElement(head, f"{{{XHTML}}}title").text = title
    body = ET.SubElement(root, f"{{{XHTML}}}body")
    heading = ET.SubElement(body, f"{{{XHTML}}}h1")
    heading.text = title
    for line in text_lines:
        paragraph = ET.SubElement(body, f"{{{XHTML}}}p")
        paragraph.text = line
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _navigation(count: int) -> bytes:
    root = ET.Element(f"{{{XHTML}}}html", {
        "lang": "und", "xmlns:epub": "http://www.idpf.org/2007/ops",
    })
    ET.SubElement(ET.SubElement(root, f"{{{XHTML}}}head"),
                  f"{{{XHTML}}}title").text = "Contents"
    body = ET.SubElement(root, f"{{{XHTML}}}body")
    nav = ET.SubElement(body, f"{{{XHTML}}}nav", {
        "{http://www.idpf.org/2007/ops}type": "toc",
    })
    ordered = ET.SubElement(nav, f"{{{XHTML}}}ol")
    for number in range(1, count + 1):
        li = ET.SubElement(ordered, f"{{{XHTML}}}li")
        ET.SubElement(li, f"{{{XHTML}}}a", {
            "href": f"page-{number:04d}.xhtml",
        }).text = f"Page {number}"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _package(count: int, input_sha: str) -> bytes:
    root = ET.Element(f"{{{OPF}}}package", {
        "version": "3.0", "unique-identifier": "book-id",
    })
    metadata = ET.SubElement(root, f"{{{OPF}}}metadata", {
        "xmlns:dc": DC,
    })
    ET.SubElement(metadata, f"{{{DC}}}identifier", {
        "id": "book-id",
    }).text = f"urn:sha256:{input_sha}"
    ET.SubElement(metadata, f"{{{DC}}}title").text = "Converted PDF text"
    ET.SubElement(metadata, f"{{{DC}}}language").text = "und"
    ET.SubElement(metadata, f"{{{OPF}}}meta", {
        "property": "dcterms:modified",
    }).text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = ET.SubElement(root, f"{{{OPF}}}manifest")
    ET.SubElement(manifest, f"{{{OPF}}}item", {
        "id": "nav", "href": "nav.xhtml",
        "media-type": "application/xhtml+xml", "properties": "nav",
    })
    spine = ET.SubElement(root, f"{{{OPF}}}spine")
    for i in range(1, count + 1):
        key = f"page-{i:04d}"
        ET.SubElement(manifest, f"{{{OPF}}}item", {
            "id": key, "href": key + ".xhtml",
            "media-type": "application/xhtml+xml",
        })
        ET.SubElement(spine, f"{{{OPF}}}itemref", {
            "idref": key,
        })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _container_xml() -> bytes:
    root = ET.Element(f"{{{CONT}}}container", {"version": "1.0"})
    files = ET.SubElement(root, f"{{{CONT}}}rootfiles")
    ET.SubElement(files, f"{{{CONT}}}rootfile", {
        "full-path": "EPUB/package.opf",
        "media-type": "application/oebps-package+xml",
    })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def pdf_to_reflowable_epub(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("EPUB source/destination must be distinct regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds EPUB text-only input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")
    pages: list[list[str]] = []
    total_chars = 0
    for page in pdf.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(width) or not math.isfinite(height)
                or not 1 <= width <= 4000 or not 1 <= height <= 4000):
            raise ValueError("Unsupported PDF page geometry for EPUB")
        lines = _extract_plain_lines(page, pdf)
        total_chars += sum(len(x) for x in lines)
        if total_chars > MAX_CHARS:
            raise ValueError("PDF EPUB text exceeds character budget")
        pages.append(lines)

    with TemporaryDirectory(prefix="pdfhub-frompdf-epub-") as temp:
        staged = Path(temp) / "result.epub"
        names = ["mimetype", "META-INF/container.xml", "EPUB/package.opf",
                 "EPUB/nav.xhtml"]
        names.extend(f"EPUB/page-{i:04d}.xhtml" for i in range(1, len(pages)+1))
        with ZipFile(staged, "w", compression=ZIP_DEFLATED, allowZip64=False) as archive:
            archive.writestr("mimetype", MIMETYPE.encode("ascii"),
                             compress_type=ZIP_STORED)
            archive.writestr("META-INF/container.xml", _container_xml())
            archive.writestr("EPUB/package.opf",
                             _package(len(pages), hashlib.sha256(source.read_bytes()).hexdigest()))
            archive.writestr("EPUB/nav.xhtml", _navigation(len(pages)))
            for i, lines in enumerate(pages, 1):
                archive.writestr(f"EPUB/page-{i:04d}.xhtml",
                                 _xhtml(lines, f"Page {i}"))
                if staged.stat().st_size > MAX_OUTPUT_BYTES:
                    raise ValueError("EPUB export exceeds output budget")
        if not 256 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("EPUB output violates budget")
        with ZipFile(staged) as proof:
            if (proof.namelist() != names or proof.testzip() is not None
                    or proof.getinfo("mimetype").compress_type != ZIP_STORED
                    or proof.read("mimetype") != MIMETYPE.encode("ascii")):
                raise ValueError("EPUB package or navigation inventory invalid")
        with staged.open("rb") as initial, output.open("xb") as dest:
            while chunk := initial.read(1024 * 1024):
                dest.write(chunk)
