from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import pdf_tools


def _make_pdf(path: Path, text: str = "base", pages: int = 2, size=(595, 842)) -> None:
    c = canvas.Canvas(str(path), pagesize=size)
    for index in range(pages):
        c.drawString(72, 760, f"{text}-{index + 1}")
        c.showPage()
    c.save()


def test_watermark_and_page_numbers(tmp_path: Path):
    source = tmp_path / "source.pdf"
    watermarked = tmp_path / "watermarked.pdf"
    numbered = tmp_path / "numbered.pdf"
    _make_pdf(source, pages=2)

    pdf_tools.watermark_text(source, watermarked, "ทดสอบ WATERMARK", opacity=0.2, rotation=30)
    pdf_tools.add_page_numbers(watermarked, numbered, format_text="หน้า {page} / {total}")

    assert watermarked.stat().st_size > 0
    reader = PdfReader(str(numbered))
    assert len(reader.pages) == 2
    assert numbered.stat().st_size > source.stat().st_size


def test_stamp_pdf(tmp_path: Path):
    source = tmp_path / "source.pdf"
    stamp = tmp_path / "stamp.pdf"
    output = tmp_path / "stamped.pdf"
    _make_pdf(source, pages=2)
    _make_pdf(stamp, text="STAMP", pages=1, size=(200, 80))

    pdf_tools.stamp_pdf(source, stamp, output, position="bottom-right", scale=0.25)

    assert len(PdfReader(str(output)).pages) == 2
    assert output.stat().st_size > 0
