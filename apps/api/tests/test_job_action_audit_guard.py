import json

from fastapi.testclient import TestClient
import pytest

from app import security
from app.db import SessionLocal
from app.identity import create_local_admin_identity, create_session_token
from app.main import app
from app.models import JobRecord
from app.routers import jobs as job_routes


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)


def owned_client():
    web = TestClient(app)
    web.cookies.set("pdfhub_session", create_session_token(create_local_admin_identity("reviewer")))
    return web


def seed_job(job_id, state):
    db = SessionLocal()
    db.add(JobRecord(id=job_id, operation="compress", status=state, progress=0,
        input_file_ids_json=json.dumps([]), params_json="{}",
        requested_by="local-admin:reviewer", rq_job_id="rq-" + job_id))
    db.commit()
    db.close()


def test_mutations_denied_if_audit_unavailable(monkeypatch):
    seed_job("guard-queued", "queued")
    seed_job("guard-failed", "failed")
    monkeypatch.setattr(job_routes, "audit_event", lambda *args, **kwargs: False)
    monkeypatch.setattr(job_routes, "ensure_daily_job_quota", lambda *args, **kwargs: None)
    web = owned_client()
    assert web.post("/api/v1/jobs/guard-queued/cancel").status_code == 503
    assert web.post("/api/v1/jobs/guard-failed/retry").status_code == 503
    assert web.delete("/api/v1/jobs/terminal").status_code == 503
    db = SessionLocal()
    try:
        assert db.get(JobRecord, "guard-queued").status == "queued"
        assert db.get(JobRecord, "guard-failed").status == "failed"
        assert db.query(JobRecord).count() == 2
    finally:
        db.close()
