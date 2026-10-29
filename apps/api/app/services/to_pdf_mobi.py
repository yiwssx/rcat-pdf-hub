"""Strictly bounded, DRM-free MOBI6 PalmDOC UTF-8 text transcription.

This is intentionally NOT a general Kindle/Kindle8/MOBI ebook decoder:
no DRM, HUFF/CDIC, embedded images, HTML/CSS/link/layout parity or native code.
Consumes only classic BOOKMOBI PalmDB records, with a small audited PalmDOC
decompressor and explicit limits. Generates safe HTML using escaped plain text.
"""
from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import struct

MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TEXT_BYTES = 192 * 1024
MAX_RECORDS = 64
MAX_PDB_RECORDS = 80
MAX_NODE_COUNT = 5000
RECORD_MAX = 4096
ALLOWED_TAGS = frozenset({"html", "body", "p", "br", "div", "h1", "h2", "h3", "b", "i", "em", "strong"})


def _u16(data: bytes, offset: int) -> int:
    if offset + 2 > len(data):
        raise ValueError("Truncated Mobipocket header")
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ValueError("Truncated Mobipocket header")
    return struct.unpack_from(">I", data, offset)[0]


def _palmdoc_decompress(payload: bytes, limit: int) -> bytes:
    """PalmDOC LZ77: capped incremental expansion, finite backrefs, no native codec."""
    result = bytearray()
    pos = 0
    while pos < len(payload):
        code = payload[pos]
        pos += 1
        if 1 <= code <= 8:
            if pos + code > len(payload):
                raise ValueError("Truncated PalmDOC literal run")
            result.extend(payload[pos:pos + code])
            pos += code
        elif code < 128:
            result.append(code)
        elif code < 192:
            if pos == len(payload):
                raise ValueError("Truncated PalmDOC backreference")
            next_byte = payload[pos]
            pos += 1
            distance = ((code & 0x3F) << 5) | (next_byte >> 3)
            length = (next_byte & 7) + 3
            if distance == 0 or distance > len(result):
                raise ValueError("Invalid PalmDOC backreference")
            for _ in range(length):
                result.append(result[-distance])
                if len(result) > limit:
                    raise ValueError("PalmDOC expansion exceeds 4096-byte record cap")
        else:
            result.extend((32, code ^ 0x80))
        if len(result) > limit:
            raise ValueError("PalmDOC expansion exceeds 4096-byte record cap")
    return bytes(result)


