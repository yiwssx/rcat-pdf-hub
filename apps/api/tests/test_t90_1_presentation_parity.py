"""T90-1.7 existing M19/M20/M21 vector and actual preview parity tests.

These execute the existing 13-operation production engines, not the staged UI.
"""
import hashlib
from pathlib import Path

from PIL import Image, ImageChops
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import pdf_tools


def _document(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=(595, 842))
    c.setFillColorRGB(0.1, 0.2, 0.9)
    c.rect(90, 90, 140, 80, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    for index in range(2):
        c.drawString(72, 710, f"RCAT PAGE {index + 1}")
        c.showPage()
    c.save()
    return path


def test_real_page_numbers_and_watermark_keep_source_pages(tmp_path: Path):
    source = _document(tmp_path / "source.pdf")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    watermark = tmp_path / "wm.pdf"
    numbered = tmp_path / "numbered.pdf"
    pdf_tools.watermark_text(source, watermark, text="RCAT APPROVED", opacity=0.2, rotation=30)
    pdf_tools.add_page_numbers(watermark, numbered, format_text="Page {page}/{total}", start_number=7)
    result = PdfReader(str(numbered), strict=True)
    assert len(result.pages) == 2
    assert "RCAT PAGE 1" in result.pages[0].extract_text()
    assert "RCAT PAGE 2" in result.pages[1].extract_text()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert numbered.stat().st_size > 0


def test_real_preview_chooses_requested_page_and_width(tmp_path: Path):
    source = _document(tmp_path / "source.pdf")
    first = tmp_path / "p1.png"
    second = tmp_path / "p2.png"
    pdf_tools.render_preview(source, first, page=1, width=320)
    pdf_tools.render_preview(source, second, page=2, width=320)
    with Image.open(first) as image1, Image.open(second) as image2:
        assert image1.width == image2.width == 320
        assert image1.height > 0 and image2.height > 0
        # Different page number text must change rendered pixels; no stale page-1 preview.
        assert ImageChops.difference(image1.convert("RGB"), image2.convert("RGB")).getbbox() is not None
