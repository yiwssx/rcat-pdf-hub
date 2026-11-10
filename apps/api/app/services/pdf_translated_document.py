"""M05: render actual translated text into a newly composed, page-marked PDF.

Does not preserve original PDF geometry or images. Translation is supplied by a
private model; Chromium/Gotenberg only typesets escaped Unicode (Thai included).
No arbitrary HTML, cloud provider URL, executable input or user-chosen endpoint.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

import httpx
from pypdf import PdfReader

from app.services import pdf_private_translation as translation
from app.services import to_pdf_engine as pdf_engine

# Deliberately fixed to the existing local Gotenberg Compose service, not an
# environment-configurable URL or externally reachable translation provider.
GOTENBERG_ORIGIN = "http://gotenberg:3000"
MAX_RENDER_BYTES = 24 * 1024 * 1024
MAX_HTML_BYTES = 512 * 1024
MAX_RENDERED_PAGES = translation.MAX_PAGES * 5

_PDF_STYLES = """<style>
.m05-part{break-before:page;min-width:0}
.m05-part:first-of-type{break-before:auto}
.m05-part h2{font-size:13pt;margin-bottom:8mm;color:#243244}
.m05-note{font-size:9pt;color:#46505a;border-bottom:1px solid #cbd5e1;padding-bottom:4mm}
.m05-translated{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;
  font-family:"Noto Sans Thai","Sarabun",sans-serif;font-size:11pt;line-height:1.75}
</style>"""


def _html_document(pages: list[str], source_language: str, target_language: str) -> bytes:
    """Only fixed HTML tags/CSS; all provider-controlled content is escaped."""
    translation.validate_languages(source_language, target_language)
    if not 1 <= len(pages) <= translation.MAX_PAGES:
        raise ValueError("M05 translated page count outside bounds")
    blocks = []
    for index, translated in enumerate(pages, 1):
        if (not isinstance(translated, str) or not translated.strip()
                or len(translated) > 12000):
            raise ValueError("M05 translation model returned unusable text")
        blocks.append(
            '<section class="m05-part"><h2>Translation of source page '
            + str(index) + '</h2><p class="m05-note">Machine translated from '
            + source_language + ' to ' + target_language
            + '. Review before use; source layout is not preserved.</p>'
            + '<pre class="m05-translated">' + escape(translated, quote=True)
            + '</pre></section>'
        )
    html = (pdf_engine._STYLE + _PDF_STYLES + "".join(blocks)
            + pdf_engine._END).encode("utf-8")
    if len(html) > MAX_HTML_BYTES:
        raise ValueError("M05 translated HTML exceeds safety budget")
    return html


def _render_local_pdf(html: bytes) -> bytes:
    if not 32 <= len(html) <= MAX_HTML_BYTES:
        raise ValueError("M05 HTML outside safety budget")
    try:
        with httpx.Client(base_url=GOTENBERG_ORIGIN, timeout=120.0,
                          trust_env=False, follow_redirects=False) as client:
            with client.stream(
                "POST", "/forms/chromium/convert/html",
                files={"files": ("index.html", html, "text/html; charset=utf-8")},
                data={"preferCssPageSize": "true"},
                headers={"Accept": "application/pdf"},
            ) as response:
                if (response.status_code != 200
                        or "application/pdf" not in response.headers.get("content-type", "").lower()):
                    raise ValueError("Internal PDF renderer unavailable")
                buffer = bytearray()
                for chunk in response.iter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > MAX_RENDER_BYTES:
                        raise ValueError("Internal renderer PDF exceeds size budget")
    except httpx.HTTPError:
        # Do not leak raw error response, translated text or document contents.
        raise ValueError("Internal PDF renderer unavailable") from None
    return bytes(buffer)


def translate_pdf_document(
    source: Path, destination: Path, *, source_language: str,
    target_language: str, translator: Callable[[str, str, str], str] | None = None,
    renderer: Callable[[bytes], bytes] | None = None,
) -> None:
    """Build PDF output atomically after real translation and rendering."""
    translation.validate_languages(source_language, target_language)
    if (source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("PDF source and new output must be distinct")
    if (source.is_symlink() or not source.is_file()
            or not 24 <= source.stat().st_size <= translation.MAX_SOURCE_BYTES):
        raise ValueError("PDF source exceeds translation budget")
    before = sha256(source.read_bytes()).digest()
    pages = translation._extract(source)
    translate = translation._translate_local if translator is None else translator
    translated = []
    for text in pages:
        result = translate(text, source_language, target_language)
        if not isinstance(result, str) or not result.strip() or len(result) > 12000:
            raise ValueError("Internal translation model response invalid")
        translated.append(result)
    html = _html_document(translated, source_language, target_language)
    render = _render_local_pdf if renderer is None else renderer
    pdf = render(html)
    if not isinstance(pdf, bytes) or not 64 <= len(pdf) <= MAX_RENDER_BYTES or not pdf.startswith(b"%PDF-"):
        raise ValueError("Internal renderer returned invalid PDF")
    try:
        reader = PdfReader(BytesIO(pdf), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_RENDERED_PAGES:
            raise ValueError("M05 rendered PDF page count outside bounds")
    except ValueError:
        raise
    except Exception:
        raise ValueError("Internal renderer returned malformed PDF") from None
    with TemporaryDirectory(prefix="pdfhub-m05-document-", dir=destination.parent) as folder:
        staged = Path(folder) / "translated.pdf"
        # Shared T90 PDF gate also validates visible rendered ink with PDFium.
        pdf_engine._checked_pdf(pdf, staged)
        if sha256(source.read_bytes()).digest() != before:
            raise ValueError("PDF source changed during translation")
        if staged.read_bytes() != pdf:
            raise ValueError("M05 PDF staging failed")
        staged.replace(destination)
