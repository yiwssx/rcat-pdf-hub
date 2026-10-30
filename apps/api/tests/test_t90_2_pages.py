"""T90-2 Apple Pages 4/5: bounded package, owner-scoped route, worker output."""
import hashlib
from io import BytesIO
import zipfile

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.routers import to_pdf
from app.services import to_pdf_engine
from app.services.to_pdf_pages import validate_pages_package
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation


def pages_bytes(version="4", *, preview_only=False, extra=None):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as arc:
        arc.writestr("Assets/test-data.bin", b"".join(hashlib.sha256(str(i).encode()).digest() for i in range(72)))
        arc.writestr("QuickLook/Preview.pdf", b"%PDF- fake preview; not evidence of real Pages content")
        if not preview_only:
            if version == "4":
                arc.writestr("index.xml", b'<?xml version="1.0"?><document><text>RCAT</text></document>')
            elif version == "5":
                arc.writestr("Index/Document.iwa", b"\x12\x10\x01\x00real-iwa-payload")
        if extra:
            arc.writestr(*extra)
    return buffer.getvalue()


def pdf_bytes():
    b = BytesIO()
    c = canvas.Canvas(b)
    c.drawString(60, 720, "RCAT Pages document")
    c.showPage()
    c.save()
    return b.getvalue()


@pytest.mark.parametrize("version", ["4", "5"])
def test_pages_actual_doc_index_and_conversion_dispatch(monkeypatch, tmp_path, version):
    source = tmp_path / "document.pages"
    source.write_bytes(pages_bytes(version))
    assert validate_pages_package(source) == "Pages" + version
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(HTTPException) as disabled:
        validate_uploaded_file(source, source.name)
    assert disabled.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    mime = "application/vnd.apple.pages"
    assert validate_uploaded_file(source, source.name) == mime
    assert any(route.path.endswith("/pages") for route in to_pdf.router.routes)
    sent = []

    class Response:
        content = pdf_bytes()
        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"] == 300.0
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def post(self, url, *, files):
            assert url.endswith("/forms/libreoffice/convert")
            filename, reader, ctype = files["files"]
            sent.append((filename, reader.read(), ctype))
            return Response()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    dest = tmp_path / "converted.pdf"
    execute_staged_to_pdf_operation("pages-to-pdf", [source], dest, {},
                                    original_name=source.name, content_type=mime)
    assert len(PdfReader(str(dest), strict=True).pages) == 1
    assert sent == [("document.pages", source.read_bytes(), "application/octet-stream")]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation("pages-to-pdf", [source], source, {},
                                        original_name=source.name, content_type=mime)
    with pytest.raises(ValueError, match="MIME"):
        checked_source("pages-to-pdf", source, name=source.name, mime="application/zip")


def test_pages_preview_alone_cannot_impersonate_document(tmp_path):
    source = tmp_path / "fake.pages"
    source.write_bytes(pages_bytes(preview_only=True))
    with pytest.raises(ValueError, match="index"):
        validate_pages_package(source)


@pytest.mark.parametrize("extra", [
    ("../escape", b"x"),
    ("/absolute", b"x"),
    ("bad\\windows", b"x"),
])
def test_pages_rejects_unsafe_container_entries(tmp_path, extra):
    source = tmp_path / "evil.pages"
    source.write_bytes(pages_bytes(extra=extra))
    with pytest.raises(ValueError):
        validate_pages_package(source)


def test_pages_corrupt_zip_and_duplicate_indexes_rejected(tmp_path):
    source = tmp_path / "invalid.pages"
    for bad in (b"NOT ZIP", b"PK\x03\x04" + b"\x00" * 2048):
        source.write_bytes(bad)
        with pytest.raises(ValueError):
            validate_pages_package(source)
    source.write_bytes(pages_bytes("4", extra=("Index/Document.iwa", b"\x01\x02")))
    with pytest.raises(ValueError, match="ambiguous"):
        validate_pages_package(source)


def test_pages_worker_rejects_source_swap(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "source.pages"
    source.write_bytes(pages_bytes("5"))
    assert validate_uploaded_file(source, source.name) == "application/vnd.apple.pages"
    source.write_bytes(b"%PDF-1.7\nspoof")
    with pytest.raises(ValueError, match="signature"):
        checked_source("pages-to-pdf", source, name=source.name, mime="application/vnd.apple.pages")
