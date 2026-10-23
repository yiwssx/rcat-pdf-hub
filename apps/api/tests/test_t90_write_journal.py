"""T90-0.9 opt-in durable write journal and claim-once worker fencing."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import storage, worker_tasks, write_journal
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, FileRecord, JobRecord, ServicePolicy


def _prepare(monkeypatch, tmp_path, *, enabled=True, multi=False):
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(worker_tasks.settings, "artifact_write_journal_enabled", enabled)
    monkeypatch.setattr(worker_tasks.settings, "multi_output_artifacts_enabled", multi)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _: "clean")
    storage.ensure_storage()
    (tmp_path / "originals" / "source.pdf").write_bytes(b"%PDF-1.4\n%mock\n")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="fence-test", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=50, webhook_url=None,
        ))
        original = FileRecord(
            original_name="source.pdf", stored_name="source.pdf",
            content_type="application/pdf", size=15, sha256="a" * 64,
            source_system="fence-test",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(original)
        db.flush()
        job = JobRecord(
            operation="compress", status="queued", progress=0,
            requested_by="fence-test", params_json="{}",
            input_file_ids_json=f'["{original.id}"]',
        )
        db.add(job)
        db.commit()
        return job.id


def _mock_compress(_source, dest):
    dest.write_bytes(b"%PDF-1.4\n%%EOF\n")


def test_claim_is_unique_and_cannot_retake_running_or_expired_job(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    with SessionLocal() as a, SessionLocal() as b:
        job_a = a.get(JobRecord, job_id)
        job_b = b.get(JobRecord, job_id)
        token = write_journal.claim_queued_job(a, job_a, 90)
        assert token
        assert write_journal.claim_queued_job(b, job_b, 90) is None
        b.refresh(job_b)
        assert job_b.status == "running" and job_b.lease_token == token
        job_b.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        b.commit()
        assert write_journal.claim_queued_job(a, job_a, 90) is None
        assert write_journal.lease_is_current(b, job_b, token) is False


def test_fenced_worker_writes_durable_intent_then_commits_with_result(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(worker_tasks.pdf_tools, "compress", _mock_compress)
    real_store = worker_tasks.store_staged_file
    seen = []

    def assert_journal_before_upload(path, area, filename=None):
        with SessionLocal() as db:
            rows = db.scalars(select(ArtifactWriteJournal)).all()
            assert len(rows) == 1
            assert rows[0].state == "planned"
            assert rows[0].stored_name == filename
            assert db.scalars(select(FileRecord).where(
                FileRecord.stored_name == filename
            )).all() == []
            seen.append(rows[0].lease_token)
        return real_store(path, area, filename=filename)

    monkeypatch.setattr(worker_tasks, "store_staged_file", assert_journal_before_upload)
    file_id = worker_tasks.process_job(job_id)
    assert seen and len(seen) == 1
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        result = db.get(FileRecord, file_id)
        journal = db.scalar(select(ArtifactWriteJournal))
        assert job.status == "completed"
        assert job.lease_epoch == 1 and job.lease_token == seen[0]
        assert result.id == job.output_file_id
        assert result.stored_name == f"{job_id}-{job.lease_token}.pdf"
        assert journal.state == "committed" and journal.file_id == file_id
        assert journal.lease_epoch == 1 and journal.lease_token == job.lease_token
        assert result.stored_name == journal.stored_name
        assert storage.path_for_stored_name(result.stored_name).exists()
    # RQ duplicate delivery cannot overwrite or generate any new journal.
    assert worker_tasks.process_job(job_id) == ""
    with SessionLocal() as db:
        assert db.scalar(select(ArtifactWriteJournal).where(
            ArtifactWriteJournal.job_id == job_id
        )).state == "committed"


def test_partially_written_local_object_is_compensated(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(worker_tasks.pdf_tools, "compress", _mock_compress)
    original = worker_tasks.store_staged_file

    def uploaded_but_lost_response(path, area, filename=None):
        original(path, area, filename=filename)
        raise OSError("ack failed after bytes persisted")

    monkeypatch.setattr(worker_tasks, "store_staged_file", uploaded_but_lost_response)
    with pytest.raises(OSError, match="ack failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        rows = db.scalars(select(ArtifactWriteJournal)).all()
        assert job.status == "failed"
        assert job.output_file_id is None
        assert len(rows) == 1 and rows[0].state == "compensated"
        assert rows[0].file_id is None
        assert db.scalars(select(FileRecord).where(
            FileRecord.source_system == "fence-test",
            FileRecord.original_name != "source.pdf",
        )).all() == []
    assert list((tmp_path / "processed").iterdir()) == []


def test_failed_compensation_preserves_needs_review_in_db(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(worker_tasks.pdf_tools, "compress", _mock_compress)
    real_store = worker_tasks.store_staged_file

    def uploaded_but_lost_response(path, area, filename=None):
        real_store(path, area, filename=filename)
        raise OSError("S3-like upload failure")

    monkeypatch.setattr(worker_tasks, "store_staged_file", uploaded_but_lost_response)
    monkeypatch.setattr(
        worker_tasks, "delete_stored_name",
        lambda _name: (_ for _ in ()).throw(OSError("cleanup unavailable")),
    )
    with pytest.raises(OSError, match="S3-like upload failure"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        record = db.scalar(select(ArtifactWriteJournal))
        assert job.status == "failed" and record.state == "needs_review"
        assert record.stored_name.startswith(f"{job_id}-")
        assert db.scalars(select(FileRecord).where(
            FileRecord.stored_name == record.stored_name,
        )).all() == []
    assert list((tmp_path / "processed").iterdir())  # retained for manual inspection


def test_uncommitted_intentions_survive_worker_death_and_are_not_auto_deleted(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        token = write_journal.claim_queued_job(db, job, 90)
        destination = storage.planned_processed_stored_name(f"{job_id}-{token}.pdf")
        write_journal.reserve_writes(db, job, token, [(destination, "result")])
    # Simulates SIGKILL immediately after the reservation was persisted.
    with SessionLocal() as db:
        row = db.scalar(select(ArtifactWriteJournal))
        assert row.state == "planned" and row.stored_name == destination
        assert db.get(JobRecord, job_id).status == "running"
        assert db.scalars(select(FileRecord).where(
            FileRecord.stored_name == destination
        )).all() == []
    assert not (tmp_path / "processed" / destination).exists()


def test_reservation_requires_current_fence_and_refuses_duplicate_names(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        token = write_journal.claim_queued_job(db, job, 90)
        name = storage.planned_processed_stored_name(f"{job_id}-{token}.pdf")
        with pytest.raises(ValueError, match="Duplicate"):
            write_journal.reserve_writes(db, job, token, [(name, "result"), (name, "part")])
        with pytest.raises(RuntimeError, match="lease"):
            write_journal.reserve_writes(db, job, "wrong-token", [(name, "result")])
        assert db.scalars(select(ArtifactWriteJournal)).all() == []


def test_legacy_flag_disabled_keeps_original_primary_filename(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path, enabled=False)
    monkeypatch.setattr(worker_tasks.pdf_tools, "compress", _mock_compress)
    file_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert db.get(FileRecord, file_id).stored_name == f"{job_id}.pdf"
        assert job.lease_epoch == 0 and job.lease_token is None
        assert db.scalars(select(ArtifactWriteJournal)).all() == []


def test_progress_rejects_wrong_token_without_overwriting_job(monkeypatch, tmp_path):
    job_id = _prepare(monkeypatch, tmp_path)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        token = write_journal.claim_queued_job(db, job, 90)
        with pytest.raises(RuntimeError, match="no longer valid"):
            write_journal.fenced_progress(db, job, "another-token", 80)
        db.refresh(job)
        assert job.progress == 10 and job.lease_token == token
