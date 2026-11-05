"""M31 bounded, tenant-safe PDF header/footer overlay adapter.

Existing staged overlay engine performs PDF page merge. This adapter provides
strict source and result constraints, new-file atomic publishing and an exact
schema validator shared by API and Worker.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from app.services.pdf_header_footer import _format, add_header_footer

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_PAGES = 200
MIN_DIMENSION_PT = 72
MAX_DIMENSION_PT = 2880
POSITIONS = frozenset({"left", "center", "right"})
FIELDS = frozenset({
    "header", "footer", "font_size", "margin",
    "header_align", "footer_align",
})


def validate_header_footer_params(params: dict) -> dict:
    """Return the exact bounded, typed, template-checked M31 parameter set."""
    if not isinstance(params, dict) or set(params) != FIELDS:
        raise ValueError("M31 requires exactly six header/footer settings")
    header, footer = params["header"], params["footer"]
    if (type(header) is not str or type(footer) is not str
            or not (header.strip() or footer.strip())):
        raise ValueError("M31 requires header or footer text")
    for value in (header, footer):
        _format(value, 1, MAX_PAGES)
    font_size, margin = params["font_size"], params["margin"]
    if type(font_size) is not int or not 8 <= font_size <= 24:
        raise ValueError("M31 font size must be 8–24 pt")
    if type(margin) is not int or not 12 <= margin <= 144:
        raise ValueError("M31 margin must be 12–144 pt")
    if (type(params["header_align"]) is not str
            or params["header_align"] not in POSITIONS
            or type(params["footer_align"]) is not str
            or params["footer_align"] not in POSITIONS):
        raise ValueError("M31 alignment must be left, center or right")
    return dict(params)


def _open_source(source: Path, destination: Path) -> PdfReader:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.is_symlink() or destination.exists()):
        raise ValueError("M31 source must be regular and destination new")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("M31 source PDF size exceeds budget")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("M31 expected PDF signature")
    original = PdfReader(str(source), strict=True)
    if original.is_encrypted or not 1 <= len(original.pages) <= MAX_PAGES:
        raise ValueError("M31 encrypted or excessive-page PDF unsupported")
    root = original.trailer["/Root"]
    if root.get("/AcroForm") is not None or root.get("/Perms") is not None:
        raise ValueError("M31 signed or interactive PDFs unsupported")
    for page in original.pages:
        if page.get("/Annots") is not None:
            raise ValueError("M31 annotated PDFs unsupported")
        media, crop = page.mediabox, page.cropbox
        if (any(abs(float(a) - float(b)) > 0.01 for a, b in zip(media, crop, strict=True))
                or abs(float(media.left)) > 0.01 or abs(float(media.bottom)) > 0.01):
            raise ValueError("M31 cropped or non-origin page unsupported")
        width, height = float(media.width), float(media.height)
        if not all(
            math.isfinite(d) and MIN_DIMENSION_PT <= d <= MAX_DIMENSION_PT
            for d in (width, height)
        ):
            raise ValueError("M31 unsupported PDF page dimensions")
        if int(page.get("/Rotate", 0)) % 90:
            raise ValueError("M31 page rotation must be multiple of 90 degrees")
    return original


def header_footer_pdf_bounded(source: Path, destination: Path, *, params: dict) -> None:
    opts = validate_header_footer_params(params)
    reader = _open_source(source, destination)

    # Both the underlying staged engine and this new-file publication happen
    # under the destination filesystem. Hard-link publication is atomic and
    # fails rather than overwriting an existing output.
    with TemporaryDirectory(prefix="pdfhub-m31-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "header-footer.pdf"
        add_header_footer(source, staged, **opts)
        if (staged.is_symlink() or not staged.is_file()
                or not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES):
            raise ValueError("M31 output size or type invalid")
        with staged.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("M31 output is not PDF")
        output = PdfReader(str(staged), strict=True)
        if output.is_encrypted or len(output.pages) != len(reader.pages):
            raise ValueError("M31 output has invalid page count/encryption")
        for index, (before, after) in enumerate(zip(reader.pages, output.pages, strict=True), 1):
            rotation = int(before.get("/Rotate", 0)) % 360
            expected_size = (
                (float(before.mediabox.height), float(before.mediabox.width))
                if rotation in (90, 270)
                else (float(before.mediabox.width), float(before.mediabox.height))
            )
            final_size = (float(after.mediabox.width), float(after.mediabox.height))
            if any(abs(a - b) > 0.1 for a, b in zip(expected_size, final_size, strict=True)):
                raise ValueError("M31 output display geometry changed")
            if int(after.get("/Rotate", 0)) % 360 != 0:
                raise ValueError("M31 output rotation not normalized")
            original_text = before.extract_text() or ""
            result_text = after.extract_text() or ""
            if original_text and original_text not in result_text:
                raise ValueError("M31 original text no longer extractable")
            for template in (opts["header"], opts["footer"]):
                formatted = _format(template, index, len(reader.pages))
                # Glyph extraction from Thai TTFonts is renderer-dependent.
                # Validate Latin text here; visual fidelity is separately gated.
                if formatted and formatted.isascii() and formatted not in result_text:
                    raise ValueError("M31 overlay text missing from output")

        os.link(staged, destination)
