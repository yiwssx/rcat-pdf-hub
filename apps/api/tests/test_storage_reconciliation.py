from fastapi.testclient import TestClient

from app import security, storage_reconciliation
from app.db import SessionLocal
from app.main import app
from app.models import FileRecord
from app.storage_reconciliation import reconcile_storage


def _record(name: str, stored_name: str, size: int) -> FileRecord:
    return FileRecord(
        original_name=name,
        stored_name=stored_name,
        content_type="application/pdf",
        size=size,
        sha256="a" * 64,
        source_system="reconcile-test",
    )


def test_local_reconciliation_reports_missing_orphan_size_and_duplicate(monkeypatch, tmp_path):
    originals = tmp_path / "originals"
    processed = tmp_path / "processed"
    originals.mkdir()
    processed.mkdir()

    (originals / "ok.pdf").write_bytes(b"ok")
    (processed / "mismatch.pdf").write_bytes(b"bad")
    (originals / "orphan.pdf").write_bytes(b"orphan")
    (originals / "dup.pdf").write_bytes(b"one")
    (processed / "dup.pdf").write_bytes(b"two")

    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_reconciliation.settings, "data_dir", tmp_path)

    db = SessionLocal()
    try:
        db.add_all(
            [
                _record("ok.pdf", "ok.pdf", 2),
                _record("missing.pdf", "missing.pdf", 7),
                _record("mismatch.pdf", "mismatch.pdf", 9),
                _record("dup.pdf", "dup.pdf", 3),
            ]
        )
        db.commit()

        report = reconcile_storage(db)
    finally:
        db.close()

    categories = {issue["category"] for issue in report["issues"]}
    assert report["dry_run"] is True
    assert report["backend"] == "local"
    assert report["database_records"] == 4
    assert report["storage_objects"] == 5
    assert report["healthy"] is False
    assert {"missing_object", "orphan_object", "size_mismatch", "duplicate_storage_name"} <= categories


class FakeS3:
    def list_objects_v2(self, **kwargs):
        assert kwargs["Bucket"] == "pdfhub-test"
        assert kwargs["Prefix"] == "pdfhub/"
        return {
            "IsTruncated": False,
            "Contents": [
                {"Key": "pdfhub/originals/ok.pdf", "Size": 2},
                {"Key": "pdfhub/processed/mismatch.pdf", "Size": 3},
                {"Key": "pdfhub/processed/orphan.pdf", "Size": 4},
                {"Key": "pdfhub/previews/ignored.png", "Size": 99},
            ],
        }


def test_s3_reconciliation_uses_managed_object_listing(monkeypatch):
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_reconciliation.settings, "s3_bucket", "pdfhub-test")
    monkeypatch.setattr(storage_reconciliation.settings, "s3_prefix", "pdfhub")
    monkeypatch.setattr(storage_reconciliation, "s3_client", lambda: FakeS3())

    db = SessionLocal()
    try:
        db.add_all(
            [
                _record("ok.pdf", "s3:pdfhub/originals/ok.pdf", 2),
                _record("missing.pdf", "s3:pdfhub/originals/missing.pdf", 7),
                _record("mismatch.pdf", "s3:pdfhub/processed/mismatch.pdf", 9),
            ]
        )
        db.commit()

        report = reconcile_storage(db)
    finally:
        db.close()

    categories = [issue["category"] for issue in report["issues"]]
    assert report["storage_objects"] == 3
    assert categories.count("missing_object") == 1
    assert categories.count("size_mismatch") == 1
    assert categories.count("orphan_object") == 1


def test_admin_reconciliation_endpoint_is_report_only(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_reconciliation.settings, "data_dir", tmp_path)

    client = TestClient(app)
    response = client.get(
        "/api/v1/admin/storage-reconciliation?detail_limit=25",
        headers={"X-API-Key": security.settings.admin_api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["healthy"] is True
    assert payload["issues"] == []
