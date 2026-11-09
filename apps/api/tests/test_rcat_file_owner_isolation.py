"""R1 RCAT admin wildcard is not permission to read or process other users' files.

Runs against isolated test database + real FastAPI authentication; does not
contact Google, process actual RCAT documents, or modify Production.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import security
from app.config import get_settings
from app.db import SessionLocal
from app.identity import create_session_token, identity_from_claims
from app.main import app
from app.models import ArchiveRecord, FileRecord
from app.routers import files, integrations
from app.security import Principal, may_bypass_file_ownership


def _admin_client(monkeypatch) -> tuple[TestClient, str]:
    settings = get_settings()
    monkeypatch.setattr(settings, "rcat_institutional_only", True)
    monkeypatch.setattr(settings, "oidc_issuer", "https://accounts.google.com")
    monkeypatch.setattr(settings, "rcat_admin_emails", "admin@rcat.ac.th")
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *a, **kw: None)
    identity = identity_from_claims({
        "iss": "https://accounts.google.com",
        "sub": "rcat-admin-unique-stable-subject",
        "email": "admin@rcat.ac.th",
        "email_verified": True,
        "hd": "rcat.ac.th",
        "groups": [],
    }, "oidc")
    assert identity["roles"] == ["admin"]
    assert identity["scopes"] == ["*"]
    client = TestClient(app)
    client.cookies.set("pdfhub_session", create_session_token(identity))
    return client, identity["name"]


def _seed_two_files(owner: str) -> tuple[str, str]:
    db = SessionLocal()
    try:
        own = FileRecord(
            original_name="own.pdf", stored_name="r1-rcat-own",
            content_type="application/pdf", size=1024,
            sha256="a" * 64, source_system=owner,
        )
        foreign = FileRecord(
            original_name="foreign.pdf", stored_name="r1-rcat-foreign",
            content_type="application/pdf", size=1024,
            sha256="b" * 64, source_system="user:oidc:foreign-subject",
        )
        db.add_all([own, foreign])
        db.flush()
        db.add_all([
            ArchiveRecord(file_id=own.id, integration_name="paperless", status="queued"),
            ArchiveRecord(file_id=foreign.id, integration_name="paperless", status="queued"),
        ])
        db.commit()
        return own.id, foreign.id
    finally:
        db.close()


def test_rcat_admin_file_library_metadata_download_and_delete_are_owner_scoped(monkeypatch):
    client, owner = _admin_client(monkeypatch)
    own_id, foreign_id = _seed_two_files(owner)

    for path in ("/api/v1/files", "/api/v1/files/library"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        rows = response.json()
        if isinstance(rows, dict):
            assert rows["total"] == 1
            rows = rows["items"]
        assert [item["id"] for item in rows] == [own_id]

    assert client.get(f"/api/v1/files/{own_id}").status_code == 200
    for url in (
        f"/api/v1/files/{foreign_id}",
        f"/api/v1/files/{foreign_id}/download",
        f"/api/v1/files/{foreign_id}/preview",
    ):
        response = client.get(url)
        assert response.status_code == 403, (url, response.text)
    assert client.delete(f"/api/v1/files/{foreign_id}").status_code == 403
    assert client.post(
        "/api/v1/files/bulk-delete",
        json={"file_ids": [own_id, foreign_id]},
    ).status_code == 403
    assert client.get(f"/api/v1/files/{own_id}").status_code == 200
    assert client.get(f"/api/v1/files/{foreign_id}").status_code == 403


def test_rcat_admin_cannot_process_foreign_files_even_with_wildcard(monkeypatch):
    client, owner = _admin_client(monkeypatch)
    own_id, foreign_id = _seed_two_files(owner)
    result = client.post("/api/v1/pdf/merge", json={"file_ids": [own_id, foreign_id]})
    assert result.status_code == 403, result.text
    # Fails before quota, RQ queueing or file access; no output is produced.


def test_rcat_admin_cannot_list_or_archive_other_users_paperless(monkeypatch):
    client, owner = _admin_client(monkeypatch)
    own_id, foreign_id = _seed_two_files(owner)
    result = client.get("/api/v1/integrations/paperless/archives")
    assert result.status_code == 200, result.text
    rows = result.json()
    assert len(rows) == 1
    assert rows[0]["file_id"] == own_id
    monkeypatch.setattr(get_settings(), "paperless_enabled", True)
    denied = client.post(f"/api/v1/integrations/paperless/{foreign_id}")
    assert denied.status_code == 403, denied.text


def test_legacy_wildcard_service_access_retained_outside_rcat_mode(monkeypatch):
    client, owner = _admin_client(monkeypatch)
    own_id, foreign_id = _seed_two_files(owner)
    settings = get_settings()
    principal = Principal(name="legacy-bootstrap", scopes={"*"}, auth_source="bootstrap")
    assert not may_bypass_file_ownership(principal)  # RCAT mode
    with SessionLocal() as db:
        # A legacy bootstrap principal is not allowed in RCAT mode.
        monkeypatch.setattr(settings, "rcat_institutional_only", False)
        assert may_bypass_file_ownership(principal)
        assert files._owned_file(db, foreign_id, principal).id == foreign_id
        assert integrations._owned_file(db, foreign_id, principal).id == foreign_id
