import subprocess
import zipfile
from io import BytesIO
from pathlib import Path
from string import Formatter
from tempfile import TemporaryDirectory

import httpx
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.config import get_settings

settings = get_settings()
FONT_NAME = "Helvetica"
ALLOWED_PAGE_FIELDS = {"page", "total"}


def _register_font() -> str:
    global FONT_NAME
    if FONT_NAME != "Helvetica":
        return FONT_NAME
    candidates = [
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            name = "PDFHubSans"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
            FONT_NAME = name
            return FONT_NAME
    return FONT_NAME


def _run(args: list[str], timeout: int = 1800) -> None:
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "PDF command failed")[-4000:]
        raise RuntimeError(message)


def merge(inputs: list[Path], output: Path) -> None:
    page_args: list[str] = []
    for item in inputs:
        page_args.extend([str(item), "1-z"])
    _run(["qpdf", "--empty", "--pages", *page_args, "--", str(output)])


def split(input_file: Path, pages: str, output: Path) -> None:
    _run(["qpdf", str(input_file), "--pages", ".", pages, "--", str(output)])


def rotate(input_file: Path, degrees: int, pages: str, output: Path) -> None:
    if degrees not in {-270, -180, -90, 90, 180, 270}:
        raise ValueError("degrees must be one of ±90, ±180, ±270")
    sign = "+" if degrees > 0 else ""
    _run(["qpdf", str(input_file), str(output), f"--rotate={sign}{degrees}:{pages}"])


def compress(input_file: Path, output: Path) -> None:
    _run([
        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6", "-dPDFSETTINGS=/ebook",
        "-dNOPAUSE", "-dQUIET", "-dBATCH", "-dDetectDuplicateImages=true",
        f"-sOutputFile={output}", str(input_file),
    ])


def ocr(input_file: Path, output: Path, languages: str, deskew: bool, rotate_pages: bool) -> None:
    args = ["ocrmypdf", "--skip-text", "--optimize", "1", "-l", languages]
    if deskew:
        args.append("--deskew")
    if rotate_pages:
        args.append("--rotate-pages")
    args.extend([str(input_file), str(output)])
    _run(args)


def pdfa(input_file: Path, output: Path, languages: str = "tha+eng") -> None:
    _run(["ocrmypdf", "--skip-text", "--output-type", "pdfa-2", "-l", languages, str(input_file), str(output)])


def office_to_pdf(input_file: Path, output: Path) -> None:
    with input_file.open("rb") as fh:
        response = httpx.post(
            f"{settings.gotenberg_url}/forms/libreoffice/convert",
            files={"files": (input_file.name, fh, "application/octet-stream")},
            timeout=300.0,
        )
    response.raise_for_status()
    output.write_bytes(response.content)


def _page_size(name: str) -> tuple[float, float] | None:
    if name == "a4":
        return A4
    if name == "letter":
        return LETTER
    if name == "auto":
        return None
    raise ValueError("page_size must be auto, a4, or letter")


def _flatten_image(path: Path) -> Image.Image:
    with Image.open(path) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGBA")
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        return background


