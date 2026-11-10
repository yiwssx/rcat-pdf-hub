"""M01 source edit must alter the original Tj operator, not paint over it."""
from hashlib import sha256
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, NumberObject, TextStringObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
    if expected:
        assert len(chunks) == 3 and int(chunks[-2]) == expected
    else:
        # Equal-width glyph sequences need no displacement and must not
        # emit a redundant zero-width TJ numeric token.
        assert len(chunks) == 2


def test_rejects_unsupported_symbol_font(tmp_path):
    source = sample(tmp_path, font="Symbol")
    output = tmp_path / "fail.pdf"
    # Symbol encoding may not expose ASCII as Tj Unicode; both a missing
    # exact source string and an unsupported built-in font must fail closed.
    with pytest.raises(ValueError, match="M01"):
        replace_pdf_text(source, output,
                         page=1, old_text="ORIGINAL", new_text="MODIFIED")
    assert not output.exists()


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


def _tj_source(tmp_path, *, font="Helvetica", gap=-40):
    """A real PDF whose original text spans two positioned TJ string parts."""
    original = sample(tmp_path, font=font)
    reader = PdfReader(str(original), strict=True)
    stream = ContentStream(reader.pages[0].get_contents(), reader)
    for i, (args, operator) in enumerate(stream.operations):
        if operator == b"Tj" and args and "FIRST ORIGINAL WORD" in str(args[0]):
            stream.operations[i] = ([ArrayObject([
                TextStringObject("FIRST OR"),
                NumberObject(gap),
                TextStringObject("IGINAL WORD"),
            ])], b"TJ")
            break
    else:
        raise AssertionError("Expected genuine source Tj object")
    writer = PdfWriter(clone_from=reader)
    writer.pages[0].replace_contents(stream)
    target = tmp_path / "source-tj.pdf"
    with target.open("wb") as fh:
        writer.write(fh)
    return target


@pytest.mark.parametrize("font", ["Courier", "Helvetica", "Times-Roman"])
def test_edits_visible_text_across_positioned_tj_fragments(tmp_path, font):
    src = _tj_source(tmp_path, font=font)
    original_hash = sha256(src.read_bytes()).digest()
    dest = tmp_path / "edited-tj.pdf"
    replace_pdf_text(src, dest, page=1, old_text="ORIGINAL", new_text="MODIFIED")
    verified = PdfReader(str(dest), strict=True)
    assert len(verified.pages) == 2
    chunks = [
        args[0] for args, cmd in ContentStream(
            verified.pages[0].get_contents(), verified
        ).operations if cmd == b"TJ"
    ]
    assert len(chunks) == 1
    assert "".join(str(x) for x in chunks[0] if isinstance(x, TextStringObject)) == (
        "FIRST MODIFIED WORD"
    )
    # Keep the original positioning instruction, plus any compensations.
    assert any(int(x) == -40 for x in chunks[0] if isinstance(x, NumberObject))
    assert "MODIFIED" in (verified.pages[0].extract_text() or "")
    assert "SECOND PAGE IS INTACT" in (verified.pages[1].extract_text() or "")
    assert sha256(src.read_bytes()).digest() == original_hash


def test_refuses_widely_spaced_tj_text_pieces(tmp_path):
    src = _tj_source(tmp_path, gap=-900)
    dest = tmp_path / "bad-layout.pdf"
    with pytest.raises(ValueError, match="wide TJ positioning gap"):
        replace_pdf_text(src, dest, page=1, old_text="ORIGINAL", new_text="MODIFIED")
    assert not dest.exists()


def _embedded_source(tmp_path):
    # API Docker image already installs fonts-noto-core; no added dependency
    # and no font file is distributed or committed with these tests.
    fonts = [
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    path = next((font for font in fonts if font.is_file()), None)
    if path is None:
        pytest.skip("No installed local TrueType font in this environment")
    font_name = "M01TestEmbedded"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(path)))
    src = tmp_path / "embedded.pdf"
    c = canvas.Canvas(str(src))
    c.setFont(font_name, 14)
    c.drawString(80, 730, "FIRST ORIGINAL WORD")
    # Explicit same-font glyph witness: no new, unembedded subset letters.
    c.drawString(80, 690, "MODIFIED")
    c.save()
    return src


def test_embedded_truetype_only_reuses_demonstrated_glyphs(tmp_path):
    src = _embedded_source(tmp_path)
    out = tmp_path / "embedded-edited.pdf"
    replace_pdf_text(src, out, page=1, old_text="ORIGINAL", new_text="MODIFIED")
    reader = PdfReader(str(out), strict=True)
    # PDF text extraction may infer extra whitespace at an unchanged text
    # cursor when the replacement is narrower. Inspect actual operators too.
    extracted = reader.pages[0].extract_text() or ""
    assert "FIRST MODIFIED" in extracted and "WORD" in extracted
    fonts = reader.pages[0]["/Resources"]["/Font"]
    assert any(str(font.get_object().get("/Subtype")) == "/TrueType"
               and font.get_object().get("/ToUnicode") is not None
               for font in fonts.values())
    assert out.stat().st_size >= 100


def test_embedded_truetype_rejects_glyph_not_used_in_source(tmp_path):
    src = _embedded_source(tmp_path)
    out = tmp_path / "missing-glyph.pdf"
    with pytest.raises(ValueError, match="witnessed embedded"):
        replace_pdf_text(src, out, page=1,
                         old_text="ORIGINAL", new_text="ZODIFIED")
    assert not out.exists()


def test_embedded_truetype_rejects_missing_to_unicode_mapping(tmp_path):
    src = _embedded_source(tmp_path)
    reader = PdfReader(str(src), strict=True)
    writer = PdfWriter(clone_from=reader)
    fonts = writer.pages[0]["/Resources"]["/Font"]
    embedded = next(font.get_object() for font in fonts.values()
                    if str(font.get_object().get("/Subtype")) == "/TrueType")
    del embedded["/ToUnicode"]
    altered = tmp_path / "embedded-no-cmap.pdf"
    with altered.open("wb") as fh:
        writer.write(fh)
    out = tmp_path / "no-cmap-edited.pdf"
    with pytest.raises(ValueError, match="witnessed embedded"):
        replace_pdf_text(altered, out, page=1,
                         old_text="ORIGINAL", new_text="MODIFIED")
    assert not out.exists()
