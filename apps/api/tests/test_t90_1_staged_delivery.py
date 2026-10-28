"""T90-1.4b staged HTTP/RQ boundary tests; production defaults remain OFF.

Real FastAPI dependencies, auth session, SQLAlchemy records, and pypdf adapter
are exercised. Only external RQ submission is replaced by a deterministic
queue stub. Follow-up 1.4c must run a complete Docker Compose storage journey.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import security
from app.config import get_settings
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app as production_app
from app.models import FileRecord, JobRecord
from app.queue import queue_class_for_operation
from app.routers import document_data, jobs, pdf as pdf_router
from app.staged_document_adapters import (
    execute_staged_document_operation, staged_output_spec,
)
from app import worker_tasks


def _session(actor: str, scopes: list[str]) -> str:
    return create_session_token({
        "name": actor, "subject": "test:" + actor,
        "display_name": actor, "groups": [],
        "scopes": scopes, "source": "session", "is_identity_admin": False,
    })


def _uploaded(name: str, owner: str, mime: str) -> FileRecord:
    return FileRecord(
        original_name=name, stored_name="staged-t90-14b-" + name,
        content_type=mime, size=120, sha256="c" * 64, source_system=owner,
    )


def test_staged_routes_not_in_default_app_or_openapi():
    settings = get_settings()
    assert settings.document_data_tools_enabled is False
    paths = {r.path for r in production_app.routes}
    for op in ("edit-metadata", "remove-metadata", "extract-text"):
        assert f"/api/v1/pdf/document-data/{op}" not in paths
    assert not any("document-data" in path for path in production_app.openapi()["paths"])


@pytest.mark.parametrize("operation,scope,payload", [
    ("edit-metadata", "pdf:metadata", {"changes": {"title": "ภาษาไทย", "author": None}}),
    ("remove-metadata", "pdf:metadata", {}),
    ("extract-text", "pdf:extract-text", {}),
])
def test_document_data_staged_api_owner_scope_mime_and_enqueue(
    monkeypatch, operation: str, scope: str, payload: dict
):
    monkeypatch.setattr(document_data.settings, "document_data_tools_enabled", True)
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "ensure_daily_job_quota", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "audit_event", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "record_job", lambda *a, **kw: None)
    monkeypatch.setattr(pdf_router, "set_queue_depth", lambda *a, **kw: None)
    queued: list[tuple[str, str]] = []

    class Queue:
        name = "t90-staged"
        def __len__(self): return 0

    def enqueue(op: str, job_id: str):
        queued.append((op, job_id))
        return Queue(), SimpleNamespace(id="rq-" + job_id)

    monkeypatch.setattr(pdf_router, "enqueue_processing_job", enqueue)
    owner, foreign = "user:t90-14b-owner", "user:t90-14b-foreign"
    db = SessionLocal()
    records = [
        _uploaded(operation + "-owned.pdf", owner, "application/pdf"),
        _uploaded(operation + "-bad.pdf", owner, "image/png"),
        _uploaded(operation + "-foreign.pdf", foreign, "application/pdf"),
    ]
    db.add_all(records)
    db.commit()
    ids = [item.id for item in records]
    db.close()

    isolated_app = FastAPI()
    isolated_app.include_router(document_data.router)
    isolated_app.include_router(jobs.router)
    client = TestClient(isolated_app)
    url = "/api/v1/pdf/document-data/" + operation

    client.cookies.set("pdfhub_session", _session(owner, ["jobs:read"]))
    assert client.post(url, json={"file_id": ids[0], **payload}).status_code == 403
    client.cookies.set("pdfhub_session", _session(owner, [scope, "jobs:read"]))
    assert client.post(url, json={"file_id": ids[1], **payload}).status_code == 415
    assert client.post(url, json={"file_id": ids[2], **payload}).status_code == 403
    assert not queued

    if operation == "edit-metadata":
        for bad_changes in (
            {}, {"xmp": "not allowed"}, {"title": "X" * 513},
            {"title": "unsafe\nnewline"},
        ):
            assert client.post(url, json={
                "file_id": ids[0], "changes": bad_changes,
            }).status_code == 422
        assert not queued

    result = client.post(url, json={"file_id": ids[0], **payload})
    assert result.status_code == 202, result.text
    data = result.json()
    assert data["operation"] == operation
    assert data["requested_by"] == owner
    assert queued == [(operation, data["id"])]
    db = SessionLocal()
    persisted = db.get(JobRecord, data["id"])
    assert persisted is not None and persisted.requested_by == owner
    db.close()

    client.cookies.set("pdfhub_session", _session(foreign, ["jobs:read", scope]))
    assert client.get("/api/v1/jobs/" + data["id"]).status_code == 403

    # Even if the flag is turned off between intake and retry, fail closed.
    monkeypatch.setattr(document_data.settings, "document_data_tools_enabled", False)
    assert client.post(url, json={"file_id": ids[0], **payload}).status_code == 404
    assert queued == [(operation, data["id"])]


def _make_pdf(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=(480, 720))
    c.drawString(60, 600, "RCAT SEARCHABLE TEXT")
    c.showPage()
    c.save()
    return path


@pytest.mark.parametrize("operation,params,ext,mime", [
    ("extract-text", {}, ".txt", "text/plain; charset=utf-8"),
    ("edit-metadata", {"changes": {"title": "ชื่อเรื่อง"}}, ".pdf", "application/pdf"),
    ("remove-metadata", {}, ".pdf", "application/pdf"),
])
def test_staged_adapter_real_outputs_and_original_unchanged(
    monkeypatch, tmp_path: Path, operation: str, params: dict, ext: str, mime: str
):
    settings = get_settings()
    monkeypatch.setattr(settings, "document_data_tools_enabled", True)
    source = _make_pdf(tmp_path / "source.pdf")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / ("result" + ext)
    assert staged_output_spec(operation) == (ext, mime)
    assert worker_tasks._output_spec_for_job(operation) == (ext, mime)
    execute_staged_document_operation(operation, [source], output, params)
    if operation == "extract-text":
        assert "RCAT SEARCHABLE TEXT" in output.read_text(encoding="utf-8")
    else:
        pdf = PdfReader(str(output), strict=True)
        assert len(pdf.pages) == 1
        if operation == "edit-metadata":
            assert pdf.metadata.title == "ชื่อเรื่อง"
        else:
            assert pdf.metadata == {}
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    monkeypatch.setattr(settings, "document_data_tools_enabled", False)
    # Output MIME resolution is pure; disabled jobs fail inside the worker's
    # guarded try/finally so they can reach a terminal state and clean up.
    assert worker_tasks._output_spec_for_job(operation) == (ext, mime)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_document_operation(operation, [source], output, params)


def test_t90_staged_queue_map_default_off_and_opt_in(monkeypatch):
    from app import queue
    assert queue.settings.document_data_tools_enabled is False
    with pytest.raises(ValueError, match="Unsupported"):
        queue_class_for_operation("extract-text")
    monkeypatch.setattr(queue.settings, "document_data_tools_enabled", True)
    assert queue_class_for_operation("extract-text") == "pdf"
    assert queue_class_for_operation("edit-metadata") == "interactive"
    assert queue_class_for_operation("remove-metadata") == "pdf"
    with pytest.raises(ValueError, match="Unsupported"):
        queue_class_for_operation("arbitrary-client-code")


def _queued_txt_job(monkeypatch, tmp_path: Path, owner: str = "t90-b-worker-owner"):
    """Real stored input and SQL job; run process_job synchronously in the CI host."""
    from datetime import datetime, timedelta, timezone
    from app import storage
    from app.models import ServicePolicy

    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    source = _make_pdf(tmp_path / "originals" / "source.pdf")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name=owner, rate_limit_per_minute=120,
            daily_job_limit=100, max_storage_mb=100,
            webhook_url=None,
        ))
        file = FileRecord(
            original_name="source.pdf", stored_name="source.pdf",
            content_type="application/pdf", size=source.stat().st_size,
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_system=owner,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(file)
        db.flush()
        job = JobRecord(
            operation="extract-text", status="queued", requested_by=owner,
            input_file_ids_json='["' + file.id + '"]', params_json="{}",
        )
        db.add(job)
        db.commit()
        return job.id, file.id, source


def test_staged_worker_persists_owner_scoped_txt_and_signed_download(
    monkeypatch, tmp_path: Path
):
    from app.models import JobOutputArtifact
    from app import storage
    from sqlalchemy import select
    from urllib.parse import urlsplit

    monkeypatch.setattr(get_settings(), "document_data_tools_enabled", True)
    job_id, input_id, source = _queued_txt_job(monkeypatch, tmp_path)
    original = hashlib.sha256(source.read_bytes()).hexdigest()

    result_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        output = db.get(FileRecord, result_id)
        links = db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all()
        assert job.status == "completed" and job.output_file_id == result_id
        assert output.content_type == "text/plain; charset=utf-8"
        assert output.original_name.endswith(".txt")
        assert output.source_system == "t90-b-worker-owner"
        assert len(links) == 1 and links[0].file_id == result_id
        assert links[0].role == "result"
        assert storage.path_for_stored_name(output.stored_name).read_bytes().startswith(b"RCAT")

    client = TestClient(production_app)
    client.cookies.set("pdfhub_session", _session("t90-b-worker-owner", ["files:read", "jobs:read"]))
    file_response = client.get("/api/v1/files/" + result_id + "/download")
    assert file_response.status_code == 200
    assert "text/plain" in file_response.headers["content-type"]
    assert "RCAT SEARCHABLE TEXT" in file_response.text
    artifact = client.get("/api/v1/jobs/" + job_id + "/artifacts")
    assert artifact.status_code == 200
    assert artifact.json()["artifacts"][0]["content_type"] == "text/plain; charset=utf-8"

    signed = client.post("/api/v1/files/" + result_id + "/signed-download")
    assert signed.status_code == 200, signed.text
    token_url = urlsplit(signed.json()["url"])
    signed_result = client.get(token_url.path + "?" + token_url.query)
    assert signed_result.status_code == 200
    assert "RCAT SEARCHABLE TEXT" in signed_result.text

    client.cookies.set("pdfhub_session", _session("t90-b-foreign-owner", ["files:read", "jobs:read"]))
    assert client.get("/api/v1/files/" + result_id + "/download").status_code == 403
    assert client.get("/api/v1/jobs/" + job_id + "/artifacts").status_code == 403
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original


def test_feature_kill_switch_marks_queued_txt_job_failed_without_output(
    monkeypatch, tmp_path: Path
):
    from app.models import JobOutputArtifact
    from sqlalchemy import select

    monkeypatch.setattr(get_settings(), "document_data_tools_enabled", False)
    job_id, input_id, source = _queued_txt_job(monkeypatch, tmp_path)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="unavailable or unauthorized"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.output_file_id is None
        assert len(db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all()) == 0
    assert source.read_bytes() == before
    assert not list((tmp_path / "processed").iterdir())
