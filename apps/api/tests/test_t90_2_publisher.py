"""T90-2 Publisher safe preflight, static owner route and worker dispatch.

A synthetic valid CFB confirms structural guards; the GitHub CI converter job
separately downloads a pinned *real* LibreOffice/Writerperfect .pub binary and
validates the actual import and nonblank two-page PDF rendering.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import struct

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.routers import to_pdf
from app.services import to_pdf_engine
from app.services.to_pdf_publisher import validate_publisher_ole
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation


def _cfb_directory(name, entry_type):
    block = bytearray(128)
    encoded = name.encode("utf-16-le") + b"\x00\x00"
    block[:len(encoded)] = encoded
    struct.pack_into("<H", block, 64, len(encoded))
    block[66] = entry_type
    return block


def _small_structural_cfb():
    # Header, one FAT sector, one directory sector, one regular stream sector.
    # This is intentionally NOT a real Microsoft Publisher document: only
    # upstream LibreOffice .pub binary supplies evidence of actual fidelity.
    header = bytearray(512)
    header[:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<H", header, 26, 3)
    struct.pack_into("<H", header, 28, 0xFFFE)
    struct.pack_into("<H", header, 30, 9)
    struct.pack_into("<H", header, 32, 6)
    struct.pack_into("<I", header, 44, 1)
    struct.pack_into("<I", header, 48, 1)
    struct.pack_into("<I", header, 56, 4096)
    struct.pack_into("<I", header, 60, 0xFFFFFFFE)
    struct.pack_into("<I", header, 68, 0xFFFFFFFE)
    struct.pack_into("<I", header, 76, 0)
    for i in range(1, 109):
        struct.pack_into("<I", header, 76 + 4 * i, 0xFFFFFFFF)
    fat = bytearray(b"\xff" * 512)
    for index, value in enumerate((0xFFFFFFFD, 0xFFFFFFFE, 0xFFFFFFFE)):
        struct.pack_into("<I", fat, index * 4, value)
    directory = (bytes(_cfb_directory("Root Entry", 5))
                 + bytes(_cfb_directory("Contents", 2))
                 + bytes(256))
    return bytes(header) + bytes(fat) + directory + bytes(512)


def _pdf():
    out = BytesIO()
    c = canvas.Canvas(out)
    c.drawString(70, 700, "Publisher test output")
    c.showPage()
    c.save()
    return out.getvalue()


def test_publisher_static_route_and_staged_job_flow(monkeypatch, tmp_path):
    source = tmp_path / "newsletter.pub"
    source.write_bytes(_small_structural_cfb())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert validate_publisher_ole(source) == ("Root Entry", "Contents")
    with pytest.raises(HTTPException) as error:
        validate_uploaded_file(source, source.name)
    assert error.value.status_code == 415

    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    mime = "application/x-mspublisher"
    assert validate_uploaded_file(source, source.name) == mime
    calls = []

    class Response:
        content = _pdf()

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, **kw):
            assert kw["follow_redirects"] is False
            assert kw["timeout"] == 300.0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, files):
            assert url.endswith("/forms/libreoffice/convert")
            filename, fh, content_type = files["files"]
            calls.append((filename, fh.read(), content_type))
            return Response()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    result = tmp_path / "generated.pdf"
    execute_staged_to_pdf_operation(
        "pub-to-pdf", [source], result, {},
        original_name=source.name, content_type=mime,
    )
    assert len(PdfReader(str(result), strict=True).pages) == 1
    assert calls == [("document.pub", source.read_bytes(), "application/octet-stream")]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert any(route.path.endswith("/pub") for route in to_pdf.router.routes)
    with pytest.raises(ValueError, match="MIME"):
        checked_source("pub-to-pdf", source, name=source.name, mime="application/msword")
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation(
            "pub-to-pdf", [source], source, {},
            original_name=source.name, content_type=mime,
        )


@pytest.mark.parametrize("which,offset,value", [
    ("bad magic", 0, 0),
    ("bad version", 26, 4),
    ("wrong byte order", 28, 0),
    ("wrong sector shift", 30, 12),
    ("wrong FAT count", 44, 0),
    ("directory out of bounds", 48, 90),
    ("nonzero DIFAT chain", 72, 1),
    ("FAT overlap", 76, 1),
])
def test_publisher_rejects_malformed_cfb_header(tmp_path, which, offset, value):
    bad = bytearray(_small_structural_cfb())
    if offset == 0:
        bad[0] = value
    elif offset in (26, 28, 30):
        struct.pack_into("<H", bad, offset, value)
    else:
        struct.pack_into("<I", bad, offset, value)
    source = tmp_path / "malformed.pub"
    source.write_bytes(bad)
    with pytest.raises(ValueError):
        validate_publisher_ole(source)


def test_publisher_rejects_fat_loops_missing_root_and_junk(tmp_path):
    correct = _small_structural_cfb()
    source = tmp_path / "publisher.pub"
    for size in (1, 700):
        source.write_bytes(correct[:size])
        with pytest.raises(ValueError):
            validate_publisher_ole(source)

    bad = bytearray(correct)
    struct.pack_into("<I", bad, 512 + 4, 1)  # directory chain points at itself
    source.write_bytes(bad)
    with pytest.raises(ValueError, match="directory chain"):
        validate_publisher_ole(source)

    bad = bytearray(correct)
    bad[512 + 512 + 66] = 2  # no Root Entry
    source.write_bytes(bad)
    with pytest.raises(ValueError, match="root storage"):
        validate_publisher_ole(source)

    bad = bytearray(correct)
    bad[512 + 512 + 128 + 66] = 0  # no regular stream
    source.write_bytes(bad)
    with pytest.raises(ValueError, match="document streams"):
        validate_publisher_ole(source)

    source.write_bytes(correct + b"garbage")
    with pytest.raises(ValueError, match="sector alignment"):
        validate_publisher_ole(source)


def test_publisher_fails_closed_after_source_tampering(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "publisher.pub"
    source.write_bytes(_small_structural_cfb())
    assert validate_uploaded_file(source, source.name) == "application/x-mspublisher"
    source.write_bytes(b"%PDF-1.7\nspoofed")
    with pytest.raises(ValueError, match="signature"):
        checked_source("pub-to-pdf", source, name=source.name,
                       mime="application/x-mspublisher")
