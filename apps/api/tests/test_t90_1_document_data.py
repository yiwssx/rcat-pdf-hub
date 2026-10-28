"""T90-1.4 staged M13/M17/M27 engine tests (no active routes).

These assert only the supported Info/XMP scope, not all-document redaction.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pypdf.errors import PdfReadError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services.pdf_document_data import (
    edit_document_info,
    extract_searchable_text,
    remove_document_info_and_xmp,
)


def make_source(path: Path, *, text: str = "RCAT FIRST PAGE", scanned: bool = False) -> Path:
    doc = canvas.Canvas(str(path), pagesize=(520, 720))
    if not scanned:
        doc.drawString(80, 620, text)
    doc.showPage()
    if not scanned:
        doc.drawString(80, 620, "SECOND PAGE")
    doc.showPage()
    doc.save()
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m13_edit_info_round_trip_thai_and_remove_selected_field(tmp_path: Path):
    source = make_source(tmp_path / "source.pdf")
    before = digest(source)
    intermediate = tmp_path / "intermediate.pdf"
    output = tmp_path / "edited.pdf"
    edit_document_info(source, intermediate, {
        "title": "รายงานการตรวจรับ ๒๕๖๙",
        "author": "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด",
        "subject": "เอกสารราชการ",
        "keywords": "ประเทศไทย,วิทยาลัย",
    })
    first = PdfReader(str(intermediate), strict=True)
    assert first.metadata.title == "รายงานการตรวจรับ ๒๕๖๙"
    assert first.metadata.author == "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"
    assert first.metadata.subject == "เอกสารราชการ"
    assert first.metadata.get("/Keywords") == "ประเทศไทย,วิทยาลัย"
    edit_document_info(intermediate, output, {"author": None, "title": "ชื่อใหม่"})
    second = PdfReader(str(output), strict=True)
    assert second.metadata.title == "ชื่อใหม่"
    assert second.metadata.get("/Author") is None
    assert second.metadata.subject == "เอกสารราชการ"
    assert [p.extract_text().strip() for p in second.pages] == [
        "RCAT FIRST PAGE", "SECOND PAGE",
    ]
    assert digest(source) == before


@pytest.mark.parametrize("changes", [
    {}, {"publisher": "unlisted"},
    {"title": "X" * 513}, {"title": "bad\nnewline"},
    {"author": "bad\x00control"}, {"title": 42},
])
def test_m13_rejects_unapproved_or_malicious_fields(tmp_path: Path, changes: dict):
    source = make_source(tmp_path / "source.pdf")
    out = tmp_path / "output.pdf"
    with pytest.raises(ValueError):
        edit_document_info(source, out, changes)
    assert not out.exists()


_XMP = (
    b'<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description>PRIVATE_XMP_T90_1_4_SENTINEL</rdf:Description>'
    b'</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
)


def make_sensitive_pdf(path: Path) -> Path:
    source = make_source(path.parent / "plain.pdf")
    writer = PdfWriter(clone_from=str(source))
    writer.add_metadata({
        "/Title": "PRIVATE_INFO_T90_1_4_SENTINEL",
        "/Author": "PRIVATE_AUTHOR_T90_1_4_SENTINEL",
    })
    stream = DecodedStreamObject()
    stream.set_data(_XMP)
    stream[NameObject("/Type")] = NameObject("/Metadata")
    stream[NameObject("/Subtype")] = NameObject("/XML")
    ref = writer._add_object(stream)
    writer._root_object[NameObject("/Metadata")] = ref
    writer.pages[0][NameObject("/Metadata")] = ref
    writer.write(str(path))
    return path


def test_m27_removes_info_root_and_page_xmp_not_just_dictionary(tmp_path: Path):
    source = make_sensitive_pdf(tmp_path / "private.pdf")
    before = digest(source)
    output = tmp_path / "cleared.pdf"
    remove_document_info_and_xmp(source, output)
    result = PdfReader(str(output), strict=True)
    assert result.metadata == {}
    assert result.root_object.get("/Metadata") is None
    assert all(page.get("/Metadata") is None for page in result.pages)
    assert len(result.pages) == 2
    assert "RCAT FIRST PAGE" in result.pages[0].extract_text()
    assert "SECOND PAGE" in result.pages[1].extract_text()
    binary = output.read_bytes()
    assert binary.startswith(b"%PDF-")
    assert b"PRIVATE_XMP_T90_1_4_SENTINEL" not in binary
    assert b"PRIVATE_INFO_T90_1_4_SENTINEL" not in binary
    assert b"PRIVATE_AUTHOR_T90_1_4_SENTINEL" not in binary
    assert digest(source) == before


def test_m13_rejects_xmp_to_avoid_conflicting_metadata(tmp_path: Path):
    source = make_sensitive_pdf(tmp_path / "xmp.pdf")
    output = tmp_path / "edited.pdf"
    with pytest.raises(ValueError, match="XMP"):
        edit_document_info(source, output, {"title": "replacement"})
    assert not output.exists()


def test_m17_searchable_pdf_text_formfeed_and_immutable_input(tmp_path: Path):
    source = make_source(tmp_path / "source.pdf")
    before = digest(source)
    output = tmp_path / "text.txt"
    extract_searchable_text(source, output)
    assert output.read_bytes() == b"RCAT FIRST PAGE\n\n\f\nSECOND PAGE\n"
    assert digest(source) == before


def test_m17_thai_unicode_utf8_text_layer(tmp_path: Path):
    fonts = [
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf"),
    ]
    font = next((font for font in fonts if font.exists()), None)
    if font is None:
        pytest.skip("Thai font missing in this host; pinned CI image provides NotoSansThai")
    pdfmetrics.registerFont(TTFont("ThaiT9014Fixture", str(font)))
    source = tmp_path / "thai.pdf"
    doc = canvas.Canvas(str(source))
    doc.setFont("ThaiT9014Fixture", 13)
    doc.drawString(80, 720, "ข้อมูลภาษาไทยทดสอบ")
    doc.showPage()
    doc.save()
    output = tmp_path / "thai.txt"
    extract_searchable_text(source, output)
    assert "ข้อมูลภาษาไทยทดสอบ" in output.read_text(encoding="utf-8")


def test_m17_scanned_pdf_needs_ocr_and_has_no_blank_success(tmp_path: Path):
    source = make_source(tmp_path / "image-only.pdf", scanned=True)
    output = tmp_path / "empty.txt"
    with pytest.raises(ValueError, match="OCR is required"):
        extract_searchable_text(source, output)
    assert not output.exists()


@pytest.mark.parametrize("method", [
    "edit", "remove", "text",
])
def test_t90_1_4_staged_operations_reject_same_source_and_output(tmp_path: Path, method: str):
    source = make_source(tmp_path / "source.pdf")
    original = digest(source)
    with pytest.raises(ValueError, match="must differ"):
        if method == "edit":
            edit_document_info(source, source, {"title": "bad"})
        elif method == "remove":
            remove_document_info_and_xmp(source, source)
        else:
            extract_searchable_text(source, source)
    assert digest(source) == original


def test_rejects_corrupt_and_encrypted_without_leaving_outputs(tmp_path: Path):
    corrupt = tmp_path / "bad.pdf"
    corrupt.write_bytes(b"%PDF-1.7\nINVALID")
    encrypted_source = make_source(tmp_path / "plain.pdf")
    w = PdfWriter(clone_from=str(encrypted_source))
    w.encrypt("user-password")
    encrypted = tmp_path / "locked.pdf"
    w.write(str(encrypted))
    for source in (corrupt, encrypted):
        for operation, suffix in (("edit", "pdf"), ("remove", "pdf"), ("text", "txt")):
            target = tmp_path / (source.stem + "-" + operation + "." + suffix)
            with pytest.raises((ValueError, PdfReadError, EOFError)):
                if operation == "edit":
                    edit_document_info(source, target, {"title": "new"})
                elif operation == "remove":
                    remove_document_info_and_xmp(source, target)
                else:
                    extract_searchable_text(source, target)
            assert not target.exists()
