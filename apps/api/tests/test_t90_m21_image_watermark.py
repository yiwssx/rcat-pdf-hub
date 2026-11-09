"""M21 real two-page image watermark and fail-closed parameter tests."""
from hashlib import sha256

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services.pdf_image_watermark import watermark_pdf_image, validate_image_watermark


def fixtures(tmp_path):
    src, img = tmp_path / "report.pdf", tmp_path / "logo.png"
    pdf = canvas.Canvas(str(src), pagesize=(595, 842))
    for label in ("PAGE ONE", "PAGE TWO"):
        pdf.drawString(90, 600, label)
        pdf.showPage()
    pdf.save()
    Image.new("RGB", (80, 40), color=(40, 90, 200)).save(img)
    return src, img


def test_m21_real_image_watermark_on_every_pdf_page(tmp_path):
    src, img = fixtures(tmp_path)
    target = tmp_path / "watermarked.pdf"
    digest = sha256(src.read_bytes()).hexdigest()
    watermark_pdf_image(src, img, target, relative_width=.3, opacity=.2)
    assert sha256(src.read_bytes()).hexdigest() == digest
    pdf = PdfReader(str(target), strict=True)
    assert len(pdf.pages) == 2
    assert all("/XObject" in p.get("/Resources", {}) for p in pdf.pages)
    assert "PAGE ONE" in pdf.pages[0].extract_text()
    assert "PAGE TWO" in pdf.pages[1].extract_text()


def test_m21_rejects_invalid_opacity_and_output_clobber(tmp_path):
    with pytest.raises(ValueError, match="opacity"):
        validate_image_watermark(relative_width=.3, opacity=1.0)
    src, img = fixtures(tmp_path)
    with pytest.raises(ValueError, match="separate"):
        watermark_pdf_image(src, img, src)
