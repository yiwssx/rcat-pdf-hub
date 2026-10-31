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


def _has_visible_pdf_content(data: bytes) -> bool:
    """Raster-validate converter PDFs, not just their container/page count.

    A PDF parser accepts documents with only blank page objects. Some real
    external Office decoders produce exactly those on unsupported input and
    previously passed as successful output. PDFium is already hash-pinned in
    the API runtime. Render no more than 32 pages with <=700px longest side (tiny source
    pages render at higher scale), without writing any file, and require
    actual visible ink (text, vector or graphics).
    This is a rejection gate, NOT a guarantee of full source-format fidelity.
    """
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(data)
        try:
            for index in range(min(len(document), 32)):
                page = document[index]
                try:
                    width, height = page.get_size()
                    if not (1 <= width <= 14400 and 1 <= height <= 14400):
                        raise ValueError("Converter PDF has unsupported page dimensions")
                    # A tiny DjVu or CAD page can legitimately be 10-20 PDF
                    # points wide. Upscale such pages to roughly 96 pixels
                    # while bounding normal/huge pages to <=700 pixels.
                    longest = max(width, height)
                    scale = min(700.0 / longest, max(0.5, 96.0 / longest))
                    bitmap = page.render(scale=scale, grayscale=True)
                    try:
                        histogram = bitmap.to_pil().histogram()
                        # True white and near-white pixels do not count.
                        # A handful of antialiased dark pixels does count:
                        # this keeps sparse signatures and small text valid.
                        if sum(histogram[:245]) >= 10:
                            return True
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        finally:
            document.close()
    except Exception as exc:
        raise ValueError("Converter PDF could not be visually validated") from exc
    return False


def _checked_pdf(data: bytes, output: Path) -> None:
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        raise ValueError("Converter returned an invalid or oversized PDF")
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= 1000:
        raise ValueError("Converter returned an unusable PDF")
    if not _has_visible_pdf_content(data):
        raise ValueError("Converter returned blank or invisible PDF pages")
    output.write_bytes(data)


