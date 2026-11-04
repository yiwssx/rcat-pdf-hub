"""M16: authentic selected-page PDF and ZIP, owner-gated dispatch and persistence."""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select

from app import storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import pdf_extract_pages
from app.routers.jobs import _require_operation_scope
from app.services.pdf_extract_pages import extract_selected_pages_pdf
from app.worker_tasks import _output_spec_for_job


def source_pdf(path: Path, count: int = 5) -> Path:
    writer = Canvas(str(path))
    for page in range(1, count + 1):
        writer.setPageSize((320 + page * 10, 450 + page * 13))
        writer.drawString(35, 320, f"M16 EXACT SOURCE PAGE {page}")
        writer.showPage()
    writer.save()
    return path


@pytest.mark.parametrize("pages,sequence", [
    ("1", [1]),
    ("1,3,5", [1, 3, 5]),
    ("z-2", [5, 4, 3, 2]),
    ("2-z", [2, 3, 4, 5]),
])
def test_extract_pdf_preserves_selected_order_and_source(tmp_path, pages, sequence):
    source = source_pdf(tmp_path / "in.pdf")
    destination = tmp_path / "selected.pdf"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    extract_selected_pages_pdf(source, destination, pages=pages)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert destination.read_bytes().startswith(b"%PDF-")
    result = PdfReader(str(destination), strict=True)
    assert len(result.pages) == len(sequence)
    assert not result.is_encrypted
    for item, original_page in zip(result.pages, sequence, strict=True):
        assert f"M16 EXACT SOURCE PAGE {original_page}" in (item.extract_text() or "")
        assert float(item.mediabox.width) == 320 + original_page * 10
        assert float(item.mediabox.height) == 450 + original_page * 13


def test_m16_pdf_rejects_encrypted_symlinks_and_overwrite(tmp_path):
    input_pdf = source_pdf(tmp_path / "in.pdf")
    destination = tmp_path / "out.pdf"
    destination.write_bytes(b"keep-old")
    with pytest.raises(ValueError, match="new distinct"):
        extract_selected_pages_pdf(input_pdf, destination, pages="2")
    assert destination.read_bytes() == b"keep-old"
    destination.unlink()
    symlink = tmp_path / "linked.pdf"
    symlink.symlink_to(input_pdf)
    with pytest.raises(ValueError, match="regular PDF"):
        extract_selected_pages_pdf(symlink, destination, pages="2")
    writer = PdfWriter()
    writer.append(PdfReader(str(input_pdf)))
    writer.encrypt("secret-password")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        extract_selected_pages_pdf(locked, destination, pages="1")
    assert not destination.exists()


@pytest.mark.parametrize("pages", [
    "", "0", "6", "1,,2", "1,1", "4-6", "1-3,2", "1-z;whoami",
])
def test_m16_pdf_rejects_invalid_and_duplicate_selection(tmp_path, pages):
    source = source_pdf(tmp_path / "in.pdf")
    target = tmp_path / "out.pdf"
    with pytest.raises(ValueError):
        extract_selected_pages_pdf(source, target, pages=pages)
    assert not target.exists()


def _record(*, owner="member-one", mime="application/pdf", name="input.pdf",
            size=2048, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=-1 if expired else 1),
    )


def _submit(monkeypatch, record, output_format="pdf"):
    monkeypatch.setattr(
        pdf_extract_pages, "_create_job",
        lambda db, principal, operation, ids, params: {
            "owner": principal.name, "operation": operation,
            "ids": ids, "params": params,
        },
    )
    return pdf_extract_pages.extract_pages(
        pdf_extract_pages.ExtractPagesRequest(
            file_id="record", pages="5-3", format=output_format,
        ),
        principal=SimpleNamespace(name="member-one"),
        db=SimpleNamespace(get=lambda _model, _id: record),
    )


def test_m16_flags_and_queue_are_independent_of_m07(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "extract_pages_tools_enabled", False)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", False)
    assert _output_spec_for_job("extract-pages-pdf") == (".pdf", "application/pdf")
    assert _output_spec_for_job("extract-pages-zip") == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation("extract-pages-pdf")
    with pytest.raises(HTTPException) as exc:
        _submit(monkeypatch, _record())
    assert exc.value.status_code == 404
    monkeypatch.setattr(flags, "extract_pages_tools_enabled", True)
    assert queue_class_for_operation("extract-pages-pdf") == "pdf"
    with pytest.raises(ValueError):
        queue_class_for_operation("extract-pages-zip")
    with pytest.raises(HTTPException) as exc:
        _submit(monkeypatch, _record(), "zip")
    assert exc.value.status_code == 404
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", True)
    assert queue_class_for_operation("extract-pages-zip") == "pdf"
    for mode in ("pdf", "zip"):
        result = _submit(monkeypatch, _record(), mode)
        assert result["owner"] == "member-one"
        assert result["operation"] == f"extract-pages-{mode}"
        assert result["params"] == {"pages": "5-3", "format": mode}
    assert queue_class_for_operation("split") == "interactive"
    assert _output_spec_for_job("split") == (".pdf", "application/pdf")


