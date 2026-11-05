"""M09 authenticated AES-256 revision-6 protection, one-time dual password handoff."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
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
from app.routers import pdf_protect
from app.routers.jobs import _require_operation_scope, retry_job
from app.services import pdf_protect_handoff as handoff
from app.services.pdf_access_control import protect_pdf, unlock_pdf
from app.worker_tasks import _output_spec_for_job


USER = "M09-user-SECRET-ภาษาไทย"
OWNER = "M09-owner-SECRET"
JOB_ID = "d6386a5a-0d9a-400f-a0d1-bf4ff0856992"
KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")


class FakeValkey:
    def __init__(self):
        self.values = {}
        self.calls = []

    def set(self, key, value, *, nx, ex):
        self.calls.append((key, nx, ex))
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def getdel(self, key):
        return self.values.pop(key, None)

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)


class FakeQueue:
    name = "pdf"

    def __len__(self):
        return 0


def enable(monkeypatch, redis=None):
    flags = get_settings()
    monkeypatch.setattr(flags, "protect_pdf_tools_enabled", True)
    monkeypatch.setattr(flags, "protect_pdf_handoff_key", KEY)
    fake = redis or FakeValkey()
    monkeypatch.setattr(handoff, "redis_conn", fake)
    return fake


def make_source(path: Path) -> Path:
    c = Canvas(str(path))
    for number in (1, 2):
        c.setPageSize((420 + number * 10, 570 + number * 9))
        c.drawString(38, 400, f"M09 protected page {number}")
        c.showPage()
    c.save()
    return path


def _request(payload):
    encoded = (payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8")
    used = False

    async def receive():
        nonlocal used
        if used:
            return {"type": "http.request", "body": b"", "more_body": False}
        used = True
        return {"type": "http.request", "body": encoded, "more_body": False}

    return Request({"type": "http", "method": "POST",
                    "headers": [(b"content-type", b"application/json")]},
                   receive=receive)


def principal(owner="rcat-owner-a", scopes=None):
    return SimpleNamespace(
        name=owner, auth_source="oidc", is_bootstrap_admin=False,
        daily_job_limit=100, scopes=set(scopes if scopes is not None
                                        else {"pdf:protect", "jobs:manage"}),
    )


def seed(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _: "clean")
    storage.ensure_storage()
    source = make_source(tmp_path / "originals" / "input.pdf")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="rcat-owner-a", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=40, webhook_url=None,
        ))
        record = FileRecord(
            original_name="input.pdf", stored_name="input.pdf",
            content_type="application/pdf", size=source.stat().st_size,
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_system="rcat-owner-a",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(record)
        db.commit()
        return record.id, hashlib.sha256(source.read_bytes()).hexdigest()


async def submit(file_id, user=USER, owner=OWNER, who=None):
    with SessionLocal() as db:
        return await pdf_protect.protect_pdf_request(
            _request({"file_id": file_id, "user_password": user,
                      "owner_password": owner}),
            principal=who or principal(), db=db,
        )


def arrange(monkeypatch, tmp_path):
    redis = enable(monkeypatch)
    file_id, sha = seed(monkeypatch, tmp_path)
    monkeypatch.setattr(pdf_protect, "audit_event", lambda *_a, **_kw: True)
    monkeypatch.setattr(pdf_protect, "set_queue_depth", lambda *_a: None)
    queued = []

    def enqueue(operation, job_id):
        queued.append((operation, job_id))
        return FakeQueue(), SimpleNamespace(id="rq-" + job_id)

    monkeypatch.setattr(pdf_protect, "enqueue_processing_job", enqueue)
    return redis, file_id, sha, queued


def test_m09_handoff_ciphertext_ttl_no_plaintext_and_aad(monkeypatch):
    redis = enable(monkeypatch)
    handoff.publish_credentials(
        JOB_ID, "alice", "file-1",
        user_password=USER, owner_password=OWNER,
    )
    key, sealed = next(iter(redis.values.items()))
    assert key == f"pdfhub:m09:passwords:{JOB_ID}"
    assert redis.calls == [(key, True, 300)]
    assert USER.encode("utf-8") not in sealed
    assert OWNER.encode("utf-8") not in sealed
    with pytest.raises(RuntimeError, match="already staged"):
        handoff.publish_credentials(
            JOB_ID, "alice", "file-1", user_password=USER, owner_password=OWNER,
        )
    with pytest.raises(ValueError, match="could not be verified"):
        handoff.take_credentials(JOB_ID, "alice", "different-file")
    assert redis.values == {}
    with pytest.raises(ValueError, match="already consumed"):
        handoff.take_credentials(JOB_ID, "alice", "file-1")
    handoff.publish_credentials(
        JOB_ID, "alice", "file-1", user_password=USER, owner_password=OWNER,
    )
    assert handoff.take_credentials(JOB_ID, "alice", "file-1") == (USER, OWNER)
    assert redis.values == {}


def test_m09_disabled_and_bad_keys_fail_closed(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "protect_pdf_tools_enabled", False)
    assert _output_spec_for_job("protect-pdf") == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation("protect-pdf")
    monkeypatch.setattr(flags, "protect_pdf_tools_enabled", True)
    monkeypatch.setattr(flags, "protect_pdf_handoff_key", "")
    with pytest.raises(RuntimeError, match="not configured"):
        handoff.publish_credentials(
            JOB_ID, "alice", "file-1", user_password=USER, owner_password=OWNER,
        )
    with pytest.raises(ValueError, match="distinct"):
        Settings(protect_pdf_tools_enabled=True, protect_pdf_handoff_key="")
    with pytest.raises(ValueError, match="must differ"):
        Settings(protect_pdf_tools_enabled=True, protect_pdf_handoff_key=KEY,
                 unlock_pdf_tools_enabled=True, unlock_pdf_handoff_key=KEY)


@pytest.mark.parametrize("user,owner", [
    ("", "owner"), ("a", "a"), ("text\nnewline", "owner"),
    ("x" * 257, "owner"), ("valid", "\x00bad"),
    (False, "owner"), ("user", False),
])
def test_m09_invalid_password_pair_never_published(monkeypatch, user, owner):
    redis = enable(monkeypatch)
    with pytest.raises(ValueError):
        handoff.publish_credentials(
            JOB_ID, "alice", "file-1",
            user_password=user, owner_password=owner,
        )
    assert redis.values == {}


def test_m09_submission_pdf_binary_and_no_leaks(monkeypatch, tmp_path):
    redis, file_id, sha, queued = arrange(monkeypatch, tmp_path)
    job_out = asyncio.run(submit(file_id))
    assert job_out.operation == "protect-pdf" and job_out.params == {}
    assert queued == [("protect-pdf", job_out.id)]
    with SessionLocal() as db:
        job = db.get(JobRecord, job_out.id)
        persisted = job.params_json + job.input_file_ids_json + (job.error or "")
        assert USER not in persisted and OWNER not in persisted
        assert job.params_json == "{}" and job.rq_job_id == "rq-" + job.id
    assert len(redis.values) == 1
    assert USER.encode() not in next(iter(redis.values.values()))
    # Protected documents must not automatically enter Paperless.
    monkeypatch.setattr(worker_tasks, "_auto_archive",
                        lambda *_args: pytest.fail("M09 auto-archived protected content"))
    output_id = worker_tasks.process_job(job_out.id)
    assert redis.values == {}
    with SessionLocal() as db:
        job = db.get(JobRecord, job_out.id)
        out = db.get(FileRecord, output_id)
        assert job.status == "completed" and job.output_file_id == out.id
        assert out.source_system == "rcat-owner-a"
        assert out.content_type == "application/pdf"
        parts = db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job.id)
        ).all()
        assert len(parts) == 1 and parts[0].role == "result"
        encrypted_path = storage.path_for_stored_name(out.stored_name)
        encrypted = PdfReader(str(encrypted_path), strict=True)
        assert encrypted.is_encrypted
        assert int(encrypted.trailer["/Encrypt"]["/V"]) == 5
        assert int(encrypted.trailer["/Encrypt"]["/R"]) == 6
        assert encrypted.decrypt(USER)
        assert len(encrypted.pages) == 2
        assert "M09 protected page 1" in encrypted.pages[0].extract_text()
        assert encrypted.pages[1].mediabox.width == 440
        owner_reader = PdfReader(str(encrypted_path), strict=True)
        assert owner_reader.decrypt(OWNER)
        assert len(owner_reader.pages) == 2
        assert hashlib.sha256(storage.path_for_stored_name("input.pdf").read_bytes()).hexdigest() == sha
        clear = tmp_path / "unlocked.pdf"
        unlock_pdf(encrypted_path, clear, password=OWNER)
        assert not PdfReader(str(clear), strict=True).is_encrypted


@pytest.mark.parametrize("what", ["wrong_owner", "bad_mime", "expired"])
def test_m09_api_rejects_wrong_owner_mime_and_expiry(monkeypatch, tmp_path, what):
    redis, file_id, _, queued = arrange(monkeypatch, tmp_path)
    with SessionLocal() as db:
        item = db.get(FileRecord, file_id)
        if what == "bad_mime":
            item.content_type = "image/png"
        elif what == "expired":
            item.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    with pytest.raises(HTTPException) as err:
        asyncio.run(submit(
            file_id, who=principal(owner="rcat-owner-b") if what == "wrong_owner" else None,
        ))
    assert err.value.status_code == {"wrong_owner": 403, "bad_mime": 415, "expired": 410}[what]
    assert redis.values == {} and queued == []
    with SessionLocal() as db:
        assert db.scalars(select(JobRecord)).all() == []


def test_m09_invalid_json_does_not_echo_passwords():
    secret = "M09-DO-NOT-REFLECT"

    async def check(payload):
        with pytest.raises(HTTPException) as rejected:
            await pdf_protect._read_credentials_request(_request(payload))
        message = f"{rejected.value.status_code}:{rejected.value.detail}"
        assert secret not in message
        return rejected.value.status_code

    for data in [
        {"file_id": "file", "user_password": secret, "owner_password": secret},
        {"file_id": "file", "user_password": secret, "owner_password": "ok", "extra": secret},
        {"file_id": "file", "user_password": "value\n", "owner_password": secret},
        {"file_id": "file", "user_password": False, "owner_password": secret},
    ]:
        assert asyncio.run(check(data)) == 422
    assert asyncio.run(check({"file_id": "file", "user_password": secret * 500,
                              "owner_password": "owner"})) == 413


def test_m09_queue_failure_erases_secret_and_sanitizes(monkeypatch, tmp_path):
    redis, file_id, _, _ = arrange(monkeypatch, tmp_path)
    monkeypatch.setattr(pdf_protect, "enqueue_processing_job",
                        lambda *_args: (_ for _ in ()).throw(RuntimeError(USER)))
    with pytest.raises(HTTPException) as err:
        asyncio.run(submit(file_id))
    assert err.value.status_code == 503
    assert USER not in str(err.value.detail) and OWNER not in str(err.value.detail)
    assert redis.values == {}
    with SessionLocal() as db:
        jobs = db.scalars(select(JobRecord)).all()
        assert len(jobs) == 1 and jobs[0].status == "failed"
        assert USER not in jobs[0].params_json + (jobs[0].error or "")
        assert OWNER not in jobs[0].params_json + (jobs[0].error or "")


def test_m09_worker_revoked_flag_and_consumed_secret_fail_closed(monkeypatch, tmp_path):
    redis, file_id, _, _ = arrange(monkeypatch, tmp_path)
    job = asyncio.run(submit(file_id))
    monkeypatch.setattr(get_settings(), "protect_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="M09 protection failed"):
        worker_tasks.process_job(job.id)
    assert len(redis.values) == 1  # ciphertext expires via TTL
    assert list((tmp_path / "processed").iterdir()) == []
    monkeypatch.setattr(get_settings(), "protect_pdf_tools_enabled", True)
    redis.values.clear()
    with SessionLocal() as db:
        db.get(JobRecord, job.id).status = "queued"
        db.commit()
    with pytest.raises(RuntimeError, match="M09 protection failed"):
        worker_tasks.process_job(job.id)
    assert redis.values == {}


def test_m09_wrong_source_signature_denied_before_secret_consumed(monkeypatch, tmp_path):
    redis, file_id, _, _ = arrange(monkeypatch, tmp_path)
    item = asyncio.run(submit(file_id))
    original = storage.path_for_stored_name("input.pdf")
    original.write_bytes(b"%ZIP-unsafe")
    with pytest.raises(RuntimeError, match="M09 protection failed"):
        worker_tasks.process_job(item.id)
    assert len(redis.values) == 1
    assert list((tmp_path / "processed").iterdir()) == []


def test_m09_retry_requires_new_credentials(monkeypatch, tmp_path):
    redis, file_id, _, _ = arrange(monkeypatch, tmp_path)
    job = asyncio.run(submit(file_id))
    redis.values.clear()
    with pytest.raises(RuntimeError, match="M09 protection failed"):
        worker_tasks.process_job(job.id)
    with SessionLocal() as db:
        with pytest.raises(HTTPException) as err:
            retry_job(job.id, principal=principal(), db=db)
        assert err.value.status_code == 409
    _require_operation_scope(SimpleNamespace(operation="protect-pdf"), principal())
    with pytest.raises(HTTPException) as err:
        _require_operation_scope(
            SimpleNamespace(operation="protect-pdf"),
            principal(scopes={"jobs:manage"}),
        )
    assert err.value.status_code == 403


def test_m09_engine_rejects_encrypted_source_and_same_password(tmp_path):
    plain = make_source(tmp_path / "plain.pdf")
    locked = tmp_path / "locked.pdf"
    protect_pdf(plain, locked, user_password=USER, owner_password=OWNER)
    out = tmp_path / "should-not-exist.pdf"
    with pytest.raises(ValueError, match="already encrypted"):
        protect_pdf(locked, out, user_password=USER, owner_password=OWNER)
    with pytest.raises(ValueError, match="must differ"):
        protect_pdf(plain, out, user_password="same", owner_password="same")
    assert not out.exists()
