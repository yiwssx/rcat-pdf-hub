#!/usr/bin/env python3
"""Generate small deterministic OOXML Thai acceptance fixtures using stdlib only.

Fixtures are intentionally synthetic; they do NOT validate real institutional
Office typography, embedded charts, complex print areas or custom font licenses.
"""
from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import sys

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
R = "http://schemas.openxmlformats.org/package/2006/relationships"
O = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
THAI = "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"
TEXT = "ทดสอบสระ วรรณยุกต์ และภาษาไทย"


def pack(path: Path, parts: dict[str, str]) -> None:
    with ZipFile(path, "w") as archive:
        for name, value in sorted(parts.items()):
            entry = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, value.encode("utf-8"))


def content_types(overrides: dict[str, str]) -> str:
    return (
        f'<Types xmlns="{CT}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(
            f'<Override PartName="/{name}" ContentType="{mime}"/>'
            for name, mime in overrides.items()
        )
        + "</Types>"
    )


def relationships(items: list[tuple[str, str]]) -> str:
    return (
        f'<Relationships xmlns="{R}">'
        + "".join(
            f'<Relationship Id="rId{i + 1}" Type="{O}/{kind}" Target="{target}"/>'
            for i, (kind, target) in enumerate(items)
        )
        + "</Relationships>"
    )


def word(path: Path) -> None:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = f'''<w:document xmlns:w="{w}"><w:body>
    <w:p><w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r><w:rPr><w:rFonts w:ascii="Garuda" w:eastAsia="Garuda" w:hAnsi="Garuda" w:cs="Garuda"/><w:sz w:val="28"/></w:rPr>
    <w:t>{THAI}</w:t></w:r></w:p>
    <w:p><w:r><w:rPr><w:rFonts w:ascii="Garuda" w:cs="Garuda"/></w:rPr><w:t>{TEXT}</w:t></w:r></w:p>
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1200" w:right="1200" w:bottom="1200" w:left="1200"/></w:sectPr>
    </w:body></w:document>'''
    pack(path, {
        "[Content_Types].xml": content_types({
            "word/document.xml":
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        }),
        "_rels/.rels": relationships([("officeDocument", "word/document.xml")]),
        "word/document.xml": document,
    })


def excel(path: Path) -> None:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    workbook = (
        f'<workbook xmlns="{ns}" xmlns:r="{rel}">'
        '<bookViews><workbookView/></bookViews><sheets>'
        '<sheet name="Thai test" sheetId="1" r:id="rId1"/>'
        '</sheets></workbook>'
    )
    styles = (
        f'<styleSheet xmlns="{ns}">'
        '<fonts count="2"><font><sz val="11"/><name val="Liberation Sans"/></font><font><sz val="13"/><name val="Garuda"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        '</styleSheet>'
    )
    sheet = f'''<worksheet xmlns="{ns}">
    <dimension ref="A1:B2"/>
    <sheetViews><sheetView workbookViewId="0"/></sheetViews>
    <sheetFormatPr defaultRowHeight="24"/>
    <cols><col min="1" max="1" width="55" customWidth="1"/><col min="2" max="2" width="28" customWidth="1"/></cols>
    <sheetData>
    <row r="1"><c r="A1" s="1" t="inlineStr"><is><t>{THAI}</t></is></c><c r="B1" t="inlineStr"><is><t>RCAT</t></is></c></row>
    <row r="2"><c r="A2" s="1" t="inlineStr"><is><t>{TEXT}</t></is></c><c r="B2"><v>123</v></c></row>
    </sheetData>
    <pageMargins left="0.3" right="0.3" top="0.4" bottom="0.4" header="0.1" footer="0.1"/>
    <pageSetup paperSize="9" orientation="landscape"/>
    </worksheet>'''
    pack(path, {
        "[Content_Types].xml": content_types({
            "xl/workbook.xml":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            "xl/styles.xml":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
            "xl/worksheets/sheet1.xml":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        }),
        "_rels/.rels": relationships([("officeDocument", "xl/workbook.xml")]),
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": relationships([
            ("worksheet", "worksheets/sheet1.xml"), ("styles", "styles.xml"),
        ]),
        "xl/styles.xml": styles,
        "xl/worksheets/sheet1.xml": sheet,
    })


def power_point(path: Path) -> None:
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    slides = []
    for label in (THAI, TEXT):
        slides.append(f'''<p:sld xmlns:p="{p}" xmlns:a="{a}" xmlns:r="{r}">
        <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
        <p:sp><p:nvSpPr><p:cNvPr id="2" name="Thai text"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="914400" y="914400"/><a:ext cx="9500000" cy="2200000"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="2800">
        <a:latin typeface="Garuda"/><a:ea typeface="Garuda"/><a:cs typeface="Garuda"/></a:rPr>
        <a:t>{label}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
        <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>''')
    presentation = f'''<p:presentation xmlns:p="{p}" xmlns:a="{a}" xmlns:r="{r}">
    <p:sldIdLst><p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst>
    <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
    <p:notesSz cx="6858000" cy="9144000"/></p:presentation>'''
    parts = {
        "[Content_Types].xml": content_types({
            "ppt/presentation.xml":
                "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
            "ppt/slides/slide1.xml":
                "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            "ppt/slides/slide2.xml":
                "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        }),
        "_rels/.rels": relationships([("officeDocument", "ppt/presentation.xml")]),
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": relationships([
            ("slide", "slides/slide1.xml"), ("slide", "slides/slide2.xml"),
        ]),
    }
    for i, slide in enumerate(slides, 1):
        parts[f"ppt/slides/slide{i}.xml"] = slide
    pack(path, parts)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: make-t90-2-office-fixtures.py output-dir")
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    for filename, create in (
        ("thai.docx", word), ("thai.xlsx", excel),
        ("thai.pptx", power_point),
    ):
        create(destination / filename)
        print(filename, (destination / filename).stat().st_size)


if __name__ == "__main__":
    main()
