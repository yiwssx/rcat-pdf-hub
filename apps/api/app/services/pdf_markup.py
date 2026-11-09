"""Real, bounded PDF markup: M25 FreeText, M26 highlight, M29 visual whiteout.

- M25 and M26 add actual editable PDF annotations.
- M29 draws an opaque white rectangle over *visible* content. The covered
  original content remains extractable: this is NOT secure redaction.
Neither operation preserves existing digital signatures or form semantics.
"""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText, Highlight
from pypdf.generic import ArrayObject, FloatObject
from reportlab.pdfgen import canvas

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT = 120
MODES = frozenset({"annotation", "highlight", "whiteout"})


def validate_markup(*, mode: str, page: int, x: float, y: float,
                    width: float, height: float, text: str = "") -> None:
    if type(mode) is not str or mode not in MODES:
        raise ValueError("Unsupported M25/M26/M29 markup mode")
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("Page outside markup budget")
    numeric = (x, y, width, height)
    if (any(type(v) not in (int, float) or not math.isfinite(float(v)) for v in numeric)
            or not 0 <= x <= 4000 or not 0 <= y <= 4000
            or not 8 <= width <= 1500 or not 8 <= height <= 1500):
        raise ValueError("Markup rectangle coordinates outside budget")
    if type(text) is not str:
        raise ValueError("Markup text must be a string")
    if mode == "annotation":
        if not 1 <= len(text) <= MAX_TEXT or not text.strip() or any(
            not 32 <= ord(char) <= 126 for char in text
        ):
            raise ValueError("M25 annotation accepts bounded printable ASCII only")
    elif text:
        raise ValueError("M26/M29 do not accept hidden annotation text")


def markup_pdf(source: Path, destination: Path, *, mode: str, page: int,
               x: float, y: float, width: float, height: float, text: str = "") -> None:
    validate_markup(mode=mode, page=page, x=x, y=y,
                    width=width, height=height, text=text)
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("Markup source and destination must be distinct regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Markup input size exceeds bounded source budget")
    with source.open("rb") as fh:
        if fh.read(5) != b"%PDF-":
            raise ValueError("Markup source PDF signature invalid")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF is unsupported")
    root = reader.trailer["/Root"]
    if root.get("/AcroForm") or root.get("/Perms"):
        raise ValueError("Signed or interactive form PDFs not supported for markup")
    for selected in reader.pages:
        if (int(selected.get("/Rotate", 0)) % 360
                or selected.get("/Annots")
                or tuple(selected.cropbox) != tuple(selected.mediabox)
                or abs(float(selected.mediabox.left)) > .01
                or abs(float(selected.mediabox.bottom)) > .01):
            raise ValueError("Markup requires plain unrotated uncropped PDF pages")
    if page > len(reader.pages):
        raise ValueError("Target page does not exist")
    target = reader.pages[page - 1]
    size_x, size_y = float(target.mediabox.width), float(target.mediabox.height)
    if (not math.isfinite(size_x) or not math.isfinite(size_y)
            or not 72 <= size_x <= 4000 or not 72 <= size_y <= 4000
            or x + width > size_x or y + height > size_y):
        raise ValueError("Markup rectangle exceeds target page bounds")

    writer = PdfWriter()
    writer.append(reader)
    rect = (x, y, x + width, y + height)
    if mode == "annotation":
        writer.add_annotation(page_number=page - 1, annotation=FreeText(
            text=text, rect=rect, font="Helvetica", font_size="12pt",
            font_color="000000", border_color="a88b29",
            background_color="fff4b8",
        ))
    elif mode == "highlight":
        # PDF QuadPoints order: upper-left, upper-right, lower-left, lower-right.
        points = ArrayObject([
            FloatObject(x), FloatObject(y + height),
            FloatObject(x + width), FloatObject(y + height),
            FloatObject(x), FloatObject(y),
            FloatObject(x + width), FloatObject(y),
        ])
        writer.add_annotation(page_number=page - 1, annotation=Highlight(
            rect=rect, quad_points=points, highlight_color="ffff55", printing=True,
        ))
    else:
        # Purely visual overlay. The covered original text/images still exist
        # in the output. Do not mistake this for secure redaction.
        layer = BytesIO()
        drawing = canvas.Canvas(layer, pagesize=(size_x, size_y), pageCompression=1)
        drawing.setFillColorRGB(1, 1, 1)
        drawing.rect(x, y, width, height, stroke=0, fill=1)
        drawing.save()
        layer.seek(0)
        overlay = PdfReader(layer, strict=True).pages[0]
        writer.pages[page - 1].merge_page(overlay)

    with TemporaryDirectory(prefix="pdfhub-m25-m26-m29-") as scratch:
        staged = Path(scratch) / "markup.pdf"
        with staged.open("xb") as stream:
            writer.write(stream)
        if not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("Markup result exceeds bounded output size")
        check = PdfReader(str(staged), strict=True)
        if check.is_encrypted or len(check.pages) != len(reader.pages):
            raise ValueError("Markup output page count mismatch")
        for index, (before, after) in enumerate(zip(reader.pages, check.pages, strict=True)):
            if (abs(float(before.mediabox.width) - float(after.mediabox.width)) > .1
                    or abs(float(before.mediabox.height) - float(after.mediabox.height)) > .1):
                raise ValueError("Markup changed source geometry")
            if index == page - 1 and mode in {"annotation", "highlight"}:
                annots = after.get("/Annots")
                if not annots or len(annots) != 1:
                    raise ValueError("M25/M26 actual PDF annotation not preserved")
                subtype = annots[0].get_object().get("/Subtype")
                expected = "/FreeText" if mode == "annotation" else "/Highlight"
                if str(subtype) != expected:
                    raise ValueError("Markup annotation subtype mismatch")
            elif index != page - 1 and after.get("/Annots"):
                raise ValueError("Markup accidentally changed another page's annotations")
        if mode == "whiteout":
            # Whiteout must not claim data has been securely removed.
            source_text = reader.pages[page - 1].extract_text() or ""
            result_text = check.pages[page - 1].extract_text() or ""
            if source_text.strip() and source_text.strip() not in result_text:
                raise ValueError("Visual-only whiteout silently removed source text")
        staged.replace(destination)
