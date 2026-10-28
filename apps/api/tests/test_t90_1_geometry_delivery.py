"""T90-1.5: flag-gated M11/M28 API, owner checks and binary worker output."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import security, storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app as production_app
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import geometry, jobs, pdf as legacy_pdf
from app.staged_geometry_adapters import (
    execute_staged_geometry_operation, geometry_output_spec,
)
from sqlalchemy import select


def session(owner, scopes):
    return create_session_token({
        "name": owner, "subject": "test:" + owner, "display_name": owner,
        "groups": [], "scopes": scopes, "source": "session",
        "is_identity_admin": False,
    })


def source_pdf(path: Path):
    c = canvas.Canvas(str(path), pagesize=(480, 720))
    c.drawString(60, 600, "RCAT GEOMETRY TEST")
    c.showPage()
    c.save()


def test_routes_and_queue_default_off(monkeypatch):
    assert get_settings().geometry_tools_enabled is False
    assert not any("/api/v1/pdf/geometry/" in r.path for r in production_app.routes)
    with pytest.raises(ValueError, match="Unsupported"):
        queue_class_for_operation("crop-pdf")
    from app import queue
    monkeypatch.setattr(queue.settings, "geometry_tools_enabled", True)
    assert queue_class_for_operation("crop-pdf") == "pdf"
    assert queue_class_for_operation("resize-pdf") == "pdf"
    with pytest.raises(ValueError, match="Unsupported"):
        queue_class_for_operation("arbitrary-pdf-code")


@pytest.mark.parametrize("operation,scope,payload", [
    ("crop-pdf", "pdf:crop", {"left": 20, "bottom": 20, "right": 450, "top": 700}),
    ("resize-pdf", "pdf:resize", {"width": 600, "height": 840}),
])
def test_geometry_api_owner_scope_validation_and_revocation(monkeypatch, operation, scope, payload):
    monkeypatch.setattr(get_settings(), "geometry_tools_enabled", True)
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *a, **kw: None)
    for fn in ("ensure_daily_job_quota", "audit_event", "record_job", "set_queue_depth"):
        monkeypatch.setattr(legacy_pdf, fn, lambda *a, **kw: None)
    enqueued = []
    class Q:
        name = "ci-geometry"
        def __len__(self): return 0
    def enqueue(op, ident):
        enqueued.append((op, ident))
        return Q(), SimpleNamespace(id="rq-" + ident)
    monkeypatch.setattr(legacy_pdf, "enqueue_processing_job", enqueue)
    owner, foreign = "test:geometry-owner", "test:geometry-other"
    with SessionLocal() as db:
        records = [
            FileRecord(original_name=f"{i}.pdf", stored_name=f"{i}.pdf", size=20,
                       sha256="d" * 64, source_system=who, content_type=mime)
            for i, (who, mime) in enumerate([
                (owner, "application/pdf"), (owner, "image/png"),
                (foreign, "application/pdf"),
            ])
        ]
        db.add_all(records)
        db.commit()
        ids = [x.id for x in records]
    app = FastAPI()
    app.include_router(geometry.router)
    app.include_router(jobs.router)
    client = TestClient(app)
    url = "/api/v1/pdf/geometry/" + operation
    client.cookies.set("pdfhub_session", session(owner, ["jobs:read"]))
    assert client.post(url, json={"file_id": ids[0], **payload}).status_code == 403
    client.cookies.set("pdfhub_session", session(owner, [scope, "jobs:read"]))
    assert client.post(url, json={"file_id": ids[1], **payload}).status_code == 415
    assert client.post(url, json={"file_id": ids[2], **payload}).status_code == 403
    for malformed in (
        {"file_id": ids[0], **payload, "not_allowlisted": 9},
        {**{"file_id": ids[0]}, **({"left": 300, "right": 200, "bottom": 0, "top": 400}
                                  if operation == "crop-pdf" else {"width": 2, "height": 3})},
    ):
        assert client.post(url, json=malformed).status_code == 422
    assert enqueued == []
    response = client.post(url, json={"file_id": ids[0], **payload})
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["operation"] == operation and data["requested_by"] == owner
    assert enqueued == [(operation, data["id"])]
    client.cookies.set("pdfhub_session", session(foreign, [scope, "jobs:read"]))
    assert client.get("/api/v1/jobs/" + data["id"]).status_code == 403
    monkeypatch.setattr(get_settings(), "geometry_tools_enabled", False)
    client.cookies.set("pdfhub_session", session(owner, [scope, "jobs:read"]))
    assert client.post(url, json={"file_id": ids[0], **payload}).status_code == 404
    assert client.get("/api/v1/jobs/" + data["id"]).status_code == 404


@pytest.mark.parametrize("operation,params,expected", [
    ("crop-pdf", {"left": 10, "bottom": 10, "right": 450, "top": 690, "pages": None}, (440, 680)),
    ("resize-pdf", {"width": 600, "height": 840}, (600, 840)),
])
def test_real_engine_output_fidelity_and_revoked_flag(monkeypatch, tmp_path, operation, params, expected):
    monkeypatch.setattr(get_settings(), "geometry_tools_enabled", True)
    src = tmp_path / "source.pdf"
    source_pdf(src)
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    out = tmp_path / "out.pdf"
    assert geometry_output_spec(operation) == (".pdf", "application/pdf")
    assert worker_tasks._output_spec_for_job(operation) == (".pdf", "application/pdf")
    execute_staged_geometry_operation(operation, [src], out, params)
    page = PdfReader(str(out), strict=True).pages[0]
    box = page.cropbox if operation == "crop-pdf" else page.mediabox
    assert tuple(round(float(x)) for x in (box.width, box.height)) == expected
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    monkeypatch.setattr(get_settings(), "geometry_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_geometry_operation(operation, [src], out, params)


@pytest.mark.parametrize("operation,params", [
    ("crop-pdf", {"left": 10, "bottom": 10, "right": 450, "top": 690, "pages": None}),
    ("resize-pdf", {"width": 600, "height": 840}),
])
def test_worker_commits_real_pdf_owner_bound_artifacts(monkeypatch, tmp_path, operation, params):
    monkeypatch.setattr(get_settings(), "geometry_tools_enabled", True)
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    path = tmp_path / "originals" / "geometry.pdf"
    source_pdf(path)
    before = path.read_bytes()
    owner = "user:geometry-worker"
    with SessionLocal() as db:
        db.add(ServicePolicy(service_name=owner, rate_limit_per_minute=120,
                             daily_job_limit=100, max_storage_mb=100, webhook_url=None))
        file = FileRecord(original_name="geometry.pdf", stored_name="geometry.pdf",
                          content_type="application/pdf", size=len(before),
                          sha256=hashlib.sha256(before).hexdigest(), source_system=owner,
                          expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add(file)
        db.flush()
        job = JobRecord(operation=operation, status="queued", requested_by=owner,
                        input_file_ids_json=json.dumps([file.id]),
                        params_json=json.dumps(params))
        db.add(job)
        db.commit()
        job_id = job.id
    artifact_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        result = db.get(FileRecord, artifact_id)
        links = db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all()
        assert job.status == "completed" and job.output_file_id == artifact_id
        assert result.source_system == owner and result.content_type == "application/pdf"
        assert len(links) == 1 and links[0].role == "result"
        output = storage.path_for_stored_name(result.stored_name)
        assert len(PdfReader(str(output), strict=True).pages) == 1
    assert path.read_bytes() == before


def test_kill_switch_rejects_queued_geometry_work_without_output(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "geometry_tools_enabled", False)
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    src = tmp_path / "originals" / "blocked.pdf"
    source_pdf(src)
    before = src.read_bytes()
    with SessionLocal() as db:
        file = FileRecord(original_name="blocked.pdf", stored_name="blocked.pdf",
                          content_type="application/pdf", size=len(before),
                          sha256=hashlib.sha256(before).hexdigest(), source_system="geometry-user")
        db.add(file)
        db.flush()
        job = JobRecord(operation="resize-pdf", status="queued", requested_by="geometry-user",
                        input_file_ids_json=json.dumps([file.id]),
                        params_json='{"width": 600, "height": 840}')
        db.add(job)
        db.commit()
        jid = job.id
    with pytest.raises(ValueError, match="unavailable or unauthorized"):
        worker_tasks.process_job(jid)
    with SessionLocal() as db:
        assert db.get(JobRecord, jid).status == "failed"
        assert db.scalar(select(JobOutputArtifact).where(JobOutputArtifact.job_id == jid)) is None
    assert src.read_bytes() == before
