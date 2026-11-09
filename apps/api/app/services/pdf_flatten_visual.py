"""M24 visual flatten: rasterize a bounded PDF to a new page-only PDF.

This is NOT object-level editable/form-preserving flattening, not secure
redaction, and NOT suitable for preserving signatures, searchable text,
accessibility tags or interactive form fields. Use on visible static pages.
The converter creates a completely separate, image-only PDF.
"""
from __future__ import annotations

import math
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from pypdf import PdfReader

from app.services.pdf_tools import _run

MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_PAGES = 25
RENDER_DPI = 96
MAX_PAGE_PIXELS = 4_000_000


def visual_flatten_pdf(source: Path, destination: Path) -> None:
    """Rasterize current visible page appearance, without editing the source."""
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("M24 source/destination must be distinct regular paths")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("M24 source size outside bounded budget")
    with source.open("rb") as fh:
        if fh.read(5) != b"%PDF-":
            raise ValueError("M24 requires original PDF signature")

    original = PdfReader(str(source), strict=True)
    if original.is_encrypted or not 1 <= len(original.pages) <= MAX_PAGES:
        raise ValueError("M24 encrypted or excessive-page PDF unsupported")
    if original.trailer["/Root"].get("/Perms"):
        raise ValueError("M24 cannot preserve a certified document signature")

    geometry: list[tuple[float, float]] = []
    for page in original.pages:
        box = page.mediabox
        if (int(page.get("/Rotate", 0)) % 360
                or tuple(page.cropbox) != tuple(box)
                or abs(float(box.left)) > 0.01
                or abs(float(box.bottom)) > 0.01):
            raise ValueError("M24 requires unrotated, uncropped origin-zero pages")
        width, height = float(box.width), float(box.height)
        if (not all(math.isfinite(v) for v in (width, height))
                or not (72 <= width <= 1200 and 72 <= height <= 1200)
                or width * height * (RENDER_DPI / 72) ** 2 > MAX_PAGE_PIXELS):
            raise ValueError("M24 page geometry exceeds visual-flatten limit")
        geometry.append((width, height))

    with TemporaryDirectory(prefix="pdfhub-m24-visual-") as scratch:
        folder = Path(scratch)
        prefix = folder / "page"
        _run([
            "pdftoppm", "-r", str(RENDER_DPI), "-png",
            "-f", "1", "-l", str(len(original.pages)),
            str(source), str(prefix),
        ], timeout=180)
        actual = sorted(folder.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        expected = list(range(1, len(original.pages) + 1))
        parsed = [int(p.stem.split("-")[-1]) for p in actual]
        if parsed != expected:
            raise ValueError("M24 renderer lost or duplicated PDF pages")

        images: list[Image.Image] = []
        try:
            for ordinal, raster in enumerate(actual):
                if raster.is_symlink() or raster.stat().st_size > 12 * 1024 * 1024:
                    raise ValueError("M24 page raster exceeds byte budget")
                with Image.open(raster) as opened:
                    opened.verify()
                with Image.open(raster) as opened:
                    if (opened.format != "PNG" or opened.width * opened.height > MAX_PAGE_PIXELS
                            or opened.width < 16 or opened.height < 16):
                        raise ValueError("M24 page raster dimensions invalid")
                    images.append(opened.convert("RGB"))
                width, height = geometry[ordinal]
                rendered_w, rendered_h = images[-1].size
                if (abs(rendered_w * 72 / RENDER_DPI - width) > 1.0
                        or abs(rendered_h * 72 / RENDER_DPI - height) > 1.0):
                    raise ValueError("M24 page raster geometry changed")
            staging = folder / "flattened.pdf"
            images[0].save(
                staging, "PDF", resolution=float(RENDER_DPI),
                save_all=True, append_images=images[1:],
            )
            if not 100 <= staging.stat().st_size <= MAX_OUTPUT_BYTES:
                raise ValueError("M24 flattened PDF outside output budget")
            rebuilt = PdfReader(str(staging), strict=True)
            if rebuilt.is_encrypted or len(rebuilt.pages) != len(geometry):
                raise ValueError("M24 visual PDF page inventory mismatched")
            for before, after in zip(geometry, rebuilt.pages, strict=True):
                if (abs(before[0] - float(after.mediabox.width)) > 1.0
                        or abs(before[1] - float(after.mediabox.height)) > 1.0):
                    raise ValueError("M24 visual PDF geometry changed")
                # Each new page is only raster content, not a hidden copy of text.
                if (after.get("/Annots") or (after.extract_text() or "").strip()):
                    raise ValueError("M24 visual flatten retained interactive/text content")
            staging.replace(destination)
        finally:
            for item in images:
                item.close()