@pytest.mark.parametrize("record,status", [
    (_record(owner="other-member"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.txt"), 415),
    (_record(expired=True), 410),
    (_record(size=20 * 1024 * 1024), 413),
])
@pytest.mark.parametrize("mode", ["pdf", "zip"])
def test_m16_owner_expiry_mime_limits(monkeypatch, record, status, mode):
    flags = get_settings()
    monkeypatch.setattr(flags, "extract_pages_tools_enabled", True)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", True)
    with pytest.raises(HTTPException) as exc:
        _submit(monkeypatch, record, mode)
    assert exc.value.status_code == status


def test_m16_strict_schema_and_retry_scope_gate(monkeypatch):
    with pytest.raises(ValidationError):
        pdf_extract_pages.ExtractPagesRequest(file_id="a", pages="1", format="gif")
    with pytest.raises(ValidationError):
        pdf_extract_pages.ExtractPagesRequest(file_id="a", pages="1", format="pdf", url="file:///etc/passwd")
    with pytest.raises(ValidationError):
        pdf_extract_pages.ExtractPagesRequest(file_id="a", pages=True)
    with pytest.raises(ValidationError):
        pdf_extract_pages.ExtractPagesRequest(file_id="a", pages="0")
    flags = get_settings()
    monkeypatch.setattr(flags, "extract_pages_tools_enabled", False)
    job = SimpleNamespace(operation="extract-pages-pdf")
    principal = SimpleNamespace(scopes={"pdf:split"})
    with pytest.raises(HTTPException) as exc:
        _require_operation_scope(job, principal)
    assert exc.value.status_code == 404
    monkeypatch.setattr(flags, "extract_pages_tools_enabled", True)
    _require_operation_scope(job, principal)
    principal.scopes = set()
    with pytest.raises(HTTPException) as exc:
        _require_operation_scope(job, principal)
    assert exc.value.status_code == 403


def _db_job(monkeypatch, tmp_path, *, mode="pdf"):
    flags = get_settings()
    monkeypatch.setattr(flags, "data_dir", tmp_path)
    monkeypatch.setattr(flags, "extract_pages_tools_enabled", True)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", True)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    source = source_pdf(tmp_path / "originals" / "source.pdf")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="member-one", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=30, webhook_url=None,
        ))
        file = FileRecord(
            original_name="source.pdf", stored_name="source.pdf",
            content_type="application/pdf", size=source.stat().st_size,
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_system="member-one",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(file)
        db.flush()
        job = JobRecord(
            operation=f"extract-pages-{mode}", status="queued",
            requested_by="member-one",
            input_file_ids_json=f'["{file.id}"]',
            params_json='{"pages":"3,1","format":"' + mode + '"}',
        )
        db.add(job)
        db.commit()
        return job.id


@pytest.mark.parametrize("mode,expected_roles", [
    ("pdf", {("result", None)}),
    ("zip", {("bundle", None), ("part", 1), ("part", 2)}),
])
def test_m16_real_worker_persists_pdf_or_zip_parts(monkeypatch, tmp_path, mode, expected_roles):
    job_id = _db_job(monkeypatch, tmp_path, mode=mode)
    result_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "completed" and job.output_file_id == result_id
        artifacts = db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all()
        assert {(link.role, link.ordinal) for link in artifacts} == expected_roles
        for link in artifacts:
            file = db.get(FileRecord, link.file_id)
            assert file.source_system == "member-one"
            data = storage.path_for_stored_name(file.stored_name).read_bytes()
            if link.role in {"result", "part"}:
                assert file.content_type == "application/pdf"
                assert len(PdfReader(io.BytesIO(data), strict=True).pages) == (
                    2 if link.role == "result" else 1
                )
            else:
                assert file.content_type == "application/zip"
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    assert len(archive.namelist()) == 2
                    assert archive.testzip() is None


@pytest.mark.parametrize("mode", ["pdf", "zip"])
def test_m16_worker_revoked_feature_does_not_commit(monkeypatch, tmp_path, mode):
    job_id = _db_job(monkeypatch, tmp_path, mode=mode)
    monkeypatch.setattr(get_settings(), "extract_pages_tools_enabled", False)
    with pytest.raises(ValueError, match="unauthorized or disabled"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all() == []
    assert list((tmp_path / "processed").iterdir()) == []


def test_m16_zip_part_store_failure_rolls_back_atomically(monkeypatch, tmp_path):
    job_id = _db_job(monkeypatch, tmp_path, mode="zip")
    original_store = worker_tasks.store_staged_file

    def break_second_part(path, area, filename=None):
        if filename and filename.endswith("part-0002-page-0001.pdf"):
            raise OSError("simulated M16 store interruption")
        return original_store(path, area, filename=filename)

    monkeypatch.setattr(worker_tasks, "store_staged_file", break_second_part)
    with pytest.raises(OSError, match="M16 store interruption"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id)).all() == []
        assert len(db.scalars(select(FileRecord)).all()) == 1
    assert list((tmp_path / "processed").iterdir()) == []
