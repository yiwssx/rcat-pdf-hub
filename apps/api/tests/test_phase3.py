from pathlib import Path
from types import SimpleNamespace

import pytest

from app import malware, storage
from app.identity import create_session_token, decode_session_token, identity_from_claims
from app.integrations import paperless


def test_session_token_round_trip():
    identity = {
        "name": "user:teacher@example.org",
        "subject": "oidc-subject-123",
        "display_name": "Teacher",
        "groups": ["teachers"],
        "scopes": ["files:read", "pdf:ocr"],
        "source": "oidc",
        "is_identity_admin": False,
    }
    decoded = decode_session_token(create_session_token(identity))
    assert decoded["name"] == identity["name"]
    assert decoded["subject"] == identity["subject"]
    assert decoded["groups"] == ["teachers"]
    assert set(decoded["scopes"]) == {"files:read", "pdf:ocr"}
    assert decoded["source"] == "oidc"


def test_identity_admin_group_receives_wildcard(monkeypatch):
    monkeypatch.setattr("app.identity.settings.admin_groups", "pdfhub-admins,system-admins")
    identity = identity_from_claims(
        {"sub": "42", "preferred_username": "admin", "groups": ["pdfhub-admins"]},
        "oidc",
    )
    assert identity["is_identity_admin"] is True
    assert identity["scopes"] == ["*"]


def test_clamav_scan_rejects_found(monkeypatch, tmp_path: Path):
    sample = tmp_path / "sample.pdf"
    sample.write_bytes(b"%PDF-test")
    monkeypatch.setattr(malware.settings, "clamav_enabled", True)
    monkeypatch.setattr(malware, "_request", lambda command, stream_path=None: "stream: Eicar-Test-Signature FOUND")
    with pytest.raises(malware.MalwareDetected, match="Eicar-Test-Signature"):
        malware.scan_file(sample)


def test_local_storage_commit(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    staged = tmp_path / "incoming.tmp"
    staged.write_bytes(b"hello")
    stored_name = storage.store_staged_file(staged, "originals", "hello.pdf")
    assert stored_name == "hello.pdf"
    assert storage.path_for_stored_name(stored_name).read_bytes() == b"hello"
    assert storage.delete_stored_name(stored_name) == 5


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def head_bucket(self, Bucket):
        return {"Bucket": Bucket}

    def upload_file(self, filename, bucket, key, **kwargs):
        self.objects[key] = Path(filename).read_bytes()

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[key])

    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)
        return {}


def test_s3_storage_round_trip(monkeypatch, tmp_path: Path):
    fake = FakeS3()
    monkeypatch.setattr(storage.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "s3_bucket", "pdfhub-test")
    monkeypatch.setattr(storage.settings, "s3_prefix", "tenant")
    monkeypatch.setattr(storage.settings, "s3_auto_create_bucket", False)
    monkeypatch.setattr(storage, "s3_client", lambda: fake)

    staged = tmp_path / "incoming.pdf"
    staged.write_bytes(b"%PDF-s3")
    stored_name = storage.store_staged_file(staged, "originals", "input.pdf")
    assert stored_name == "s3:tenant/originals/input.pdf"
    materialized = storage.path_for_stored_name(stored_name)
    assert materialized.read_bytes() == b"%PDF-s3"
    assert storage.delete_stored_name(stored_name) == len(b"%PDF-s3")


def test_paperless_archive_returns_task_id(monkeypatch, tmp_path: Path):
    document = tmp_path / "document.pdf"
    document.write_bytes(b"%PDF-paperless")
    record = SimpleNamespace(original_name="document.pdf", content_type="application/pdf")
    monkeypatch.setattr(paperless.settings, "paperless_enabled", True)
    monkeypatch.setattr(paperless.settings, "paperless_token", "token")
    monkeypatch.setattr(paperless.settings, "paperless_url", "http://paperless")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"task_id": "task-123"}

    monkeypatch.setattr(paperless.httpx, "post", lambda *args, **kwargs: Response())
    assert paperless.archive_to_paperless(record, document) == "task-123"
