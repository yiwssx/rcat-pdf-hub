"""M30: real Ghostscript grayscale output, tenant isolation and artifact safety."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject
from reportlab.lib.colors import blue, green, red
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select

from app import storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import pdf_grayscale
from app.routers.jobs import _require_operation_scope
from app.services.pdf_grayscale import (
    MAX_OUTPUT_BYTES, _checked_pdf, grayscale_pdf_bounded,
)
from app.worker_tasks import _output_spec_for_job


def source_pdf(path: Path) -> Path:
    canvas = Canvas(str(path), pagesize=(320, 400))
    for index, fill in ((1, red), (2, green)):
        canvas.setPageSize((320 + (index - 1) * 10, 400 + (index - 1) * 5))
        canvas.setFillColor(fill)
        canvas.rect(20, 20, 100, 100, stroke=0, fill=1)
        canvas.setFillColor(blue)
        canvas.rect(180, 220, 45, 70, stroke=0, fill=1)
        canvas.setFillColorRGB(0, 0, 0)
        canvas.drawString(24, 330, f"M30 COLOR TEST PAGE {index}")
        canvas.showPage()
    canvas.save()
    return path


def render_rgb(path: Path, directory: Path, page: int) -> Image.Image:
    target = directory / f"render-{page}"
    subprocess.run([
        "pdftoppm", "-f", str(page), "-l", str(page),
        "-r", "72", "-singlefile", "-png", str(path), str(target),
    ], check=True, capture_output=True, timeout=30)
    with Image.open(target.with_suffix(".png")) as image:
        return image.convert("RGB")


def test_m30_real_binary_grayscale_channels_geometry_and_text(tmp_path):
    source = source_pdf(tmp_path / "colors.pdf")
    out = tmp_path / "gray.pdf"
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    grayscale_pdf_bounded(source, out)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha
    assert out.read_bytes().startswith(b"%PDF-")
    original, rebuilt = PdfReader(str(source), strict=True), PdfReader(str(out), strict=True)
    assert not rebuilt.is_encrypted
    assert len(rebuilt.pages) == len(original.pages) == 2
    for i in range(1, 3):
        before, after = original.pages[i - 1], rebuilt.pages[i - 1]
        assert "M30 COLOR TEST PAGE" in after.extract_text()
        assert abs(float(before.mediabox.width) - float(after.mediabox.width)) <= 0.1
        assert abs(float(before.mediabox.height) - float(after.mediabox.height)) <= 0.1
        original_pixel = render_rgb(source, tmp_path, i).getpixel((50, 355))
        gray_pixel = render_rgb(out, tmp_path, i).getpixel((50, 355))
        assert max(original_pixel) - min(original_pixel) > 40
        assert max(gray_pixel) - min(gray_pixel) <= 1


def test_m30_rejects_encrypted_and_preserves_source(tmp_path):
    source = source_pdf(tmp_path / "colors.pdf")
    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter(clone_from=str(source))
    writer.encrypt("passphrase", algorithm="AES-256")
    writer.write(str(encrypted))
    with pytest.raises(ValueError, match="encrypted"):
        grayscale_pdf_bounded(encrypted, tmp_path / "no-gray.pdf")
    assert not (tmp_path / "no-gray.pdf").exists()


def test_m30_rejects_overwrite_symlink_malformed_and_unsigned_forms(tmp_path):
    source = source_pdf(tmp_path / "colors.pdf")
    result = tmp_path / "existing.pdf"
    result.write_bytes(b"cannot overwrite")
    with pytest.raises(ValueError, match="different new file"):
        grayscale_pdf_bounded(source, result)
    assert result.read_bytes() == b"cannot overwrite"
    result.unlink()

    symlink = tmp_path / "source-link.pdf"
    symlink.symlink_to(source)
    with pytest.raises(ValueError, match="regular"):
        grayscale_pdf_bounded(symlink, result)

    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"invalid PDF input")
    with pytest.raises(ValueError):
        grayscale_pdf_bounded(invalid, result)

    writer = PdfWriter(clone_from=str(source))
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"): __import__("pypdf").generic.ArrayObject([]),
    })
    forms = tmp_path / "form.pdf"
    writer.write(str(forms))
    with pytest.raises(ValueError, match="form"):
        grayscale_pdf_bounded(forms, result)
    assert not result.exists()


def test_m30_does_not_publish_partial_output_after_engine_failure(monkeypatch, tmp_path):
    from app.services import pdf_export_stage
    original = source_pdf(tmp_path / "color.pdf")
    dest = tmp_path / "result.pdf"
    def fail_engine(_args, timeout):
        raise RuntimeError("M30 simulated malformed PDF interpreter failure")
    monkeypatch.setattr(pdf_export_stage, "_run", fail_engine)
    with pytest.raises(RuntimeError, match="malformed PDF"):
        grayscale_pdf_bounded(original, dest)
    assert not dest.exists()


def _record(owner="rcat-user", *, mime="application/pdf", name="source.pdf",
            size=1024, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=-1 if expired else 1),
    )


def _api_submit(monkeypatch, record):
    monkeypatch.setattr(pdf_grayscale, "_create_job",
                        lambda db, principal, operation, ids, params: {
                            "owner": principal.name, "operation": operation,
                            "file_ids": ids, "params": params,
                        })
    return pdf_grayscale.grayscale_pdf_request(
        pdf_grayscale.GrayscalePdfRequest(file_id="record"),
        principal=SimpleNamespace(name="rcat-user"),
        db=SimpleNamespace(get=lambda _model, _id: record),
    )


def test_m30_route_permissions_queue_and_output_contract(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "grayscale_pdf_tools_enabled", False)
    assert _output_spec_for_job("grayscale-pdf") == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation("grayscale-pdf")
    with pytest.raises(HTTPException) as exc:
        _api_submit(monkeypatch, _record())
    assert exc.value.status_code == 404

    monkeypatch.setattr(flags, "grayscale_pdf_tools_enabled", True)
    assert queue_class_for_operation("grayscale-pdf") == "pdf"
    assert _api_submit(monkeypatch, _record()) == {
        "owner": "rcat-user", "operation": "grayscale-pdf",
        "file_ids": ["record"], "params": {},
    }
    _require_operation_scope(
        SimpleNamespace(operation="grayscale-pdf"),
        SimpleNamespace(scopes={"pdf:grayscale"}),
    )
    with pytest.raises(HTTPException) as exc:
        _require_operation_scope(
            SimpleNamespace(operation="grayscale-pdf"),
            SimpleNamespace(scopes={"pdf:pdf-to-image"}),
        )
    assert exc.value.status_code == 403
    with pytest.raises(ValidationError):
        pdf_grayscale.GrayscalePdfRequest(file_id="record", url="http://localhost")


@pytest.mark.parametrize("record,code", [
    (_record(owner="other-account"), 403),
    (_record(mime="text/plain"), 415),
    (_record(name="not-pdf.txt"), 415),
    (_record(expired=True), 410),
    (_record(size=20 * 1024 * 1024), 413),
])
def test_m30_api_fails_closed_for_cross_user_and_invalid_source(monkeypatch, record, code):
    monkeypatch.setattr(get_settings(), "grayscale_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _api_submit(monkeypatch, record)
    assert err.value.status_code == code


def queued_job(monkeypatch, tmp_path):
    flags = get_settings()
    monkeypatch.setattr(flags, "data_dir", tmp_path)
    monkeypatch.setattr(flags, "grayscale_pdf_tools_enabled", True)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    original = source_pdf(tmp_path / "originals" / "input.pdf")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="rcat-user", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=64, webhook_url=None,
        ))
        file = FileRecord(
            original_name="input.pdf", stored_name="input.pdf",
            content_type="application/pdf", size=original.stat().st_size,
            sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
            source_system="rcat-user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(file)
        db.flush()
        job = JobRecord(
            operation="grayscale-pdf", status="queued", requested_by="rcat-user",
            input_file_ids_json=json.dumps([file.id]), params_json="{}",
        )
        db.add(job)
        db.commit()
        return job.id, hashlib.sha256(original.read_bytes()).hexdigest()


def test_m30_real_db_worker_writes_grayscale_owner_bound_pdf(monkeypatch, tmp_path):
    job_id, original_hash = queued_job(monkeypatch, tmp_path)
    monkeypatch.setattr(
        worker_tasks, "_auto_archive",
        lambda *_args: pytest.fail("Grayscale source must not auto-archive"),
    )
    file_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        result = db.get(FileRecord, file_id)
        links = db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all()
        assert job.status == "completed" and job.output_file_id == file_id
        assert result.source_system == "rcat-user" and result.content_type == "application/pdf"
        assert len(links) == 1 and links[0].role == "result"
        data = storage.path_for_stored_name(result.stored_name)
        assert data.read_bytes().startswith(b"%PDF-")
        assert len(PdfReader(str(data), strict=True).pages) == 2
        for index in (1, 2):
            pixel = render_rgb(data, tmp_path, index).getpixel((50, 355))
            assert max(pixel) - min(pixel) <= 1
        assert hashlib.sha256(storage.path_for_stored_name("input.pdf").read_bytes()).hexdigest() == original_hash


def test_m30_worker_revocation_never_stores_output(monkeypatch, tmp_path):
    job_id, _ = queued_job(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "grayscale_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="M30 grayscale conversion failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.output_file_id is None
        assert db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all() == []
    assert list((tmp_path / "processed").iterdir()) == []


def test_m30_worker_rejects_modified_source_signature_and_sanitizes_error(monkeypatch, tmp_path):
    job_id, _ = queued_job(monkeypatch, tmp_path)
    storage.path_for_stored_name("input.pdf").write_bytes(b"not-a-pdf")
    with pytest.raises(RuntimeError, match="M30 grayscale conversion failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed"
        assert "not-a-pdf" not in (job.error or "")
        assert db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all() == []


def test_m30_storage_upload_failure_compensates(monkeypatch, tmp_path):
    job_id, _ = queued_job(monkeypatch, tmp_path)
    def fail_storage(_path, _area, filename=None):
        raise OSError("M30 simulated storage write failure")
    monkeypatch.setattr(worker_tasks, "store_staged_file", fail_storage)
    with pytest.raises(RuntimeError, match="M30 grayscale conversion failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.output_file_id is None
        assert db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all() == []
        assert len(db.scalars(select(FileRecord)).all()) == 1
    assert list((tmp_path / "processed").iterdir()) == []
