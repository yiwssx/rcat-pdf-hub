import hashlib
import json
from datetime import datetime, timezone

from app.audit import audit_event
from app.db import SessionLocal
from app.models import FileRecord, JobRecord
from app.services import pdf_tools
from app.storage import default_expiry, new_output_path, path_for_stored_name
from app.webhooks import dispatch_job_webhook


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


def process_job(job_id: str) -> str:
    db = SessionLocal()
    job = db.get(JobRecord, job_id)
    if not job:
        db.close()
        raise RuntimeError(f"Unknown job {job_id}")

    try:
        _set_job(db, job, status="running", progress=10, started_at=_now(), error=None)
        audit_event("job.started", job.requested_by, "job", job.id, {"operation": job.operation})
        file_ids = json.loads(job.input_file_ids_json)
        params = json.loads(job.params_json)
        files = [db.get(FileRecord, fid) for fid in file_ids]
        if any(item is None for item in files):
            raise RuntimeError("One or more input files no longer exist")
        inputs = [path_for_stored_name(item.stored_name) for item in files]
        output = new_output_path(job.id)

        _set_job(db, job, progress=25)
        if job.operation == "merge":
            pdf_tools.merge(inputs, output)
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

        _set_job(db, job, progress=85)
        digest = _output_hash(output)
        output_size = output.stat().st_size
        record = FileRecord(
            original_name=f"{job.operation}-{job.id}.pdf",
            stored_name=output.name,
            content_type="application/pdf",
            size=output_size,
            sha256=digest,
            source_system=job.requested_by,
            expires_at=default_expiry(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        _set_job(db, job, status="completed", progress=100, output_file_id=record.id, finished_at=_now())
        audit_event(
            "job.completed", job.requested_by, "job", job.id,
            {"operation": job.operation, "output_file_id": record.id, "output_size": output_size},
        )
        dispatch_job_webhook(db, job)
        return record.id
    except Exception as exc:
        _set_job(db, job, status="failed", progress=100, error=str(exc)[-4000:], finished_at=_now())
        audit_event("job.failed", job.requested_by, "job", job.id, {"operation": job.operation, "error": str(exc)[-1000:]})
        dispatch_job_webhook(db, job)
        raise
    finally:
        db.close()
