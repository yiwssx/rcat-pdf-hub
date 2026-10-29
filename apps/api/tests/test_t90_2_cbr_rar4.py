"""Real RAR4 stored CBR binary with independent standard RAR header format.

The test fixture can be parsed by Python's external rarfile package; runtime
does not need rarfile nor a native/unrar tool. Only stored images are accepted.
"""
from io import BytesIO
import struct
import zlib

import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.routers import to_pdf
from app.services.to_pdf_cbr import read_stored_rar4_images
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation


def _block(kind, flags, tail=b""):
    head = struct.pack("<BHH", kind, flags, 7 + len(tail)) + tail
    return struct.pack("<H", zlib.crc32(head) & 0xFFFF) + head


def _image(color):
    frame = Image.new("RGB", (80, 40), color)
    out = BytesIO()
    try:
        frame.save(out, format="PNG")
        return out.getvalue()
    finally:
        frame.close()


def rar4_archive(entries, *, method=0x30, flags=0x8000):
    data = bytearray(b"Rar!\x1a\x07\x00")
    data += _block(0x73, 0, b"\x00" * 6)
    for name, payload in entries:
        encoded = name.encode("utf-8")
        extra = struct.pack(
            "<IIBIIBBHI", len(payload), len(payload), 2,
            zlib.crc32(payload), 0, 20, method, len(encoded), 0x20,
        ) + encoded
        data += _block(0x74, flags, extra) + payload
    data += _block(0x7B, 0)
    return bytes(data)


def test_real_stored_rar4_cbr_to_pdf(monkeypatch, tmp_path):
    src = tmp_path / "album.cbr"
    img1, img2 = _image("red"), _image("blue")
    src.write_bytes(rar4_archive([("page10.png", img2), ("page2.png", img1)]))
    original = src.read_bytes()
    assert read_stored_rar4_images(src) == [
        ("page10.png", img2), ("page2.png", img1)
    ]
    with pytest.raises(HTTPException) as disabled:
        validate_uploaded_file(src, src.name)
    assert disabled.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    mime = "application/vnd.comicbook-rar"
    assert validate_uploaded_file(src, src.name) == mime
    assert any(route.path.endswith("/cbr") for route in to_pdf.router.routes)
    out = tmp_path / "album.pdf"
    execute_staged_to_pdf_operation(
        "cbr-to-pdf", [src], out, {},
        original_name=src.name, content_type=mime,
    )
    assert len(PdfReader(str(out), strict=True).pages) == 2
    assert src.read_bytes() == original
    with pytest.raises(ValueError, match="MIME"):
        checked_source("cbr-to-pdf", src, name=src.name, mime="application/zip")
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation(
            "cbr-to-pdf", [src], src, {},
            original_name=src.name, content_type=mime,
        )


@pytest.mark.parametrize("payload", [
    b"Rar!\x1a\x07\x01" + b"\x00" * 80,  # RAR5 signature
    b"%PDF-1.7\n" + b"0" * 100,
    b"Rar!\x1a\x07\x00" + b"\0" * 70,
])
def test_rejects_spoofed_rar_and_bad_crc(tmp_path, payload):
    src = tmp_path / "invalid.cbr"
    src.write_bytes(payload)
    with pytest.raises(ValueError):
        read_stored_rar4_images(src)


@pytest.mark.parametrize("name", [
    "../escape.png", "/etc/passwd.png", "evil\\path.png",
    "outside:page.png", "not_image.exe", "..png", "UPPER.png",
])
def test_rejects_traversal_or_non_image(tmp_path, name):
    src = tmp_path / "unsafe.cbr"
    payload = _image("green")
    if name == "UPPER.png":
        data = rar4_archive([("upper.png", payload), (name, payload)])
        error = "unique"
    else:
        data = rar4_archive([(name, payload)])
        error = "image"
    src.write_bytes(data)
    with pytest.raises(ValueError, match=error):
        read_stored_rar4_images(src)


def test_rejects_compression_encryption_source_tamper_and_missing_end(tmp_path):
    img = _image("purple")
    src = tmp_path / "bad.cbr"
    for blob in (
        rar4_archive([("one.png", img)], method=0x33),
        rar4_archive([("one.png", img)], flags=0x8004),
        rar4_archive([("one.png", img)])[:-7],
    ):
        src.write_bytes(blob)
        with pytest.raises(ValueError):
            read_stored_rar4_images(src)
    data = bytearray(rar4_archive([("one.png", img)]))
    data[-8] ^= 0x21  # modify file data or end header checksum
    src.write_bytes(data)
    with pytest.raises(ValueError):
        read_stored_rar4_images(src)
