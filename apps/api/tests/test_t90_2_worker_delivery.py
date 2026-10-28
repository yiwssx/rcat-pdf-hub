"""T90-2 worker integration: binary output ownership, expiry and kill switch."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select

from app import storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy


def _job(source: Path, owner: str, operation: str, mime: str, *,
         expires_at=None, job_owner: str | None = None) -> str:
    data = source.read_bytes()
    with SessionLocal() as db:
        db.add(ServicePolicy(service_name=owner, rate_limit_per_minute=120,
                             daily_job_limit=100, max_storage_mb=100, webhook_url=None))
        record = FileRecord(
            original_name=source.name, stored_name=source.name,
            content_type=mime, size=len(data), sha256=hashlib.sha256(data).hexdigest(),
            source_system=owner, expires_at=expires_at,
        )
        db.add(record)
        db.flush()
        job = JobRecord(
            operation=operation, status="queued", requested_by=job_owner or owner,
            input_file_ids_json=json.dumps([record.id]), params_json="{}",
        )
        db.add(job)
        db.commit()
        return job.id


def _make_tiff(path: Path) -> None:
    one = Image.new("RGB", (60, 80), "white")
    two = Image.new("RGB", (60, 80), "blue")
    try:
        one.save(path, format="TIFF", save_all=True, append_images=[two])
    finally:
        one.close()
        two.close()


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()


def test_t90_2_real_worker_owner_bound_tiff_pdf(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "originals" / "source.tiff"
    _make_tiff(source)
    original = source.read_bytes()
    owner = "user:t90-2-worker"
    job_id = _job(source, owner, "tiff-to-pdf", "image/tiff",
                  expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        artifact = db.get(FileRecord, output_id)
        links = db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all()
        assert job.status == "completed" and job.output_file_id == output_id
        assert artifact.content_type == "application/pdf" and artifact.source_system == owner
        assert len(links) == 1 and links[0].role == "result"
        result_file = storage.path_for_stored_name(artifact.stored_name)
        assert len(PdfReader(str(result_file), strict=True).pages) == 2
    assert source.read_bytes() == original


@pytest.mark.parametrize("case", ["revoked", "foreign", "expired", "wrong-mime"])
def test_t90_2_worker_rejects_unauthorized_queued_jobs(monkeypatch, tmp_path, case):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", case != "revoked")
    source = tmp_path / "originals" / (case + ".tiff")
    _make_tiff(source)
    original = source.read_bytes()
    job_id = _job(
        source, "user:t90-2-" + case, "tiff-to-pdf",
        "application/pdf" if case == "wrong-mime" else "image/tiff",
        expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1))
        if case == "expired" else None,
        job_owner="user:attacker" if case == "foreign" else None,
    )
    with pytest.raises(ValueError):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalar(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)) is None
    assert source.read_bytes() == original
