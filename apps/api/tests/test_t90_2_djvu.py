"""DjVuLibre native decoder regression: real PDF, IFF spoofing, resource policy."""
from __future__ import annotations

import hashlib
import struct
import subprocess
from io import BytesIO

import pytest
from fastapi import HTTPException
from pypdf import PdfReader

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.routers import to_pdf
from app.services.to_pdf_djvu import validate_single_page_djvu
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation

MIME = "image/vnd.djvu"


def make_real_djvu(path):
    """Generate an actual single-page bitonal document with Debian cjb2."""
    picture = path.parent / "source.pbm"
    # 64x64 with nonblank black/white bars. P4 contains raw packed bits.
    picture.write_bytes(b"P4\n64 64\n" + b"".join(
        bytes([0xFF] * 4 + [0x00] * 4) if index % 3 == 0
        else bytes([0x00] * 4 + [0xFF] * 4)
        for index in range(64)
    ))
    proc = subprocess.run(
        ["/usr/bin/cjb2", str(picture), str(path)],
        check=False, capture_output=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    assert path.read_bytes().startswith(b"AT&TFORM")
    return path


def test_real_single_page_djvu_to_pdf_and_source_immutability(monkeypatch, tmp_path):
    source = make_real_djvu(tmp_path / "image.djvu")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    chunks = validate_single_page_djvu(source)
    assert "INFO" in chunks
    assert any(x in chunks for x in ("Sjbz", "BG44", "FG44"))
    assert any(r.path.endswith("/djvu") for r in to_pdf.router.routes)
    with pytest.raises(HTTPException) as denied:
        validate_uploaded_file(source, source.name)
    assert denied.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(source, source.name) == MIME
    output = tmp_path / "document.pdf"
    execute_staged_to_pdf_operation(
        "djvu-to-pdf", [source], output, {},
        original_name=source.name, content_type=MIME,
    )
    result = output.read_bytes()
    assert result.startswith(b"%PDF-")
    pdf = PdfReader(BytesIO(result), strict=True)
    assert len(pdf.pages) == 1 and not pdf.is_encrypted
    assert float(pdf.pages[0].mediabox.width) > 0
    assert float(pdf.pages[0].mediabox.height) > 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation(
            "djvu-to-pdf", [source], source, {},
            original_name=source.name, content_type=MIME,
        )
    with pytest.raises(ValueError, match="MIME"):
        checked_source("djvu-to-pdf", source, name=source.name, mime="text/plain")


@pytest.mark.parametrize("payload", [
    b"%PDF-1.7\nspoof",
    b"AT&TFORM" + (30).to_bytes(4, "big") + b"DJVM" + b"\0" * 30,
    b"AT&TFORM" + (64).to_bytes(4, "big") + b"DJVU" + b"\0" * 20,
    b"AT&TFORM" + (4).to_bytes(4, "big") + b"DJVU" + b"\0" * 16,
    b"AT&TFORM" + (16).to_bytes(4, "big") + b"DJVU" + b"INCL" + (4).to_bytes(4, "big") + b"evil",
])
def test_rejects_spoofed_multifile_or_corrupt_iff(tmp_path, payload):
    src = tmp_path / "bad.djvu"
    src.write_bytes(payload)
    with pytest.raises(ValueError):
        validate_single_page_djvu(src)


def test_rejects_external_includes_and_oversized_declared_geometry(tmp_path):
    source = make_real_djvu(tmp_path / "original.djvu")
    blob = bytearray(source.read_bytes())
    info = blob.find(b"INFO")
    assert info >= 16
    # Update image geometry in the IFF INFO payload: width 65535.
    blob[info + 8:info + 10] = (65535).to_bytes(2, "big")
    wrong = tmp_path / "oversized.djvu"
    wrong.write_bytes(blob)
    with pytest.raises(ValueError, match="geometry"):
        validate_single_page_djvu(wrong)

    blob = bytearray(source.read_bytes())
    extra = b"INCL" + (4).to_bytes(4, "big") + b"evil"
    struct.pack_into(">I", blob, 8, struct.unpack_from(">I", blob, 8)[0] + len(extra))
    wrong.write_bytes(blob + extra)
    with pytest.raises(ValueError, match="external"):
        validate_single_page_djvu(wrong)


def test_corrupted_source_recheck_and_flag_off(monkeypatch, tmp_path):
    source = make_real_djvu(tmp_path / "upload.djvu")
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(source, source.name) == MIME
    source.write_bytes(b"not a DjVu")
    with pytest.raises(ValueError, match="signature"):
        checked_source("djvu-to-pdf", source, name=source.name, mime=MIME)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_to_pdf_operation(
            "djvu-to-pdf", [source], tmp_path / "bad.pdf", {},
            original_name=source.name, content_type=MIME,
        )
