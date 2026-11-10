"""M01 source edit must alter the original Tj operator, not paint over it."""
from hashlib import sha256

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from app.services.pdf_text_replacement import replace_pdf_text, validate_edit


def sample(tmp_path, font="Courier", first="FIRST ORIGINAL WORD", duplicate=False):
    source = tmp_path / "source.pdf"
    doc = canvas.Canvas(str(source), pagesize=(595, 842))
    doc.setFont(font, 14)
    doc.drawString(80, 700, first)
    if duplicate:
        doc.drawString(80, 675, first)
    doc.showPage()
    doc.setFont("Courier", 12)
    doc.drawString(80, 700, "SECOND PAGE IS INTACT")
    doc.save()
    return source


def test_replaces_existing_courier_text_without_overlay(tmp_path):
    source = sample(tmp_path)
    original_hash = sha256(source.read_bytes()).hexdigest()
    result = tmp_path / "edited.pdf"
    replace_pdf_text(source, result, page=1, old_text="ORIGINAL", new_text="MODIFIED")
    before, after = PdfReader(str(source), strict=True), PdfReader(str(result), strict=True)
    assert len(after.pages) == len(before.pages) == 2
    assert "FIRST MODIFIED WORD" in (after.pages[0].extract_text() or "")
    assert "ORIGINAL" not in (after.pages[0].extract_text() or "")
    assert after.pages[1].extract_text() == before.pages[1].extract_text()
    assert sha256(source.read_bytes()).hexdigest() == original_hash
    assert result.read_bytes().startswith(b"%PDF-")
    # The new text lives in the actual PDF content stream, not an overlay.
    assert b"(FIRST MODIFIED WORD) Tj" in after.pages[0].get_contents().get_data()
    assert b"(FIRST ORIGINAL WORD) Tj" not in after.pages[0].get_contents().get_data()


@pytest.mark.parametrize("previous,replacement", [
    ("ORIGINAL", "NEW"), ("ORIGINAL", "ORIGINAL"),
    ("ไทย", "abc"), ("WORD", "NO\n!"), ("  ", "ab"), ("A" * 97, "B" * 97),
    ("A B", "ABC"),
])
def test_invalid_text_parameters_rejected(previous, replacement):
    with pytest.raises(ValueError):
        validate_edit(page=1, old_text=previous, new_text=replacement)


def test_rejects_duplicate_source_without_writing(tmp_path):
    source = sample(tmp_path, duplicate=True)
    result = tmp_path / "fail.pdf"
    with pytest.raises(ValueError, match="not unique"):
        replace_pdf_text(source, result, page=1, old_text="ORIGINAL", new_text="MODIFIED")
    assert not result.exists()


@pytest.mark.parametrize("font", ["Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold"])
def test_standard_proportional_fonts_compensate_following_text(tmp_path, font):
    source = sample(tmp_path, font=font)
    before = PdfReader(str(source), strict=True)
    output = tmp_path / "proportional.pdf"
    replace_pdf_text(source, output, page=1,
                     old_text="ORIGINAL", new_text="MODIFIED")
    after = PdfReader(str(output), strict=True)
    extracted = after.pages[0].extract_text() or ""
    assert "MODIFIED" in extracted and "ORIGINAL" not in extracted
    assert "WORD" in extracted
    assert after.pages[1].extract_text() == before.pages[1].extract_text()
    operations = ContentStream(after.pages[0].get_contents(), after).operations
    arrays = [args[0] for args, cmd in operations if cmd == b"TJ"]
    assert len(arrays) == 1
    chunks = arrays[0]
    assert "MODIFIED" in str(chunks[0])
    assert str(chunks[-1]) == " WORD"
    expected = round(
        pdfmetrics.stringWidth("MODIFIED", font, 1000)
        - pdfmetrics.stringWidth("ORIGINAL", font, 1000)
    )
    assert expected != 0 and int(chunks[-2]) == expected


def test_rejects_unsupported_symbol_font(tmp_path):
    source = sample(tmp_path, font="Symbol")
    with pytest.raises(ValueError, match="Courier, Helvetica or Times"):
        replace_pdf_text(source, tmp_path / "fail.pdf",
                         page=1, old_text="ORIGINAL", new_text="MODIFIED")


def test_rejects_nonexistent_page_and_text(tmp_path):
    source = sample(tmp_path)
    with pytest.raises(ValueError, match="page"):
        replace_pdf_text(source, tmp_path / "fail.pdf",
                         page=3, old_text="ORIGINAL", new_text="MODIFIED")
    with pytest.raises(ValueError, match="not found"):
        replace_pdf_text(source, tmp_path / "fail.pdf",
                         page=1, old_text="NOTEXIST", new_text="CHANGED!")


def test_rejects_encrypted_pdf(tmp_path):
    source = sample(tmp_path)
    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    for page in PdfReader(str(source)).pages:
        writer.add_page(page)
    writer.encrypt("secret")
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="encrypted"):
        replace_pdf_text(encrypted, tmp_path / "fail.pdf", page=1,
                         old_text="ORIGINAL", new_text="MODIFIED")


def test_rejects_existing_output_and_alias(tmp_path):
    source = sample(tmp_path)
    dest = tmp_path / "already.pdf"
    dest.write_bytes(b"PREEXISTING")
    with pytest.raises(ValueError, match="distinct"):
        replace_pdf_text(source, dest, page=1,
                         old_text="ORIGINAL", new_text="MODIFIED")
    assert dest.read_bytes() == b"PREEXISTING"
    with pytest.raises(ValueError, match="distinct"):
        replace_pdf_text(source, source, page=1,
                         old_text="ORIGINAL", new_text="MODIFIED")


def test_m01_queue_routing_is_explicitly_default_off(monkeypatch):
    from app import queue
    baseline = queue.settings
    monkeypatch.setattr(
        queue, "settings", baseline.model_copy(update={"pdf_edit_text_tools_enabled": False}),
    )
    with pytest.raises(ValueError, match="Unsupported"):
        queue.queue_class_for_operation("edit-existing-pdf-text")
    monkeypatch.setattr(
        queue, "settings", baseline.model_copy(update={"pdf_edit_text_tools_enabled": True}),
    )
    assert queue.queue_class_for_operation("edit-existing-pdf-text") == "pdf"
