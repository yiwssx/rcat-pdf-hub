import shutil
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import pdf_tools


def _image(path: Path, size: tuple[int, int], color: str) -> None:
    image = Image.new("RGB", size, color)
    try:
        image.save(path, format="PNG")
    finally:
        image.close()


def test_images_to_pdf_creates_one_page_per_image(tmp_path: Path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    output = tmp_path / "images.pdf"
    _image(first, (320, 200), "white")
    _image(second, (200, 320), "gray")

    pdf_tools.images_to_pdf([first, second], output, page_size="a4", fit="contain", dpi=150)

    reader = PdfReader(str(output))
    assert len(reader.pages) == 2
    assert output.stat().st_size > 0


def test_images_to_pdf_flattens_transparent_input(tmp_path: Path):
    source = tmp_path / "transparent.png"
    output = tmp_path / "transparent.pdf"
    image = Image.new("RGBA", (160, 120), (20, 100, 180, 96))
    try:
        image.save(source, format="PNG")
    finally:
        image.close()

    pdf_tools.images_to_pdf([source], output, page_size="auto", fit="contain", dpi=150)

    reader = PdfReader(str(output))
    assert len(reader.pages) == 1
    assert output.stat().st_size > 0


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="pdftoppm is not installed")
def test_pdf_to_images_creates_zip_with_selected_pages(tmp_path: Path):
    source = tmp_path / "source.pdf"
    output = tmp_path / "pages.zip"
    c = canvas.Canvas(str(source))
    for label in ("one", "two", "three"):
        c.drawString(72, 720, label)
        c.showPage()
    c.save()

    pdf_tools.pdf_to_images(source, output, image_format="png", dpi=72, first_page=2, last_page=3)

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["page-0002.png", "page-0003.png"]
