"""Native-image vs raster and real Ghostscript grayscale binary acceptance."""
from io import BytesIO
from pathlib import Path
import subprocess
import zipfile

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_export_stage import extract_embedded_images, grayscale_pdf


def _fixture(path: Path, with_image: bool = True) -> Path:
    c = canvas.Canvas(str(path), pagesize=(600, 800))
    c.setFillColorRGB(1, 0, 0)
    c.rect(30, 30, 90, 120, stroke=0, fill=1)
    if with_image:
        image = Image.new("RGB", (20, 10), (255, 0, 0))
        image.save(path.parent / "red.png")
        c.drawImage(str(path.parent / "red.png"), 70, 300, width=120, height=60)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(70, 720, "T90 SECONDARY TEXT")
    c.showPage()
    c.save()
    return path


def test_extract_real_embedded_object_not_raster(tmp_path: Path):
    source = _fixture(tmp_path / "image.pdf")
    output = tmp_path / "native.zip"
    extract_embedded_images(source, output)
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["page-0001-image-0001.png"]
        data = archive.read(archive.namelist()[0])
        assert data.startswith(b"\x89PNG\r\n")
        with Image.open(BytesIO(data)) as decoded:
            image_size = decoded.size
        assert image_size == (20, 10)


def test_no_embedded_images_never_creates_empty_zip(tmp_path: Path):
    source = _fixture(tmp_path / "blank.pdf", with_image=False)
    output = tmp_path / "native.zip"
    with pytest.raises(ValueError, match="no native image"):
        extract_embedded_images(source, output)
    assert not output.exists()


def test_grayscale_rendered_rgb_channels_equal_and_text_kept(tmp_path: Path):
    source = _fixture(tmp_path / "color.pdf")
    output = tmp_path / "gray.pdf"
    grayscale_pdf(source, output)
    result = PdfReader(str(output), strict=True)
    assert len(result.pages) == 1
    assert "T90 SECONDARY TEXT" in result.pages[0].extract_text()
    subprocess.run([
        "pdftoppm", "-f", "1", "-l", "1", "-r", "72",
        "-png", "-singlefile", str(output), str(tmp_path / "render"),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with Image.open(tmp_path / "render.png") as rendered:
        rgb = rendered.convert("RGB").getpixel((50, rendered.height - 60))
        assert max(rgb) - min(rgb) <= 1


def test_encrypted_export_fails_closed(tmp_path: Path):
    source = _fixture(tmp_path / "color.pdf")
    writer = PdfWriter(clone_from=str(source))
    writer.encrypt("password", algorithm="AES-256")
    encrypted = tmp_path / "locked.pdf"
    writer.write(str(encrypted))
    for operation, suffix in ((grayscale_pdf, ".pdf"), (extract_embedded_images, ".zip")):
        output = tmp_path / ("no" + suffix)
        with pytest.raises(ValueError, match="Encrypted"):
            operation(encrypted, output)
        assert not output.exists()
