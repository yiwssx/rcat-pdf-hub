"""Real HWP97 importer regression and strict versioned upload guard."""
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
from app.services.to_pdf_hwp3 import MAGIC, MIN_HWP_BYTES, validate_hwp3
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation


def _hwp3_bytes():
    data = bytearray(MIN_HWP_BYTES + 200)
    data[:30] = MAGIC
    return data


def _pdf():
    out = BytesIO()
    c = canvas.Canvas(out)
    c.drawString(100, 750, "Hangul HWP97")
    c.showPage()
    c.save()
    return out.getvalue()


def test_guarded_hwp3_owner_route_and_gotenberg_dispatch(monkeypatch, tmp_path):
    src = tmp_path / "hangul97.hwp"
    src.write_bytes(_hwp3_bytes())
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    validate_hwp3(src)
    with pytest.raises(HTTPException) as e:
        validate_uploaded_file(src, src.name)
    assert e.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    mime = "application/x-hwp"
    assert validate_uploaded_file(src, src.name) == mime
    assert any(route.path.endswith("/hwp") for route in to_pdf.router.routes)
    calls = []

    class Response:
        content = _pdf()
        def raise_for_status(self): pass

    class Client:
        def __init__(self, **kw):
            assert kw["timeout"] == 300.0 and kw["follow_redirects"] is False
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, *, files):
            assert url.endswith("/forms/libreoffice/convert")
            name, fh, ctype = files["files"]
            calls.append((name, fh.read(), ctype))
            return Response()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    output = tmp_path / "real.pdf"
    execute_staged_to_pdf_operation("hwp-to-pdf", [src], output, {},
                                    original_name=src.name, content_type=mime)
    assert len(PdfReader(str(output), strict=True).pages) == 1
    assert calls == [("document.hwp", src.read_bytes(), "application/octet-stream")]
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    with pytest.raises(ValueError, match="MIME"):
        checked_source("hwp-to-pdf", src, name=src.name, mime="application/msword")
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation("hwp-to-pdf", [src], src, {},
                                        original_name=src.name, content_type=mime)


@pytest.mark.parametrize("mutation", [
    lambda b: b.__setitem__(slice(0, 3), b"BAD"),
    lambda b: b.__setitem__(slice(19, 24), b"V5.00"),
    lambda b: struct.pack_into("<I", b, 30 + 24, 1),
    lambda b: struct.pack_into("<H", b, 30 + 96, 1),
])
def test_hwp3_rejects_spoofed_newer_protected_and_passworded(tmp_path, mutation):
    src = tmp_path / "bad.hwp"
    blob = _hwp3_bytes()
    mutation(blob)
    src.write_bytes(blob)
    with pytest.raises(ValueError):
        validate_hwp3(src)


def test_hwp3_rejects_short_file_and_worker_source_swap(monkeypatch, tmp_path):
    src = tmp_path / "empty.hwp"
    src.write_bytes(bytes(_hwp3_bytes())[:600])
    with pytest.raises(ValueError, match="size"):
        validate_hwp3(src)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    src.write_bytes(_hwp3_bytes())
    assert validate_uploaded_file(src, src.name) == "application/x-hwp"
    src.write_bytes(b"\xd0\xcf\x11\xe0" + bytes(1200))  # HWP 5 OLE
    with pytest.raises(ValueError, match="signature"):
        checked_source("hwp-to-pdf", src, name=src.name, mime="application/x-hwp")
