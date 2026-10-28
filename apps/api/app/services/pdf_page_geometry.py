"""Staged T90-1.5 geometry engines: M11 crop and M28 exact page resize.

Not registered with the legacy runtime or a public API. Coordinates are PDF
points in unrotated user space. CropBox hides content; it is NOT redaction.
"""
from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader, PdfWriter

_MAX_PAGES = 1000
_MAX_SOURCE_BYTES = 100 * 1024 * 1024
_MIN_SIDE = 10.0
_MAX_SIDE = 14400.0


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite PDF points")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite PDF points")
    return result


def _open(source: Path, destination: Path) -> PdfReader:
    if source.resolve() == destination.resolve():
        raise ValueError("PDF source and destination must differ")
    if source.stat().st_size > _MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds staged 100 MiB input limit")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Expected a PDF signature")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF requires authorized unlocking")
    if not 1 <= len(reader.pages) <= _MAX_PAGES:
        raise ValueError("PDF page count exceeds staged bounds")
    return reader


def _write(writer: PdfWriter, target: Path, expected_pages: int) -> None:
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-geometry-", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as handle:
            temp = handle.name
            writer.write(handle)
        check = PdfReader(temp, strict=True)
        if check.is_encrypted or len(check.pages) != expected_pages:
            raise ValueError("PDF geometry output validation failed")
        os.replace(temp, target)
        temp = None
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)


def crop_pdf(
    source: Path, destination: Path, *,
    left: float, bottom: float, right: float, top: float,
    pages: Sequence[int] | None = None,
) -> None:
    """Hide selected areas without deleting original PDF content or changing MediaBox.

    Coordinates must fit each selected page's existing visible CropBox;
    /Rotate is preserved, not interpreted as a transformed screen coordinate.
    """
    x0, y0, x1, y1 = (
        _finite(left, "left"), _finite(bottom, "bottom"),
        _finite(right, "right"), _finite(top, "top"),
    )
    if not _MIN_SIDE <= x1 - x0 <= _MAX_SIDE or not _MIN_SIDE <= y1 - y0 <= _MAX_SIDE:
        raise ValueError("Crop width and height must be between 10 and 14400 points")
    reader = _open(source, destination)
    total = len(reader.pages)
    if pages is None:
        selected = set(range(1, total + 1))
    else:
        if not pages or any(type(number) is not int or number < 1 or number > total for number in pages):
            raise ValueError("Invalid 1-based crop page selection")
        if len(set(pages)) != len(pages):
            raise ValueError("Duplicate crop page numbers are not supported")
        selected = set(pages)
    writer = PdfWriter(clone_from=reader)
    for index, page in enumerate(writer.pages, 1):
        if index not in selected:
            continue
        original = page.cropbox
        if not (
            x0 >= float(original.left) - 1e-6
            and y0 >= float(original.bottom) - 1e-6
            and x1 <= float(original.right) + 1e-6
            and y1 <= float(original.top) + 1e-6
        ):
            raise ValueError(f"Crop rectangle is outside existing page {index} CropBox")
        page.cropbox.lower_left = (x0, y0)
        page.cropbox.upper_right = (x1, y1)
    _write(writer, destination, total)


def resize_pdf(source: Path, destination: Path, *, width: float, height: float) -> None:
    """Exact target geometry by X/Y scaling; this may distort aspect ratios.

    Scale-to-exact-size is NOT a proportion-preserving print-layout feature.
    """
    w, h = _finite(width, "width"), _finite(height, "height")
    if not _MIN_SIDE <= w <= _MAX_SIDE or not _MIN_SIDE <= h <= _MAX_SIDE:
        raise ValueError("Resize width and height must be between 10 and 14400 points")
    reader = _open(source, destination)
    writer = PdfWriter(clone_from=reader)
    for index, page in enumerate(writer.pages, 1):
        old_w, old_h = float(page.mediabox.width), float(page.mediabox.height)
        if not (math.isfinite(old_w) and math.isfinite(old_h) and old_w > 0 and old_h > 0):
            raise ValueError(f"Invalid source page {index} geometry")
        page.scale_to(w, h)
    _write(writer, destination, len(reader.pages))
