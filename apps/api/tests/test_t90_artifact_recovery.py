"""T90-0.8: recoverable S3 write failures and safe read-only crash-orphan diagnostics."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import artifact_recovery, storage, storage_reconciliation, worker_tasks
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy


NOW = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)


def _job(status="failed", *, owner="service-a"):
    job_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(JobRecord(
            id=job_id, operation="pdf-to-images", status=status, progress=100,
            requested_by=owner, input_file_ids_json="[]", params_json="{}",
        ))
        db.commit()
    return job_id


def _old_file(path, *, hours=48):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test-output")
    modified = (NOW - timedelta(hours=hours)).timestamp()
    os.utime(path, (modified, modified))


def _inventory(monkeypatch, tmp_path, *, age=24):
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_reconciliation.settings, "data_dir", tmp_path)
    with SessionLocal() as db:
        return artifact_recovery.inventory_orphan_job_outputs(
            db, min_age_hours=age, now=NOW,
        )


def test_local_stale_failed_job_generated_output_report_only(monkeypatch, tmp_path):
    job_id = _job("failed")
    path = tmp_path / "processed" / f"{job_id}-page-0001.png"
    _old_file(path)
    before = path.read_bytes()
    report = _inventory(monkeypatch, tmp_path)
    assert report["dry_run"] is True and report["auto_delete"] is False
    assert report["eligible_count"] == 1
    assert report["candidates"][0]["job_id"] == job_id
    assert report["candidates"][0]["stored_name"] == path.name
    assert path.read_bytes() == before  # diagnostic cannot remove contents


def test_cancelled_job_zip_is_a_report_candidate(monkeypatch, tmp_path):
    job_id = _job("cancelled")
    _old_file(tmp_path / "processed" / f"{job_id}.zip")
    report = _inventory(monkeypatch, tmp_path)
    assert report["eligible_count"] == 1


@pytest.mark.parametrize("status", ["queued", "running", "completed"])
def test_nonterminal_or_completed_job_never_reclaimed(monkeypatch, tmp_path, status):
    job_id = _job(status)
    _old_file(tmp_path / "processed" / f"{job_id}.zip")
    assert _inventory(monkeypatch, tmp_path)["eligible_count"] == 0


def test_recent_failed_job_output_is_protected(monkeypatch, tmp_path):
    job_id = _job()
    _old_file(tmp_path / "processed" / f"{job_id}.pdf", hours=2)
    report = _inventory(monkeypatch, tmp_path)
    assert report["eligible_count"] == 0
    with pytest.raises(ValueError, match="24 hours"):
        _inventory(monkeypatch, tmp_path, age=1)


def test_reference_from_any_file_record_blocks_reclaim(monkeypatch, tmp_path):
    job_id = _job()
    name = f"{job_id}.zip"
    _old_file(tmp_path / "processed" / name)
    with SessionLocal() as db:
        db.add(FileRecord(
            original_name="user-kept.zip", stored_name=name,
            content_type="application/zip", size=11, sha256="a" * 64,
            source_system="someone-else",
        ))
        db.commit()
    assert _inventory(monkeypatch, tmp_path)["eligible_count"] == 0


def test_unknown_unmanaged_and_unrecognized_files_are_protected(monkeypatch, tmp_path):
    job_id = _job()
    _old_file(tmp_path / "originals" / f"{job_id}.pdf")
    _old_file(tmp_path / "processed" / f"{job_id}-personal-upload.pdf")
    _old_file(tmp_path / "processed" / f"{uuid.uuid4()}.zip")
    _old_file(tmp_path / "processed" / "not-a-uuid.zip")
    assert _inventory(monkeypatch, tmp_path)["eligible_count"] == 0


def test_report_pagination_keeps_total_and_does_not_mutate(monkeypatch, tmp_path):
    job1 = _job()
    job2 = _job()
    paths = [
        tmp_path / "processed" / f"{job1}.zip",
        tmp_path / "processed" / f"{job2}.zip",
    ]
    for path in paths:
        _old_file(path)
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_reconciliation.settings, "data_dir", tmp_path)
    with SessionLocal() as db:
        report = artifact_recovery.inventory_orphan_job_outputs(
            db, now=NOW, detail_limit=1
        )
    assert report["eligible_count"] == 2
    assert report["truncated"] is True
    assert len(report["candidates"]) == 1
    assert all(p.exists() for p in paths)


def test_naive_or_missing_s3_lastmodified_is_excluded(monkeypatch):
    job_id = _job()
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_reconciliation.settings, "s3_prefix", "pdfhub")
    metadata = [
        {"stored_name": f"s3:pdfhub/processed/{job_id}.zip",
         "location": f"pdfhub/processed/{job_id}.zip", "size": 3,
         "modified_at": None},
    ]
    monkeypatch.setattr(
        storage_reconciliation, "_scan_s3_objects",
        lambda: {item["stored_name"]: item for item in metadata},
    )
    with SessionLocal() as db:
        assert artifact_recovery.inventory_orphan_job_outputs(
            db, now=NOW
        )["eligible_count"] == 0
        metadata[0]["modified_at"] = datetime(2026, 10, 20)
        assert artifact_recovery.inventory_orphan_job_outputs(
            db, now=NOW
        )["eligible_count"] == 0


def test_s3_orphan_detected_read_only_with_age_and_prefix(monkeypatch):
    job_id = _job("failed")
    another = _job("running")
    old = NOW - timedelta(hours=72)
    fake_objects = {
        f"s3:pdfhub/processed/{job_id}.zip": {
            "stored_name": f"s3:pdfhub/processed/{job_id}.zip",
            "location": f"pdfhub/processed/{job_id}.zip",
            "size": 9, "modified_at": old,
        },
        f"s3:pdfhub/originals/{job_id}.pdf": {
            "stored_name": f"s3:pdfhub/originals/{job_id}.pdf",
            "location": f"pdfhub/originals/{job_id}.pdf",
            "size": 9, "modified_at": old,
        },
        f"s3:pdfhub/processed/{another}.zip": {
            "stored_name": f"s3:pdfhub/processed/{another}.zip",
            "location": f"pdfhub/processed/{another}.zip",
            "size": 9, "modified_at": old,
        },
    }
    monkeypatch.setattr(storage_reconciliation.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage_reconciliation.settings, "s3_prefix", "pdfhub")
    monkeypatch.setattr(storage_reconciliation, "_scan_s3_objects", lambda: fake_objects)
    with SessionLocal() as db:
        report = artifact_recovery.inventory_orphan_job_outputs(db, now=NOW)
    assert report["backend"] == "s3"
    assert report["eligible_count"] == 1
    assert report["candidates"][0]["job_id"] == job_id
    assert report["auto_delete"] is False


class PartialUploadS3:
    """Fake self-hosted S3: commits bytes, then simulates a lost ACK."""
    def __init__(self):
        self.objects = {}
        self.deleted = []
        self.fail_delete = False

    def head_bucket(self, **_kwargs):
        return {}

    def upload_file(self, source, bucket, key, **_kwargs):
        assert bucket == "pdfhub-test"
        with open(source, "rb") as src:
            self.objects[key] = src.read()
        raise OSError("simulated lost S3 upload acknowledgment")

    def head_object(self, Bucket, Key):
        from botocore.exceptions import ClientError
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"ContentLength": len(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        if self.fail_delete:
            raise OSError("simulated S3 deletion outage")
        self.deleted.append(Key)
        self.objects.pop(Key, None)
        return {}

    def list_objects_v2(self, **_kwargs):
        return {
            "IsTruncated": False,
            "Contents": [
                {"Key": key, "Size": len(data),
                 "LastModified": NOW - timedelta(hours=48)}
                for key, data in self.objects.items()
            ],
        }


def _prepare_fake_s3_worker(monkeypatch, tmp_path):
    monkeypatch.setattr(storage.settings, "data_dir", tmp_path)
    monkeypatch.setattr(storage.settings, "storage_backend", "s3")
    monkeypatch.setattr(storage.settings, "s3_bucket", "pdfhub-test")
    monkeypatch.setattr(storage.settings, "s3_prefix", "pdfhub")
    monkeypatch.setattr(storage.settings, "s3_endpoint_url", "http://127.0.0.1:8333")
    monkeypatch.setattr(worker_tasks.settings, "multi_output_artifacts_enabled", False)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    fake = PartialUploadS3()
    monkeypatch.setattr(storage, "s3_client", lambda: fake)
    storage.ensure_storage()
    (tmp_path / "originals" / "source.pdf").write_bytes(b"source")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="t90-service", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=10, webhook_url=None,
        ))
        src = FileRecord(
            original_name="source.pdf", stored_name="source.pdf",
            content_type="application/pdf", size=6, sha256="a" * 64,
            source_system="t90-service", expires_at=NOW + timedelta(days=5),
        )
        db.add(src)
        db.flush()
        job = JobRecord(
            operation="compress", status="queued", progress=0,
            input_file_ids_json=f'["{src.id}"]', params_json="{}",
            requested_by="t90-service",
        )
        db.add(job)
        db.commit()
        job_id = job.id
    monkeypatch.setattr(
        worker_tasks.pdf_tools, "compress",
        lambda _src, dest: dest.write_bytes(b"%PDF-1.4\nfake\n%%EOF"),
    )
    return fake, job_id


def test_s3_upload_ack_failure_compensates_even_without_returned_name(monkeypatch, tmp_path):
    fake, job_id = _prepare_fake_s3_worker(monkeypatch, tmp_path)
    with pytest.raises(OSError, match="lost S3 upload acknowledgment"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.output_file_id is None
        assert db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id
        )).all() == []
        assert db.scalars(select(FileRecord).where(
            FileRecord.source_system == "t90-service",
            FileRecord.content_type == "application/pdf",
            FileRecord.original_name != "source.pdf",
        )).all() == []
    assert fake.objects == {}
    assert fake.deleted == [f"pdfhub/processed/{job_id}.pdf"]


def test_s3_cleanup_outage_retains_orphan_for_read_only_report(monkeypatch, tmp_path):
    fake, job_id = _prepare_fake_s3_worker(monkeypatch, tmp_path)
    fake.fail_delete = True
    with pytest.raises(OSError, match="lost S3 upload acknowledgment"):
        worker_tasks.process_job(job_id)
    assert f"pdfhub/processed/{job_id}.pdf" in fake.objects
    monkeypatch.setattr(storage_reconciliation.settings, "s3_prefix", "pdfhub")
    monkeypatch.setattr(storage_reconciliation, "s3_client", lambda: fake)
    with SessionLocal() as db:
        report = artifact_recovery.inventory_orphan_job_outputs(db, now=NOW)
    assert report["eligible_count"] == 1
    assert report["auto_delete"] is False
