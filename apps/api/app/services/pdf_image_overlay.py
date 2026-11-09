"""M23 bounded image-on-PDF overlay (not a general editor or redaction).

A real embedded raster is composited into an ordinary unsigned PDF page.
Only one owned JPEG/PNG source, one unrotated page, fixed point coordinates and
strictly bounded document/image/pixel/output sizes are supported.
"""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 40 * 1024 * 1024
MAX_PAGES = 80
MAX_PIXELS = 20_000_000


def validate_image_overlay(*, page: int, x: float, y: float,
                           width: float, height: float) -> None:
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("M23 page must be an integer between 1 and 80")
    fields = (x, y, width, height)
    if (any(type(value) not in (int, float) for value in fields)
            or not all(math.isfinite(float(value)) for value in fields)
            or not all(0 <= float(value) <= 4000 for value in (x, y))
            or not all(8 <= float(value) <= 2000 for value in (width, height))):
        raise ValueError("M23 overlay coordinates/dimensions outside supported bounds")


def add_image_to_pdf(pdf_path: Path, image_path: Path, destination: Path, *,
                     page: int, x: float, y: float,
                     width: float, height: float) -> None:
    validate_image_overlay(page=page, x=x, y=y, width=width, height=height)
    for source in (pdf_path, image_path):
        if source.is_symlink() or not source.is_file():
            raise ValueError("M23 inputs must be regular, not symlinked files")
        if source.resolve() == destination.resolve():
            raise ValueError("M23 cannot overwrite an input")
    if destination.exists() or destination.is_symlink():
        raise ValueError("M23 output must not exist")
    if not 24 <= pdf_path.stat().st_size <= MAX_PDF_BYTES:
        raise ValueError("M23 PDF exceeds source budget")
    if not 100 <= image_path.stat().st_size <= MAX_IMAGE_BYTES:
        raise ValueError("M23 image exceeds source budget")

    reader = PdfReader(str(pdf_path), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("M23 encrypted/empty/long PDF unsupported")
    if page > len(reader.pages):
        raise ValueError("M23 target page does not exist")
    root = reader.trailer["/Root"]
    if any(root.get(key) for key in ("/AcroForm", "/Perms", "/OpenAction", "/AA")):
        raise ValueError("M23 signed, interactive or active PDFs unsupported")
    for source_page in reader.pages:
        if (int(source_page.get("/Rotate", 0)) % 360
                or source_page.get("/Annots")):
            raise ValueError("M23 rotated or annotated PDFs unsupported")
    target = reader.pages[page - 1]
    if (list(target.cropbox) != list(target.mediabox)
            or float(target.mediabox.left) != 0
            or float(target.mediabox.bottom) != 0):
        raise ValueError("M23 cropped/offset page geometry unsupported")
    page_width = float(target.mediabox.width)
    page_height = float(target.mediabox.height)
    if (not all(math.isfinite(v) and 64 <= v <= 4000
                for v in (page_width, page_height))
            or x + width > page_width or y + height > page_height):
        raise ValueError("M23 image would extend outside PDF page")

    try:
        with Image.open(image_path) as uploaded:
            if (uploaded.format not in {"JPEG", "PNG"}
                    or getattr(uploaded, "is_animated", False)
                    or not 1 <= uploaded.width * uploaded.height <= MAX_PIXELS):
                raise ValueError("M23 accepts a bounded still JPEG or PNG only")
            normalized = ImageOps.exif_transpose(uploaded)
            if normalized.mode not in {"RGB", "RGBA"}:
                normalized = normalized.convert("RGBA" if "A" in normalized.getbands() else "RGB")
            normalized.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("M23 image cannot be decoded safely") from exc

    layer = BytesIO()
    painter = canvas.Canvas(layer, pagesize=(page_width, page_height), pageCompression=1)
    painter.drawImage(ImageReader(normalized), float(x), float(y),
                      width=float(width), height=float(height), mask="auto")
    painter.save()
    layer.seek(0)
    overlay = PdfReader(layer, strict=True).pages[0]
    writer = PdfWriter()
    for index, original in enumerate(reader.pages, start=1):
        writer.add_page(original)
        if index == page:
            writer.pages[-1].merge_page(overlay)

    with TemporaryDirectory(prefix="pdfhub-m23-") as tmp:
        output = Path(tmp) / "m23-result.pdf"
        with output.open("xb") as handle:
            writer.write(handle)
        if not 100 <= output.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("M23 generated PDF size exceeds budget")
        verified = PdfReader(str(output), strict=True)
        if verified.is_encrypted or len(verified.pages) != len(reader.pages):
            raise ValueError("M23 PDF output changed the page count")
        if "/XObject" not in verified.pages[page - 1].get("/Resources", {}):
            raise ValueError("M23 expected image layer is missing")
        for index in range(len(reader.pages)):
            if index == page - 1:
                continue
            before = reader.pages[index].get_contents()
            after = verified.pages[index].get_contents()
            if ((before.get_data() if before else b"")
                    != (after.get_data() if after else b"")):
                raise ValueError("M23 modified an unselected page")
        with output.open("rb") as source, destination.open("xb") as target_handle:
            while data := source.read(1024 * 1024):
                target_handle.write(data)
