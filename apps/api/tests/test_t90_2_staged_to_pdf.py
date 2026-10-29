"""T90-2: live binary frame acceptance, HTML escaping and opt-in authorization.

These tests do not claim Gotenberg Thai golden visual acceptance or T90 release.
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import filetypes, queue, security
from app.config import get_settings
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app as production_app
from app.models import FileRecord
from app.routers import pdf as legacy_pdf, to_pdf
from app.services import to_pdf_engine
from app.staged_to_pdf_adapters import (
    STAGED_TO_PDF_INPUTS, checked_source, execute_staged_to_pdf_operation,
)


def _pdf_bytes() -> bytes:
    stream = BytesIO()
    doc = canvas.Canvas(stream)
    doc.drawString(30, 750, "RCAT T90-2")
    doc.showPage()
    doc.save()
    return stream.getvalue()


def _frames(path: Path, fmt: str, count: int) -> None:
    images = [Image.new("RGB", (160, 100), (i * 40, 40, 60)) for i in range(count)]
    try:
        if fmt in ("GIF", "TIFF"):
            images[0].save(path, format=fmt, save_all=True,
                           append_images=images[1:], duration=100)
        else:
            images[0].save(path, format=fmt)
    finally:
        for img in images:
            img.close()


def test_default_off_routes_and_queue(monkeypatch):
    assert get_settings().to_pdf_tools_enabled is False
    assert not any("/api/v1/pdf/to-pdf/" in route.path for route in production_app.routes)
    for operation in STAGED_TO_PDF_INPUTS:
        with pytest.raises(ValueError, match="Unsupported"):
            queue.queue_class_for_operation(operation)
    monkeypatch.setattr(queue.settings, "to_pdf_tools_enabled", True)
    for operation in STAGED_TO_PDF_INPUTS:
        assert queue.queue_class_for_operation(operation) == "heavy"
    with pytest.raises(ValueError, match="Unsupported"):
        queue.queue_class_for_operation("script-to-pdf")


@pytest.mark.parametrize("suffix,mime", [
    (".txt", "text/plain"), (".csv", "text/csv"), (".md", "text/markdown"),
    (".gif", "image/gif"), (".jfif", "image/jpeg"),
])
def test_new_upload_signatures_flagged_and_fail_closed(monkeypatch, tmp_path, suffix, mime):
    path = tmp_path / ("sample" + suffix)
    if suffix in (".txt", ".csv", ".md"):
        path.write_text("สวัสดี,RCAT\n", encoding="utf-8")
    elif suffix == ".gif":
        _frames(path, "GIF", 2)
    else:
        _frames(path, "JPEG", 1)
    with pytest.raises(Exception):
        filetypes.validate_uploaded_file(path, path.name)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert filetypes.validate_uploaded_file(path, path.name) == mime
    original = path.read_bytes()
    # Arbitrary UTF-8 text is valid TXT; use invalid UTF-8 to test rejection.
    invalid = b"\xff\xfeinvalid" if suffix in (".txt", ".csv", ".md") else b"not a valid " + suffix.encode()
    path.write_bytes(invalid)
    with pytest.raises(Exception):
        filetypes.validate_uploaded_file(path, path.name)
    path.write_bytes(original)


@pytest.mark.parametrize("kind,ext,fmt,n", [
    ("jfif", ".jfif", "JPEG", 1),
    ("gif", ".gif", "GIF", 3),
    ("tiff", ".tiff", "TIFF", 3),
])
def test_real_image_frames_pdf_page_count_and_original_immutable(
    monkeypatch, tmp_path, kind, ext, fmt, n
):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / ("source" + ext)
    _frames(source, fmt, n)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    out = tmp_path / "output.pdf"
    op = kind + "-to-pdf"
    mime = STAGED_TO_PDF_INPUTS[op][0]
    execute_staged_to_pdf_operation(op, [source], out, {},
                                    original_name=source.name, content_type=mime)
    reader = PdfReader(str(out), strict=True)
    assert len(reader.pages) == n
    assert all(round(float(page.mediabox.width)) == 595 for page in reader.pages)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    with pytest.raises(ValueError):
        checked_source(op, source, name="spoofed.txt", mime=mime)
    with pytest.raises(ValueError):
        checked_source(op, source, name=source.name, mime="application/pdf")
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_to_pdf_operation(op, [source], out, {},
                                        original_name=source.name, content_type=mime)


@pytest.mark.parametrize("format_name", ["txt", "csv"])
def test_text_csv_escaped_html_and_pdf_binary(monkeypatch, tmp_path, format_name):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / ("source." + format_name)
    if format_name == "txt":
        source.write_text("ภาษาไทย <script>alert(1)</script> & DONE", encoding="utf-8")
    else:
        source.write_text("หัวข้อ,หมายเหตุ\nRCAT,\"<img src='http://unsafe/'>\"\n", encoding="utf-8")
    before = source.read_bytes()
    sent = []
    class Response:
        content = _pdf_bytes()
        def raise_for_status(self): pass
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, *, files):
            assert url.endswith("/forms/chromium/convert/html")
            sent.append(files["files"][1].decode("utf-8"))
            return Response()
    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    out = tmp_path / "document.pdf"
    op = format_name + "-to-pdf"
    execute_staged_to_pdf_operation(op, [source], out, {},
                                    original_name=source.name,
                                    content_type=STAGED_TO_PDF_INPUTS[op][0])
    assert len(PdfReader(str(out), strict=True).pages) == 1
    assert sent and "ภาษาไทย" in sent[0] if format_name == "txt" else bool(sent)
    assert "<script>" not in sent[0] and "<img src=" not in sent[0]
    assert "&lt;" in sent[0]
    assert source.read_bytes() == before


def test_text_encoding_csv_limits_and_mismatched_dispatch(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "source.txt"
    source.write_bytes(b"\xff\xfeinvalid")
    with pytest.raises(ValueError, match="UTF-8"):
        to_pdf_engine.text_to_pdf(source, tmp_path / "bad.pdf")
    source.write_text("text\x00invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="Control"):
        to_pdf_engine.text_to_pdf(source, tmp_path / "bad.pdf")
    csv_path = tmp_path / "source.csv"
    csv_path.write_text(",".join(["cell"] * 21), encoding="utf-8")
    with pytest.raises(ValueError, match="limits"):
        to_pdf_engine.csv_to_pdf(csv_path, tmp_path / "bad.pdf")
    with pytest.raises(ValueError, match="parameters"):
        execute_staged_to_pdf_operation(
            "csv-to-pdf", [csv_path], tmp_path / "bad.pdf", {"command": "ls"},
            original_name=csv_path.name, content_type="text/csv",
        )
    assert not (tmp_path / "bad.pdf").exists()


@pytest.mark.parametrize("kind,extension,fmt", [
    ("gif", ".gif", "GIF"), ("tiff", ".tiff", "TIFF"), ("jfif", ".jfif", "JPEG"),
])
def test_in_place_conversion_refused_without_modifying_source(tmp_path, kind, extension, fmt):
    source = tmp_path / ("original" + extension)
    _frames(source, fmt, 2 if kind != "jfif" else 1)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="differ"):
        to_pdf_engine.image_frames_to_pdf(source, source, kind=kind)
    assert source.read_bytes() == before


def test_text_csv_in_place_conversion_refused(tmp_path):
    for kind in ("txt", "csv"):
        source = tmp_path / ("original." + kind)
        source.write_text("RCAT,ภาษาไทย", encoding="utf-8")
        before = source.read_bytes()
        method = to_pdf_engine.text_to_pdf if kind == "txt" else to_pdf_engine.csv_to_pdf
        with pytest.raises(ValueError, match="differ"):
            method(source, source)
        assert source.read_bytes() == before


def _session(actor: str, scopes: list[str]) -> str:
    return create_session_token({
        "name": actor, "subject": "test:" + actor, "display_name": actor,
        "groups": [], "scopes": scopes, "source": "session",
        "is_identity_admin": False,
    })


@pytest.mark.parametrize("operation,extension,mime", [
    ("txt-to-pdf", ".txt", "text/plain"),
    ("csv-to-pdf", ".csv", "text/csv"),
    ("md-to-pdf", ".md", "text/markdown"),
    ("epub-to-pdf", ".epub", "application/epub+zip"),
    ("fb2-to-pdf", ".fb2", "application/x-fictionbook+xml"),
    ("jfif-to-pdf", ".jfif", "image/jpeg"),
    ("gif-to-pdf", ".gif", "image/gif"),
    ("tiff-to-pdf", ".tiff", "image/tiff"),
])
def test_flagged_api_requires_owner_scope_mime_then_enqueues(
    monkeypatch, operation, extension, mime,
):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *a, **kw: None)
    for func in ("ensure_daily_job_quota", "audit_event", "record_job", "set_queue_depth"):
        monkeypatch.setattr(legacy_pdf, func, lambda *a, **kw: None)
    calls = []
    class Q:
        name = "t90-2-staged"
        def __len__(self): return 0
    def enqueue(op, ident):
        calls.append((op, ident))
        return Q(), SimpleNamespace(id="rq-" + ident)
    monkeypatch.setattr(legacy_pdf, "enqueue_processing_job", enqueue)
    actor, other = "user:t90-2-owner", "user:t90-2-foreign"
    with SessionLocal() as db:
        items = [
            FileRecord(original_name="good" + extension, stored_name="good" + extension,
                       content_type=mime, size=123, sha256="a"*64, source_system=actor),
            FileRecord(original_name="bad" + extension, stored_name="bad" + extension,
                       content_type="application/pdf", size=123, sha256="a"*64, source_system=actor),
            FileRecord(original_name="other" + extension, stored_name="other" + extension,
                       content_type=mime, size=123, sha256="a"*64, source_system=other),
        ]
        db.add_all(items)
        db.commit()
        ids = [i.id for i in items]
    app = FastAPI()
    app.include_router(to_pdf.router)
    client = TestClient(app)
    endpoint = "/api/v1/pdf/to-pdf/" + operation.removesuffix("-to-pdf")
    client.cookies.set("pdfhub_session", _session(actor, ["jobs:read"]))
    assert client.post(endpoint, json={"file_id": ids[0]}).status_code == 403
    expected_scope = ("pdf:convert" if operation in {"txt-to-pdf", "csv-to-pdf", "md-to-pdf", "epub-to-pdf", "fb2-to-pdf"}
                      else "pdf:image-to-pdf")
    if expected_scope != "pdf:convert":
        client.cookies.set("pdfhub_session", _session(actor, ["pdf:convert"]))
        assert client.post(endpoint, json={"file_id": ids[0]}).status_code == 403
    client.cookies.set("pdfhub_session", _session(actor, [expected_scope]))
    assert client.post(endpoint, json={"file_id": ids[1]}).status_code == 415
    assert client.post(endpoint, json={"file_id": ids[2]}).status_code == 403
    assert client.post(endpoint, json={"file_id": ids[0], "url": "http://127.0.0.1"}).status_code == 422
    assert calls == []
    good = client.post(endpoint, json={"file_id": ids[0]})
    assert good.status_code == 202, good.text
    assert good.json()["operation"] == operation
    assert calls == [(operation, good.json()["id"])]
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    assert client.post(endpoint, json={"file_id": ids[0]}).status_code == 404
