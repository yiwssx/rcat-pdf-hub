import subprocess
from io import BytesIO
from pathlib import Path
from string import Formatter

import httpx
from pypdf import PdfReader, PdfWriter, Transformation
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
