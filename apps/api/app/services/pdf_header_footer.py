"""T90-1.7 staged M31 Thai header/footer overlay; never mounted to the runtime."""
from __future__ import annotations

import os
import tempfile
from io import BytesIO
from pathlib import Path
from string import Formatter

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT_NAME = "Helvetica"
_MAX_PAGES = 1000


def _font() -> str:
    global _FONT_NAME
    if _FONT_NAME == "Helvetica":
        path = Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf")
        if path.exists():
            if "T90-HeaderThai" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("T90-HeaderThai", str(path)))
            _FONT_NAME = "T90-HeaderThai"
    return _FONT_NAME


def _format(value: str, page: int, total: int) -> str:
    if not isinstance(value, str) or len(value) > 256 or any(ord(x) < 32 or ord(x) == 127 for x in value):
        raise ValueError("Header/footer must contain at most 256 printable characters")
    try:
        for _, field, format_spec, conversion in Formatter().parse(value):
            if field is not None and (field not in {"page", "total"} or format_spec or conversion):
                raise ValueError("Only plain {page} and {total} placeholders are supported")
        return value.format(page=page, total=total)
    except (ValueError, KeyError, IndexError) as exc:
        raise ValueError("Invalid header/footer template") from exc


def add_header_footer(
    source: Path, target: Path, *, header: str = "", footer: str = "",
    font_size: float = 12, margin: float = 30,
) -> None:
    if source.resolve() == target.resolve():
        raise ValueError("Source and target PDF must differ")
    if (
        not isinstance(font_size, (float, int)) or isinstance(font_size, bool)
        or not 6 <= font_size <= 72
    ):
        raise ValueError("Font size outside 6-72 point bounds")
    if not isinstance(margin, (float, int)) or isinstance(margin, bool) or not 6 <= margin <= 144:
        raise ValueError("Margin outside 6-144 point bounds")
    if not header and not footer:
        raise ValueError("Header and footer cannot both be empty")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Expected PDF signature")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= _MAX_PAGES:
        raise ValueError("Encrypted or out-of-bound source PDF")
    writer = PdfWriter(clone_from=reader)
    font = _font()
    for index, page in enumerate(writer.pages, 1):
        if int(page.get("/Rotate", 0)) % 360:
            page.transfer_rotation_to_content()
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if width <= 2 * margin or height <= 2 * margin:
            raise ValueError("Page too small for header/footer margins")
        title = _format(header, index, len(writer.pages))
        foot = _format(footer, index, len(writer.pages))
        for item in (title, foot):
            selected_font = "Helvetica" if item.isascii() else font
            if pdfmetrics.stringWidth(item, selected_font, font_size) > width - 2 * margin:
                raise ValueError("Header/footer exceeds page width")
        buffer = BytesIO()
        overlay = canvas.Canvas(buffer, pagesize=(width, height))
        overlay.setFont(font, font_size)
        if title:
            overlay.drawCentredString(width / 2, height - margin - font_size, title)
        if foot:
            overlay.setFont("Helvetica" if foot.isascii() else font, font_size)
            overlay.drawCentredString(width / 2, margin, foot)
        overlay.showPage()
        overlay.save()
        buffer.seek(0)
        page.merge_page(PdfReader(buffer).pages[0])
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-header-", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as handle:
            temporary = handle.name
            writer.write(handle)
        result = PdfReader(temporary, strict=True)
        if result.is_encrypted or len(result.pages) != len(reader.pages):
            raise ValueError("Header/footer output verification failed")
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