def _html_to_pdf(body: str, output: Path) -> None:
    markup = (_STYLE + body + _END).encode("utf-8")
    with httpx.Client(timeout=180.0, follow_redirects=False) as client:
        response = client.post(
            get_settings().gotenberg_url.rstrip("/") + "/forms/chromium/convert/html",
            files={"files": ("index.html", markup, "text/html")},
            data={"preferCssPageSize": "true"},
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


def html_to_pdf(source: Path, output: Path) -> None:
    """HTML content-only subset: never render untrusted tags/attributes/CSS."""
    from html.parser import HTMLParser

    _distinct(source, output)
    raw = _read_utf8(source)
    allowed = frozenset({
        "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span",
        "strong", "em", "b", "i", "u", "pre", "code", "blockquote",
        "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
        "br", "hr",
    })
    forbidden = frozenset({
        "script", "style", "iframe", "object", "embed", "svg", "math",
        "noscript", "template", "head", "canvas", "video", "audio",
    })

    class SafeTextHtml(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.fragments: list[str] = []
            self.suppressed = 0
            self.tags = 0

        def handle_starttag(self, tag, attrs):
            self.tags += 1
            if self.tags > 20000:
                raise ValueError("HTML exceeds tag-count limit")
            if tag in forbidden:
                self.suppressed += 1
            elif not self.suppressed and tag in allowed:
                self.fragments.append("<" + tag + ">")

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)

        def handle_endtag(self, tag):
            if tag in forbidden:
                self.suppressed = max(0, self.suppressed - 1)
            elif not self.suppressed and tag in allowed and tag not in {"hr", "br"}:
                self.fragments.append("</" + tag + ">")

        def handle_data(self, data):
            if not self.suppressed:
                self.fragments.append(escape(data))

    parser = SafeTextHtml()
    parser.feed(raw)
    parser.close()
    fragment = "".join(parser.fragments)
    if not fragment.strip():
        raise ValueError("HTML has no printable text content")
    _html_to_pdf(fragment, output)


def xml_to_pdf(source: Path, output: Path) -> None:
    """Render a readable XML source listing, never execute XML or fetch entities."""
    from xml.etree import ElementTree

    _distinct(source, output)
    text = _read_utf8(source)
    if any(token in text.upper() for token in ("<!DOCTYPE", "<!ENTITY", "<?XML-STYLESHEET")):
        raise ValueError("XML entity and stylesheet declarations are not accepted")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ValueError("Invalid XML document") from exc
    nodes = 0
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > 10000 or depth > 64 or len(node.attrib) > 50:
            raise ValueError("XML complexity exceeds staged limits")
        stack.extend((child, depth + 1) for child in node)
    _html_to_pdf("<h1>XML document</h1><pre>" + escape(text) + "</pre>", output)


def eml_to_pdf(source: Path, output: Path) -> None:
    """Convert email headers and plain-text body, never MIME attachments/HTML."""
    from email import policy
    from email.parser import BytesParser

    _distinct(source, output)
    if source.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError("EML exceeds staged 2 MiB limit")
    raw = source.read_bytes()
    if b"\x00" in raw:
        raise ValueError("EML contains unsafe control characters")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if message.defects:
            raise ValueError("Malformed EML")
        if message.is_multipart():
            candidates = []
            for index, part in enumerate(message.walk()):
                if index > 64:
                    raise ValueError("Too many EML parts")
                if (part.get_content_type() == "text/plain"
                        and part.get_content_disposition() != "attachment"):
                    candidates.append(part.get_content())
            body = "\n\n".join(candidates)
        else:
            if message.get_content_type() != "text/plain":
                raise ValueError("Only plain-text EML bodies are supported")
            body = message.get_content()
    except (UnicodeError, LookupError, TypeError, ValueError) as exc:
        raise ValueError("Unsupported EML body or encoding") from exc
    if not isinstance(body, str) or not body.strip() or len(body) > 200000:
        raise ValueError("EML plain-text body is empty or too large")
    headers = "".join(
        "<p><strong>" + escape(label) + ":</strong> "
        + escape(str(message.get(label, ""))[:2000]) + "</p>"
        for label in ("From", "To", "Date", "Subject")
    )
    _html_to_pdf("<h1>Email</h1>" + headers + "<pre>" + escape(body) + "</pre>", output)


def archive_images_to_pdf(source: Path, output: Path, *, kind: str) -> None:
    """CBZ or images-only ZIP, in memory with bounded metadata and no extraction."""
    import re
    import zipfile

    _distinct(source, output)
    if kind not in {"cbz", "zip"}:
        raise ValueError("Unknown archive format")
    if source.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError("Archive exceeds staged 30 MiB limit")
    with TemporaryDirectory(prefix="pdfhub-comic-") as folder:
        files = []
        total = 0
        pixels = 0
        try:
            with zipfile.ZipFile(source, "r") as archive:
                infos = archive.infolist()
                if not 1 <= len(infos) <= 256:
                    raise ValueError("Archive entry count exceeds limits")
                images = []
                for info in infos:
                    name = info.filename
                    parts = name.rstrip("/").split("/")
                    mode = (info.external_attr >> 16) & 0o170000
                    if (not name or name.startswith("/") or "\\" in name or ":" in name
                            or any(part in ("", ".", "..") for part in parts)
                            or mode not in (0, 0o100000, 0o040000)
                            or (mode == 0o040000 and not info.is_dir())
                            or info.flag_bits & 1
                            or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                        raise ValueError("Unsafe archive entry")
                    if info.is_dir():
                        continue
                    if name.casefold().endswith("comicinfo.xml") and info.file_size <= 1024*1024:
                        continue
                    if Path(name).suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                        raise ValueError("Only image-only ZIP/CBZ archives are supported")
                    total += info.file_size
                    if (info.file_size > 12 * 1024 * 1024
                            or total > 50 * 1024 * 1024
                            or info.file_size > (info.compress_size + 1024) * 100):
                        raise ValueError("Archive expansion exceeds limits")
                    images.append(info)
                if not 1 <= len(images) <= MAX_FRAMES:
                    raise ValueError("Image count exceeds staged 64-page limit")
                # Natural order, not archive metadata order.
                key = lambda info: [int(v) if v.isdigit() else v.casefold()
                                    for v in re.split(r"(\d+)", info.filename)]
                images.sort(key=key)
                for index, info in enumerate(images):
                    data = archive.read(info)
                    if len(data) != info.file_size:
                        raise ValueError("Archive member length changed")
                    with Image.open(BytesIO(data)) as image:
                        if image.format not in {"JPEG", "PNG", "WEBP", "BMP"}:
                            raise ValueError("Archive image signature mismatch")
                        width, height = image.size
                        count = width * height
                        pixels += count
                        if count > MAX_FRAME_PIXELS or pixels > MAX_TOTAL_PIXELS:
                            raise ValueError("Archive image pixels exceed staged limits")
                        frame = ImageOps.exif_transpose(image.copy())
                    try:
                        target = Path(folder) / f"page-{index:04d}.png"
                        frame.save(target, format="PNG")
                        files.append(target)
                    finally:
                        frame.close()
        except (zipfile.BadZipFile, OSError, RuntimeError, EOFError, UnidentifiedImageError) as exc:
            raise ValueError("Invalid image archive") from exc
        pdf_tools.images_to_pdf(files, output, page_size="a4", fit="contain",
                                margin=18, dpi=150)
        pdf = output.read_bytes()
        if not pdf.startswith(b"%PDF-") or len(pdf) > MAX_PDF_BYTES:
            output.unlink(missing_ok=True)
            raise ValueError("Archive PDF output invalid or oversized")
        try:
            result = PdfReader(BytesIO(pdf), strict=True)
            if len(result.pages) != len(files):
                raise ValueError("Archive conversion page count mismatch")
        except Exception:
            output.unlink(missing_ok=True)
            raise


def svg_to_pdf(source: Path, output: Path) -> None:
    """Render only an allowlisted SVG geometry/text subset, default OFF."""
    from app.services.to_pdf_svg import safe_svg_markup
    _distinct(source, output)
    _html_to_pdf(safe_svg_markup(source), output)


def epub_to_pdf(source: Path, output: Path) -> None:
    """Convert bounded EPUB text spine; no remote resources, CSS or DRM."""
    from app.services.to_pdf_ebooks import epub_to_safe_html
    _distinct(source, output)
    _html_to_pdf(epub_to_safe_html(source), output)


def fb2_to_pdf(source: Path, output: Path) -> None:
    """Convert bounded FictionBook XML body; images intentionally omitted."""
    from app.services.to_pdf_ebooks import fb2_to_safe_html
    _distinct(source, output)
    _html_to_pdf(fb2_to_safe_html(source), output)


def office_document_to_pdf(source: Path, output: Path, *, original_suffix: str) -> None:
    """Forward validated Office bytes with original extension to pinned Gotenberg.

    Stored upload names are randomized and may lack the original extension.
    LibreOffice format detection needs the checked source extension preserved.
    """
    _distinct(source, output)
    if original_suffix not in {
        ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".rtf", ".pub", ".pages", ".hwp",
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
