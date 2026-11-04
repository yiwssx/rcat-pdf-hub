"""T90-1 M07: real per-page PDFs, ZIP safety, staged API and owner quota."""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select
import pytest

from app import storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import pdf_split_zip
from app.services.pdf_split_zip import (
    make_split_pdf_zip, selected_page_numbers, stage_split_pdf_parts,
)
from app.worker_tasks import _output_spec_for_job


def create_source(path: Path, count=5) -> Path:
    pdf = Canvas(str(path))
    for number in range(1, count + 1):
        pdf.setPageSize((290 + number * 11, 400 + number * 17))
        pdf.drawString(30, 300, f"RCAT SPLIT SOURCE PAGE {number}")
        pdf.showPage()
    pdf.save()
    return path


@pytest.mark.parametrize("expression,expected", [
    ("1", [1]),
    ("1,3,5", [1, 3, 5]),
    ("5-3", [5, 4, 3]),
    ("z-1", [5, 4, 3, 2, 1]),
    ("2-z", [2, 3, 4, 5]),
])
def test_m07_resolves_page_order(expression, expected):
    assert selected_page_numbers(expression, 5) == expected


@pytest.mark.parametrize("expression", [
    "", "0", "1,,2", "5-0", "6", "2,2", "1-3,3",
    "100001", "1-z;rm -rf", "1,z,5", "3-6",
])
def test_m07_rejects_bad_or_ambiguous_selection(expression):
    with pytest.raises(ValueError):
        selected_page_numbers(expression, 5)


@pytest.mark.parametrize("expression,expected", [
    ("1,3,5", [1, 3, 5]), ("5-3", [5, 4, 3]),
    ("1-z", [1, 2, 3, 4, 5]),
])
def test_real_individual_page_pdfs_and_unmodified_source(tmp_path, expression, expected):
    source = create_source(tmp_path / "input.pdf")
    bundle = tmp_path / "result.zip"
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    make_split_pdf_zip(source, bundle, pages=expression)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    assert bundle.read_bytes()[:4] == b"PK\x03\x04"
    with zipfile.ZipFile(bundle) as zip_file:
        assert zip_file.testzip() is None
        assert zip_file.namelist() == [
            f"part-{ordinal:04d}-page-{number:04d}.pdf"
            for ordinal, number in enumerate(expected, 1)
        ]
        for name, number in zip(zip_file.namelist(), expected, strict=True):
            page_reader = PdfReader(io.BytesIO(zip_file.read(name)), strict=True)
            assert not page_reader.is_encrypted
            assert len(page_reader.pages) == 1
            assert f"RCAT SPLIT SOURCE PAGE {number}" in page_reader.pages[0].extract_text()
            assert float(page_reader.pages[0].mediabox.width) == 290 + number * 11
    staged = stage_split_pdf_parts(bundle, tmp_path / "parts", pages=expected)
    assert [p.ordinal for p in staged] == list(range(1, len(expected) + 1))
    assert all(p.content_type == "application/pdf" and p.path.is_file() for p in staged)


def test_split_refuses_existing_output_symlink_and_encrypted_pdf(tmp_path):
    source = create_source(tmp_path / "source.pdf")
    output = tmp_path / "out.zip"
    output.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        make_split_pdf_zip(source, output, pages="1")
    assert output.read_bytes() == b"preserve"
    output.unlink()
    link = tmp_path / "link.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        make_split_pdf_zip(link, output, pages="1")
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("owner-pass")
    encrypted = tmp_path / "encrypted.pdf"
    with encrypted.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(ValueError, match="Encrypted"):
        make_split_pdf_zip(encrypted, output, pages="1")
    assert not output.exists()


def test_split_rejects_over_80_parts_and_source_over_200_pages():
    with pytest.raises(ValueError, match="Too many"):
        selected_page_numbers("1-81", 81)
    with pytest.raises(ValueError, match="count"):
        selected_page_numbers("1", 201)


@pytest.mark.parametrize("filename,payload", [
    ("../bad.pdf", b"%PDF-1.4\n"),
    ("part-0001-page-0002.pdf", b"%PDF-1.4\n"),
    ("part-0001-page-0001.pdf", b"fake-pdf-contents"),
])
def test_stage_blocks_traversal_wrong_page_and_fake_pdf(tmp_path, filename, payload):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(filename, payload)
    with pytest.raises(ValueError):
        stage_split_pdf_parts(archive, tmp_path / "staged", pages=[1])


def test_stage_rejects_decompression_budget(tmp_path):
    source = create_source(tmp_path / "source.pdf")
    bundle = tmp_path / "pages.zip"
    make_split_pdf_zip(source, bundle, pages="1")
    with pytest.raises(ValueError, match="Unsafe"):
        stage_split_pdf_parts(bundle, tmp_path / "too-small", pages=[1], max_bytes=200)


