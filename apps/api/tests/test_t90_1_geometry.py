"""Real binary M11/M28 geometry regression; no production activation."""
import hashlib
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_page_geometry import crop_pdf, resize_pdf


def _fixture(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=(500, 720))
    c.drawString(30, 690, "FIRST PAGE T90 1.5")
    c.showPage()
    c.setPageSize((640, 480))
    c.drawString(20, 440, "SECOND PAGE T90 1.5")
    c.showPage()
    c.save()
    writer = PdfWriter(clone_from=str(path))
    writer.pages[1].rotate(90)
    rotated = path.parent / "rotated.pdf"
    writer.write(str(rotated))
    return rotated


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_crop_selected_retains_media_rotation_text_and_source(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    before = _digest(source)
    out = tmp_path / "crop.pdf"
    crop_pdf(source, out, left=50, bottom=80, right=350, top=400, pages=[1])
    reader = PdfReader(str(out), strict=True)
    assert len(reader.pages) == 2
    assert tuple(map(float, reader.pages[0].cropbox)) == (50, 80, 350, 400)
    assert tuple(map(float, reader.pages[0].mediabox)) == (0, 0, 500, 720)
    assert tuple(map(float, reader.pages[1].cropbox)) == (0, 0, 640, 480)
    assert reader.pages[1].get("/Rotate") == 90
    assert "FIRST PAGE" in reader.pages[0].extract_text()
    assert "SECOND PAGE" in reader.pages[1].extract_text()
    assert _digest(source) == before


def test_mixed_page_invalid_crop_fails_atomically(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    out = tmp_path / "crop.pdf"
    with pytest.raises(ValueError, match="outside"):
        crop_pdf(source, out, left=50, bottom=80, right=450, top=600)
    assert not out.exists()


def test_resize_mixed_dimensions_keeps_rotation_content(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    before = _digest(source)
    out = tmp_path / "resized.pdf"
    resize_pdf(source, out, width=595, height=842)
    reader = PdfReader(str(out), strict=True)
    assert len(reader.pages) == 2
    assert all(
        abs(float(page.mediabox.width) - 595) < .001
        and abs(float(page.mediabox.height) - 842) < .001
        for page in reader.pages
    )
    assert reader.pages[1].get("/Rotate") == 90
    assert "FIRST PAGE" in reader.pages[0].extract_text()
    assert "SECOND PAGE" in reader.pages[1].extract_text()
    assert _digest(source) == before


@pytest.mark.parametrize("bounds", [
    (10, 10, 10, 100),
    (10, 10, 9999, 100),
    (float("nan"), 10, 50, 100),
    (0, 0, float("inf"), 100),
])
def test_crop_rejects_invalid_bounds(tmp_path: Path, bounds):
    source = _fixture(tmp_path / "source.pdf")
    output = tmp_path / "bad.pdf"
    with pytest.raises(ValueError):
        crop_pdf(source, output, left=bounds[0], bottom=bounds[1], right=bounds[2], top=bounds[3])
    assert not output.exists()


@pytest.mark.parametrize("pages", [[], [0], [3], [1, 1], [True]])
def test_crop_rejects_invalid_selection(tmp_path: Path, pages):
    source = _fixture(tmp_path / "source.pdf")
    output = tmp_path / "bad.pdf"
    with pytest.raises(ValueError):
        crop_pdf(source, output, left=10, bottom=10, right=300, top=300, pages=pages)
    assert not output.exists()


@pytest.mark.parametrize("size", [
    (0, 500), (-10, 200), (float("inf"), 200),
    (500, float("nan")), (30000, 50), (True, 300),
])
def test_resize_rejects_invalid_dimensions(tmp_path: Path, size):
    source = _fixture(tmp_path / "source.pdf")
    output = tmp_path / "bad.pdf"
    with pytest.raises(ValueError):
        resize_pdf(source, output, width=size[0], height=size[1])
    assert not output.exists()


def test_encrypted_and_corrupt_are_rejected(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    writer = PdfWriter(clone_from=str(source))
    writer.encrypt("secret", algorithm="AES-256")
    encrypted = tmp_path / "encrypted.pdf"
    writer.write(str(encrypted))
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\nGARBAGE")
    for input_file in (encrypted, corrupt):
        for op, kwargs in (
            (crop_pdf, {"left": 10, "bottom": 10, "right": 100, "top": 100}),
            (resize_pdf, {"width": 400, "height": 400}),
        ):
            output = tmp_path / "bad.pdf"
            with pytest.raises(Exception):
                op(input_file, output, **kwargs)
            assert not output.exists()


def test_never_write_to_original(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    before = _digest(source)
    with pytest.raises(ValueError, match="differ"):
        crop_pdf(source, source, left=10, bottom=10, right=100, top=100)
    with pytest.raises(ValueError, match="differ"):
        resize_pdf(source, source, width=400, height=400)
    assert _digest(source) == before
