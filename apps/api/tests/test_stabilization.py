import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import audit, policy, principal_id, reconcile, storage, verify_storage
from app.db import SessionLocal
from app.models import FileRecord, JobRecord
from app.principal_id import principal_name_for_identity
from app.routers import files


def test_oidc_tenant_key_survives_display_rename(monkeypatch):
    monkeypatch.setattr(principal_id.settings, "oidc_issuer", "https://idp.example.org")
    before = {
        "source": "oidc",
        "subject": "immutable-subject-1",
        "display_name": "Alice",
        "name": "user:alice",
    }
    after = {**before, "display_name": "Alice Renamed", "name": "user:alice.new"}
    assert principal_name_for_identity(before) == principal_name_for_identity(after)


def test_oidc_same_display_different_subjects_are_isolated(monkeypatch):
    monkeypatch.setattr(principal_id.settings, "oidc_issuer", "https://idp.example.org")
    first = {"source": "oidc", "subject": "sub-a", "display_name": "Shared Name"}
    second = {"source": "oidc", "subject": "sub-b", "display_name": "Shared Name"}
    assert principal_name_for_identity(first) != principal_name_for_identity(second)


def test_oidc_issuer_is_part_of_tenant_key(monkeypatch):
    identity = {"source": "oidc", "subject": "same-subject"}
    monkeypatch.setattr(principal_id.settings, "oidc_issuer", "https://idp-a.example")
    first = principal_name_for_identity(identity)
    monkeypatch.setattr(principal_id.settings, "oidc_issuer", "https://idp-b.example")
    second = principal_name_for_identity(identity)
    assert first != second


def test_ldap_tenant_key_uses_subject_not_display():
    first = {"source": "ldap", "subject": "uid=a,ou=People,dc=example", "display_name": "Same"}
    second = {"source": "ldap", "subject": "uid=b,ou=People,dc=example", "display_name": "Same"}
    assert principal_name_for_identity(first) != principal_name_for_identity(second)


def test_postgres_quota_lock_exists_without_policy_row():
    captured = {}

    class Dialect:
        name = "postgresql"

    class Bind:
        dialect = Dialect()

    class FakeSession:
        def get_bind(self):
            return Bind()

        def execute(self, statement, params=None):
            captured["statement"] = str(statement)
            captured["params"] = params

    policy._lock_principal_quota(FakeSession(), "principal-with-default-policy")
    assert "pg_advisory_xact_lock" in captured["statement"]
    assert captured["params"] == {"service_name": "principal-with-default-policy"}


def test_old_queued_job_without_rq_identity_is_reconciled_failed():
    with SessionLocal() as db:
        job = JobRecord(
            operation="compress",
            status="queued",
            requested_by="service-reconcile",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    result = reconcile.reconcile_stale_jobs_once()
    assert result["reconciled_failed"] >= 1
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed"
        assert "no RQ job id" in job.error


def test_old_running_job_is_reconciled_after_timeout(monkeypatch):
    monkeypatch.setattr(reconcile.settings, "rq_job_timeout_seconds", 60)
    with SessionLocal() as db:
        job = JobRecord(
            operation="compress",
            status="running",
            requested_by="service-running",
            rq_job_id="irrelevant-because-timeout-wins",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            started_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    reconcile.reconcile_stale_jobs_once()
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed"
        assert "exceeded timeout" in job.error


def test_audit_is_daily_and_prunable(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(audit.settings, "data_dir", tmp_path)
    assert audit.audit_event("test.daily", "tester") is True
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert (tmp_path / "audit" / f"audit-{today}.jsonl").exists()

    old = tmp_path / "audit" / "audit-2000-01-01.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=365)).timestamp()
    import os
    os.utime(old, (old_time, old_time))
    assert audit.prune_audit_files(retention_days=30) == 1
    assert not old.exists()


def test_upload_route_runs_in_fastapi_threadpool():
    assert not inspect.iscoroutinefunction(files.upload_file)


def test_database_storage_consistency_verifier(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(verify_storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(verify_storage.settings, "storage_backend", "local")
    storage.ensure_storage()
    payload = b"verified-payload"
    digest = __import__("hashlib").sha256(payload).hexdigest()
    (tmp_path / "originals" / "verified.bin").write_bytes(payload)
    with SessionLocal() as db:
        db.add(
            FileRecord(
                original_name="verified.bin",
                stored_name="verified.bin",
                content_type="application/octet-stream",
                size=len(payload),
                sha256=digest,
                source_system="service-verify",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    result = verify_storage.verify_database_storage_consistency()
    assert result["failures"] == []
    assert result["verified"] >= 1
