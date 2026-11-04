"""M22 source-level real PDF overlay binary and negative regression tests."""
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
import pytest

from app.services.pdf_text_overlay import add_text_to_pdf, validate_overlay_parameters


def source_pdf(path: Path, n: int = 3, *, rotate: bool = False) -> None:
    canvas = Canvas(str(path), pagesize=(320, 200))
    for index in range(n):
        canvas.drawString(20, 120, f"Original page {index + 1}")
        canvas.showPage()
    canvas.save()
    if rotate:
        source = PdfReader(str(path))
        writer = PdfWriter()
        for page in source.pages:
            writer.add_page(page)
        writer.pages[0].rotate(90)
        with path.open("wb") as stream:
            writer.write(stream)


def test_real_text_overlay_preserves_page_order_and_source(tmp_path):
    source, output = tmp_path / "in.pdf", tmp_path / "out.pdf"
    source_pdf(source)
    before = source.read_bytes()
    add_text_to_pdf(source, output, page=2, x=20, y=50,
                    font_size=12, text="Hello RCAT 2026")
    assert before == source.read_bytes()
    result = PdfReader(str(output), strict=True)
    assert len(result.pages) == 3
    assert "Hello RCAT 2026" in result.pages[1].extract_text()
    assert "Original page 1" in result.pages[0].extract_text()
    assert "Original page 3" in result.pages[2].extract_text()


@pytest.mark.parametrize("options", [
    {"page": True, "x": 20, "y": 40, "font_size": 12, "text": "abc"},
    {"page": 1, "x": float("nan"), "y": 40, "font_size": 12, "text": "abc"},
    {"page": 1, "x": 20, "y": 40, "font_size": 12, "text": "ภาษาไทย"},
    {"page": 1, "x": 20, "y": 40, "font_size": 12, "text": "hello\nWorld"},
    {"page": 1, "x": 20, "y": 40, "font_size": 8, "text": " "},
    {"page": 1, "x": 20, "y": 40, "font_size": 25, "text": "hello"},
])
def test_invalid_parameters(options):
    with pytest.raises(ValueError):
        validate_overlay_parameters(**options)


def test_bounds_existing_destination_and_source_immutability(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "result.pdf"
    source_pdf(source)
    before = source.read_bytes()
    with pytest.raises(ValueError):
        add_text_to_pdf(source, output, page=8, x=10, y=20,
                        font_size=12, text="hi")
    with pytest.raises(ValueError):
        add_text_to_pdf(source, output, page=1, x=300, y=20,
                        font_size=12, text="Long text does not fit")
    assert source.read_bytes() == before
    assert not output.exists()
    output.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        add_text_to_pdf(source, output, page=1, x=10, y=20,
                        font_size=12, text="hi")
    assert output.read_bytes() == b"preserve"


def test_rotated_or_encrypted_pdf_and_symlink_refused(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "result.pdf"
    source_pdf(source, rotate=True)
    with pytest.raises(ValueError, match="Rotated"):
        add_text_to_pdf(source, output, page=2, x=10, y=20,
                        font_size=12, text="hello")
    assert not output.exists()
    link = tmp_path / "link.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        add_text_to_pdf(link, output, page=1, x=20, y=30,
                        font_size=12, text="hello")
    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt("secret")
    with source.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        add_text_to_pdf(source, output, page=1, x=20, y=30,
                        font_size=12, text="hello")
    assert not output.exists()

def test_cropped_page_is_not_treated_as_full_visible_media(tmp_path):
    source, output = tmp_path / "cropped.pdf", tmp_path / "output.pdf"
    source_pdf(source)
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.pages[0].cropbox.lower_left = (20, 20)
    with source.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Cropped"):
        add_text_to_pdf(source, output, page=1, x=20, y=40,
                        font_size=12, text="Not visible")
    assert not output.exists()
