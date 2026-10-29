"""Security and real PDF binary regression for bounded DRM-free MOBI6.
Fixture is a self-contained synthetic PalmDB/BOOKMOBI produced with stdlib.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
import struct

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services.to_pdf_mobi import mobi_to_safe_html, _palmdoc_decompress
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation

THAI = "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"


def mobi_bytes(text: str, *, compression: int = 1, drm: int = 0,
               encoding: int = 65001, mobiversion: int = 6,
               header_length: int = 228, header_flags: int = 0) -> bytes:
    data = text.encode("utf-8")
    if compression == 2:
        # Real PalmDOC literal-run representation (1-8 bytes each).
        segment = b"".join(bytes((len(data[i:i + 8]),)) + data[i:i + 8]
                           for i in range(0, len(data), 8))
    else:
        segment = data
    assert len(segment) <= 4096
    pdb = bytearray(78)
    pdb[:12] = b"Thai book CI"
    pdb[0x3C:0x44] = b"BOOKMOBI"
    struct.pack_into(">H", pdb, 0x4C, 2)
    record0 = bytearray(16 + header_length)
    struct.pack_into(">H", record0, 0, compression)
    struct.pack_into(">I", record0, 4, len(data))
    struct.pack_into(">H", record0, 8, 1)
    struct.pack_into(">H", record0, 10, 4096)
    struct.pack_into(">H", record0, 12, drm)
    record0[16:20] = b"MOBI"
    struct.pack_into(">I", record0, 20, header_length)
    struct.pack_into(">I", record0, 24, 2)
    struct.pack_into(">I", record0, 28, encoding)
    struct.pack_into(">I", record0, 36, mobiversion)
    struct.pack_into(">I", record0, 16 + 0xE0, header_flags)
    table_end = 78 + 16 + 2
    table = (
        struct.pack(">I", table_end) + bytes(4)
        + struct.pack(">I", table_end + len(record0)) + bytes(4)
    )
    return bytes(pdb) + table + b"\x00\x00" + record0 + segment


def _pdf() -> bytes:
    buf = BytesIO()
    page = canvas.Canvas(buf)
    page.drawString(100, 710, "MOBI")
    page.showPage()
    page.save()
    return buf.getvalue()


@pytest.mark.parametrize("compression", [1, 2])
def test_mobi_real_safe_transcript_route_and_pdf_binary(monkeypatch, tmp_path, compression):
    source = tmp_path / "novel.mobi"
    source.write_bytes(mobi_bytes(f"<p>{THAI}</p><p>Thai ABC</p>", compression=compression))
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    html = mobi_to_safe_html(source)
    assert THAI in html and "<p>Thai ABC</p>" in html
    with pytest.raises(HTTPException) as flag_off:
        validate_uploaded_file(source, source.name)
    assert flag_off.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    mime = "application/x-mobipocket-ebook"
    assert validate_uploaded_file(source, source.name) == mime
    called = []
    def mock_converter(content, path):
        called.append(content)
        path.write_bytes(_pdf())
    monkeypatch.setattr("app.services.to_pdf_engine._html_to_pdf", mock_converter)
    target = tmp_path / "converted.pdf"
    execute_staged_to_pdf_operation("mobi-to-pdf", [source], target, {},
                                    original_name=source.name, content_type=mime)
    assert len(called) == 1 and THAI in called[0]
    assert len(PdfReader(BytesIO(target.read_bytes()), strict=True).pages) == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha
    with pytest.raises(ValueError, match="MIME"):
        checked_source("mobi-to-pdf", source, name=source.name, mime="text/plain")
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation("mobi-to-pdf", [source], source, {},
                                        original_name=source.name, content_type=mime)


@pytest.mark.parametrize("text", [
    "<script>alert(1)</script>",
    '<p onclick="fetch(\'https://evil.example\')">bad</p>',
    '<img src="https://evil.example/image.png">',
    "<style>@import url(https://evil.example/style)</style>",
    "<!--javascript--><p>test</p>",
    "abc\x00def",
    "\u202eABC",
])
def test_mobi_refuses_active_markup_and_untrusted_controls(tmp_path, text):
    source = tmp_path / "untrusted.mobi"
    source.write_bytes(mobi_bytes(text))
    with pytest.raises(ValueError):
        mobi_to_safe_html(source)


@pytest.mark.parametrize("mutate", [
    lambda b: b[:0x3C] + b"NOTMOBI" + b[0x44:],
    lambda b: b[:0x3C] + b"BAD!MOBI" + b[0x44:],
    lambda b: b[:-10],
    lambda b: bytes(bytearray(b[:0x4C]) + b"\x00\x00" + b[0x4E:]),
])
def test_mobi_rejects_invalid_container(tmp_path, mutate):
    source = tmp_path / "bad.mobi"
    source.write_bytes(mutate(mobi_bytes(THAI)))
    with pytest.raises(ValueError):
        mobi_to_safe_html(source)


@pytest.mark.parametrize("option,value", [
    ("compression", 17480), ("drm", 2), ("encoding", 1252),
    ("mobiversion", 8), ("header_flags", 1),
])
def test_mobi_rejects_drm_kf8_huff_unsupported_features(tmp_path, option, value):
    source = tmp_path / "unsupported.mobi"
    source.write_bytes(mobi_bytes(THAI, **{option: value}))
    with pytest.raises(ValueError):
        mobi_to_safe_html(source)


def test_mobi_bounded_backrefs_and_expansion():
    assert _palmdoc_decompress(b"\x03abc\x80\x18", 4096) == b"abcabc"
    with pytest.raises(ValueError, match="backreference"):
        _palmdoc_decompress(b"\x80", 4096)
    with pytest.raises(ValueError, match="backreference"):
        _palmdoc_decompress(b"\x80\x18", 4096)
    with pytest.raises(ValueError, match="expansion"):
        _palmdoc_decompress(b"\x03abc\x80\x1f", 4)
    with pytest.raises(ValueError, match="literal"):
        _palmdoc_decompress(b"\x08hi", 4096)


def test_mobi_forged_text_length_and_trailing_junk_rejected(tmp_path):
    good = mobi_bytes(THAI)
    source = tmp_path / "bad.mobi"
    record0_start = 78 + 16 + 2
    bad = bytearray(good)
    struct.pack_into(">I", bad, record0_start + 4, 10000)
    source.write_bytes(bad)
    with pytest.raises(ValueError, match="length mismatch"):
        mobi_to_safe_html(source)
    source.write_bytes(good + b"\x00" * 4096)
    with pytest.raises(ValueError, match="bounds"):
        mobi_to_safe_html(source)
