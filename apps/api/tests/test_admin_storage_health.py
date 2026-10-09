from fastapi.testclient import TestClient
import pytest

from app import security, storage_reconciliation
from app.db import SessionLocal
from app.identity import create_local_admin_identity, create_session_token
from app.main import app
from app.routers import admin as admin_router
from app.security import Principal


@pytest.fixture(autouse=True)
def isolate_rate_and_audit(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    events = []
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: events.append((args, kwargs)) or True)
    return events


def human_admin():
    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token(create_local_admin_identity("storage-admin")))
    return client


def test_storage_health_is_human_only_and_excludes_sensitive_paths(monkeypatch, isolate_rate_and_audit):
    secret = "secret-object-name-and-full-storage-path"
    def snapshot(_db, detail_limit):
        assert detail_limit == 1
        return {
            "dry_run": True, "backend": "local", "database_records": 6,
            "storage_objects": 5, "issue_count": 3, "healthy": False,
            "category_counts": {"missing_object": 2, "orphan_object": 1},
            "issues": [{"file_id": "file-private", "stored_name": secret,
                        "locations": ["/storage/" + secret]}], "truncated": True,
        }

    monkeypatch.setattr(admin_router, "reconcile_storage", snapshot)
    response = human_admin().get("/api/v1/admin/storage/health")
    assert response.status_code == 200
    result = response.json()
    assert set(result) == {
        "dry_run", "backend", "database_records", "storage_objects",
        "issue_count", "healthy", "category_counts",
    }
    assert result["issue_count"] == 3
    assert result["category_counts"] == {"missing_object": 2, "orphan_object": 1}
    assert secret not in response.text
    assert "file-private" not in response.text
    assert len(isolate_rate_and_audit) == 1
    args = isolate_rate_and_audit[0][0]
    assert args[0] == "admin.storage_health.read"
    assert args[4] == {"mode": "dry_run"}


def test_storage_health_denies_non_human_and_unauthenticated():
    assert TestClient(app).get("/api/v1/admin/storage/health").status_code == 401
    assert TestClient(app).get("/api/v1/admin/storage/health", headers={
        "X-API-Key": "pdfh_ci_admin_key_change_me",
    }).status_code == 403
    operator = TestClient(app)
    operator.cookies.set("pdfhub_session", create_session_token({
        "name": "user:operator", "subject": "operator", "source": "session",
        "roles": ["operator"], "groups": [], "scopes": ["admin:keys"],
    }))
    assert operator.get("/api/v1/admin/storage/health").status_code == 403


def test_storage_health_audit_failure_prevents_storage_scan(monkeypatch):
    scans = []
    monkeypatch.setattr(admin_router, "audit_event", lambda *args, **kwargs: False)
    monkeypatch.setattr(admin_router, "reconcile_storage", lambda *args, **kwargs: scans.append(True))
    response = human_admin().get("/api/v1/admin/storage/health")
    assert response.status_code == 503
    assert scans == []


def test_storage_health_handler_directly_exercises_summary_and_denial(monkeypatch):
    monkeypatch.setattr(admin_router, "reconcile_storage", lambda *args, **kwargs: {
        "backend": "s3", "database_records": 0, "storage_objects": 0,
        "issue_count": 0, "healthy": True, "category_counts": {},
    })
    db = SessionLocal()
    try:
        user = Principal(name="user:admin", scopes={"*"}, roles={"admin"},
                         is_identity_admin=True, auth_source="local-admin")
        result = admin_router.admin_storage_health(principal=user, db=db)
        assert result.dry_run is True
        assert result.healthy is True
        assert result.backend == "s3"
        from fastapi import HTTPException
        guest = Principal(name="service", scopes={"*"}, roles={"admin"},
                          is_identity_admin=True, auth_source="api_key")
        with pytest.raises(HTTPException) as denied:
            admin_router.admin_storage_health(principal=guest, db=db)
        assert denied.value.status_code == 403
    finally:
        db.close()


def test_reconciliation_category_counts_include_all_issues_after_truncation(monkeypatch, tmp_path):
    originals = tmp_path / "originals"
    originals.mkdir()
    (originals / "untracked-1.pdf").write_bytes(b"one")
    (originals / "untracked-2.pdf").write_bytes(b"two")
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_reconciliation.settings, "data_dir", tmp_path)
    db = SessionLocal()
    try:
        result = storage_reconciliation.reconcile_storage(db, detail_limit=1)
        assert len(result["issues"]) == 1
        assert result["issue_count"] == 2
        assert result["truncated"] is True
        assert result["category_counts"] == {"orphan_object": 2}
    finally:
        db.close()
