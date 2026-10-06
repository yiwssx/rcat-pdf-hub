from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import security
from app.filetypes import validate_uploaded_file
from app.identity import create_session_token, create_web_console_identity, decode_session_token
from app.db import SessionLocal
from app.main import app, migrate_legacy_web_console_ownership
from app.models import FileRecord, JobRecord
from app.passwords import hash_password, verify_password
from app.services import pdf_tools


def test_local_password_hash_round_trip():
    encoded = hash_password("correct-horse-battery-staple")
    assert encoded.startswith("scrypt:")
    assert verify_password("correct-horse-battery-staple", encoded)
    assert not verify_password("wrong-password", encoded)


def test_web_console_identity_is_stable(monkeypatch):
    monkeypatch.setattr("app.identity.settings.web_console_workspace_id", "rcat-test")
    first = create_web_console_identity()
    second = create_web_console_identity()
    assert first["name"] == second["name"] == "web-console:rcat-test"
    assert first["subject"] == second["subject"] == "workspace:rcat-test"


def test_local_admin_login_creates_admin_session(monkeypatch):
    password = "admin-password-for-test"
    monkeypatch.setattr("app.routers.auth.settings.local_admin_username", "admin")
    monkeypatch.setattr("app.routers.auth.settings.local_admin_password_hash", hash_password(password))
    monkeypatch.setattr("app.routers.auth.ensure_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)

    client = TestClient(app)
    response = client.post("/api/v1/auth/local/login", json={"username": "admin", "password": password})
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_admin"] is True
    assert payload["auth_source"] == "local-admin"
    assert payload["scopes"] == ["*"]

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["is_admin"] is True


def test_file_signature_validation_rejects_fake_pdf(tmp_path: Path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not-a-pdf")
    try:
        validate_uploaded_file(fake, "fake.pdf")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 415
    else:
        raise AssertionError("fake PDF must be rejected")


def test_file_signature_validation_normalizes_png(tmp_path: Path):
    image = tmp_path / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"payload")
    assert validate_uploaded_file(image, "image.png") == "image/png"


def test_pdf_organizer_reorders_and_rotates_pages(tmp_path: Path):
    source = tmp_path / "source.pdf"
    output = tmp_path / "organized.pdf"
    c = canvas.Canvas(str(source))
    for label in ("ONE", "TWO", "THREE"):
        c.drawString(72, 720, label)
        c.showPage()
    c.save()

    pdf_tools.organize(source, [{"page": 3, "rotation": 90}, {"page": 1, "rotation": 0}], output)
    reader = PdfReader(str(output))
    assert len(reader.pages) == 2
    assert "THREE" in (reader.pages[0].extract_text() or "")
    assert int(reader.pages[0].get("/Rotate", 0)) % 360 == 90
    assert "ONE" in (reader.pages[1].extract_text() or "")


def test_legacy_web_console_ownership_is_migrated(monkeypatch):
    monkeypatch.setattr("app.main.settings.web_console_auto_login", True)
    monkeypatch.setattr("app.main.settings.oidc_enabled", False)
    monkeypatch.setattr("app.main.settings.ldap_enabled", False)
    monkeypatch.setattr("app.main.settings.web_console_workspace_id", "rcat-test")
    monkeypatch.setattr("app.main.audit_event", lambda *args, **kwargs: None)

    db = SessionLocal()
    file = FileRecord(
        original_name="legacy.pdf",
        stored_name="legacy-migration-test.pdf",
        content_type="application/pdf",
        size=1,
        sha256="f" * 64,
        source_system="web-console:old-random-session",
    )
    job = JobRecord(
        operation="compress",
        input_file_ids_json="[]",
        params_json="{}",
        requested_by="web-console:another-old-session",
    )
    db.add(file)
    db.add(job)
    db.commit()
    file_id, job_id = file.id, job.id
    db.close()

    result = migrate_legacy_web_console_ownership()
    assert result["files"] >= 1
    assert result["jobs"] >= 1

    db = SessionLocal()
    assert db.get(FileRecord, file_id).source_system == "web-console:rcat-test"
    assert db.get(JobRecord, job_id).requested_by == "web-console:rcat-test"
    db.delete(db.get(FileRecord, file_id))
    db.delete(db.get(JobRecord, job_id))
    db.commit()
    db.close()


def test_job_history_cleanup_requires_manage_scope_and_preserves_active_jobs(monkeypatch):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    actor = "user:workflow-tester"
    db = SessionLocal()
    completed = JobRecord(
        operation="compress",
        status="completed",
        progress=100,
        input_file_ids_json="[]",
        params_json="{}",
        requested_by=actor,
    )
    queued = JobRecord(
        operation="compress",
        status="queued",
        progress=0,
        input_file_ids_json="[]",
        params_json="{}",
        requested_by=actor,
    )
    other = JobRecord(
        operation="compress",
        status="completed",
        progress=100,
        input_file_ids_json="[]",
        params_json="{}",
        requested_by="user:other",
    )
    db.add_all([completed, queued, other])
    db.commit()
    completed_id, queued_id, other_id = completed.id, queued.id, other.id
    db.close()

    client = TestClient(app)
    read_only = {
        "name": actor,
        "subject": "workflow-read-only",
        "display_name": "Workflow Tester",
        "groups": [],
        "scopes": ["jobs:read"],
        "source": "session",
        "is_identity_admin": False,
    }
    client.cookies.set("pdfhub_session", create_session_token(read_only))
    denied = client.delete("/api/v1/jobs/terminal")
    assert denied.status_code == 403

    manager = {**read_only, "scopes": ["jobs:read", "jobs:manage"]}
    client.cookies.set("pdfhub_session", create_session_token(manager))
    response = client.delete("/api/v1/jobs/terminal")
    assert response.status_code == 200
    assert response.json()["deleted"] == 1

    db = SessionLocal()
    assert db.get(JobRecord, completed_id) is None
    assert db.get(JobRecord, queued_id) is not None
    assert db.get(JobRecord, other_id) is not None
    db.close()


def test_legacy_web_console_cookie_is_normalized_to_stable_workspace(monkeypatch):
    monkeypatch.setattr("app.identity.settings.web_console_auto_login", True)
    monkeypatch.setattr("app.identity.settings.oidc_enabled", False)
    monkeypatch.setattr("app.identity.settings.ldap_enabled", False)
    monkeypatch.setattr("app.identity.settings.web_console_workspace_id", "rcat-stable")
    legacy = {
        "name": "web-console:old-random-cookie",
        "subject": "old-random-cookie",
        "display_name": "Web Console",
        "groups": [],
        "scopes": ["files:read"],
        "source": "web-console",
        "is_identity_admin": False,
    }
    decoded = decode_session_token(create_session_token(legacy))
    assert decoded["name"] == "web-console:rcat-stable"
    assert decoded["subject"] == "workspace:rcat-stable"
    assert "jobs:manage" in decoded["scopes"]
