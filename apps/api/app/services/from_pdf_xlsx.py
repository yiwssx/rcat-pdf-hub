"""F07: strict ruled PDF grid tables -> real editable OOXML Excel worksheets.

Never infer columns from whitespace. Uses F13's conservative grid parser,
preserves each source cell as a string, and never fabricates formulas/numbers.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader

from app.services.from_pdf_csv import (
    _table, MAX_CELLS, MAX_PAGES, MAX_SOURCE_BYTES,
)

MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_OUTPUT_BYTES = 6 * 1024 * 1024
MAX_SHEET_BYTES = 1024 * 1024
SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
C = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("r", R)


def _ns(ns: str, key: str) -> str:
    return f"{{{ns}}}{key}"


def _xml(root: ET.Element, default_ns: str) -> bytes:
    ET.register_namespace("", default_ns)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def pdf_grid_to_editable_xlsx(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("XLSX input/output must be separate regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds ruled table XLSX input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted/excessive-page PDF cannot become XLSX")

    workbook = ET.Element(_ns(SS, "workbook"))
    sheets = ET.SubElement(workbook, _ns(SS, "sheets"))
    relationship = ET.Element(_ns(P, "Relationships"))
    package_relationship = ET.Element(_ns(P, "Relationships"))
    ET.SubElement(package_relationship, _ns(P, "Relationship"), {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        "Target": "xl/workbook.xml",
    })
    types = ET.Element(_ns(C, "Types"))
    for ext, mime in (
        ("rels", "application/vnd.openxmlformats-package.relationships+xml"),
        ("xml", "application/xml"),
    ):
        ET.SubElement(types, _ns(C, "Default"), {
            "Extension": ext, "ContentType": mime,
        })
    ET.SubElement(types, _ns(C, "Override"), {
        "PartName": "/xl/workbook.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    })
    content_parts: list[tuple[str, bytes]] = []
    total_cells = 0
    for page_number, page in enumerate(pdf.pages, 1):
        if page.get("/Resources", {}).get("/XObject"):
            raise ValueError("Embedded PDF graphics unsupported for editable grid XLSX")
        rows = _table(page, pdf)
        total_cells += len(rows) * len(rows[0])
        if total_cells > MAX_CELLS:
            raise ValueError("Too many spreadsheet cells")
        name = f"Page {page_number}"
        rel_id = f"rId{page_number}"
        ET.SubElement(sheets, _ns(SS, "sheet"), {
            "name": name, "sheetId": str(page_number), _ns(R, "id"): rel_id,
        })
        path = f"xl/worksheets/sheet{page_number}.xml"
        ET.SubElement(relationship, _ns(P, "Relationship"), {
            "Id": rel_id,
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": f"worksheets/sheet{page_number}.xml",
        })
        ET.SubElement(types, _ns(C, "Override"), {
            "PartName": "/" + path,
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        })
        sheet = ET.Element(_ns(SS, "worksheet"))
        sheet_data = ET.SubElement(sheet, _ns(SS, "sheetData"))
        for row_no, row in enumerate(rows, 1):
            row_node = ET.SubElement(sheet_data, _ns(SS, "row"), {"r": str(row_no)})
            for col_no, value in enumerate(row, 1):
                if not value:
                    continue
                cell = ET.SubElement(row_node, _ns(SS, "c"), {
                    "r": chr(ord("A")+col_no-1)+str(row_no), "t": "inlineStr",
                })
                inline = ET.SubElement(cell, _ns(SS, "is"))
                text = ET.SubElement(inline, _ns(SS, "t"))
                text.text = value
        binary = _xml(sheet, SS)
        if len(binary) > MAX_SHEET_BYTES:
            raise ValueError("XLSX worksheet XML exceeds output budget")
        content_parts.append((path, binary))

    members = [
        ("[Content_Types].xml", _xml(types, C)),
        ("_rels/.rels", _xml(package_relationship, P)),
        ("xl/workbook.xml", _xml(workbook, SS)),
        ("xl/_rels/workbook.xml.rels", _xml(relationship, P)),
        *content_parts,
    ]
    with TemporaryDirectory(prefix="pdfhub-frompdf-xlsx-") as temp:
        staged = Path(temp) / "result.xlsx"
        with ZipFile(staged, "w", compression=ZIP_DEFLATED, allowZip64=False) as archive:
            for path, data in members:
                archive.writestr(path, data)
        if not 400 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("XLSX output exceeds budget")
        with ZipFile(staged) as check:
            if (check.namelist() != [name for name, _ in members]
                    or check.testzip() is not None):
                raise ValueError("XLSX package inventory/CRC invalid")
        with staged.open("rb") as initial, output.open("xb") as dest:
            while chunk := initial.read(1024 * 1024):
                dest.write(chunk)
