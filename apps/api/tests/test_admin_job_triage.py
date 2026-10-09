import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import security
from app.db import SessionLocal
from app.identity import create_local_admin_identity, create_session_token
from app.main import app
from app.models import JobRecord
from app.routers import admin as admin_router
from app.security import Principal


@pytest.fixture(autouse=True)
def mock_audit_and_rate_limit(monkeypatch):
    events = []
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: events.append((args, kwargs)) or True)
    return events


def client_for(identity=None):
    client = TestClient(app)
    if identity is not None:
        client.cookies.set("pdfhub_session", create_session_token(identity))
    return client


def seed_jobs():
    db = SessionLocal()
    base = datetime(2026, 10, 9, 6, tzinfo=timezone.utc)
    for idx, (name, operation, status, owner) in enumerate([
        ("old", "ocr", "failed", "user:alice"),
        ("new", "compress", "running", "user:bob"),
        ("medium", "compress", "failed", "user:alice"),
    ]):
        db.add(JobRecord(
            id=f"triage-{name}",
            operation=operation, status=status, progress=idx * 25,
            input_file_ids_json=json.dumps(["secret-file-id"]), output_file_id="secret-output-id",
            params_json=json.dumps({"password": "secret-param"}), error="secret exception path",
            requested_by=owner, created_at=base + timedelta(minutes=idx),
        ))
    db.commit()
    db.close()


def test_read_only_admin_job_triage_is_minimized_paginated_and_audited(mock_audit_and_rate_limit):
    seed_jobs()
    admin = client_for(create_local_admin_identity("triage-admin"))
    first = admin.get("/api/v1/admin/jobs/triage", params={"limit": 1, "offset": 0})
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["has_more"] is True
    assert data["limit"] == 1 and data["offset"] == 0
    assert data["items"][0]["id"] == "triage-medium"
    assert set(data["items"][0]) == {
        "id", "operation", "status", "progress", "created_at",
        "started_at", "finished_at", "failure_recorded",
    }
    assert "secret" not in first.text and "user:alice" not in first.text
    assert data["items"][0]["failure_recorded"] is True

    second = admin.get("/api/v1/admin/jobs/triage", params={"limit": 1, "offset": 1})
    assert second.status_code == 200
    assert second.json()["items"][0]["id"] == "triage-new"

    filtered = admin.get("/api/v1/admin/jobs/triage", params={
        "status": "failed", "operation": "compress", "limit": 100,
    })
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == ["triage-medium"]
    assert filtered.json()["has_more"] is False

    assert len(mock_audit_and_rate_limit) == 3
    for args, kwargs in mock_audit_and_rate_limit:
        assert args[:3] == ("admin.jobs_triage.read", "local-admin:triage-admin", "job_triage")
        detail = args[4]
        assert set(detail) == {"status", "operation", "limit", "offset"}
        assert "secret" not in json.dumps(detail)


def test_admin_triage_denies_viewer_operator_legacy_service_and_bootstrap(mock_audit_and_rate_limit):
    seed_jobs()
    anonymous = client_for()
    assert anonymous.get("/api/v1/admin/jobs/triage").status_code == 401

    for role in ("viewer", "operator"):
        session = {
            "name": f"user:{role}", "subject": role,
            "roles": [role], "groups": [], "scopes": ["admin:keys"],
            "source": "session", "is_identity_admin": False,
        }
        assert client_for(session).get("/api/v1/admin/jobs/triage").status_code == 403

    # A legacy session with signed wildcard scopes is not a human Admin role.
    legacy = {
        "name": "service:legacy", "subject": "legacy", "groups": [],
        "scopes": ["*"], "source": "session", "is_identity_admin": True,
    }
    assert client_for(legacy).get("/api/v1/admin/jobs/triage").status_code == 403
    bootstrap = TestClient(app)
    assert bootstrap.get("/api/v1/admin/jobs/triage", headers={
        "X-API-Key": "pdfh_ci_admin_key_change_me",
    }).status_code == 403
    assert mock_audit_and_rate_limit == []


def test_triage_rejects_unbounded_and_invalid_query_without_audit(mock_audit_and_rate_limit):
    admin = client_for(create_local_admin_identity("triage-admin"))
    for params in (
        {"limit": 101}, {"limit": 0}, {"offset": -1}, {"offset": 100001},
        {"status": "arbitrary"}, {"operation": "A" * 41},
        {"operation": "compress;drop"},
    ):
        assert admin.get("/api/v1/admin/jobs/triage", params=params).status_code == 422
    assert mock_audit_and_rate_limit == []


def test_triage_fails_closed_on_missing_audit(monkeypatch):
    seed_jobs()
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: False)
    admin = client_for(create_local_admin_identity("triage-admin"))
    response = admin.get("/api/v1/admin/jobs/triage")
    assert response.status_code == 503
    assert response.json()["detail"] == "Admin audit unavailable"


def test_triage_handler_direct_branches_and_privilege_guard(mock_audit_and_rate_limit):
    seed_jobs()
    db = SessionLocal()
    try:
        principal = Principal(name="human", scopes={"*"}, roles={"admin"},
                              is_identity_admin=True, auth_source="local-admin")
        result = admin_router.list_admin_job_triage(
            status="failed", operation=None, limit=1, offset=1,
            principal=principal, db=db,
        )
        assert result.items[0].id == "triage-old"
        assert result.has_more is False

        for source in ("api_key", "bootstrap", "web-console"):
            unauthorized = Principal(name="service", scopes={"*"}, roles={"admin"},
                                     is_identity_admin=True, auth_source=source)
            with pytest.raises(HTTPException) as error:
                admin_router.list_admin_job_triage(
                    status=None, operation=None, limit=25, offset=0,
                    principal=unauthorized, db=db,
                )
            assert error.value.status_code == 403
    finally:
        db.close()
