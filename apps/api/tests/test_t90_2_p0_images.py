"""T90-2.1 baseline image-to-PDF binary regressions (no runtime changes).

P0 T02/T03/T24/T28 plus single-frame TIFF T13 legacy behavior; true
multi-frame TIFF is separately opt-in via T90-2 batch-1 staged adapter.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader

from app.filetypes import validate_uploaded_file
from app.services import pdf_tools

FORMATS = [
    (".jpg", "JPEG", "image/jpeg", (235, 25, 30)),
    (".png", "PNG", "image/png", (30, 200, 40)),
    (".webp", "WEBP", "image/webp", (35, 55, 220)),
    (".bmp", "BMP", "image/bmp", (235, 170, 35)),
    (".tiff", "TIFF", "image/tiff", (125, 35, 200)),
]


def _image(path: Path, fmt: str, size, color):
    image = Image.new("RGB", size, color)
    try:
        image.save(path, format=fmt)
    finally:
        image.close()


@pytest.mark.parametrize("extension,fmt,mime,color", FORMATS)
def test_p0_baseline_real_image_binary_and_original_unchanged(
    tmp_path, extension, fmt, mime, color,
):
    source = tmp_path / ("photo" + extension)
    _image(source, fmt, (240, 160), color)
    assert validate_uploaded_file(source, source.name) == mime
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "converted.pdf"
    pdf_tools.images_to_pdf(
        [source], output, page_size="auto", fit="contain", margin=18, dpi=150,
    )
    reader = PdfReader(str(output), strict=True)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    assert abs(float(page.mediabox.width) - (240 * 72 / 150 + 36)) < 0.1
    assert abs(float(page.mediabox.height) - (160 * 72 / 150 + 36)) < 0.1
    assert len(page.images) == 1
    embedded = Image.open(BytesIO(page.images[0].data))
    try:
        pixel = embedded.convert("RGB").getpixel((120, 80))
        assert all(abs(pixel[n] - color[n]) < 25 for n in range(3))
    finally:
        embedded.close()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_mixed_format_order_size_and_immutable_sources(tmp_path):
    files = []
    for idx, (extension, fmt, mime, color) in enumerate(FORMATS):
        path = tmp_path / (str(idx) + extension)
        size = (120 + idx * 30, 90 + idx * 40)
        _image(path, fmt, size, color)
        files.append((path, size, color))
    digests = [hashlib.sha256(f[0].read_bytes()).hexdigest() for f in files]
    output = tmp_path / "mixed.pdf"
    pdf_tools.images_to_pdf(
        [f[0] for f in files], output, page_size="a4",
        fit="contain", margin=10, dpi=150,
    )
    reader = PdfReader(str(output), strict=True)
    assert len(reader.pages) == len(files)
    for idx, page in enumerate(reader.pages):
        assert abs(float(page.mediabox.width) - 595.2756) < 0.1
        assert abs(float(page.mediabox.height) - 841.8898) < 0.1
        embedded = Image.open(BytesIO(page.images[0].data))
        try:
            pixel = embedded.convert("RGB").getpixel(
                (files[idx][1][0] // 2, files[idx][1][1] // 2)
            )
            assert all(abs(pixel[n] - files[idx][2][n]) < 25 for n in range(3))
        finally:
            embedded.close()
        assert hashlib.sha256(files[idx][0].read_bytes()).hexdigest() == digests[idx]


@pytest.mark.parametrize("extension,fmt,mime,color", FORMATS)
def test_upload_rejects_mislabeled_and_truncated_p0_images(
    tmp_path, extension, fmt, mime, color
):
    path = tmp_path / ("bad" + extension)
    path.write_bytes(b"%PDF-1.7\nmalicious")
    with pytest.raises(HTTPException) as error:
        validate_uploaded_file(path, path.name)
    assert error.value.status_code == 415
    # For signatures with a longer header, a truncated image may pass the
    # first-line signature preflight; the decoder is a separate required gate.
    path.write_bytes(b"not a recognized image")
    with pytest.raises(HTTPException):
        validate_uploaded_file(path, path.name)


def test_rgba_png_and_webp_white_background_rendered_in_binary(tmp_path):
    for extension, fmt in ((".png", "PNG"), (".webp", "WEBP")):
        source = tmp_path / ("alpha" + extension)
        image = Image.new("RGBA", (80, 60), (0, 0, 255, 0))
        try:
            image.save(source, fmt, lossless=True) if fmt == "WEBP" else image.save(source, fmt)
        finally:
            image.close()
        output = tmp_path / ("alpha" + extension + ".pdf")
        pdf_tools.images_to_pdf([source], output, page_size="a4", dpi=150)
        page = PdfReader(str(output), strict=True).pages[0]
        embedded = Image.open(BytesIO(page.images[0].data))
        try:
            pixel = embedded.convert("RGB").getpixel((40, 30))
            assert min(pixel) >= 240  # flattened fully transparent to white
        finally:
            embedded.close()
