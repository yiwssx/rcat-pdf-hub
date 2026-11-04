"""M08 unlock PDF: AEAD password handoff, real cryptographic output and no leaks.

This test suite deliberately passes sentinel passwords and asserts that none
are persisted in JobRecord, queued arguments, Valkey plaintext or responses.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select
from starlette.requests import Request

from app import storage, worker_tasks
from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import pdf_unlock
from app.routers.jobs import _require_operation_scope, retry_job
from app.services import pdf_unlock_handoff as handoff
from app.services.pdf_access_control import protect_pdf
from app.worker_tasks import _output_spec_for_job


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.set_calls = []

    def set(self, key, value, *, nx, ex):
        self.set_calls.append((key, nx, ex))
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def getdel(self, key):
        return self.values.pop(key, None)

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)


class QueueStub:
    name = "pdf"

    def __len__(self):
        return 0


def enable_m08(monkeypatch, redis=None):
    flags = get_settings()
    monkeypatch.setattr(flags, "unlock_pdf_tools_enabled", True)
    key = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
    monkeypatch.setattr(flags, "unlock_pdf_handoff_key", key)
    fake = redis or MemoryRedis()
    monkeypatch.setattr(handoff, "redis_conn", fake)
    return fake


def make_pdf(path: Path):
    canvas = Canvas(str(path))
    canvas.drawString(52, 600, "M08 ENCRYPTED SOURCE PDF")
    canvas.showPage()
    canvas.save()
    return path


def _asgi_request(payload: dict | str):
    encoded = (payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8")
    received = False

    async def receiver():
        nonlocal received
        if received:
            return {"type": "http.request", "body": b"", "more_body": False}
        received = True
        return {"type": "http.request", "body": encoded, "more_body": False}

    return Request({
        "type": "http", "method": "POST",
        "headers": [(b"content-type", b"application/json")],
    }, receive=receiver)


def seed(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    plain = make_pdf(tmp_path / "plain-original.pdf")
    source = tmp_path / "originals" / "encrypted.pdf"
    protect_pdf(
        plain, source,
        user_password="M08-Password-SECRET-ภาษาไทย",
        owner_password="M08-owner-SECRET",
    )
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="rcat-user-a",
            rate_limit_per_minute=100, daily_job_limit=100,
            max_storage_mb=40, webhook_url=None,
        ))
        rec = FileRecord(
            original_name="encrypted.pdf", stored_name="encrypted.pdf",
            content_type="application/pdf", size=source.stat().st_size,
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_system="rcat-user-a",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(rec)
        db.commit()
        return rec.id, hashlib.sha256(source.read_bytes()).hexdigest()


def _principal(owner="rcat-user-a", scopes=None):
    return SimpleNamespace(
        name=owner, is_bootstrap_admin=False, daily_job_limit=100,
        auth_source="oidc",
        scopes=set(scopes or {"pdf:unlock", "jobs:manage"}),
    )


async def _submit(file_id, password="M08-Password-SECRET-ภาษาไทย", principal=None):
    with SessionLocal() as db:
        return await pdf_unlock.unlock_pdf_request(
            _asgi_request({"file_id": file_id, "password": password}),
            principal=principal or _principal(), db=db,
        )


def arrange_api(monkeypatch, tmp_path):
    fake = enable_m08(monkeypatch)
    file_id, original_sha = seed(monkeypatch, tmp_path)
    monkeypatch.setattr(pdf_unlock, "audit_event", lambda *args, **kwargs: True)
    submitted = []

    def fake_enqueue(operation, job_id):
        submitted.append((operation, job_id))
        return QueueStub(), SimpleNamespace(id=f"rq-{job_id}")

    monkeypatch.setattr(pdf_unlock, "enqueue_processing_job", fake_enqueue)
    monkeypatch.setattr(pdf_unlock, "set_queue_depth", lambda *_: None)
    return fake, file_id, original_sha, submitted


def test_m08_handoff_ciphertext_is_bound_single_use_and_ttl(monkeypatch):
    fake = enable_m08(monkeypatch)
    job_id = "d6386a5a-0d9a-400f-a0d1-bf4ff0856992"
    handoff.publish_password(job_id, "alice", "file-01", "secret-日本語")
    assert len(fake.values) == 1
    key, ciphertext = next(iter(fake.values.items()))
    assert key.endswith(job_id)
    assert b"secret-" not in ciphertext
    assert fake.set_calls == [(key, True, 300)]
    with pytest.raises(RuntimeError, match="already exists"):
        handoff.publish_password(job_id, "alice", "file-01", "different")
    with pytest.raises(ValueError, match="could not be verified"):
        handoff.take_password(job_id, "bob", "file-01")
    assert fake.values == {}
    with pytest.raises(ValueError, match="expired or already used"):
        handoff.take_password(job_id, "alice", "file-01")
    handoff.publish_password(job_id, "alice", "file-01", "secret-日本語")
    assert handoff.take_password(job_id, "alice", "file-01") == "secret-日本語"
    assert fake.values == {}


def test_m08_broken_and_missing_key_fail_closed(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "unlock_pdf_tools_enabled", False)
    assert _output_spec_for_job("unlock-pdf") == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation("unlock-pdf")
    monkeypatch.setattr(flags, "unlock_pdf_tools_enabled", True)
    monkeypatch.setattr(flags, "unlock_pdf_handoff_key", "")
    with pytest.raises(RuntimeError, match="not configured"):
        handoff.publish_password("d6386a5a-0d9a-400f-a0d1-bf4ff0856992", "a", "b", "secret")
    with pytest.raises(ValueError, match="dedicated"):
        Settings(unlock_pdf_tools_enabled=True, unlock_pdf_handoff_key="")
    assert not handoff.valid_handoff_key("not-a-valid-key")


def test_m08_submission_is_secret_free_everywhere(monkeypatch, tmp_path):
    fake, file_id, original_sha, queued = arrange_api(monkeypatch, tmp_path)
    result = asyncio.run(_submit(file_id))
    assert result.operation == "unlock-pdf"
    assert result.params == {}
    assert len(queued) == 1 and queued[0] == ("unlock-pdf", result.id)
    assert len(fake.values) == 1
    assert b"M08-Password-SECRET" not in next(iter(fake.values.values()))
    with SessionLocal() as db:
        job = db.get(JobRecord, result.id)
        public_dump = json.dumps({
            "params": job.params_json,
            "ids": job.input_file_ids_json,
            "error": job.error,
            "rq": job.rq_job_id,
        })
        assert "M08-Password-SECRET" not in public_dump
        assert job.params_json == "{}"
        assert job.input_file_ids_json == json.dumps([file_id])
        assert job.rq_job_id == f"rq-{job.id}"
    output_id = worker_tasks.process_job(result.id)
    assert fake.values == {}
    with SessionLocal() as db:
        job = db.get(JobRecord, result.id)
        output = db.get(FileRecord, output_id)
        assert job.status == "completed" and job.output_file_id == output_id
        assert output.source_system == "rcat-user-a"
        assert output.content_type == "application/pdf"
        artifact = db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job.id)).all()
        assert len(artifact) == 1 and artifact[0].role == "result"
        original = storage.path_for_stored_name("encrypted.pdf")
        assert hashlib.sha256(original.read_bytes()).hexdigest() == original_sha
        decrypted = PdfReader(str(storage.path_for_stored_name(output.stored_name)), strict=True)
        assert not decrypted.is_encrypted
        assert "M08 ENCRYPTED SOURCE PDF" in decrypted.pages[0].extract_text()


@pytest.mark.parametrize("password", ["wrong", "not-the-password", "owner-password!"])
def test_m08_wrong_password_fails_with_generic_error(monkeypatch, tmp_path, password):
    fake, file_id, _, _ = arrange_api(monkeypatch, tmp_path)
    result = asyncio.run(_submit(file_id, password=password))
    with pytest.raises(RuntimeError, match="M08 unlock failed"):
        worker_tasks.process_job(result.id)
    assert fake.values == {}
    with SessionLocal() as db:
        job = db.get(JobRecord, result.id)
        assert job.status == "failed" and job.output_file_id is None
        assert "password" not in (job.error or "").lower() or "resubmit" in (job.error or "")
        assert password not in job.params_json + (job.error or "")
    assert list((tmp_path / "processed").iterdir()) == []


def test_m08_worker_missing_ephemeral_secret_no_output(monkeypatch, tmp_path):
    fake, file_id, _, _ = arrange_api(monkeypatch, tmp_path)
    result = asyncio.run(_submit(file_id))
    fake.values.clear()  # TTL expiry / eviction / cancellation
    with pytest.raises(RuntimeError, match="M08 unlock failed"):
        worker_tasks.process_job(result.id)
    with SessionLocal() as db:
        assert db.get(JobRecord, result.id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == result.id)).all() == []


def test_m08_revoked_feature_does_not_consume_or_decrypt(monkeypatch, tmp_path):
    fake, file_id, _, _ = arrange_api(monkeypatch, tmp_path)
    result = asyncio.run(_submit(file_id))
    monkeypatch.setattr(get_settings(), "unlock_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="M08 unlock failed"):
        worker_tasks.process_job(result.id)
    assert len(fake.values) == 1  # encrypted only, hard TTL still expires
    assert list((tmp_path / "processed").iterdir()) == []


def test_m08_owner_scope_expiry_and_input_mime_rejected(monkeypatch, tmp_path):
    fake, file_id, _, _ = arrange_api(monkeypatch, tmp_path)
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(_submit(file_id, principal=_principal(owner="different-rcat-account")))
    assert rejected.value.status_code == 403
    with SessionLocal() as db:
        rec = db.get(FileRecord, file_id)
        rec.content_type = "application/octet-stream"
        db.commit()
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(_submit(file_id))
    assert rejected.value.status_code == 415
    assert fake.values == {}
    with SessionLocal() as db:
        assert db.scalars(select(JobRecord)).all() == []


def test_m08_http_validation_does_not_reflect_secret():
    marker = "SECRET-DO-NOT-REFLECT-42"
    async def reject(payload):
        try:
            await pdf_unlock._read_password_request(_asgi_request(payload))
        except HTTPException as err:
            return f"{err.status_code}:{err.detail}"
        raise AssertionError("Expected a safe request rejection")
    for bad in [
        {"file_id": "fake-id", "password": marker, "url": "http://localhost"},
        {"file_id": "fake-id", "password": marker + "\n"},
        {"file_id": "fake-id", "password": marker * 400},
        {"file_id": "fake-id", "password": False},
    ]:
        message = asyncio.run(reject(bad))
        assert marker not in message and message.startswith(("413:", "422:"))


def test_m08_queue_failure_erases_ciphertext(monkeypatch, tmp_path):
    fake, file_id, _, _ = arrange_api(monkeypatch, tmp_path)
    def broken_queue(op, job_id):
        raise RuntimeError("queue offline")
    monkeypatch.setattr(pdf_unlock, "enqueue_processing_job", broken_queue)
    with pytest.raises(HTTPException) as rejected:
        asyncio.run(_submit(file_id))
    assert rejected.value.status_code == 503
    assert fake.values == {}
    with SessionLocal() as db:
        jobs = db.scalars(select(JobRecord)).all()
        assert len(jobs) == 1 and jobs[0].status == "failed"
        assert jobs[0].params_json == "{}"
        assert "M08-Password-SECRET" not in (jobs[0].error or "")


def test_m08_retry_rejected_without_password(monkeypatch, tmp_path):
    fake, file_id, _, _ = arrange_api(monkeypatch, tmp_path)
    item = asyncio.run(_submit(file_id, password="wrong"))
    with pytest.raises(RuntimeError):
        worker_tasks.process_job(item.id)
    assert fake.values == {}
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as rejected:
            retry_job(item.id, principal=_principal(), db=db)
        assert rejected.value.status_code == 409
        assert db.scalars(select(JobRecord)).all().__len__() == 1
    job = SimpleNamespace(operation="unlock-pdf")
    _require_operation_scope(job, _principal())
    with pytest.raises(HTTPException) as denied:
        _require_operation_scope(job, _principal(scopes={"jobs:manage"}))
    assert denied.value.status_code == 403