def images_to_pdf(
    inputs: list[Path],
    output: Path,
    page_size: str = "auto",
    fit: str = "contain",
    margin: float = 18,
    dpi: int = 150,
) -> None:
    if not inputs:
        raise ValueError("At least one image is required")
    if fit not in {"contain", "cover"}:
        raise ValueError("fit must be contain or cover")
    fixed_page = _page_size(page_size)
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output))
    for item in inputs:
        image = _flatten_image(item)
        try:
            pixel_w, pixel_h = image.size
            if pixel_w <= 0 or pixel_h <= 0:
                raise ValueError(f"Image has invalid dimensions: {item.name}")
            natural_w = pixel_w * 72.0 / dpi
            natural_h = pixel_h * 72.0 / dpi
            if fixed_page is None:
                page_w = natural_w + margin * 2
                page_h = natural_h + margin * 2
            else:
                page_w, page_h = fixed_page
            available_w = max(1.0, page_w - margin * 2)
            available_h = max(1.0, page_h - margin * 2)
            scale_x = available_w / natural_w
            scale_y = available_h / natural_h
            scale = min(scale_x, scale_y) if fit == "contain" else max(scale_x, scale_y)
            draw_w = natural_w * scale
            draw_h = natural_h * scale
            x = (page_w - draw_w) / 2
            y = (page_h - draw_h) / 2

            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=95, optimize=True)
            buffer.seek(0)
            c.setPageSize((page_w, page_h))
            c.drawImage(ImageReader(buffer), x, y, width=draw_w, height=draw_h, mask="auto")
            c.showPage()
        finally:
            image.close()
    c.save()


def pdf_to_images(
    input_file: Path,
    output_zip: Path,
    image_format: str = "png",
    dpi: int = 150,
    first_page: int = 1,
    last_page: int | None = None,
) -> None:
    if image_format not in {"png", "jpeg"}:
        raise ValueError("format must be png or jpeg")
    reader = PdfReader(str(input_file))
    total = len(reader.pages)
    if total < 1:
        raise ValueError("PDF has no pages")
    if first_page > total:
        raise ValueError("first_page exceeds the PDF page count")
    end_page = total if last_page is None else min(last_page, total)
    if end_page < first_page:
        raise ValueError("last_page must be greater than or equal to first_page")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    extension = "png" if image_format == "png" else "jpg"
    flag = "-png" if image_format == "png" else "-jpeg"
    with TemporaryDirectory(prefix="pdfhub-raster-") as tmp:
        tmp_path = Path(tmp)
        prefix = tmp_path / "page"
        _run([
            "pdftoppm",
            "-f", str(first_page),
            "-l", str(end_page),
            "-r", str(dpi),
            flag,
            str(input_file),
            str(prefix),
        ])
        generated = list(tmp_path.glob(f"page-*.{extension}"))
        generated.sort(key=lambda p: int(p.stem.rsplit("-", 1)[-1]))
        if not generated:
            raise RuntimeError("PDF rasterizer did not create any images")
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for page_path in generated:
                page_number = int(page_path.stem.rsplit("-", 1)[-1])
                archive.write(page_path, arcname=f"page-{page_number:04d}.{extension}")


def _text_coordinates(width: float, height: float, position: str, margin: float) -> tuple[float, float, str]:
    if position.endswith("left"):
        x, align = margin, "left"
    elif position.endswith("right"):
        x, align = width - margin, "right"
    else:
        x, align = width / 2, "center"

    if position.startswith("top"):
        y = height - margin
    elif position.startswith("bottom"):
        y = margin
    else:
        y = height / 2
    return x, y, align


def _draw_text(c: canvas.Canvas, text: str, x: float, y: float, align: str) -> None:
    if align == "left":
        c.drawString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawCentredString(x, y, text)


def _overlay_page(width: float, height: float, draw) -> object:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    draw(c)
    c.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def watermark_text(
    input_file: Path,
    output: Path,
    text: str,
    font_size: float = 48,
    opacity: float = 0.18,
    rotation: float = 45,
    position: str = "center",
    margin: float = 36,
) -> None:
    font = _register_font()
    reader = PdfReader(str(input_file))
    writer = PdfWriter()
    for source_page in reader.pages:
        writer.add_page(source_page)
        page = writer.pages[-1]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        x, y, align = _text_coordinates(width, height, position, margin)

        def draw(c: canvas.Canvas, *, _x=x, _y=y, _align=align):
            c.saveState()
            c.setFont(font, font_size)
            try:
                c.setFillAlpha(opacity)
            except AttributeError:
                pass
            c.translate(_x, _y)
            c.rotate(rotation)
            _draw_text(c, text, 0, 0, _align)
            c.restoreState()

        page.merge_page(_overlay_page(width, height, draw))
    with output.open("wb") as fh:
        writer.write(fh)


