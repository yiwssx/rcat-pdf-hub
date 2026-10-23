import hashlib
import json
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update

from app.audit import audit_event
from app.config import get_settings
from app.db import SessionLocal
from app.integrations.paperless import archive_to_paperless
from app.malware import MalwareDetected, scan_file
from app.models import ArchiveRecord, FileRecord, JobOutputArtifact, JobRecord
from app.observability import record_archive, record_job, record_job_duration, record_malware
from app.policy import effective_policy, ensure_storage_quota
from app.services import pdf_tools
from app.services.output_artifacts import stage_raster_pages
from app.storage import (
    default_expiry,
    delete_stored_name,
    new_output_path,
    path_for_stored_name,
    planned_processed_stored_name,
    store_staged_file,
)
from app.webhooks import queue_job_webhook
from app import write_journal

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
    if job.status == "cancelled":
        db.close()
        return ""

    journal_enabled = settings.artifact_write_journal_enabled
    token = str(uuid.uuid4()) if journal_enabled else None
    suffix, content_type = _output_spec(job.operation)
    # Every fenced attempt has a distinct temporary filename AND distinct
    # destination object key, so a stale process cannot clobber a new attempt.
    committed = False
    heartbeat: write_journal.LeaseHeartbeat | None = None
    stored_names: list[str] = []
    journal_files: dict[str, str] = {}
    reserved_names: list[str] = []
    staged_pages = []
    staging: TemporaryDirectory | None = None
    started_monotonic = time.perf_counter()
    terminal_state: str | None = None
    if journal_enabled:
        lease_seconds = max(
            settings.rq_interactive_job_timeout_seconds,
            settings.rq_job_timeout_seconds,
            settings.rq_heavy_job_timeout_seconds,
        ) + 900
        claimed = write_journal.claim_queued_job(db, job, lease_seconds)
        if claimed is None:
            # RQ duplicate deliveries must not touch storage or status.
            db.close()
            return ""
        token = claimed
    # Use the token confirmed by the atomic claim for the local work path.
    output = new_output_path(f"{job.id}-{token}" if token else job.id, suffix=suffix)
    try:
        if not journal_enabled:
            _set_job(db, job, status="running", progress=10, started_at=_now(), error=None)
        else:
            # Separate DB Session: PDF tools are blocking; heartbeat keeps
            # running while OCR, office conversion and S3 uploads execute.
            heartbeat = write_journal.LeaseHeartbeat(
                SessionLocal, job.id, token, lease_seconds,
                settings.artifact_heartbeat_interval_seconds,
            ).start()
        record_job(job.operation, "running")
        audit_event("job.started", job.requested_by, "job", job.id, {"operation": job.operation})
        file_ids = json.loads(job.input_file_ids_json)
        params = json.loads(job.params_json)
        files = [db.get(FileRecord, fid) for fid in file_ids]
        if any(item is None for item in files):
            raise RuntimeError("One or more input files no longer exist")
        inputs = [path_for_stored_name(item.stored_name) for item in files if item is not None]

        if token:
            write_journal.fenced_progress(db, job, token, 25)
        else:
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
        elif job.operation == "organize":
            pdf_tools.organize(inputs[0], params["pages"], output)
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

        if token:
            write_journal.fenced_progress(db, job, token, 80)
        else:
            _set_job(db, job, progress=80)
        if job.operation == "pdf-to-images" and settings.multi_output_artifacts_enabled:
            # Extract only self-generated, verified page images. Keep the
            # original ZIP as the backward-compatible output_file_id.
            staging = TemporaryDirectory(prefix="pdfhub-pages-", dir=output.parent)
            staged_pages = stage_raster_pages(
                output, Path(staging.name),
                first_page=int(params.get("first_page", 1)),
                max_bytes=settings.max_upload_mb * 5 * 1024 * 1024,
            )
        try:
            scan_status = scan_file(output)
        except MalwareDetected as exc:
            record_malware("infected")
            audit_event("job.output_malware_rejected", job.requested_by, "job", job.id, {"signature": str(exc)[:500]})
            raise RuntimeError("Processed output was rejected by malware scanning") from exc
        record_malware(scan_status)
        for staged in staged_pages:
            try:
                part_scan = scan_file(staged.path)
            except MalwareDetected as exc:
                record_malware("infected")
                audit_event(
                    "job.output_malware_rejected", job.requested_by, "job", job.id,
                    {"signature": str(exc)[:500], "part": staged.ordinal},
                )
                raise RuntimeError("Processed output part was rejected by malware scanning") from exc
            record_malware(part_scan)

        db.refresh(job)
        if job.status == "cancelled":
            output.unlink(missing_ok=True)
            terminal_state = "cancelled"
            record_job(job.operation, "cancelled")
            audit_event("job.cancelled_before_commit", job.requested_by, "job", job.id, {"operation": job.operation})
            return ""

        digest = _output_hash(output)
        output_size = output.stat().st_size
        total_output_bytes = output_size + sum(page.path.stat().st_size for page in staged_pages)
        if job.requested_by != "bootstrap-admin":
            policy = effective_policy(db, job.requested_by)
            try:
                ensure_storage_quota(db, job.requested_by, policy.max_storage_mb, total_output_bytes)
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

        if token:
            if heartbeat and heartbeat.lost.is_set():
                raise RuntimeError("Job execution heartbeat lost its lease")
            # Record ALL destinations durably before the first S3/local write.
            # No FileRecord exists in this transaction yet, so committing the
            # journal cannot prematurely publish a partial result.
            reserved_names = [
                planned_processed_stored_name(
                    f"{job.id}-{token}{suffix}"
                )
            ]
            reserved_names.extend(
                planned_processed_stored_name(f"{job.id}-{token}-{page.display_name}")
                for page in staged_pages
            )
            write_journal.reserve_writes(
                db, job, token,
                [(reserved_names[0], "bundle" if job.operation == "pdf-to-images" else "result")]
                + [(name, "part") for name in reserved_names[1:]],
            )
        primary_name = f"{job.id}-{token}{suffix}" if token else f"{job.id}{suffix}"
        stored_name = planned_processed_stored_name(primary_name)
        # Record the planned object BEFORE calling upload_file: S3 may write an
        # object and then raise without returning the storage key.
        stored_names.append(stored_name)
        if db.scalar(select(FileRecord.id).where(FileRecord.stored_name == stored_name)) is not None:
            raise RuntimeError("Output storage destination already belongs to a saved file")
        actual_name = store_staged_file(output, "processed", filename=primary_name)
        if actual_name != stored_name:
            raise RuntimeError("Storage returned an unexpected output destination")
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
        db.flush()
        if token:
            journal_files[stored_name] = record.id
        db.add(JobOutputArtifact(
            job_id=job.id, file_id=record.id,
            role="bundle" if job.operation == "pdf-to-images" else "result",
            ordinal=None,
        ))
        for page in staged_pages:
            page_size = page.path.stat().st_size
            page_digest = _output_hash(page.path)
            part_filename = (f"{job.id}-{token}-{page.display_name}" if token
                             else f"{job.id}-{page.display_name}")
            page_name = planned_processed_stored_name(part_filename)
            stored_names.append(page_name)
            if db.scalar(select(FileRecord.id).where(FileRecord.stored_name == page_name)) is not None:
                raise RuntimeError("Part storage destination already belongs to a saved file")
            actual_name = store_staged_file(
                page.path, "processed", filename=part_filename
            )
            if actual_name != page_name:
                raise RuntimeError("Storage returned an unexpected part destination")
            part_record = FileRecord(
                original_name=page.display_name,
                stored_name=page_name,
                content_type=page.content_type,
                size=page_size,
                sha256=page_digest,
                source_system=job.requested_by,
                expires_at=default_expiry(),
            )
            db.add(part_record)
            db.flush()
            if token:
                journal_files[page_name] = part_record.id
            db.add(JobOutputArtifact(
                job_id=job.id, file_id=part_record.id, role="part",
                ordinal=page.ordinal,
            ))
        db.flush()
        if token:
            if heartbeat and heartbeat.lost.is_set():
                raise RuntimeError("Job execution heartbeat lost its lease")
            write_journal.mark_committed(db, job, token, journal_files)
        # Do not overwrite a concurrently cancelled job. Stage the complete
        # FileRecord/link set and completion state in ONE database transaction.
        completed = db.execute(
            update(JobRecord)
            .execution_options(synchronize_session=False)
            .where(
                JobRecord.id == job.id, JobRecord.status == "running",
                *((JobRecord.lease_token == token,
                   JobRecord.lease_expires_at > _now()) if token else ()),
            )
            .values(status="completed", progress=100, output_file_id=record.id, finished_at=_now())
        )
        if completed.rowcount != 1:
            raise RuntimeError("Job was cancelled before output commit")
        db.commit()
        committed = True
    except Exception as exc:
        db.rollback()
        output.unlink(missing_ok=True)
        if not committed:
            cleanup_outcomes: dict[str, bool] = {}
            for name in reversed(stored_names):
                try:
                    # Attempt-key isolation prevents one worker deleting another
                    # worker's output. Never delete a committed FileRecord object.
                    if db.scalar(select(FileRecord.id).where(FileRecord.stored_name == name)) is None:
                        delete_stored_name(name)
                        cleanup_outcomes[name] = True
                except Exception:
                    cleanup_outcomes[name] = False
            if token and reserved_names:
                # Reservations not yet attempted are harmless: this is an
                # explicit negative proof only for the unattempted locations.
                for name in reserved_names:
                    if name not in stored_names:
                        cleanup_outcomes[name] = True
                try:
                    write_journal.compensate_writes(db, job, token, cleanup_outcomes)
                except Exception:
                    db.rollback()  # leave journal as 'planned' for operator review
        try:
            db.refresh(job)
            if job.status != "cancelled":
                if token:
                    changed = db.execute(
                        update(JobRecord).execution_options(synchronize_session=False).where(
                            JobRecord.id == job.id, JobRecord.status == "running",
                            JobRecord.lease_token == token,
                            JobRecord.lease_expires_at > _now(),
                        ).values(
                            status="failed", progress=100,
                            error=str(exc)[-4000:], finished_at=_now(),
                        )
                    )
                    if changed.rowcount:
                        db.commit()
                    else:
                        db.rollback()
                    db.refresh(job)
                else:
                    _set_job(db, job, status="failed", progress=100, error=str(exc)[-4000:], finished_at=_now())
        except Exception:
            db.rollback()
        if job.status == "cancelled":
            terminal_state = "cancelled"
            record_job(job.operation, "cancelled")
            audit_event("job.cancelled_worker_stop", job.requested_by, "job", job.id, {"operation": job.operation})
            return ""
        terminal_state = "failed"
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
        terminal_state = "completed"
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
        if heartbeat is not None:
            heartbeat.stop()
        if staging is not None:
            staging.cleanup()
        if terminal_state is not None:
            record_job_duration(job.operation, terminal_state, time.perf_counter() - started_monotonic)
        db.close()
