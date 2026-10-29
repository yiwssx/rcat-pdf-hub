"""T90-2 opt-in, bounded conversion engines (not a public release claim).

No arbitrary HTML, URLs, archive extraction, JavaScript, local file references,
or client-selected commands. HTML is generated internally from escaped text.
"""
from __future__ import annotations

import csv
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil

import httpx
from markdown_it import MarkdownIt
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

from app.config import get_settings
from app.services import pdf_tools

MAX_TEXT_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_FRAMES = 64
MAX_TOTAL_PIXELS = 50_000_000
MAX_FRAME_PIXELS = 20_000_000
MAX_PDF_BYTES = 40 * 1024 * 1024

_STYLE = """<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<style>@page{size:A4;margin:17mm}body{font-family:"Noto Sans Thai","Sarabun",sans-serif;font-size:11pt;line-height:1.6;color:#111}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-family:inherit}
table{border-collapse:collapse;width:100%;table-layout:fixed}
td,th{border:1px solid #999;padding:5px;vertical-align:top;overflow-wrap:anywhere}
thead{display:table-header-group}tr{break-inside:avoid}</style><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; connect-src &#39;none&#39;; img-src &#39;none&#39;; font-src &#39;none&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;"></head><body>"""
_END = "</body></html>"


def _distinct(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("Converter source and destination must differ")


def _read_utf8(source: Path) -> str:
    if source.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("Text source exceeds the staged 2 MiB limit")
    data = source.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Only UTF-8 text is accepted") from exc
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        raise ValueError("Control characters are not supported")
    if len(text) > 200_000:
        raise ValueError("Text source exceeds the character limit")
    return text


def _checked_pdf(data: bytes, output: Path) -> None:
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        raise ValueError("Converter returned an invalid or oversized PDF")
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 1000:
        raise ValueError("Converter returned an unusable PDF")
    output.write_bytes(data)


def _html_to_pdf(body: str, output: Path) -> None:
    markup = (_STYLE + body + _END).encode("utf-8")
    with httpx.Client(timeout=180.0, follow_redirects=False) as client:
        response = client.post(
            get_settings().gotenberg_url.rstrip("/") + "/forms/chromium/convert/html",
            files={"files": ("index.html", markup, "text/html")},
        )
    response.raise_for_status()
    _checked_pdf(response.content, output)


def text_to_pdf(source: Path, output: Path) -> None:
    _distinct(source, output)
    text = _read_utf8(source)
    if not text.strip():
        raise ValueError("Empty text cannot be converted")
    _html_to_pdf("<pre>" + escape(text) + "</pre>", output)


def csv_to_pdf(source: Path, output: Path) -> None:
    _distinct(source, output)
    text = _read_utf8(source)
    reader = csv.reader(StringIO(text, newline=""), delimiter=",", strict=True)
    rows: list[list[str]] = []
    for row in reader:
        if len(rows) >= 1000 or len(row) > 20 or any(len(cell) > 2000 for cell in row):
            raise ValueError("CSV exceeds staged row, column or cell limits")
        rows.append(row)
    if not rows or not any(cell.strip() for row in rows for cell in row):
        raise ValueError("Empty CSV cannot be converted")
    columns = max(map(len, rows))
    if columns == 0:
        raise ValueError("CSV has no columns")
    def cells(row: list[str], tag: str) -> str:
        return "<tr>" + "".join(
            f"<{tag}>" + escape(row[i] if i < len(row) else "") + f"</{tag}>"
            for i in range(columns)
        ) + "</tr>"
    body = "<table><thead>" + cells(rows[0], "th") + "</thead><tbody>"
    body += "".join(cells(row, "td") for row in rows[1:]) + "</tbody></table>"
    _html_to_pdf(body, output)


def markdown_to_pdf(source: Path, output: Path) -> None:
    """Safe CommonMark and tables; render external links and images as text only.

    Parsing has no raw HTML or autolink support. Input never introduces
    fetchable browser URLs, scripts, resource tags, or arbitrary attributes.
    """
    _distinct(source, output)
    text = _read_utf8(source)
    if not text.strip():
        raise ValueError("Empty Markdown cannot be converted")
    parser = MarkdownIt("commonmark", {
        "html": False, "linkify": False, "typographer": False,
    }).enable("table").disable(["link", "autolink", "image"])
    body = parser.render(text)
    # Fail closed if a future Markdown plugin unexpectedly emits active tags.
    import re
    if re.search(
        r"<\s*(?:a|img|script|iframe|link|object|embed|video|audio|source|form)\b",
        body, flags=re.IGNORECASE,
    ):
        raise ValueError("Rendered Markdown contained forbidden markup")
    _html_to_pdf(body, output)


def office_document_to_pdf(source: Path, output: Path, *, original_suffix: str) -> None:
    """Forward validated Office bytes with original extension to pinned Gotenberg.

    Stored upload names are randomized and may lack the original extension.
    LibreOffice format detection needs the checked source extension preserved.
    """
    _distinct(source, output)
    if original_suffix not in {
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".rtf",
    }:
        raise ValueError("Unsupported Office document extension")
    if source.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("Office input exceeds staged file-size limit")
    with TemporaryDirectory(prefix="pdfhub-office-to-pdf-") as folder:
        copy = Path(folder) / ("document" + original_suffix)
        shutil.copyfile(source, copy)
        with copy.open("rb") as fh:
            with httpx.Client(timeout=300.0, follow_redirects=False) as client:
                response = client.post(
                    get_settings().gotenberg_url.rstrip("/") + "/forms/libreoffice/convert",
                    files={"files": (copy.name, fh, "application/octet-stream")},
                )
        response.raise_for_status()
        _checked_pdf(response.content, output)


def image_frames_to_pdf(source: Path, output: Path, *, kind: str) -> None:
    _distinct(source, output)
    allowed = {"jfif": "JPEG", "gif": "GIF", "tiff": "TIFF",
               "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG",
               "webp": "WEBP", "bmp": "BMP"}
    if kind not in allowed:
        raise ValueError("Unknown staged image format")
    if source.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds staged 30 MiB limit")
    total_pixels = 0
    with TemporaryDirectory(prefix="pdfhub-t90-2-") as workspace:
        images = []
        try:
            with Image.open(source) as original:
                if original.format != allowed[kind]:
                    raise ValueError("Image decoder format does not match the requested tool")
                count = getattr(original, "n_frames", 1) if kind != "jfif" else 1
                if not 1 <= count <= MAX_FRAMES:
                    raise ValueError("Image frame count exceeds staged limits")
                for index in range(count):
                    original.seek(index)
                    w, h = original.size
                    pixels = w * h
                    total_pixels += pixels
                    if not 0 < pixels <= MAX_FRAME_PIXELS or total_pixels > MAX_TOTAL_PIXELS:
                        raise ValueError("Image dimensions exceed staged limits")
                    frame = ImageOps.exif_transpose(original.copy())
                    try:
                        name = Path(workspace) / f"frame-{index:04d}.png"
                        frame.save(name, format="PNG")
                        images.append(name)
                    finally:
                        frame.close()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Invalid or unsupported image") from exc
        pdf_tools.images_to_pdf(images, output, page_size="a4", fit="contain", margin=18, dpi=150)
    data = output.read_bytes()
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        output.unlink(missing_ok=True)
        raise ValueError("Image converter returned an invalid or oversized PDF")
    parsed = PdfReader(BytesIO(data), strict=True)
    if len(parsed.pages) != len(images):
        output.unlink(missing_ok=True)
        raise ValueError("Converted frame count mismatch")
