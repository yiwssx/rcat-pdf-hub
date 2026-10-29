#!/usr/bin/env python3
"""Deterministic, synthetic OpenDocument and Unicode RTF Thai test inputs.

Only standard-library packaging. These are format baselines, not visual goldens
for real school documents or fonts that are unavailable in source control.
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_STORED, ZIP_DEFLATED, ZipFile, ZipInfo

THAI = "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"
TEXT = "ทดสอบสระ วรรณยุกต์ และภาษาไทย"
MIME = {
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "odp": "application/vnd.oasis.opendocument.presentation",
}
NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
      'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
      'xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"')


def add(archive: ZipFile, name: str, data: str, compression: int) -> None:
    entry = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
    entry.compress_type = compression
    entry.external_attr = 0o100644 << 16
    archive.writestr(entry, data.encode("utf-8"))


def page_layout(kind: str) -> str:
    if kind == "odp":
        attributes = ('fo:page-width="33.867cm" fo:page-height="19.05cm" '
                      'style:print-orientation="landscape"')
    elif kind == "ods":
        attributes = ('fo:page-width="29.7cm" fo:page-height="21cm" '
                      'fo:margin-top="1cm" fo:margin-bottom="1cm" '
                      'fo:margin-left="1cm" fo:margin-right="1cm" '
                      'style:print-orientation="landscape" '
                      'style:scale-to-pages-x="1" style:scale-to-pages-y="1"')
    else:
        attributes = ('fo:page-width="21cm" fo:page-height="29.7cm" '
                      'fo:margin-top="2cm" fo:margin-bottom="2cm" '
                      'fo:margin-left="2cm" fo:margin-right="2cm" '
                      'style:print-orientation="portrait"')
    return ('<style:page-layout style:name="pm1">'
            '<style:page-layout-properties ' + attributes + '/>'
            '</style:page-layout>')


def odf(path: Path, kind: str, body: str, styles: str, automatic: str) -> None:
    root = {"odt": "text", "ods": "spreadsheet", "odp": "presentation"}[kind]
    font_decls = ('<office:font-face-decls><style:font-face style:name="Garuda" '
                  'svg:font-family="Garuda"/></office:font-face-decls>')
    content = (f'<?xml version="1.0" encoding="UTF-8"?>'
               f'<office:document-content {NS} office:version="1.2">'
               f'{font_decls}<office:automatic-styles>{automatic}</office:automatic-styles>'
               f'<office:body><office:{root}>{body}</office:{root}>'
               '</office:body></office:document-content>')
    styles_xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
                  f'<office:document-styles {NS} office:version="1.2">'
                  f'{font_decls}<office:styles>{styles}</office:styles>'
                  f'<office:automatic-styles>{page_layout(kind)}</office:automatic-styles>'
                  '<office:master-styles>'
                  '<style:master-page style:name="Standard" style:page-layout-name="pm1"/>'
                  '</office:master-styles></office:document-styles>')
    manifest = ('''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
<manifest:file-entry manifest:full-path="/" manifest:media-type="''' + MIME[kind] + '''"/>
<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
</manifest:manifest>''')
    with ZipFile(path, "w") as archive:
        # ODF requires a first, uncompressed mimetype entry.
        for name, payload, compression in (
            ("mimetype", MIME[kind], ZIP_STORED),
            ("content.xml", content, ZIP_DEFLATED),
            ("styles.xml", styles_xml, ZIP_DEFLATED),
            ("META-INF/manifest.xml", manifest, ZIP_DEFLATED),
        ):
            add(archive, name, payload, compression)


FONT_STYLE = ('<style:style style:name="Thai" style:family="paragraph">'
              '<style:text-properties style:font-name="Garuda" '
              'fo:font-family="Garuda" fo:font-size="14pt"/>'
              '</style:style>')


def make_odt(path: Path) -> None:
    body = (f'<text:p text:style-name="Thai">{escape(THAI)}</text:p>'
            f'<text:p text:style-name="Thai">{escape(TEXT)}</text:p>')
    odf(path, "odt", body, FONT_STYLE, "")


def make_ods(path: Path) -> None:
    cell_style = ('<style:style style:name="ThaiCell" style:family="table-cell">'
                  '<style:text-properties style:font-name="Garuda" '
                  'fo:font-family="Garuda" fo:font-size="13pt"/>'
                  '</style:style>')
    body = (f'<table:table table:name="Thai test" table:style-name="Sheet">'
            '<table:table-column table:style-name="WideColumn"/>'
            '<table:table-column table:style-name="NarrowColumn"/>'
            '<table:table-row>'
            f'<table:table-cell table:style-name="ThaiCell" office:value-type="string">'
            f'<text:p>{escape(THAI)}</text:p></table:table-cell>'
            '<table:table-cell office:value-type="string"><text:p>RCAT</text:p></table:table-cell>'
            '</table:table-row><table:table-row>'
            f'<table:table-cell table:style-name="ThaiCell" office:value-type="string">'
            f'<text:p>{escape(TEXT)}</text:p></table:table-cell>'
            '<table:table-cell office:value-type="float" office:value="123">'
            '<text:p>123</text:p></table:table-cell>'
            '</table:table-row></table:table>')
    auto = ('<style:style style:name="WideColumn" style:family="table-column">'
            '<style:table-column-properties style:column-width="15cm"/></style:style>'
            '<style:style style:name="NarrowColumn" style:family="table-column">'
            '<style:table-column-properties style:column-width="5cm"/></style:style>'
            '<style:style style:name="Sheet" style:family="table" '
            'style:master-page-name="Standard">'
            '<style:table-properties table:display="true"/></style:style>')
    odf(path, "ods", body, cell_style, auto)


def make_odp(path: Path) -> None:
    pages = []
    for index, label in enumerate((THAI, TEXT), 1):
        pages.append(
            f'<draw:page draw:name="slide{index}" draw:style-name="dp1" '
            'draw:master-page-name="Standard">'
            '<draw:frame draw:style-name="gr1" svg:x="2cm" svg:y="3cm" '
            'svg:width="28cm" svg:height="5cm">'
            f'<draw:text-box><text:p text:style-name="Thai">{escape(label)}</text:p>'
            '</draw:text-box></draw:frame></draw:page>'
        )
    auto = ('<style:style style:name="dp1" style:family="drawing-page"/>'
            '<style:style style:name="gr1" style:family="graphic"/>')
    odf(path, "odp", "".join(pages), FONT_STYLE, auto)


def rtf_unicode(text: str) -> str:
    # One signed 16-bit UTF-16 unit per RTF \uN? escape.
    encoded = text.encode("utf-16-le")
    return "".join(
        f'\\u{int.from_bytes(encoded[index:index + 2], "little", signed=True)}?'
        for index in range(0, len(encoded), 2)
    )


def make_rtf(path: Path) -> None:
    data = (r"{\rtf1\ansi\deff0\uc1\deflang1054"
            r"{\fonttbl{\f0\fnil Garuda;}}"
            r"\paperw11906\paperh16838\margl1200\margr1200\margt1200\margb1200 "
            r"\pard\qc\f0\fs28 " + rtf_unicode(THAI) + r"\par "
            r"\pard\ql\f0\fs28 " + rtf_unicode(TEXT) + r"\par}")
    path.write_bytes(data.encode("ascii"))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: make-t90-2-odf-fixtures.py output-dir")
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    for extension, generate in (
        ("odt", make_odt), ("ods", make_ods),
        ("odp", make_odp), ("rtf", make_rtf),
    ):
        output = folder / ("thai." + extension)
        generate(output)
        print(output.name, output.stat().st_size)


if __name__ == "__main__":
    main()
