import json
from datetime import datetime, timezone
from pathlib import Path

from app.db import SessionLocal
from app.models import FileRecord, JobRecord
from app.services import pdf_tools
from app.storage import default_expiry, new_output_path, path_for_stored_name


def _now():
    return datetime.now(timezone.utc)


def _set_job(db, job: JobRecord, **values):
    for key, value in values.items():
        setattr(job, key, value)
    db.commit()


def process_job(job_id: str) -> str:
    db = SessionLocal()
    job = db.get(JobRecord, job_id)
    if not job:
        db.close()
        raise RuntimeError(f"Unknown job {job_id}")

    try:
        _set_job(db, job, status="running", progress=10, started_at=_now(), error=None)
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
            pdf_tools.ocr(inputs[0], output, params.get("languages", "tha+eng"), bool(params.get("deskew", True)), bool(params.get("rotate_pages", True)))
        elif job.operation == "pdfa":
            pdf_tools.pdfa(inputs[0], output, params.get("languages", "tha+eng"))
        elif job.operation == "office-to-pdf":
            pdf_tools.office_to_pdf(inputs[0], output)
        else:
            raise RuntimeError(f"Unsupported operation: {job.operation}")

        _set_job(db, job, progress=85)
        import hashlib
        hasher = hashlib.sha256()
        with output.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        output_size = output.stat().st_size
        source = files[0].source_system if len(files) == 1 else job.requested_by
        record = FileRecord(
            original_name=f"{job.operation}-{job.id}.pdf",
            stored_name=output.name,
            content_type="application/pdf",
            size=output_size,
            sha256=digest,
            source_system=source,
            expires_at=default_expiry(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        _set_job(db, job, status="completed", progress=100, output_file_id=record.id, finished_at=_now())
        return record.id
    except Exception as exc:
        _set_job(db, job, status="failed", progress=100, error=str(exc)[-4000:], finished_at=_now())
        raise
    finally:
        db.close()
