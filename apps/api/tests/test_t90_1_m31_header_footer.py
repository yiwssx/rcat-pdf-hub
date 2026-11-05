"""M31 header/footer acceptance: real PDF, rotation, template guards and rollback."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select

from app import storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import pdf_header_footer
from app.routers.jobs import _require_operation_scope
from app.services.pdf_header_footer_bounded import (
    header_footer_pdf_bounded,
    validate_header_footer_params,
)
from app.worker_tasks import _output_spec_for_job


def source_pdf(path: Path) -> Path:
    surface = Canvas(str(path), pagesize=(480, 720))
    surface.drawString(40, 330, "M31 FIRST PAGE SOURCE TEXT")
    surface.showPage()
    surface.setPageSize((700, 480))
    surface.drawString(40, 280, "M31 SECOND PAGE SOURCE TEXT")
    surface.showPage()
    surface.save()
    # A rotated landscape input must remain legible in the output.
    writer = PdfWriter(clone_from=str(path))
    writer.pages[1].rotate(90)
    with path.open("wb") as output:
        writer.write(output)
    return path


def options(**overrides):
    return {
        "header": "RCAT Header {page}/{total}",
        "footer": "RCAT Footer {page}",
        "font_size": 12,
        "margin": 30,
        "header_align": "left",
        "footer_align": "right",
        **overrides,
    }


def test_m31_native_pdf_mixed_page_rotation_templates_and_original_hash(tmp_path):
    source = source_pdf(tmp_path / "source.pdf")
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    result = tmp_path / "result.pdf"
    header_footer_pdf_bounded(source, result, params=options())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha
    assert result.read_bytes().startswith(b"%PDF-")
    before = PdfReader(str(source), strict=True)
    after = PdfReader(str(result), strict=True)
    assert len(after.pages) == len(before.pages) == 2
    for number in (1, 2):
        page = after.pages[number - 1]
        text = page.extract_text()
        assert f"RCAT Header {number}/2" in text
        assert f"RCAT Footer {number}" in text
        assert f"M31 {'FIRST' if number == 1 else 'SECOND'} PAGE SOURCE TEXT" in text
        assert int(page.get("/Rotate", 0)) % 360 == 0
    assert abs(float(after.pages[0].mediabox.width) - 480) <= 0.1
    assert abs(float(after.pages[1].mediabox.width) - 480) <= 0.1
    assert abs(float(after.pages[1].mediabox.height) - 700) <= 0.1


def test_m31_thai_header_with_font_and_overlays(tmp_path):
    from app.services.pdf_header_footer import _font
    if _font() == "Helvetica":
        pytest.skip("Host has no Noto Thai; CI Docker installs fonts-noto-core")
    source = source_pdf(tmp_path / "source.pdf")
    result = tmp_path / "thai.pdf"
    header_footer_pdf_bounded(
        source, result, params=options(
            header="วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด {page}",
            footer="เลขหน้า {page}/{total}",
            header_align="center", footer_align="center",
        ),
    )
    check = PdfReader(str(result), strict=True)
    assert len(check.pages) == 2
    assert "M31 FIRST PAGE SOURCE TEXT" in check.pages[0].extract_text()
    assert "M31 SECOND PAGE SOURCE TEXT" in check.pages[1].extract_text()
    assert result.stat().st_size > source.stat().st_size


@pytest.mark.parametrize("override", [
    {"header": "", "footer": ""},
    {"header": "{foo}"},
    {"header": "{page.__class__}"},
    {"footer": "{page:x}"},
    {"header": "{page!r}"},
    {"header": "x" * 257},
    {"header": "first\nsecond"},
    {"footer": "blocked\u202econtrol"},
    {"font_size": True},
    {"font_size": 7},
    {"font_size": 25},
    {"margin": 11},
    {"margin": 145},
    {"header_align": "diagonal"},
    {"footer_align": "random"},
    {"header_align": 1},
])
def test_m31_schema_rejects_unbounded_or_malicious_templates(override):
    with pytest.raises((ValueError, TypeError)):
        validate_header_footer_params(options(**override))


def test_m31_schema_rejects_unknown_missing_fields_and_input_spoofing():
    for params in [
        {**options(), "file_id": "another-file"},
        {k: v for k, v in options().items() if k != "margin"},
        {"header": "OK"},
        ["header", "footer"],
    ]:
        with pytest.raises(ValueError):
            validate_header_footer_params(params)
    with pytest.raises(ValidationError):
        pdf_header_footer.HeaderFooterRequest(
            file_id="file", header="allowed", unknown_param="unexpected",
        )
    with pytest.raises(ValidationError):
        pdf_header_footer.HeaderFooterRequest(
            file_id="file", footer="{page.__class__}",
        )
    with pytest.raises(ValidationError):
        pdf_header_footer.HeaderFooterRequest(
            file_id="file", header="header", font_size=True,
        )


def test_m31_rejects_encrypted_annotated_form_and_overwrite(tmp_path):
    source = source_pdf(tmp_path / "source.pdf")
    result = tmp_path / "existing.pdf"
    result.write_bytes(b"never overwrite")
    with pytest.raises(ValueError, match="destination new"):
        header_footer_pdf_bounded(source, result, params=options())
    assert result.read_bytes() == b"never overwrite"
    result.unlink()

    linked = tmp_path / "source-link.pdf"
    linked.symlink_to(source)
    with pytest.raises(ValueError, match="regular"):
        header_footer_pdf_bounded(linked, result, params=options())

    locked = tmp_path / "locked.pdf"
    writer = PdfWriter(clone_from=str(source))
    writer.encrypt("password", algorithm="AES-256")
    writer.write(str(locked))
    with pytest.raises(ValueError, match="encrypted"):
        header_footer_pdf_bounded(locked, result, params=options())

    form = tmp_path / "form.pdf"
    writer = PdfWriter(clone_from=str(source))
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"): ArrayObject([]),
    })
    writer.write(str(form))
    with pytest.raises(ValueError, match="interactive"):
        header_footer_pdf_bounded(form, result, params=options())

    annotated = tmp_path / "annotated.pdf"
    writer = PdfWriter(clone_from=str(source))
    writer.pages[0][NameObject("/Annots")] = ArrayObject([])
    writer.write(str(annotated))
    with pytest.raises(ValueError, match="annotated"):
        header_footer_pdf_bounded(annotated, result, params=options())
    assert not result.exists()


def test_m31_rejects_text_outside_page_and_preserves_destination(tmp_path):
    original = source_pdf(tmp_path / "source.pdf")
    destination = tmp_path / "bad.pdf"
    with pytest.raises(ValueError, match="page width"):
        header_footer_pdf_bounded(
            original, destination, params=options(header="A" * 250, font_size=24),
        )
    assert not destination.exists()


def _record(owner="rcat-user", *, mime="application/pdf", name="source.pdf", size=1024, expired=False):
    return SimpleNamespace(
        source_system=owner,
        content_type=mime,
        original_name=name,
        size=size,
        expires_at=datetime.now(timezone.utc) + timedelta(days=-1 if expired else 1),
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(
        pdf_header_footer, "_create_job",
        lambda db, principal, operation, ids, params: {
            "owner": principal.name,
            "operation": operation,
            "files": ids, "params": params,
        },
    )
    return pdf_header_footer.header_footer_request(
        pdf_header_footer.HeaderFooterRequest(file_id="record", **options()),
        principal=SimpleNamespace(name="rcat-user"),
        db=SimpleNamespace(get=lambda _model, _id: record),
    )


def test_m31_route_feature_permission_and_queue_contract(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "header_footer_tools_enabled", False)
    assert _output_spec_for_job("header-and-footer") == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation("header-and-footer")
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, _record())
    assert error.value.status_code == 404

    monkeypatch.setattr(flags, "header_footer_tools_enabled", True)
    assert queue_class_for_operation("header-and-footer") == "pdf"
    result = _submit(monkeypatch, _record())
    assert result == {
        "owner": "rcat-user",
        "operation": "header-and-footer",
        "files": ["record"], "params": options(),
    }
    _require_operation_scope(
        SimpleNamespace(operation="header-and-footer"),
        SimpleNamespace(scopes={"pdf:header-footer"}),
    )
    with pytest.raises(HTTPException) as denied:
        _require_operation_scope(
            SimpleNamespace(operation="header-and-footer"),
            SimpleNamespace(scopes={"pdf:grayscale"}),
        )
    assert denied.value.status_code == 403


@pytest.mark.parametrize("record,status", [
    (_record(owner="someone-else"), 403),
    (_record(mime="image/jpeg"), 415),
    (_record(name="source.docx"), 415),
    (_record(expired=True), 410),
    (_record(size=18 * 1024 * 1024), 413),
])
def test_m31_api_rejects_foreign_or_bad_source(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "header_footer_tools_enabled", True)
    with pytest.raises(HTTPException) as raised:
        _submit(monkeypatch, record)
    assert raised.value.status_code == status


def _queued_job(monkeypatch, tmp_path):
    flags = get_settings()
    monkeypatch.setattr(flags, "data_dir", tmp_path)
    monkeypatch.setattr(flags, "header_footer_tools_enabled", True)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    source = source_pdf(tmp_path / "originals" / "original.pdf")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="rcat-user", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=64, webhook_url=None,
        ))
        record = FileRecord(
            original_name="original.pdf", stored_name="original.pdf",
            content_type="application/pdf", size=source.stat().st_size,
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_system="rcat-user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(record)
        db.flush()
        job = JobRecord(
            operation="header-and-footer", status="queued", requested_by="rcat-user",
            input_file_ids_json=json.dumps([record.id]),
            params_json=json.dumps(options()),
        )
        db.add(job)
        db.commit()
        return job.id, hashlib.sha256(source.read_bytes()).hexdigest()


def test_m31_real_db_worker_preserves_text_and_artifacts(monkeypatch, tmp_path):
    job_id, original_hash = _queued_job(monkeypatch, tmp_path)
    monkeypatch.setattr(
        worker_tasks, "_auto_archive",
        lambda *_args: pytest.fail("M31 output unexpectedly auto-archived"),
    )
    output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        record = db.get(FileRecord, output_id)
        links = db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all()
        assert job.status == "completed" and job.output_file_id == record.id
        assert record.source_system == "rcat-user" and record.content_type == "application/pdf"
        assert len(links) == 1 and links[0].role == "result"
        output = storage.path_for_stored_name(record.stored_name)
        pdf = PdfReader(str(output), strict=True)
        assert len(pdf.pages) == 2
        for i, page in enumerate(pdf.pages, 1):
            assert f"RCAT Header {i}/2" in page.extract_text()
            assert f"RCAT Footer {i}" in page.extract_text()
        original = storage.path_for_stored_name("original.pdf")
        assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash


def test_m31_worker_revoked_flag_and_tampered_parameters_fail_closed(monkeypatch, tmp_path):
    job_id, _ = _queued_job(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "header_footer_tools_enabled", False)
    with pytest.raises(RuntimeError, match="M31 header/footer conversion failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all() == []

    monkeypatch.setattr(get_settings(), "header_footer_tools_enabled", True)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        job.status = "queued"
        job.params_json = json.dumps({**options(), "unexpected": "injection"})
        db.commit()
    with pytest.raises(RuntimeError, match="M31 header/footer conversion failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all() == []


def test_m31_storage_failure_rolls_back_without_partial_outputs(monkeypatch, tmp_path):
    job_id, _ = _queued_job(monkeypatch, tmp_path)
    def fail_upload(*_args, **_kwargs):
        raise OSError("simulated M31 storage error, must not leak paths")
    monkeypatch.setattr(worker_tasks, "store_staged_file", fail_upload)
    with pytest.raises(RuntimeError, match="M31 header/footer conversion failed"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.output_file_id is None
        assert db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all() == []
        assert len(db.scalars(select(FileRecord)).all()) == 1
        assert "simulated M31 storage error" not in (job.error or "")
    assert list((tmp_path / "processed").iterdir()) == []
