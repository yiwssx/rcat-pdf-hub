"""M05 selectable-text PDF translation through a fixed private model endpoint.

This generates a page-marked UTF-8 transcript, not a translated-layout PDF.
No configurable public translation URL and no silent dummy translation fallback.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

import httpx
from pypdf import PdfReader

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_PAGES = 20
MAX_PAGE_CHARS = 3000
MAX_TOTAL_CHARS = 30000
MAX_PAGE_STREAM_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
TRANSLATOR_ORIGIN = "http://pdf-translate:5000"


def validate_languages(source_language: str, target_language: str) -> None:
    if (type(source_language) is not str or type(target_language) is not str
            or source_language not in {"en", "th"}
            or target_language not in {"en", "th"}
            or source_language == target_language):
        raise ValueError("M05 requires distinct en/th language pairs")


def _extract(source: Path) -> list[str]:
    if source.is_symlink() or not source.is_file():
        raise ValueError("PDF source must be a regular file")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF source exceeds translation budget")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("PDF signature invalid")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted PDF or unsupported page count")
    pages = []
    total = 0
    for page in reader.pages:
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > MAX_PAGE_STREAM_BYTES:
            raise ValueError("PDF page content over budget")
        raw = page.extract_text() or ""
        text = "\n".join(" ".join(line.split()) for line in raw.splitlines()
                         if line.strip()).strip()
        if not text:
            raise ValueError("No selectable text on PDF page; run OCR first")
        if any(ord(c) == 0 or (ord(c) < 32 and c != "\n") for c in text):
            raise ValueError("Extracted PDF text contains controls")
        if len(text) > MAX_PAGE_CHARS:
            raise ValueError("PDF page text exceeds translation budget")
        total += len(text)
        if total > MAX_TOTAL_CHARS:
            raise ValueError("PDF translation text exceeds overall budget")
        pages.append(text)
    return pages


def _translate_local(text: str, source_language: str, target_language: str) -> str:
    """Call a LibreTranslate-compatible service on the isolated Compose network."""
    try:
        with httpx.Client(base_url=TRANSLATOR_ORIGIN, timeout=15.0,
                          follow_redirects=False, trust_env=False) as client:
            with client.stream("POST", "/translate", json={
                "q": text, "source": source_language,
                "target": target_language, "format": "text",
            }, headers={"Accept": "application/json"}) as response:
                if response.status_code != 200:
                    raise ValueError("Internal translation model unavailable")
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload.extend(chunk)
                    if len(payload) > 64 * 1024:
                        raise ValueError("Internal translation response oversized")
        result = json.loads(payload)
    except (httpx.HTTPError, json.JSONDecodeError, UnicodeError):
        raise ValueError("Internal translation model unavailable") from None
    if not isinstance(result, dict):
        raise ValueError("Internal translation response invalid")
    answer = result.get("translatedText")
    if (not isinstance(answer, str) or not answer.strip() or len(answer) > 12000
            or any(ord(ch) == 0 or (ord(ch) < 32 and ch not in "\n\t")
                   for ch in answer)):
        raise ValueError("Internal translation response invalid")
    return answer.strip()


def translate_pdf_text(
    source: Path, destination: Path, *, source_language: str,
    target_language: str, translator: Callable[[str, str, str], str] | None = None,
) -> None:
    """Commit the output only after all pages are translated successfully."""
    validate_languages(source_language, target_language)
    if (source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("Source and new output must be distinct")
    if source.is_symlink() or not source.is_file() or not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF source exceeds translation budget")
    original_hash = sha256(source.read_bytes()).digest()
    pages = _extract(source)
    translate = _translate_local if translator is None else translator
    rendered = []
    for i, original in enumerate(pages, 1):
        translated = translate(original, source_language, target_language)
        if not isinstance(translated, str) or not translated.strip() or len(translated) > 12000:
            raise ValueError("Internal translation response invalid")
        rendered.append("[Page " + str(i) + "]\n" + translated.strip() + "\n")
    output = (
        "M05 PDF TEXT TRANSLATION / แปลข้อความจาก PDF\n"
        "From: " + source_language + " | To: " + target_language + "\n"
        "Machine translation, proofread before use. Text only; no original PDF layout.\n"
        "Not a certified translation; images and scanned pages are not translated.\n\n"
        + "\n".join(rendered)
    ).encode("utf-8")
    if not 40 <= len(output) <= MAX_OUTPUT_BYTES:
        raise ValueError("Translated output exceeds budget")
    with TemporaryDirectory(prefix="pdfhub-m05-", dir=destination.parent) as folder:
        temporary = Path(folder) / "translated.txt"
        temporary.write_bytes(output)
        if sha256(source.read_bytes()).digest() != original_hash:
            raise ValueError("Original PDF changed during translation")
        if temporary.read_bytes() != output:
            raise ValueError("Translation staging failed")
        temporary.replace(destination)
