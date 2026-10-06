from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import security
from app.filetypes import validate_uploaded_file
from app.identity import create_web_console_identity
from app.main import app
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
