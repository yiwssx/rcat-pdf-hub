import socket
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from reportlab.pdfgen import canvas

from app import audit, cleanup, storage, webhooks, worker_tasks
from app.db import SessionLocal
from app.models import FileRecord, JobRecord, ServicePolicy
from app.policy import ensure_daily_job_quota, ensure_rate_limit, ensure_storage_quota
from app.routers.admin import _require_bootstrap_admin
from app.security import Principal
from app.services import pdf_tools


def _policy(db, name="service-a", *, storage_mb=10, daily=100, rate=100, webhook_url=None):
    db.add(ServicePolicy(service_name=name, rate_limit_per_minute=rate, daily_job_limit=daily, max_storage_mb=storage_mb, webhook_url=webhook_url)); db.commit()


def _configure_data_dir(monkeypatch, tmp_path):
    for module in (audit, cleanup, storage):
        monkeypatch.setattr(module.settings, "data_dir", tmp_path)
    storage.ensure_storage()


def _make_worker_job(monkeypatch, tmp_path, *, storage_mb=10, recorded_input_size=5):
    _configure_data_dir(monkeypatch, tmp_path)
    with SessionLocal() as db:
        _policy(db, storage_mb=storage_mb); (tmp_path / "originals" / "input.pdf").write_bytes(b"input")
        record = FileRecord(original_name="input.pdf", stored_name="input.pdf", content_type="application/pdf", size=recorded_input_size, sha256="a" * 64, source_system="service-a", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add(record); db.commit(); db.refresh(record)
        job = JobRecord(operation="compress", status="queued", requested_by="service-a", input_file_ids_json=f'["{record.id}"]')
        db.add(job); db.commit(); db.refresh(job); return job.id


def test_storage_quota_counts_active_files():
    with SessionLocal() as db:
        _policy(db, storage_mb=1)
        db.add(FileRecord(original_name="a.pdf", stored_name="a.pdf", content_type="application/pdf", size=900_000, sha256="a" * 64, source_system="service-a", expires_at=datetime.now(timezone.utc) + timedelta(hours=1))); db.commit()
        with pytest.raises(HTTPException) as exc: ensure_storage_quota(db, "service-a", 1, 200_000)
        assert exc.value.status_code == 413


def test_daily_job_quota_is_enforced():
    with SessionLocal() as db:
        _policy(db, daily=1); db.add(JobRecord(operation="compress", requested_by="service-a")); db.commit()
        with pytest.raises(HTTPException) as exc: ensure_daily_job_quota(db, "service-a", 1)
        assert exc.value.status_code == 429


def test_rate_limit_backend_failure_is_fail_closed(monkeypatch):
    class BrokenRedis:
        def incr(self, _key): raise ConnectionError("down")
    monkeypatch.setitem(sys.modules, "app.queue", types.SimpleNamespace(redis_conn=BrokenRedis()))
    with pytest.raises(HTTPException) as exc: ensure_rate_limit("service-a", 10)
    assert exc.value.status_code == 503


def test_rate_limit_exceeded_returns_429(monkeypatch):
    class BusyRedis:
        def incr(self, _key): return 2
        def expire(self, _key, _ttl): raise AssertionError("expire must not be called for an existing bucket")
    monkeypatch.setitem(sys.modules, "app.queue", types.SimpleNamespace(redis_conn=BusyRedis()))
    with pytest.raises(HTTPException) as exc: ensure_rate_limit("service-a", 1)
    assert exc.value.status_code == 429


def test_audit_disk_failure_is_best_effort(monkeypatch):
    monkeypatch.setattr(audit.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk unavailable")))
    assert audit.audit_event("test.event", "tester") is False


def _addr(ip: str, port: int = 443):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, port))]


def test_webhook_global_wildcard_is_rejected(): assert not webhooks._host_allowed("anything.example.org", ["*"])


def test_webhook_private_resolution_blocked_by_default(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "webhook_allowed_hosts", "hook.example.org"); monkeypatch.setattr(webhooks.settings, "webhook_allow_private_networks", False); monkeypatch.setattr(webhooks.socket, "getaddrinfo", lambda *_args, **_kwargs: _addr("127.0.0.1"))
    with pytest.raises(ValueError, match="non-public"): webhooks.validate_webhook_url("https://hook.example.org/events")


def test_webhook_public_resolution_allowed(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "webhook_allowed_hosts", "hook.example.org"); monkeypatch.setattr(webhooks.settings, "webhook_allow_private_networks", False); monkeypatch.setattr(webhooks.socket, "getaddrinfo", lambda *_args, **_kwargs: _addr("93.184.216.34"))
    assert webhooks.validate_webhook_url("https://hook.example.org/events") == "https://hook.example.org/events"