def _record(*, owner="school-a", mime="application/pdf", name="input.pdf",
            size=2000, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=datetime.now(timezone) + timedelta(days=-1 if expired else 1),
    )


def _post(monkeypatch, record):
    monkeypatch.setattr(pdf_split_zip, "_create_job",
                        lambda db, principal, op, ids, params: {
                            "owner": principal.name, "op": op,
                            "ids": ids, "params": params,
                        })
    return pdf_split_zip.split_to_zip(
        pdf_split_zip.SplitZipRequest(file_id="input", pages="5-3"),
        principal=SimpleNamespace(name="school-a"),
        db=SimpleNamespace(get=lambda model, fid: record),
    )


def test_m07_staged_gate_owner_and_queue(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "split_zip_tools_enabled", False)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", False)
    assert _output_spec_for_job("split") == (".pdf", "application/pdf")
    assert _output_spec_for_job("split-to-zip") == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation("split-to-zip")
    with pytest.raises(HTTPException) as denied:
        _post(monkeypatch, _record())
    assert denied.value.status_code == 404
    monkeypatch.setattr(flags, "split_zip_tools_enabled", True)
    with pytest.raises(HTTPException) as denied:
        _post(monkeypatch, _record())
    assert denied.value.status_code == 404
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", True)
    assert queue_class_for_operation("split-to-zip") == "pdf"
    assert queue_class_for_operation("split") == "interactive"
    created = _post(monkeypatch, _record())
    assert created == {
        "owner": "school-a", "op": "split-to-zip",
        "ids": ["input"], "params": {"pages": "5-3"},
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="another-owner"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="image.png"), 415),
    (_record(expired=True), 410),
    (_record(size=20 * 1024 * 1024), 413),
])
def test_m07_api_source_policy(monkeypatch, record, status):
    flags = get_settings()
    monkeypatch.setattr(flags, "split_zip_tools_enabled", True)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", True)
    with pytest.raises(HTTPException) as denied:
        _post(monkeypatch, record)
    assert denied.value.status_code == status


def test_m07_request_is_strict():
    with pytest.raises(ValidationError):
        pdf_split_zip.SplitZipRequest(file_id="input", pages="2-3", url="https://example.com")
    with pytest.raises(ValidationError):
        pdf_split_zip.SplitZipRequest(file_id="input", pages=True)
    with pytest.raises(ValidationError):
        pdf_split_zip.SplitZipRequest(file_id="input", pages="0,3")


def _real_job(monkeypatch, tmp_path):
    flags = get_settings()
    monkeypatch.setattr(flags, "data_dir", tmp_path)
    monkeypatch.setattr(flags, "split_zip_tools_enabled", True)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", True)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    source = create_source(tmp_path / "originals" / "source.pdf")
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="school-a", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=30, webhook_url=None,
        ))
        src = FileRecord(
            original_name="source.pdf", stored_name="source.pdf",
            content_type="application/pdf", size=source.stat().st_size,
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            source_system="school-a",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(src)
        db.flush()
        job = JobRecord(
            operation="split-to-zip", status="queued", requested_by="school-a",
            input_file_ids_json=f'["{src.id}"]',
            params_json='{"pages":"3,1"}',
        )
        db.add(job)
        db.commit()
        return job.id


def test_worker_persists_zip_and_owner_scoped_parts_atomically(monkeypatch, tmp_path):
    job_id = _real_job(monkeypatch, tmp_path)
    output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "completed" and job.output_file_id == output_id
        links = db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id,
        )).all()
        assert {(x.role, x.ordinal) for x in links} == {
            ("bundle", None), ("part", 1), ("part", 2),
        }
        for link in links:
            item = db.get(FileRecord, link.file_id)
            assert item.source_system == "school-a"
            assert storage.path_for_stored_name(item.stored_name).is_file()
            if link.role == "part":
                assert item.content_type == "application/pdf"
                actual = PdfReader(
                    str(storage.path_for_stored_name(item.stored_name)),
                    strict=True,
                )
                assert len(actual.pages) == 1


def test_worker_flag_revocation_fails_closed(monkeypatch, tmp_path):
    job_id = _real_job(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "split_zip_tools_enabled", False)
    with pytest.raises(ValueError, match="unauthorized"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id,
        )).all() == []
    assert list((tmp_path / "processed").iterdir()) == []


def test_worker_storage_failure_compensates_zip_and_parts(monkeypatch, tmp_path):
    job_id = _real_job(monkeypatch, tmp_path)
    original_store = worker_tasks.store_staged_file

    def partial_failure(path, area, filename=None):
        if filename and filename.endswith("part-0002-page-0001.pdf"):
            raise OSError("storage outage on second PDF part")
        return original_store(path, area, filename=filename)

    monkeypatch.setattr(worker_tasks, "store_staged_file", partial_failure)
    with pytest.raises(OSError, match="storage outage"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id,
        )).all() == []
    assert list((tmp_path / "processed").iterdir()) == []
