"""F15: bounded, genuine DRM-free classic MOBI6 from selectable PDF text.

A deliberately narrow no-dependency writer, sharing F05's reviewed PDF
text extraction and T19's strict real PalmDB/MOBI parser for round-trip proof.
Not KF8, full Kindle publishing, scanned/graphical PDF, original layout or DRM.
"""
from __future__ import annotations

from html import escape
import math
from pathlib import Path
import struct
from pypdf import PdfReader

from app.services.from_pdf_rtf import (
    _extract_plain_lines, MAX_SOURCE_BYTES, MAX_PAGES, MAX_CHARS,
)
from app.services.to_pdf_mobi import (
    MAX_TEXT_BYTES, MAX_RECORDS, RECORD_MAX, mobi_to_safe_html,
)

MAX_OUTPUT_BYTES = 256 * 1024
MAX_PARAGRAPHS = 500


def _mobi6_bytes(lines: list[str]) -> bytes:
    """Emit a PalmDB BOOKMOBI with uncompressed, UTF-8 MOBI6 text records."""
    if not lines or len(lines) > MAX_PARAGRAPHS:
        raise ValueError("MOBI needs one to 500 nonempty paragraphs")
    markup = "".join("<p>" + escape(line, quote=False) + "</p>" for line in lines)
    body = markup.encode("utf-8")
    if not 0 < len(body) <= MAX_TEXT_BYTES:
        raise ValueError("MOBI text exceeds the supported budget")
    records = [body[i:i + RECORD_MAX] for i in range(0, len(body), RECORD_MAX)]
    if not 1 <= len(records) <= MAX_RECORDS:
        raise ValueError("MOBI text record count exceeds the budget")

    # Palm Database header: name, BOOK/MOBI creator and ordered 8-byte records.
    pdb = bytearray(78)
    pdb[:13] = b"RCAT PDF TEXT"
    pdb[0x3C:0x44] = b"BOOKMOBI"
    struct.pack_into(">H", pdb, 0x4C, len(records) + 1)

    # Real PalmDOC record-zero + standard 228-byte MOBI header.
    record0 = bytearray(16 + 228)
    struct.pack_into(">H", record0, 0, 1)  # Uncompressed PalmDOC
    struct.pack_into(">I", record0, 4, len(body))
    struct.pack_into(">H", record0, 8, len(records))
    struct.pack_into(">H", record0, 10, RECORD_MAX)
    struct.pack_into(">H", record0, 12, 0)  # No encryption
    record0[16:20] = b"MOBI"
    struct.pack_into(">I", record0, 20, 228)
    struct.pack_into(">I", record0, 24, 2)  # Mobipocket book
    struct.pack_into(">I", record0, 28, 65001)  # UTF-8
    struct.pack_into(">I", record0, 36, 6)  # Classic MOBI6
    # EXTH/DRM/trailing-record flags remain zero: no hidden assets or DRM.

    offset = 78 + (len(records) + 1) * 8 + 2
    table = bytearray()
    for record in [bytes(record0), *records]:
        table.extend(struct.pack(">I", offset))
        table.extend(b"\x00" * 4)
        offset += len(record)
    blob = bytes(pdb) + bytes(table) + b"\x00\x00" + bytes(record0) + b"".join(records)
    if not 256 <= len(blob) <= MAX_OUTPUT_BYTES:
        raise ValueError("MOBI output exceeds the allowed size")
    return blob


def pdf_to_legacy_mobi(source: Path, output: Path) -> None:
    """Reject complex PDFs; write a real MOBI output, no external converters."""
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("MOBI input/output must be distinct regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF source exceeds MOBI budget")

    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("MOBI does not support encrypted or oversized PDFs")
    lines: list[str] = []
    total_chars = 0
    for page in pdf.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(width) or not math.isfinite(height)
                or not 1 <= width <= 4000 or not 1 <= height <= 4000):
            raise ValueError("Unsupported PDF page geometry")
        page_lines = _extract_plain_lines(page, pdf)
        if not page_lines:
            raise ValueError("Empty PDF page is unsupported for reflowable MOBI")
        total_chars += sum(len(line) for line in page_lines)
        if total_chars > MAX_CHARS:
            raise ValueError("PDF text exceeds conversion budget")
        lines.extend(page_lines)
        if len(lines) > MAX_PARAGRAPHS:
            raise ValueError("Too many paragraphs for classic MOBI")
    blob = _mobi6_bytes(lines)

    # Exclusive output, parser-validated before use by the shared job/artifact
    # contract. Failure never leaves a truncated downloadable MOBI behind.
    try:
        with output.open("xb") as target:
            target.write(blob)
        checked_html = mobi_to_safe_html(output)
        if any(escape(line, quote=False) not in checked_html for line in lines):
            raise ValueError("MOBI round-trip lost source text")
    except Exception:
        output.unlink(missing_ok=True)
        raise
