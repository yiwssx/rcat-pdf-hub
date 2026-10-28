"""T90-1.1 / M04: real qpdf binary acceptance and authenticated merge intake.

These tests deliberately do not certify a production release. They exercise the
existing operation, not a mock that writes an arbitrary .pdf filename.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app import security
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app
from app.models import FileRecord, JobRecord
from app.routers import pdf as pdf_router
from app.services import pdf_tools


def _make_pdf(path: Path, pages: list[tuple[str, tuple[int, int]]]) -> Path:
    drawing = canvas.Canvas(str(path))
    for label, size in pages:
        drawing.setPageSize(size)
        drawing.drawString(72, size[1] - 72, label)
        drawing.showPage()
    drawing.save()
    return path


@pytest.mark.skipif(shutil.which("qpdf") is None, reason="real qpdf binary required")
def test_m04_merge_binary_order_mixed_geometry_and_immutable_inputs(tmp_path: Path):
    first = _make_pdf(tmp_path / "ต้นฉบับ-หนึ่ง.pdf", [
        ("RCAT FIRST", (612, 792)),
        ("RCAT SECOND", (420, 595)),
    ])
    second = _make_pdf(tmp_path / "second.pdf", [("RCAT THIRD", (595, 842))])
    output = tmp_path / "merged.pdf"

    source_hashes = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (first, second)
    }
    pdf_tools.merge([first, second], output)

    assert output.read_bytes().startswith(b"%PDF-")
    merged = PdfReader(str(output), strict=True)
    assert len(merged.pages) == 3
    for page, (expected_text, expected_size) in zip(merged.pages, [
        ("RCAT FIRST", (612, 792)),
        ("RCAT SECOND", (420, 595)),
        ("RCAT THIRD", (595, 842)),
    ], strict=True):
        assert expected_text in (page.extract_text() or "")
        assert (round(float(page.mediabox.width)), round(float(page.mediabox.height))) == expected_size
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (first, second)
    } == source_hashes


@pytest.mark.skipif(shutil.which("qpdf") is None, reason="real qpdf binary required")
@pytest.mark.parametrize("invalid_kind", ["corrupt", "encrypted"])
def test_m04_merge_rejects_unreadable_sources_without_claiming_success(
    tmp_path: Path, invalid_kind: str
):
    good = _make_pdf(tmp_path / "good.pdf", [("VALID PAGE", (612, 792))])
    bad = tmp_path / "unreadable.pdf"
    if invalid_kind == "corrupt":
        bad.write_bytes(b"%PDF-1.7\ntruncated without objects or xref\n")
    else:
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.encrypt(user_password="user-secret", owner_password="owner-secret")
        with bad.open("wb") as handle:
            writer.write(handle)

    with pytest.raises(RuntimeError):
        pdf_tools.merge([good, bad], tmp_path / "should-not-complete.pdf")


def _session(actor: str, scopes: list[str]) -> str:
    return create_session_token({
        "name": actor,
        "subject": "test:" + actor,
        "display_name": actor,
        "groups": [],
        "scopes": scopes,
        "source": "session",
        "is_identity_admin": False,
    })


def _file(name: str, owner: str, mime: str) -> FileRecord:
    return FileRecord(
        original_name=name,
        stored_name="t90-m04-" + name,
        content_type=mime,
        size=128,
        sha256="a" * 64,
        source_system=owner,
    )


def test_m04_merge_api_scope_owner_mime_and_job_visibility(monkeypatch):
    """Real FastAPI route, session principal and database; only RQ dispatch is stubbed."""
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "ensure_daily_job_quota", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "set_queue_depth", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "record_job", lambda *a, **kw: None)

    queued: list[tuple[str, str]] = []

    class FakeQueue:
        name = "pdf-test"

        def __len__(self) -> int:
            return 0

    def fake_enqueue(operation: str, job_id: str):
        queued.append((operation, job_id))
        return FakeQueue(), SimpleNamespace(id="rq-" + job_id)

    monkeypatch.setattr(pdf_router, "enqueue_processing_job", fake_enqueue)

    owner = "user:t90-m04-owner"
    foreign = "user:t90-m04-foreign"
    db = SessionLocal()
    a = _file("a.pdf", owner, "application/pdf")
    b = _file("b.pdf", owner, "application/pdf")
    foreign_pdf = _file("c.pdf", foreign, "application/pdf")
    fake_pdf = _file("misleading.pdf", owner, "image/png")
    db.add_all([a, b, foreign_pdf, fake_pdf])
    db.commit()
    ids = (a.id, b.id, foreign_pdf.id, fake_pdf.id)
    db.close()

    client = TestClient(app)
    full_scopes = ["pdf:merge", "jobs:read", "files:read"]
    client.cookies.set("pdfhub_session", _session(owner, ["jobs:read"]))
    assert client.post("/api/v1/pdf/merge", json={"file_ids": list(ids[:2])}).status_code == 403
    assert not queued

    client.cookies.set("pdfhub_session", _session(owner, full_scopes))
    cross_owner = client.post("/api/v1/pdf/merge", json={"file_ids": [ids[0], ids[2]]})
    assert cross_owner.status_code == 403
    wrong_mime = client.post("/api/v1/pdf/merge", json={"file_ids": [ids[0], ids[3]]})
    assert wrong_mime.status_code == 415
    assert not queued

    valid = client.post("/api/v1/pdf/merge", json={"file_ids": list(ids[:2])})
    assert valid.status_code == 202, valid.text
    payload = valid.json()
    assert payload["operation"] == "merge"
    assert payload["input_file_ids"] == list(ids[:2])
    assert payload["requested_by"] == owner
    assert queued == [("merge", payload["id"])]

    db = SessionLocal()
    stored = db.get(JobRecord, payload["id"])
    assert stored is not None and stored.requested_by == owner
    db.close()

    client.cookies.set("pdfhub_session", _session(foreign, full_scopes))
    assert client.get("/api/v1/jobs/" + payload["id"]).status_code == 403
