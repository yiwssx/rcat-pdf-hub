"""M22 limited text overlay: actual PDF content, not an annotation or redaction.

The first stage supports visible printable ASCII text only, unrotated plain
PDF pages, and one bounded placement at a time. It deliberately does not
claim Thai font shaping, signed-PDF validity, or complex PDF compatibility.
"""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT_CHARS = 120


def validate_overlay_parameters(*, page: int, x: float, y: float,
                                font_size: int, text: str) -> None:
    """Prevent implicit coercion, control glyphs, and explosive coordinates."""
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("Invalid overlay page number")
    if type(font_size) is not int or not 8 <= font_size <= 24:
        raise ValueError("Invalid overlay font size")
    if (type(x) not in (int, float) or type(y) not in (int, float)
            or not all(math.isfinite(float(v)) and 0 <= v <= 4000 for v in (x, y))):
        raise ValueError("Invalid overlay placement coordinates")
    if (type(text) is not str or not 1 <= len(text) <= MAX_TEXT_CHARS
            or not text.strip()
            or any(not 32 <= ord(ch) <= 126 for ch in text)):
        raise ValueError("Only bounded printable ASCII text is supported")


def add_text_to_pdf(source: Path, destination: Path, *, page: int,
                    x: float, y: float, font_size: int, text: str) -> None:
    validate_overlay_parameters(page=page, x=x, y=y,
                                font_size=font_size, text=text)
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("PDF source/destination must be distinct regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF text-overlay source size exceeds budget")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")
    if page > len(reader.pages):
        raise ValueError("Overlay target page does not exist")
    # Incremental signatures, form appearances and active annotations may be
    # broken by a page rewrite. Do not pretend we can safely preserve them.
    root = reader.trailer["/Root"]
    if root.get("/AcroForm"):
        raise ValueError("Interactive or signed forms are unsupported")
    for p in reader.pages:
        if int(p.get("/Rotate", 0)) % 360 != 0 or p.get("/Annots"):
            raise ValueError("Rotated or annotated PDFs are unsupported")
    target = reader.pages[page - 1]
    if float(target.mediabox.left) != 0 or float(target.mediabox.bottom) != 0:
        raise ValueError("Non-origin PDF pages are unsupported")
    width, height = float(target.mediabox.width), float(target.mediabox.height)
    if (not math.isfinite(width) or not math.isfinite(height)
            or not 64 <= width <= 4000 or not 64 <= height <= 4000):
        raise ValueError("PDF page dimensions outside supported range")
    if (x + stringWidth(text, "Helvetica", font_size) > width - 8
            or y < font_size or y + font_size > height - 8):
        raise ValueError("Overlay would fall outside the PDF page")

    layer = BytesIO()
    surface = canvas.Canvas(layer, pagesize=(width, height), pageCompression=1)
    surface.setFont("Helvetica", font_size)
    surface.setFillColorRGB(0, 0, 0)
    surface.drawString(float(x), float(y), text)
    surface.save()
    layer.seek(0)
    overlay = PdfReader(layer, strict=True).pages[0]
    writer = PdfWriter()
    for index, original in enumerate(reader.pages, start=1):
        writer.add_page(original)
        if index == page:
            writer.pages[-1].merge_page(overlay)
    with TemporaryDirectory(prefix="pdfhub-add-text-") as temp:
        staged = Path(temp) / "result.pdf"
        with staged.open("xb") as fh:
            writer.write(fh)
        if not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("Overlay output exceeds budget")
        result = PdfReader(str(staged), strict=True)
        if result.is_encrypted or len(result.pages) != len(reader.pages):
            raise ValueError("Overlay output has lost pages")
        if text not in (result.pages[page - 1].extract_text() or ""):
            raise ValueError("Overlay output is missing text")
        for index in range(len(reader.pages)):
            if index == page - 1:
                continue
            before = reader.pages[index].get_contents()
            after = result.pages[index].get_contents()
            if (before.get_data() if before else b"") != (after.get_data() if after else b""):
                raise ValueError("Overlay modified another page")
        with staged.open("rb") as fh, destination.open("xb") as dst:
            while chunk := fh.read(1024 * 1024):
                dst.write(chunk)