def _format_page_number(template: str, page: int, total: int) -> str:
    for _, field_name, format_spec, conversion in Formatter().parse(template):
        if field_name is None:
            continue
        if field_name not in ALLOWED_PAGE_FIELDS or format_spec or conversion:
            raise ValueError("format may only use plain {page} and {total} placeholders")
    return template.format(page=page, total=total)


def add_page_numbers(
    input_file: Path,
    output: Path,
    format_text: str = "{page} / {total}",
    start_number: int = 1,
    font_size: float = 10,
    position: str = "bottom-center",
    margin: float = 24,
) -> None:
    font = _register_font()
    reader = PdfReader(str(input_file))
    writer = PdfWriter()
    total = len(reader.pages)
    for index, source_page in enumerate(reader.pages):
        writer.add_page(source_page)
        page = writer.pages[-1]
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        display_page = start_number + index
        text = _format_page_number(format_text, display_page, total)
        x, y, align = _text_coordinates(width, height, position, margin)

        def draw(c: canvas.Canvas, *, _text=text, _x=x, _y=y, _align=align):
            c.setFont(font, font_size)
            _draw_text(c, _text, _x, _y, _align)

        page.merge_page(_overlay_page(width, height, draw))
    with output.open("wb") as fh:
        writer.write(fh)


def _stamp_coordinates(
    target_width: float,
    target_height: float,
    stamp_width: float,
    stamp_height: float,
    position: str,
    margin: float,
) -> tuple[float, float]:
    if position.endswith("left"):
        x = margin
    elif position.endswith("right"):
        x = target_width - stamp_width - margin
    else:
        x = (target_width - stamp_width) / 2

    if position.startswith("top"):
        y = target_height - stamp_height - margin
    elif position.startswith("bottom"):
        y = margin
    else:
        y = (target_height - stamp_height) / 2
    return max(0, x), max(0, y)


def stamp_pdf(
    input_file: Path,
    stamp_file: Path,
    output: Path,
    position: str = "bottom-right",
    scale: float = 0.20,
    margin: float = 24,
) -> None:
    reader = PdfReader(str(input_file))
    stamp_reader = PdfReader(str(stamp_file))
    if not stamp_reader.pages:
        raise ValueError("Stamp PDF has no pages")
    source_stamp = stamp_reader.pages[0]
    source_width = float(source_stamp.mediabox.width)
    source_height = float(source_stamp.mediabox.height)
    if source_width <= 0 or source_height <= 0:
        raise ValueError("Stamp PDF has invalid dimensions")

    writer = PdfWriter()
    for source_page in reader.pages:
        writer.add_page(source_page)
        page = writer.pages[-1]
        target_width = float(page.mediabox.width)
        target_height = float(page.mediabox.height)
        factor = (target_width * scale) / source_width
        rendered_width = source_width * factor
        rendered_height = source_height * factor
        x, y = _stamp_coordinates(target_width, target_height, rendered_width, rendered_height, position, margin)
        transform = Transformation().scale(factor).translate(x, y)
        page.merge_transformed_page(source_stamp, transform, over=True)
    with output.open("wb") as fh:
        writer.write(fh)


def render_preview(input_file: Path, output_png: Path, page: int = 1, width: int = 640) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)
    prefix = output_png.with_suffix("")
    _run([
        "pdftoppm",
        "-f", str(page),
        "-singlefile",
        "-png",
        "-scale-to-x", str(width),
        "-scale-to-y", "-1",
        str(input_file),
        str(prefix),
    ], timeout=60)
    generated = Path(f"{prefix}.png")
    if generated != output_png and generated.exists():
        generated.replace(output_png)
    if not output_png.exists():
        raise RuntimeError("Preview renderer did not create an image")