def test_private_webhook_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "webhook_allowed_hosts", "hook.internal"); monkeypatch.setattr(webhooks.settings, "webhook_allow_private_networks", True); monkeypatch.setattr(webhooks.socket, "getaddrinfo", lambda *_args, **_kwargs: _addr("10.0.0.10"))
    assert webhooks.validate_webhook_url("http://hook.internal/events") == "http://hook.internal/events"


def test_dispatch_network_failure_never_raises(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "webhook_allowed_hosts", "hook.example.org"); monkeypatch.setattr(webhooks.settings, "webhook_allow_private_networks", False); monkeypatch.setattr(webhooks.socket, "getaddrinfo", lambda *_args, **_kwargs: _addr("93.184.216.34")); monkeypatch.setattr(webhooks.time, "sleep", lambda _seconds: None); monkeypatch.setattr(webhooks.httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")))
    with SessionLocal() as db:
        _policy(db, webhook_url="https://hook.example.org/events"); job = JobRecord(operation="compress", status="completed", progress=100, requested_by="service-a", finished_at=datetime.now(timezone.utc)); db.add(job); db.commit(); db.refresh(job); assert webhooks.dispatch_job_webhook(db, job) is False


def test_worker_rejects_output_that_exceeds_storage_quota(monkeypatch, tmp_path):
    job_id = _make_worker_job(monkeypatch, tmp_path, storage_mb=1, recorded_input_size=900_000); monkeypatch.setattr(worker_tasks.pdf_tools, "compress", lambda _src, dst: dst.write_bytes(b"x" * 200_000))
    with pytest.raises(RuntimeError, match="storage quota"): worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id); assert job.status == "failed"; assert job.output_file_id is None; assert len(db.query(FileRecord).filter(FileRecord.source_system == "service-a").all()) == 1
    assert not (tmp_path / "processed" / f"{job_id}.pdf").exists()


def test_audit_disk_failure_does_not_flip_completed_job(monkeypatch, tmp_path):
    job_id = _make_worker_job(monkeypatch, tmp_path); monkeypatch.setattr(worker_tasks.pdf_tools, "compress", lambda _src, dst: dst.write_bytes(b"result")); monkeypatch.setattr(audit.os, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk unavailable"))); output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id); assert job.status == "completed"; assert job.output_file_id == output_id


def test_webhook_exception_does_not_flip_completed_job(monkeypatch, tmp_path):
    job_id = _make_worker_job(monkeypatch, tmp_path); monkeypatch.setattr(worker_tasks.pdf_tools, "compress", lambda _src, dst: dst.write_bytes(b"result")); monkeypatch.setattr(worker_tasks, "dispatch_job_webhook", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("webhook bug"))); output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id); assert job.status == "completed"; assert job.output_file_id == output_id


def test_cleanup_purges_expired_metadata_and_protects_active_inputs(monkeypatch, tmp_path):
    _configure_data_dir(monkeypatch, tmp_path); expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
    with SessionLocal() as db:
        removable = FileRecord(original_name="old.pdf", stored_name="old.pdf", content_type="application/pdf", size=3, sha256="a" * 64, source_system="service-a", expires_at=expired_at); protected = FileRecord(original_name="busy.pdf", stored_name="busy.pdf", content_type="application/pdf", size=4, sha256="b" * 64, source_system="service-a", expires_at=expired_at); db.add_all([removable, protected]); db.commit(); db.refresh(removable); db.refresh(protected); db.add(JobRecord(operation="compress", status="queued", requested_by="service-a", input_file_ids_json=f'["{protected.id}"]')); db.commit(); removable_id, protected_id = removable.id, protected.id
    (tmp_path / "originals" / "old.pdf").write_bytes(b"old"); (tmp_path / "originals" / "busy.pdf").write_bytes(b"busy"); result = cleanup.cleanup_once(); assert result["expired_records_purged"] == 1
    with SessionLocal() as db: assert db.get(FileRecord, removable_id) is None; assert db.get(FileRecord, protected_id) is not None


def test_page_number_format_blocks_attribute_traversal(tmp_path: Path):
    source = tmp_path / "source.pdf"; output = tmp_path / "numbered.pdf"; c = canvas.Canvas(str(source), pagesize=(595, 842)); c.showPage(); c.save()
    with pytest.raises(ValueError, match="plain"): pdf_tools.add_page_numbers(source, output, format_text="{page.__class__}")


def test_sensitive_admin_scope_requires_bootstrap_admin():
    with pytest.raises(HTTPException) as exc: _require_bootstrap_admin(Principal(name="delegated", scopes={"admin:keys"}))
    assert exc.value.status_code == 403
