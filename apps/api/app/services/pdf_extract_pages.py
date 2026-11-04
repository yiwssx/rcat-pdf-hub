"""M16 selected-page extraction: authentic ordered PDF and optional per-page ZIP.

The ZIP implementation intentionally reuses reviewed M07 binary extraction;
M16 adds a dedicated feature-gated workflow rather than duplicating ZIP code.
"""
from __future__ import annotations

from pathlib import Path
from pypdf import PdfReader, PdfWriter

from app.services.pdf_split_zip import (
    _source_document,
    selected_page_numbers,
    MAX_PARTS_BYTES,
)


def extract_selected_pages_pdf(source: Path, output: Path, *, pages: str) -> None:
    """Preserve requested page content/order in one new PDF; never mutate source."""
    if output.is_symlink() or output.exists() or source.resolve() == output.resolve():
        raise ValueError("M16 extraction destination must be a new distinct PDF")
    reader = _source_document(source)  # same strict input/annotation/signature gate as M07
    selection = selected_page_numbers(pages, len(reader.pages))
    writer = PdfWriter()
    for number in selection:
        writer.add_page(reader.pages[number - 1])
    with output.open("xb") as stream:
        writer.write(stream)
    if not 100 <= output.stat().st_size <= MAX_PARTS_BYTES:
        output.unlink(missing_ok=True)
        raise ValueError("M16 extracted PDF exceeds output budget")
    try:
        verified = PdfReader(str(output), strict=True)
        if verified.is_encrypted or len(verified.pages) != len(selection):
            raise ValueError("M16 extracted PDF page count invalid")
        for original_index, copied in zip(selection, verified.pages, strict=True):
            original = reader.pages[original_index - 1]
            contents_original = original.get_contents()
            contents_copied = copied.get_contents()
            if (
                (contents_original.get_data() if contents_original else b"")
                != (contents_copied.get_data() if contents_copied else b"")
                or tuple(original.mediabox) != tuple(copied.mediabox)
                or tuple(original.cropbox) != tuple(copied.cropbox)
                or int(original.get("/Rotate", 0)) != int(copied.get("/Rotate", 0))
            ):
                raise ValueError("M16 extracted PDF page content or geometry changed")
    except Exception:
        output.unlink(missing_ok=True)
        raise
