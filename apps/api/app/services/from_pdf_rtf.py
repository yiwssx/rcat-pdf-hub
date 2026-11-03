"""F14 strict text-only PDF -> editable Unicode RTF paragraphs.

This is NOT layout-preserving PDF -> RTF. Refuse diagrams, embedded images,
tables, rotated/multicolumn/ambiguous text and encrypted/scanned originals.
"""
from __future__ import annotations

import math
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_PAGES = 12
MAX_CHARS = 150_000
MAX_OUTPUT_BYTES = 3 * 1024 * 1024

GRAPHIC_OPERATORS = {
    b"Do", b"re", b"m", b"l", b"c", b"v", b"y", b"h",
    b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*",
    b"sh", b"BI", b"ID", b"EI",
}


def _extract_plain_lines(page, reader) -> list[str]:
    if int(page.get("/Rotate", 0)) % 360:
        raise ValueError("Rotated PDF text is not supported by the RTF subset")
    if page.get("/Resources", {}).get("/XObject"):
        raise ValueError("Embedded graphics unsupported for editable plain-text RTF")
    for operands, op in ContentStream(page.get_contents(), reader).operations:
        if op in GRAPHIC_OPERATORS:
            raise ValueError("Graphical PDF page is not plain text")
        if op == b"cm" and any(
            abs(float(v)-expected) > .001
            for v, expected in zip(operands, (1, 0, 0, 1, 0, 0))
        ):
            raise ValueError("Transformed PDF text is not supported")
    chunks: list[tuple[float, float, str]] = []

    def visitor(text, cm, tm, font_dict, font_size):
        value = text.strip("\r\n")
        if not value.strip():
            return
        if ("\n" in value or "\r" in value or "\x00" in value
                or any(ord(ch) < 32 and ch != "\t" for ch in value)
                or len(value) > 2_000):
            raise ValueError("Unsupported multiline/control PDF text")
        if any(abs(float(v)-expected) > .001
               for v, expected in zip(cm, (1, 0, 0, 1, 0, 0))):
            raise ValueError("Transformed text position unsupported")
        if any(abs(float(v)-expected) > .001
               for v, expected in zip(tm[:4], (1, 0, 0, 1))):
            raise ValueError("Rotated or stretched PDF text unsupported")
        x, y = float(tm[4]), float(tm[5])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Nonfinite PDF text position")
        chunks.append((x, y, value.rstrip()))

    page.extract_text(visitor_text=visitor)
    if not chunks:
        raise ValueError("No editable/selectable text in PDF page")
    initial_x = chunks[0][0]
    for i, (x, y, text) in enumerate(chunks):
        if abs(x-initial_x) > 8:
            raise ValueError("Multicolumn or indented text needs reviewed layout converter")
        if i and y >= chunks[i-1][1]-0.5:
            raise ValueError("Text line order is ambiguous in PDF")
    return [item[2] for item in chunks]


def _rtf_escape(text: str) -> str:
    output: list[str] = []
    for ch in text:
        if ch in "{}\\":
            output.append("\\"+ch)
        elif ch == "\t":
            output.append(r"\tab ")
        elif 32 <= ord(ch) <= 126:
            output.append(ch)
        else:
            units = ch.encode("utf-16-le")
            for pos in range(0, len(units), 2):
                unit = int.from_bytes(units[pos:pos+2], "little")
                if unit >= 32768:
                    unit -= 65536
                output.append(r"\u"+str(unit)+"?")
    return "".join(output)


def pdf_to_text_only_rtf(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("RTF source and destination must be separate")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Source PDF exceeds text-only RTF budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported for RTF")
    parts: list[str] = [
        r"{\rtf1\ansi\ansicpg1252\uc1\deff0",
        r"{\fonttbl{\f0\fnil Noto Sans Thai;}}",
        r"\viewkind4\f0\fs24",
    ]
    total_chars = 0
    for i, page in enumerate(pdf.pages):
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(width) or not math.isfinite(height)
                or not 1 <= width <= 4000 or not 1 <= height <= 4000):
            raise ValueError("Invalid text-only PDF page dimensions")
        lines = _extract_plain_lines(page, pdf)
        total_chars += sum(len(line) for line in lines)
        if total_chars > MAX_CHARS:
            raise ValueError("Too much extracted RTF text")
        if i:
            parts.append(r"\page")
        for line in lines:
            parts.append(_rtf_escape(line))
            parts.append(r"\par")
    parts.append("}")
    data = ("\n".join(parts)+"\n").encode("ascii")
    if not 32 <= len(data) <= MAX_OUTPUT_BYTES:
        raise ValueError("RTF output exceeds budget")
    with output.open("xb") as stream:
        stream.write(data)
