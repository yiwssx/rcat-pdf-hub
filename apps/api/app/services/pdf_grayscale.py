"""M30: bounded, conservative Ghostscript grayscale PDF transformation.

Converts page content through GS pdfwrite using DeviceGray. An output is
committed only after validating actual PDF bytes and each page's geometry.
Digital signatures, interactive forms and annotations are unsupported:
pdfwrite can silently alter these, so they must fail closed.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from app.services.pdf_export_stage import grayscale_pdf

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_SOURCE_PAGES = 200
MAX_PAGE_DIMENSION_PT = 2880
MIN_PAGE_DIMENSION_PT = 10


def _checked_pdf(path: Path, *, source: bool) -> PdfReader:
    if path.is_symlink() or not path.is_file():
        raise ValueError("M30 requires a regular PDF file")
    length = path.stat().st_size
    cap = MAX_SOURCE_BYTES if source else MAX_OUTPUT_BYTES
    if not 24 <= length <= cap:
        raise ValueError("M30 PDF exceeds byte limits")
    with path.open("rb") as fp:
        if fp.read(5) != b"%PDF-":
            raise ValueError("M30 invalid PDF header")
    reader = PdfReader(str(path), strict=True)
    if reader.is_encrypted:
        raise ValueError("M30 encrypted PDF unsupported; unlock it first")
    if not 1 <= len(reader.pages) <= MAX_SOURCE_PAGES:
        raise ValueError("M30 page limit exceeded")
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if (not MIN_PAGE_DIMENSION_PT <= width <= MAX_PAGE_DIMENSION_PT
                or not MIN_PAGE_DIMENSION_PT <= height <= MAX_PAGE_DIMENSION_PT):
            raise ValueError("M30 unsupported page dimensions")
    if source:
        root = reader.trailer["/Root"]
        # Conservatively reject any forms, permissions, or page annotations
        # rather than claiming pdfwrite preserves signatures/interactive state.
        if root.get("/AcroForm") or root.get("/Perms") or any(
            page.get("/Annots") for page in reader.pages
        ):
            raise ValueError("M30 signed, annotated or form PDF unsupported")
    return reader


def grayscale_pdf_bounded(source: Path, destination: Path) -> None:
    """Write a new grayscale PDF without modifying the source.

    The legacy staged engine uses Ghostscript -dSAFER/DeviceGray and rewrites
    PDF objects; this cannot be interpreted as a preservation of digital
    signatures, ICC profiles, transparency compositing or PDF/A compliance.
    """
    if (source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("M30 destination must be a different new file")
    original = _checked_pdf(source, source=True)
    with TemporaryDirectory(prefix="pdfhub-m30-") as scratch:
        output = Path(scratch) / "grayscale.pdf"
        grayscale_pdf(source, output)
        rebuilt = _checked_pdf(output, source=False)
        if len(rebuilt.pages) != len(original.pages):
            raise ValueError("M30 output page count changed")
        for before, after in zip(original.pages, rebuilt.pages, strict=True):
            # Rotation and exact geometry must be preserved, including
            # non-A4 page sizes.
            if (int(before.get("/Rotate", 0)) % 360
                    != int(after.get("/Rotate", 0)) % 360):
                raise ValueError("M30 output page rotation changed")
            for name in ("mediabox", "cropbox"):
                a = getattr(before, name)
                b = getattr(after, name)
                if any(abs(float(x) - float(y)) > 0.1 for x, y in zip(a, b, strict=True)):
                    raise ValueError("M30 output page geometry changed")
        # The new file is written exclusively once validation succeeds.
        with output.open("rb") as inp, destination.open("xb") as out:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
