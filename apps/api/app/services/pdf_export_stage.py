"""Staged T90-1.7 M18 native image extraction and M30 grayscale PDF.

Extract original image XObjects rather than page screenshots. Grayscale PDF
rebuild is NOT signature/annotation/interactive-form preserving. No API routes
or production adapters invoke these engines until independent acceptance.
"""
from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from pypdf import PdfReader

from app.services.pdf_tools import _run

_MAX_PAGES = 1000
_MAX_IMAGES = 2000
_MAX_TOTAL_IMAGE_BYTES = 100 * 1024 * 1024
_ALLOWED_EXT = frozenset({"png", "jpg", "jpeg", "jp2", "tiff", "tif", "bmp"})


def _reader(source: Path, destination: Path) -> PdfReader:
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output must be different paths")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Expected PDF signature")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF must be unlocked with authorized password first")
    if not 1 <= len(reader.pages) <= _MAX_PAGES:
        raise ValueError("PDF page count outside staged bounds")
    return reader


def extract_embedded_images(source: Path, destination_zip: Path) -> None:
    """Extract original embedded image bytes; ZIP is not a page rasterization."""
    reader = _reader(source, destination_zip)
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-images-", suffix=".zip",
            dir=destination_zip.parent, delete=False,
        ) as handle:
            temp = handle.name
        image_count = 0
        written = 0
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for page_number, page in enumerate(reader.pages, 1):
                for index, image in enumerate(page.images, 1):
                    image_count += 1
                    if image_count > _MAX_IMAGES:
                        raise ValueError("PDF contains too many extractable images")
                    data = image.data
                    written += len(data)
                    if written > _MAX_TOTAL_IMAGE_BYTES:
                        raise ValueError("PDF embedded image bytes exceed staged quota")
                    extension = image.name.rsplit(".", 1)[-1].lower()
                    if extension not in _ALLOWED_EXT:
                        raise ValueError("Unsupported embedded image encoding")
                    archive.writestr(f"page-{page_number:04d}-image-{index:04d}.{extension}", data)
        if not image_count:
            raise ValueError("PDF contains no native image objects; use page rasterization")
        with zipfile.ZipFile(temp) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != image_count:
                raise ValueError("Extracted image ZIP integrity check failed")
        os.replace(temp, destination_zip)
        temp = None
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)


def grayscale_pdf(source: Path, destination: Path) -> None:
    """Produce DeviceGray PDF; may drop original signatures and interactive state."""
    reader = _reader(source, destination)
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-gray-", suffix=".pdf",
            dir=destination.parent, delete=False,
        ) as handle:
            temp = handle.name
        _run([
            "gs", "-dSAFER", "-dNOPAUSE", "-dBATCH", "-dQUIET",
            "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
            "-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray",
            f"-sOutputFile={temp}", str(source),
        ], timeout=600)
        check = PdfReader(temp, strict=True)
        if check.is_encrypted or len(check.pages) != len(reader.pages):
            raise ValueError("Grayscale PDF output validation failed")
        os.replace(temp, destination)
        temp = None
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)
