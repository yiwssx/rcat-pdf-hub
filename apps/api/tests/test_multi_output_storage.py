"""T90 multi-output worker persistence: safety and legacy compatibility."""
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app import storage, worker_tasks
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.services.output_artifacts import stage_raster_pages


def _png():
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), (30, 70, 120)).save(stream, format="PNG")
    return stream.getvalue()


def _setup(monkeypatch, tmp_path, *, enabled=True, input_size=5):
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(worker_tasks.settings, "data_dir", tmp_path)
    monkeypatch.setattr(worker_tasks.settings, "multi_output_artifacts_enabled", enabled)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    (tmp_path / "originals" / "source.pdf").write_bytes(b"source")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="service-a", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=1, webhook_url=None,
        ))
        src = FileRecord(
            original_name="source.pdf", stored_name="source.pdf",
            content_type="application/pdf", size=input_size, sha256="a" * 64,
            source_system="service-a",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(src)
        db.flush()
        job = JobRecord(
            operation="pdf-to-images", status="queued",
            requested_by="service-a", input_file_ids_json=f'["{src.id}"]',
            params_json='{"format":"png","first_page":1,"last_page":2}',
        )
        db.add(job)
        db.commit()
        return job.id


def _fake_raster(_source, target, **_params):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("page-0001.png", _png())
        archive.writestr("page-0002.png", _png())


def test_flag_off_keeps_zip_as_only_persisted_output(monkeypatch, tmp_path):
    job_id = _setup(monkeypatch, tmp_path, enabled=False)
    monkeypatch.setattr(worker_tasks.pdf_tools, "pdf_to_images", _fake_raster)
    output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        rows = db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all()
        assert job.status == "completed"
        assert job.output_file_id == output_id
        assert len(rows) == 1 and rows[0].role == "bundle"
        assert db.scalar(select(FileRecord).where(FileRecord.id == output_id)).content_type == "application/zip"


def test_opt_in_persists_two_individual_images_and_retains_zip(monkeypatch, tmp_path):
    job_id = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(worker_tasks.pdf_tools, "pdf_to_images", _fake_raster)
    output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "completed" and job.output_file_id == output_id
        rows = db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all()
        assert len(rows) == 3
        assert {(r.role, r.ordinal) for r in rows} == {("bundle", None), ("part", 1), ("part", 2)}
        for item in rows:
            file = db.get(FileRecord, item.file_id)
            assert file.source_system == job.requested_by
            assert file.size > 0
            assert len(file.sha256) == 64
            assert storage.path_for_stored_name(file.stored_name).exists()
            if item.role == "part":
                assert file.content_type == "image/png"
                assert file.original_name.startswith("page-")


def test_aggregate_quota_blocks_zip_plus_pages_atomically(monkeypatch, tmp_path):
    job_id = _setup(monkeypatch, tmp_path, input_size=1024 * 1024 - 20)
    monkeypatch.setattr(worker_tasks.pdf_tools, "pdf_to_images", _fake_raster)
    with pytest.raises(RuntimeError, match="storage quota"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.output_file_id is None
        assert db.scalars(select(JobOutputArtifact)).all() == []
        assert db.scalars(select(FileRecord)).all().__len__() == 1
    assert list((tmp_path / "processed").iterdir()) == []


def test_store_failure_rolls_back_links_and_cleans_files(monkeypatch, tmp_path):
    job_id = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(worker_tasks.pdf_tools, "pdf_to_images", _fake_raster)
    original = worker_tasks.store_staged_file
    seen = []

    def fail_on_part_two(path, area, filename=None):
        if filename and filename.endswith("page-0002.png"):
            raise OSError("simulated storage backend outage")
        result = original(path, area, filename=filename)
        seen.append(result)
        return result

    monkeypatch.setattr(worker_tasks, "store_staged_file", fail_on_part_two)
    with pytest.raises(OSError, match="simulated storage"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact)).all() == []
        assert len(db.scalars(select(FileRecord)).all()) == 1
    for stored_name in seen:
        with pytest.raises(FileNotFoundError):
            storage.path_for_stored_name(stored_name)


def test_generated_zip_path_traversal_is_rejected(monkeypatch, tmp_path):
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../secrets.png", _png())
    with pytest.raises(ValueError, match="Unsafe"):
        stage_raster_pages(zip_path, tmp_path / "staged", first_page=1, max_bytes=100000)


def test_generated_zip_wrong_image_content_is_rejected(tmp_path):
    path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("page-0001.png", b"this-is-not-a-png")
    with pytest.raises(ValueError, match="Invalid raster image"):
        stage_raster_pages(path, tmp_path / "staged", first_page=1, max_bytes=100000)


def test_generated_zip_is_bounded_by_decompressed_bytes(tmp_path):
    path = tmp_path / "large.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("page-0001.png", _png())
    with pytest.raises(ValueError, match="byte limit"):
        stage_raster_pages(path, tmp_path / "staged", first_page=1, max_bytes=20)


def test_generated_zip_requires_ordered_contiguous_page_numbers(tmp_path):
    path = tmp_path / "unordered.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("page-0001.png", _png())
        archive.writestr("page-0003.png", _png())
    with pytest.raises(ValueError, match="ordered and contiguous"):
        stage_raster_pages(path, tmp_path / "staged", first_page=1, max_bytes=100000)
