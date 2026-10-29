"""Restricted XPS text transcript and Illustrator PDF-compatible T90-2 acceptance."""
from __future__ import annotations

import hashlib
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation
from app.services.to_pdf_special import xps_to_safe_html


def pdf_bytes() -> bytes:
    buf = BytesIO()
    writer = canvas.Canvas(buf, pagesize=(595.28, 841.89))
    writer.drawString(80, 740, "VECTOR AI PDF")
    writer.showPage()
    writer.save()
    return buf.getvalue()


XPS_NS = "http://schemas.microsoft.com/xps/2005/06"
RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
ROOT_RELS = (
    f'<Relationships xmlns="{RELS}"><Relationship Id="R1" '
    'Type="http://schemas.microsoft.com/xps/2005/06/fixedrepresentation" '
    'Target="FixedDocSeq.fdseq"/></Relationships>'
)
SEQ = f'<FixedDocumentSequence xmlns="{XPS_NS}"><DocumentReference Source="Documents/1/FixedDoc.fdoc"/></FixedDocumentSequence>'
DOC = f'<FixedDocument xmlns="{XPS_NS}"><PageContent Source="Pages/1.fpage"/></FixedDocument>'
PAGE = (f'<FixedPage xmlns="{XPS_NS}" Width="793.7" Height="1122.5">'
        '<Glyphs UnicodeString="วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด" '
        'FontUri="/Resources/Thai.odttf" OriginX="30" OriginY="80"/>'
        '</FixedPage>')


def make_xps(target, *, page=PAGE, rels=ROOT_RELS, extras=None):
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as out:
        entries = {
            "[Content_Types].xml": "<Types/>",
            "_rels/.rels": rels,
            "FixedDocSeq.fdseq": SEQ,
            "Documents/1/FixedDoc.fdoc": DOC,
            "Documents/1/Pages/1.fpage": page,
        }
        entries.update(extras or {})
        for name, content in entries.items():
            out.writestr(name, content)


def test_pdf_compatible_illustrator_real_output_and_immutable_source(monkeypatch, tmp_path):
    source = tmp_path / "vector.ai"
    source.write_bytes(pdf_bytes())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(HTTPException) as off:
        validate_uploaded_file(source, source.name)
    assert off.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    mime = "application/vnd.adobe.illustrator"
    assert validate_uploaded_file(source, source.name) == mime
    output = tmp_path / "result.pdf"
    execute_staged_to_pdf_operation(
        "ai-to-pdf", [source], output, {},
        original_name=source.name, content_type=mime,
    )
    reader = PdfReader(BytesIO(output.read_bytes()), strict=True)
    assert len(reader.pages) == 1
    assert reader.pages[0].extract_text().strip() == "VECTOR AI PDF"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert output.read_bytes().startswith(b"%PDF-")
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation(
            "ai-to-pdf", [source], source, {},
            original_name=source.name, content_type=mime,
        )
    with pytest.raises(ValueError, match="MIME"):
        checked_source("ai-to-pdf", source, name=source.name, mime="application/pdf")


def test_illustrator_blocks_postscript_encryption_and_actions(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "evil.ai"
    for bad in (b"%!PS-Adobe-3.0\n0 0 moveto\n", b"%PDF-spoof"):
        source.write_bytes(bad)
        with pytest.raises(HTTPException) as error:
            validate_uploaded_file(source, source.name)
        assert error.value.status_code == 415
    writer = PdfWriter()
    writer.add_page(PdfReader(BytesIO(pdf_bytes())).pages[0])
    writer.encrypt("secret")
    out = BytesIO()
    writer.write(out)
    source.write_bytes(out.getvalue())
    with pytest.raises(HTTPException):
        validate_uploaded_file(source, source.name)
    writer = PdfWriter()
    writer.add_page(PdfReader(BytesIO(pdf_bytes())).pages[0])
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject({
        NameObject("/S"): NameObject("/JavaScript"),
        NameObject("/JS"): TextStringObject("app.alert('unsafe')")
    })
    out = BytesIO()
    writer.write(out)
    source.write_bytes(out.getvalue())
    with pytest.raises(HTTPException):
        validate_uploaded_file(source, source.name)


def test_xps_real_transcript_and_signed_worker_dispatch(monkeypatch, tmp_path):
    source = tmp_path / "document.xps"
    make_xps(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด" in xps_to_safe_html(source)
    with pytest.raises(HTTPException):
        validate_uploaded_file(source, source.name)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(source, source.name) == "application/vnd.ms-xpsdocument"
    calls = []
    def fake_html_to_pdf(html, output):
        calls.append(html)
        output.write_bytes(pdf_bytes())
    monkeypatch.setattr("app.services.to_pdf_engine._html_to_pdf", fake_html_to_pdf)
    output = tmp_path / "result.pdf"
    execute_staged_to_pdf_operation(
        "xps-to-pdf", [source], output, {},
        original_name=source.name, content_type="application/vnd.ms-xpsdocument",
    )
    assert len(calls) == 1
    assert "<p>วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด</p>" in calls[0]
    assert len(PdfReader(str(output), strict=True).pages) == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("page,rels,extras", [
    (
        f'<FixedPage xmlns="{XPS_NS}"><Path Data="M 0,0 L 1,1"/></FixedPage>',
        ROOT_RELS, None,
    ),
    (
        f'<FixedPage xmlns="{XPS_NS}"><Glyphs UnicodeString="hi" Indices="0,20"/></FixedPage>',
        ROOT_RELS, None,
    ),
    (
        f'<FixedPage xmlns="{XPS_NS}"><Glyphs UnicodeString="hi" FontUri="https://example.org/a"/></FixedPage>',
        ROOT_RELS, None,
    ),
    (
        PAGE,
        f'<Relationships xmlns="{RELS}"><Relationship Id="R1" '
        'Type="http://schemas.microsoft.com/xps/2005/06/fixedrepresentation" '
        'Target="http://127.0.0.1/private"/></Relationships>',
        None,
    ),
    (PAGE, ROOT_RELS, {"../outside.xml": "<x/>"}),
])
def test_xps_rejects_unsafe_or_unsupported_structures(tmp_path, page, rels, extras):
    source = tmp_path / "malicious.xps"
    make_xps(source, page=page, rels=rels, extras=extras)
    with pytest.raises(ValueError):
        xps_to_safe_html(source)


def test_xps_rejects_corrupt_and_decompression_bomb(monkeypatch, tmp_path):
    source = tmp_path / "bad.xps"
    source.write_bytes(b"PK\x03\x04" + b"garbage")
    with pytest.raises(ValueError):
        xps_to_safe_html(source)
    source = tmp_path / "too-large.xps"
    make_xps(source, extras={"many.txt": "x" * (2 * 1024 * 1024 + 1)})
    with pytest.raises(ValueError):
        xps_to_safe_html(source)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(source, source.name)
    assert exc.value.status_code == 415
