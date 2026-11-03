"""F08: PDF -> real editable modern PowerPoint .pptx (text-only subset).

No screenshots, fake legacy .ppt, or assertions of full visual PDF layout.
One strict single-column selectable PDF page -> one editable slide text box.
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

MIMETYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_LINES_PER_SLIDE = 20
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_R = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
for prefix, namespace in (("p", P), ("a", A), ("r", R)):
    ET.register_namespace(prefix, namespace)


def _tag(ns: str, key: str) -> str:
    return f"{{{ns}}}{key}"


def _encode(node: ET.Element) -> bytes:
    return ET.tostring(node, encoding="utf-8", xml_declaration=True)


def _content_types(count: int) -> bytes:
    types = ET.Element(_tag(CT, "Types"))
    for ext, mime in (
        ("rels", "application/vnd.openxmlformats-package.relationships+xml"),
        ("xml", "application/xml"),
    ):
        ET.SubElement(types, _tag(CT, "Default"), {
            "Extension": ext, "ContentType": mime,
        })
    ET.SubElement(types, _tag(CT, "Override"), {
        "PartName": "/ppt/presentation.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
    })
    for i in range(1, count + 1):
        ET.SubElement(types, _tag(CT, "Override"), {
            "PartName": f"/ppt/slides/slide{i}.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        })
    return _encode(types)


def _relationship(items: list[tuple[str, str, str]]) -> bytes:
    root = ET.Element(_tag(PKG_R, "Relationships"))
    for rel_id, kind, target in items:
        ET.SubElement(root, _tag(PKG_R, "Relationship"), {
            "Id": rel_id,
            "Type": f"http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}",
            "Target": target,
        })
    return _encode(root)


def _presentation(count: int) -> bytes:
    root = ET.Element(_tag(P, "presentation"))
    slide_list = ET.SubElement(root, _tag(P, "sldIdLst"))
    for i in range(1, count + 1):
        ET.SubElement(slide_list, _tag(P, "sldId"), {
            "id": str(255 + i), _tag(R, "id"): f"rId{i}",
        })
    ET.SubElement(root, _tag(P, "sldSz"), {
        "cx": "9144000", "cy": "6858000", "type": "screen4x3",
    })
    ET.SubElement(root, _tag(P, "notesSz"), {
        "cx": "6858000", "cy": "9144000",
    })
    return _encode(root)


def _slide(lines: list[str]) -> bytes:
    root = ET.Element(_tag(P, "sld"))
    canvas = ET.SubElement(root, _tag(P, "cSld"))
    shapes = ET.SubElement(canvas, _tag(P, "spTree"))
    group = ET.SubElement(shapes, _tag(P, "nvGrpSpPr"))
    ET.SubElement(group, _tag(P, "cNvPr"), {"id": "1", "name": ""})
    ET.SubElement(group, _tag(P, "cNvGrpSpPr"))
    ET.SubElement(group, _tag(P, "nvPr"))
    transform = ET.SubElement(ET.SubElement(shapes, _tag(P, "grpSpPr")),
                              _tag(A, "xfrm"))
    for label, values in (
        ("off", {"x": "0", "y": "0"}),
        ("ext", {"cx": "0", "cy": "0"}),
        ("chOff", {"x": "0", "y": "0"}),
        ("chExt", {"cx": "0", "cy": "0"}),
    ):
        ET.SubElement(transform, _tag(A, label), values)
    shape = ET.SubElement(shapes, _tag(P, "sp"))
    properties = ET.SubElement(shape, _tag(P, "nvSpPr"))
    ET.SubElement(properties, _tag(P, "cNvPr"), {
        "id": "2", "name": "Editable PDF source text",
    })
    ET.SubElement(properties, _tag(P, "cNvSpPr"), {"txBox": "1"})
    ET.SubElement(properties, _tag(P, "nvPr"))
    geometry = ET.SubElement(shape, _tag(P, "spPr"))
    transform = ET.SubElement(geometry, _tag(A, "xfrm"))
    ET.SubElement(transform, _tag(A, "off"), {"x": "457200", "y": "457200"})
    ET.SubElement(transform, _tag(A, "ext"), {
        "cx": "8229600", "cy": "5943600",
    })
    ET.SubElement(ET.SubElement(geometry, _tag(A, "prstGeom"), {
        "prst": "rect",
    }), _tag(A, "avLst"))
    ET.SubElement(geometry, _tag(A, "noFill"))
    text_box = ET.SubElement(shape, _tag(P, "txBody"))
    ET.SubElement(text_box, _tag(A, "bodyPr"), {"wrap": "square"})
    ET.SubElement(text_box, _tag(A, "lstStyle"))
    for line in lines:
        paragraph = ET.SubElement(text_box, _tag(A, "p"))
        run = ET.SubElement(paragraph, _tag(A, "r"))
        ET.SubElement(run, _tag(A, "rPr"), {
            "lang": "und", "sz": "1400",
        })
        ET.SubElement(run, _tag(A, "t")).text = line
    override = ET.SubElement(root, _tag(P, "clrMapOvr"))
    ET.SubElement(override, _tag(A, "masterClrMapping"))
    return _encode(root)


def pdf_to_editable_text_pptx(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("PPTX source/output must be independent regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds PPTX text-only budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported for slides")

    slides: list[bytes] = []
    total_chars = 0
    for page in pdf.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(width) or not math.isfinite(height)
                or not 1 <= width <= 4000 or not 1 <= height <= 4000):
            raise ValueError("Invalid PDF page geometry for slides")
        lines = _extract_plain_lines(page, pdf)
        if len(lines) > MAX_LINES_PER_SLIDE:
            raise ValueError("Too much text for faithful editable slide export")
        total_chars += sum(len(text) for text in lines)
        if total_chars > MAX_CHARS:
            raise ValueError("Source PDF text exceeds PPTX budget")
        slides.append(_slide(lines))

    members = [
        ("[Content_Types].xml", _content_types(len(slides))),
        ("_rels/.rels", _relationship([
            ("rId1", "officeDocument", "ppt/presentation.xml"),
        ])),
        ("ppt/presentation.xml", _presentation(len(slides))),
        ("ppt/_rels/presentation.xml.rels", _relationship([
            (f"rId{i}", "slide", f"slides/slide{i}.xml")
            for i in range(1, len(slides)+1)
        ])),
    ]
    members.extend((f"ppt/slides/slide{i}.xml", blob)
                   for i, blob in enumerate(slides, 1))
    with TemporaryDirectory(prefix="pdfhub-frompdf-pptx-") as temp:
        candidate = Path(temp) / "result.pptx"
        with ZipFile(candidate, "w", compression=ZIP_DEFLATED,
                     allowZip64=False) as archive:
            for name, blob in members:
                archive.writestr(name, blob)
        if not 400 <= candidate.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("PPTX package exceeds output limits")
        with ZipFile(candidate) as proof:
            if (proof.namelist() != [name for name, _ in members]
                    or proof.testzip() is not None):
                raise ValueError("PPTX package inventory or CRC invalid")
        with candidate.open("rb") as original, output.open("xb") as dest:
            while chunk := original.read(1024 * 1024):
                dest.write(chunk)