class _PlainMobipocket(HTMLParser):
    """Accept a minimal unstyled text subset; reject active and resource markup."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.count = 0

    def _node(self):
        self.count += 1
        if self.count > MAX_NODE_COUNT:
            raise ValueError("MOBI HTML structure exceeds node limit")

    def handle_starttag(self, tag, attrs):
        self._node()
        if tag not in ALLOWED_TAGS or attrs:
            raise ValueError("MOBI HTML rich markup, attributes or resources unsupported")
        if tag in {"p", "div", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self._node()
        if tag not in ALLOWED_TAGS:
            raise ValueError("MOBI closing unsupported HTML element")
        if tag in {"p", "div", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self._node()
        self.parts.append(data)

    def handle_entityref(self, name):
        raise ValueError("Unprocessed HTML entity in MOBI")

    def handle_charref(self, name):
        raise ValueError("Unprocessed HTML character reference in MOBI")

    def handle_comment(self, data):
        raise ValueError("MOBI HTML comments unsupported")

    def handle_decl(self, decl):
        raise ValueError("MOBI HTML declarations unsupported")

    def handle_pi(self, data):
        raise ValueError("MOBI processing instructions unsupported")


def mobi_to_safe_html(source: Path) -> str:
    if not 0 < source.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError("MOBI exceeds bounded file size")
    blob = source.read_bytes()
    if len(blob) < 90 or blob[0x3C:0x44] != b"BOOKMOBI":
        raise ValueError("Not a supported BOOKMOBI Palm database")
    count = _u16(blob, 0x4C)
    if not 2 <= count <= MAX_PDB_RECORDS:
        raise ValueError("MOBI record count exceeds supported bounds")
    table_end = 78 + count * 8
    if table_end + 2 > len(blob):
        raise ValueError("Truncated Mobipocket record table")
    offsets = [_u32(blob, 78 + index * 8) for index in range(count)]
    if offsets[0] < table_end + 2 or offsets[-1] >= len(blob):
        raise ValueError("Mobipocket record offsets outside file")
    if any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("Non-monotonic MOBI record offsets")
    sections = [blob[offsets[i]:offsets[i + 1] if i + 1 < count else len(blob)]
                for i in range(count)]
    header = sections[0]
    if len(header) < 16 + 228 or header[16:20] != b"MOBI":
        raise ValueError("Unsupported or truncated MOBI header")
    compression = _u16(header, 0)
    total_length = _u32(header, 4)
    text_records = _u16(header, 8)
    record_size = _u16(header, 10)
    encryption = _u16(header, 12)
    mobi_header_length = _u32(header, 20)
    mobi_type = _u32(header, 24)
    encoding = _u32(header, 28)
    mobi_version = _u32(header, 36)
    if (compression not in (1, 2) or encryption != 0
            or mobi_type != 2 or encoding != 65001
            or mobi_version not in (4, 5, 6)
            or mobi_header_length not in (228, 232)
            or 16 + mobi_header_length > len(header)):
        raise ValueError("Only DRM-free, classic UTF-8 MOBI4-6 is supported")
    if (not 1 <= text_records <= MAX_RECORDS
            or count != text_records + 1
            or not 0 < total_length <= MAX_TEXT_BYTES
            or record_size != RECORD_MAX):
        raise ValueError("MOBI text size or record count exceeds bounds")
    drm_offset = _u32(header, 16 + 0xA8)
    drm_count = _u32(header, 16 + 0xAC)
    drm_size = _u32(header, 16 + 0xB0)
    drm_flags = _u32(header, 16 + 0xB4)
    if (drm_offset not in (0, 0xFFFFFFFF)
            or drm_count not in (0, 0xFFFFFFFF)
            or drm_size or drm_flags):
        raise ValueError("MOBI DRM metadata is unsupported")
    # Reject EXTH and trailer extensions: this subset has no hidden assets.
    if _u32(header, 16 + 0x80) != 0 or _u32(header, 16 + 0xE0) != 0:
        raise ValueError("MOBI trailing record flags or unsupported layout")
    chunks = []
    produced = 0
    for segment in sections[1:text_records + 1]:
        if not 0 < len(segment) <= RECORD_MAX:
            raise ValueError("MOBI text block outside record bounds")
        part = (segment if compression == 1
                else _palmdoc_decompress(segment, RECORD_MAX))
        if not part:
            raise ValueError("Empty MOBI text block")
        produced += len(part)
        if produced > MAX_TEXT_BYTES:
            raise ValueError("MOBI decompressed length outside bounds")
        chunks.append(part)
    content = b"".join(chunks)
    if len(content) != total_length:
        raise ValueError("MOBI declared text length mismatch")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Only valid UTF-8 MOBI text is supported") from exc
    if (not text.strip() or any(
        ord(c) < 32 and c not in "\t\r\n" or c in "\u202a\u202b\u202c\u202d\u202e"
        for c in text
    )):
        raise ValueError("MOBI contains control or bidi override characters")
    reader = _PlainMobipocket()
    reader.feed(text)
    reader.close()
    plain = "".join(reader.parts)
    lines = [line.strip() for line in plain.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 1000:
        raise ValueError("MOBI paragraph count is outside bounds")
    title_bytes = blob[:32].split(b"\x00", 1)[0]
    title = title_bytes.decode("ascii", errors="replace").strip()
    body = "".join("<p>" + escape(line) + "</p>" for line in lines)
    if len(body) > MAX_TEXT_BYTES * 6:
        raise ValueError("MOBI transcript exceeds HTML size cap")
    return ("<h1>" + escape(title) + "</h1>" if title else "") + body


def restricted_mobi_to_pdf(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("MOBI source and destination must differ")
    html = mobi_to_safe_html(source)
    from app.services.to_pdf_engine import _html_to_pdf
    _html_to_pdf(html, output)
