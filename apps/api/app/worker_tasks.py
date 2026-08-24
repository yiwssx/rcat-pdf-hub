import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.integrations.paperless import archive_to_paperless
from app.malware import MalwareDetected, scan_file
from app.models import ArchiveRecord, FileRecord, JobRecord
from app.observability import record_archive, record_job, record_malware
from app.policy import effective_policy, ensure_storage_quota
from app.services import pdf_tools
from app.storage import (
    default_expiry,
    delete_stored_name,
    new_output_path,
    path_for_stored_name,
    store_staged_file,
)
from app.webhooks import queue_job_webhook

settings = get_settings()


def _now():
    return datetime.now(timezone.utc)


def _set_job(db, job: JobRecord, **values):
    for key, value in values.items():
        setattr(job, key, value)
    db.commit()


def _output_hash(path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _output_spec(operation: str) -> tuple[str, str]:
    if operation == "pdf-to-images":
        return ".zip", "application/zip"
    return ".pdf", "application/pdf"


def _notify_job(db, job: JobRecord) -> None:
    try:
        queue_job_webhook(db, job)
    except Exception as exc:
        db.rollback()
        audit_event(
            "webhook.queue_failed",
            job.requested_by,
            "job",
            job.id,
            {"error": str(exc)[-1000:]},
        )


def _auto_archive(db, record: FileRecord, actor: str) -> None:
    if record.content_type != "application/pdf":
        return
    if not settings.paperless_enabled or not settings.paperless_auto_archive:
        return
    archive = db.scalar(
        select(ArchiveRecord).where(
            ArchiveRecord.file_id == record.id,
            ArchiveRecord.integration_name == "paperless",
        )
    )
    if not archive:
        archive = ArchiveRecord(file_id=record.id, integration_name="paperless", status="submitting")
        db.add(archive)
        db.commit()
        db.refresh(archive)
    try:
        archive.external_id = archive_to_paperless(record, path_for_stored_name(record.stored_name))
        archive.status = "submitted"
        archive.error = None
        db.commit()
        record_archive("paperless", "submitted")
        audit_event("archive.paperless_submitted", actor, "file", record.id, {"task_id": archive.external_id, "automatic": True})
    except Exception as exc:
        db.rollback()
        archive = db.get(ArchiveRecord, archive.id)
        if archive:
            archive.status = "failed"
            archive.error = str(exc)[-4000:]
            db.commit()
        record_archive("paperless", "failed")
        audit_event("archive.paperless_failed", actor, "file", record.id, {"error": str(exc)[-1000:], "automatic": True})


def process_job(job_id: str) -> str:
    db = SessionLocal()
    job = db.get(JobRecord, job_id)
    if not job:
        db.close()
        raise RuntimeError(f"Unknown job {job_id}")

    suffix, content_type = _output_spec(job.operation)
    output = new_output_path(job.id, suffix=suffix)
    record_created = False
    stored_name: str | None = None
    try:
        _set_job(db, job, status="running", progress=10, started_at=_now(), error=None)
        record_job(job.operation, "running")
        audit_event("job.started", job.requested_by, "job", job.id, {"operation": job.operation})
        file_ids = json.loads(job.input_file_ids_json)
        params = json.loads(job.params_json)
        files = [db.get(FileRecord, fid) for fid in file_ids]
        if any(item is None for item in files):
            raise RuntimeError("One or more input files no longer exist")
        inputs = [path_for_stored_name(item.stored_name) for item in files if item is not None]

        _set_job(db, job, progress=25)
        if job.operation == "merge":
            pdf_tools.merge(inputs, output)
        elif job.operation == "images-to-pdf":
            pdf_tools.images_to_pdf(
                inputs,
                output,
                page_size=params.get("page_size", "auto"),
                fit=params.get("fit", "contain"),
                margin=float(params.get("margin", 18)),
                dpi=int(params.get("dpi", 150)),
            )
        elif job.operation == "pdf-to-images":
            pdf_tools.pdf_to_images(
                inputs[0],
                output,
                image_format=params.get("format", "png"),
                dpi=int(params.get("dpi", 150)),
                first_page=int(params.get("first_page", 1)),
                last_page=params.get("last_page"),
            )
        elif job.operation == "split":
            pdf_tools.split(inputs[0], params["pages"], output)
        elif job.operation == "rotate":
            pdf_tools.rotate(inputs[0], int(params["degrees"]), params["pages"], output)
        elif job.operation == "compress":
            pdf_tools.compress(inputs[0], output)
        elif job.operation == "ocr":
            pdf_tools.ocr(
                inputs[0], output,
                params.get("languages", "tha+eng"),
                bool(params.get("deskew", True)),
                bool(params.get("rotate_pages", True)),
            )
        elif job.operation == "pdfa":
            pdf_tools.pdfa(inputs[0], output, params.get("languages", "tha+eng"))
        elif job.operation == "office-to-pdf":
            pdf_tools.office_to_pdf(inputs[0], output)
        elif job.operation == "watermark":
            pdf_tools.watermark_text(
                inputs[0], output,
                text=params["text"],
                font_size=float(params.get("font_size", 48)),
                opacity=float(params.get("opacity", 0.18)),
                rotation=float(params.get("rotation", 45)),
                position=params.get("position", "center"),
                margin=float(params.get("margin", 36)),
            )
        elif job.operation == "page-numbers":
            pdf_tools.add_page_numbers(
                inputs[0], output,
                format_text=params.get("format", "{page} / {total}"),
                start_number=int(params.get("start_number", 1)),
                font_size=float(params.get("font_size", 10)),
                position=params.get("position", "bottom-center"),
                margin=float(params.get("margin", 24)),
            )
        elif job.operation == "stamp":
            pdf_tools.stamp_pdf(
                inputs[0], inputs[1], output,
                position=params.get("position", "bottom-right"),
                scale=float(params.get("scale", 0.20)),
                margin=float(params.get("margin", 24)),
            )
        else:
            raise RuntimeError(f"Unsupported operation: {job.operation}")

        _set_job(db, job, progress=80)
        try:
            scan_status = scan_file(output)
        except MalwareDetected as exc:
            record_malware("infected")
            audit_event("job.output_malware_rejected", job.requested_by, "job", job.id, {"signature": str(exc)[:500]})
            raise RuntimeError("Processed output was rejected by malware scanning") from exc
        record_malware(scan_status)

        digest = _output_hash(output)
        output_size = output.stat().st_size
        if job.requested_by != "bootstrap-admin":
            policy = effective_policy(db, job.requested_by)
            try:
                ensure_storage_quota(db, job.requested_by, policy.max_storage_mb, output_size)
            except HTTPException as exc:
                output.unlink(missing_ok=True)
                audit_event(
                    "job.output_quota_rejected",
                    job.requested_by,
                    "job",
                    job.id,
                    {"operation": job.operation, "output_size": output_size, "detail": exc.detail},
                )
                raise RuntimeError(str(exc.detail)) from exc

        stored_name = store_staged_file(output, "processed", filename=f"{job.id}{suffix}")
        record = FileRecord(
            original_name=f"{job.operation}-{job.id}{suffix}",
            stored_name=stored_name,
            content_type=content_type,
            size=output_size,
            sha256=digest,
            source_system=job.requested_by,
            expires_at=default_expiry(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        record_created = True
        _set_job(db, job, status="completed", progress=100, output_file_id=record.id, finished_at=_now())
    except Exception as exc:
        db.rollback()
        output.unlink(missing_ok=True)
        if stored_name and not record_created:
            try:
                delete_stored_name(stored_name)
            except Exception:
                pass
        try:
            _set_job(db, job, status="failed", progress=100, error=str(exc)[-4000:], finished_at=_now())
        except Exception:
            db.rollback()
        record_job(job.operation, "failed")
        audit_event(
            "job.failed",
            job.requested_by,
            "job",
            job.id,
            {"operation": job.operation, "error": str(exc)[-1000:]},
        )
        _notify_job(db, job)
        raise
    else:
        record_job(job.operation, "completed")
        audit_event(
            "job.completed",
            job.requested_by,
            "job",
            job.id,
            {
                "operation": job.operation,
                "output_file_id": record.id,
                "output_size": output_size,
                "content_type": record.content_type,
                "storage_backend": settings.storage_backend,
            },
        )
        _auto_archive(db, record, job.requested_by)
        _notify_job(db, job)
        return record.id
    finally:
        db.close()
