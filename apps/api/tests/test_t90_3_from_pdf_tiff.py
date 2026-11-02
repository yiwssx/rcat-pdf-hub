"""F09 native PDF->TIFF: actual Poppler raster and multipage TIFF evidence."""
from __future__ import annotations

from pathlib import Path
import shutil

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.services.from_pdf_tiff import pdf_to_multipage_tiff


def _two_page_pdf(path: Path) -> None:
    canvas = Canvas(str(path), pagesize=(240, 180))
    canvas.setFillColorRGB(0.9, 0.2, 0.2)
    canvas.rect(20, 20, 100, 100, fill=1)
    canvas.showPage()
    canvas.setFillColorRGB(0.2, 0.3, 0.9)
    canvas.rect(80, 20, 100, 100, fill=1)
    canvas.showPage()
    canvas.save()


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler not on host")
def test_real_pdf_to_multipage_tiff_has_exact_page_count_and_rgb(tmp_path):
    source = tmp_path / "source.pdf"
    out = tmp_path / "converted.tiff"
    _two_page_pdf(source)
    pdf_to_multipage_tiff(source, out, dpi=96)
    assert out.read_bytes()[:4] in (b"II*\x00", b"MM\x00*")
    with Image.open(out) as image:
        assert image.format == "TIFF"
        assert image.n_frames == 2
        colors = []
        for index in range(2):
            image.seek(index)
            assert image.width > 200
            assert image.height > 150
            # Pick a pixel inside both actual colored rectangles after
            # PDF-bottom-up to raster-top-down coordinate conversion.
            colors.append(image.convert("RGB").getpixel((130, 160)))
        assert colors[0] != colors[1]


@pytest.mark.parametrize("dpi", [0, 50, 301, 100.5, True])
def test_pdf_to_tiff_rejects_unsupported_dpi(tmp_path, dpi):
    source = tmp_path / "file.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    with pytest.raises(ValueError, match="DPI"):
        pdf_to_multipage_tiff(source, tmp_path / "out.tiff", dpi=dpi)


def test_pdf_to_tiff_rejects_symlink_and_non_pdf(tmp_path):
    source = tmp_path / "payload.pdf"
    source.write_bytes(b"not a pdf")
    alias = tmp_path / "alias.pdf"
    alias.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_multipage_tiff(alias, tmp_path / "result.tiff")
    with pytest.raises(Exception):
        pdf_to_multipage_tiff(source, tmp_path / "result.tiff")
    assert not (tmp_path / "result.tiff").exists()


def test_pdf_to_tiff_rejects_encrypted_source(tmp_path):
    source = tmp_path / "source.pdf"
    protected = tmp_path / "encrypted.pdf"
    _two_page_pdf(source)
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    with protected.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_multipage_tiff(protected, tmp_path / "result.tiff", dpi=96)
