"""M21 real repeated JPEG/PNG image watermark, separate from M23 single-page overlay.

Adds an opacity-controlled image to every unrotated PDF page, preserving the
original document. This is visual marking only, not cryptographic signing,
watermark removal resistance or secure redaction.
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
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_PAGES = 80
MAX_PIXELS = 20_000_000


def validate_image_watermark(*, relative_width: float, opacity: float) -> None:
    if (type(relative_width) not in (int, float)
            or type(opacity) not in (int, float)
            or not math.isfinite(float(relative_width))
            or not math.isfinite(float(opacity))
            or not 0.10 <= relative_width <= 0.80
            or not 0.05 <= opacity <= 0.70):
        raise ValueError("Image watermark width or opacity outside supported bounds")


def watermark_pdf_image(pdf_path: Path, image_path: Path, destination: Path,
                        *, relative_width: float = 0.30, opacity: float = 0.20) -> None:
    validate_image_watermark(relative_width=relative_width, opacity=opacity)
    for path in (pdf_path, image_path):
        if path.is_symlink() or not path.is_file() or path.resolve() == destination.resolve():
            raise ValueError("M21 inputs must be separate regular files")
    if destination.exists() or destination.is_symlink():
        raise ValueError("M21 output must be new")
    if not 24 <= pdf_path.stat().st_size <= MAX_PDF_BYTES:
        raise ValueError("M21 PDF exceeds input budget")
    if not 16 <= image_path.stat().st_size <= MAX_IMAGE_BYTES:
        raise ValueError("M21 image exceeds input budget")

    reader = PdfReader(str(pdf_path), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("M21 encrypted/long/empty PDF unsupported")
    root = reader.trailer["/Root"]
    if any(root.get(key) for key in ("/AcroForm", "/Perms", "/OpenAction", "/AA")):
        raise ValueError("M21 interactive or certified PDFs unsupported")
    for page in reader.pages:
        if (int(page.get("/Rotate", 0)) % 360 or page.get("/Annots")
                or tuple(page.cropbox) != tuple(page.mediabox)
                or abs(float(page.mediabox.left)) > .01
                or abs(float(page.mediabox.bottom)) > .01):
            raise ValueError("M21 requires unrotated uncropped plain PDF pages")

    try:
        with Image.open(image_path) as loaded:
            if (loaded.format not in {"JPEG", "PNG"}
                    or getattr(loaded, "is_animated", False)
                    or not 1 <= loaded.width * loaded.height <= MAX_PIXELS):
                raise ValueError("M21 requires bounded still PNG/JPEG")
            image = ImageOps.exif_transpose(loaded)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("M21 image cannot be decoded safely") from exc

    aspect = image.height / image.width
    if not math.isfinite(aspect) or aspect <= 0:
        raise ValueError("M21 invalid image aspect ratio")
    writer = PdfWriter()
    for source_page in reader.pages:
        page_w, page_h = float(source_page.mediabox.width), float(source_page.mediabox.height)
        if not all(math.isfinite(v) and 72 <= v <= 4000 for v in (page_w, page_h)):
            raise ValueError("M21 page geometry outside PDF budget")
        w = page_w * relative_width
        h = w * aspect
        if h > page_h * .8:
            h = page_h * .8
            w = h / aspect
        x = (page_w - w) / 2
        y = (page_h - h) / 2
        layer = BytesIO()
        painter = canvas.Canvas(layer, pagesize=(page_w, page_h), pageCompression=1)
        painter.saveState()
        painter.setFillAlpha(float(opacity))
        painter.drawImage(ImageReader(image), x, y, width=w, height=h, mask="auto")
        painter.restoreState()
        painter.save()
        layer.seek(0)
        overlay = PdfReader(layer, strict=True).pages[0]
        writer.add_page(source_page)
        writer.pages[-1].merge_page(overlay)

    with TemporaryDirectory(prefix="pdfhub-m21-image-watermark-") as scratch:
        staged = Path(scratch) / "watermark.pdf"
        with staged.open("xb") as handle:
            writer.write(handle)
        if not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("M21 output exceeds budget")
        output = PdfReader(str(staged), strict=True)
        if output.is_encrypted or len(output.pages) != len(reader.pages):
            raise ValueError("M21 watermark output lost PDF pages")
        for page in output.pages:
            resources = page.get("/Resources", {})
            if "/XObject" not in resources:
                raise ValueError("M21 watermark image missing on one PDF page")
        staged.replace(destination)
