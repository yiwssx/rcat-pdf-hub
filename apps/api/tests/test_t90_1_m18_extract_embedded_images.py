"""M18 genuine embedded-image extraction and source-owner-bound artifacts."""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select

from app import storage, worker_tasks
from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord, JobOutputArtifact, JobRecord, ServicePolicy
from app.queue import queue_class_for_operation
from app.routers import pdf_extract_images
from app.routers.jobs import _require_operation_scope
from app.services.pdf_extract_embedded_images import (
    _validate_image, extract_embedded_images_zip,
    stage_embedded_image_parts,
)
from app.worker_tasks import _output_spec_for_job


def make_source(tmp_path: Path, *, with_images=True) -> Path:
    source = tmp_path / "source.pdf"
    picture1 = tmp_path / "picture-1.png"
    picture2 = tmp_path / "picture-2.png"
    Image.new("RGB", (40, 24), (223, 45, 19)).save(picture1)
    Image.new("RGB", (25, 30), (5, 89, 219)).save(picture2)
    c = Canvas(str(source))
    c.setPageSize((360, 420))
    c.drawString(30, 330, "M18 text is not an image")
    if with_images:
        c.drawImage(str(picture1), 20, 80, width=80, height=48)
    c.showPage()
    c.drawString(30, 330, "M18 source page two")
    if with_images:
        c.drawImage(str(picture2), 35, 100, width=60, height=72)
    c.showPage()
    c.save()
    return source


def test_m18_extracts_real_pdf_embedded_images_not_page_screenshots(tmp_path):
    source = make_source(tmp_path)
    output = tmp_path / "images.zip"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    extract_embedded_images_zip(source, output)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert output.read_bytes().startswith(b"PK\x03\x04")
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == 2
        assert names[0].startswith("page-0001-image-0001.")
        assert names[1].startswith("page-0002-image-0001.")
        for name, expected_size in zip(names, [(40, 24), (25, 30)], strict=True):
            with Image.open(io.BytesIO(archive.read(name))) as picture:
                assert picture.size == expected_size
                assert picture.format in {"PNG", "JPEG"}
    staged = stage_embedded_image_parts(output, tmp_path / "staged")
    assert [item.ordinal for item in staged] == [1, 2]
    assert all(item.content_type in {"image/png", "image/jpeg"} for item in staged)
    assert all(item.path.is_file() for item in staged)


def test_m18_without_images_fails_without_output(tmp_path):
    source = make_source(tmp_path, with_images=False)
    dest = tmp_path / "empty.zip"
    with pytest.raises(ValueError, match="no embedded images"):
        extract_embedded_images_zip(source, dest)
    assert not dest.exists()


def test_m18_encrypted_symlink_overwrite_and_truncated_input(tmp_path):
    source = make_source(tmp_path)
    dest = tmp_path / "zip"
    dest.write_bytes(b"must-stay")
    with pytest.raises(ValueError, match="new destination"):
        extract_embedded_images_zip(source, dest)
    assert dest.read_bytes() == b"must-stay"
    dest.unlink()
    linked = tmp_path / "symlink.pdf"
    linked.symlink_to(source)
    with pytest.raises(ValueError, match="regular source"):
        extract_embedded_images_zip(linked, dest)
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("known-password")
    encrypted = tmp_path / "encrypted.pdf"
    with encrypted.open("wb") as out:
        writer.write(out)
    with pytest.raises(ValueError, match="encrypted"):
        extract_embedded_images_zip(encrypted, dest)
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    with pytest.raises(ValueError):
        extract_embedded_images_zip(broken, dest)
    assert not dest.exists()


@pytest.mark.parametrize("filename", [
    "../outside.png", "page-0001-image-0001.svg", "page-0000-image-0001.png",
    "page-0001-image-0002.png", "page-9999-image-0001.png",
])
def test_m18_stage_rejects_traversal_or_unexpected_members(tmp_path, filename):
    image_bytes = io.BytesIO()
    Image.new("RGB", (12, 12)).save(image_bytes, format="PNG")
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr(filename, image_bytes.getvalue())
    with pytest.raises(ValueError):
        stage_embedded_image_parts(archive, tmp_path / "parts")


def test_m18_stage_rejects_non_image_and_zip_budget(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as out:
        out.writestr("page-0001-image-0001.png", b"%PDF-fake-data" * 12)
    with pytest.raises(ValueError):
        stage_embedded_image_parts(archive, tmp_path / "wrong-content")
    source = make_source(tmp_path)
    safe = tmp_path / "images.zip"
    extract_embedded_images_zip(source, safe)
    with pytest.raises(ValueError):
        stage_embedded_image_parts(safe, tmp_path / "small", max_bytes=65)
    with pytest.raises(ValueError):
        _validate_image(b"invalid image contents" * 8, "png")


def _record(owner="rcat-user", *, mime="application/pdf", name="source.pdf",
            size=1024, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=-1 if expired else 1),
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(pdf_extract_images, "_create_job",
                        lambda db, principal, operation, ids, params: {
                            "owner": principal.name, "operation": operation,
                            "file_ids": ids, "params": params,
                        })
    return pdf_extract_images.extract_images(
        pdf_extract_images.ExtractImagesRequest(file_id="record"),
        principal=SimpleNamespace(name="rcat-user"),
        db=SimpleNamespace(get=lambda _model, _id: record),
    )


def test_m18_route_queue_output_scope_and_feature_gate(monkeypatch):
    flags = get_settings()
    monkeypatch.setattr(flags, "extract_embedded_images_tools_enabled", False)
    assert _output_spec_for_job("extract-images") == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation("extract-images")
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, _record())
    assert err.value.status_code == 404
    monkeypatch.setattr(flags, "extract_embedded_images_tools_enabled", True)
    assert queue_class_for_operation("extract-images") == "pdf"
    assert _submit(monkeypatch, _record()) == {
        "owner": "rcat-user", "operation": "extract-images",
        "file_ids": ["record"], "params": {},
    }
    _require_operation_scope(
        SimpleNamespace(operation="extract-images"),
        SimpleNamespace(scopes={"pdf:extract-images"}),
    )
    with pytest.raises(HTTPException) as err:
        _require_operation_scope(
            SimpleNamespace(operation="extract-images"),
            SimpleNamespace(scopes={"pdf:pdf-to-image"}),
        )
    assert err.value.status_code == 403
    with pytest.raises(ValidationError):
        pdf_extract_images.ExtractImagesRequest(file_id="record", url="https://example.com")


@pytest.mark.parametrize("record,status", [
    (_record(owner="other-owner"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.txt"), 415),
    (_record(expired=True), 410),
    (_record(size=20 * 1024 * 1024), 413),
])
def test_m18_api_fails_closed_for_tenants_and_bad_input(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "extract_embedded_images_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, record)
    assert err.value.status_code == status


def _queued_job(monkeypatch, tmp_path, *, multipart=True):
    flags = get_settings()
    monkeypatch.setattr(flags, "data_dir", tmp_path)
    monkeypatch.setattr(flags, "extract_embedded_images_tools_enabled", True)
    monkeypatch.setattr(flags, "multi_output_artifacts_enabled", multipart)
    monkeypatch.setattr(worker_tasks, "scan_file", lambda _path: "clean")
    storage.ensure_storage()
    original = make_source(tmp_path)
    target = tmp_path / "originals" / "input.pdf"
    target.write_bytes(original.read_bytes())
    with SessionLocal() as db:
        db.add(ServicePolicy(
            service_name="rcat-user", rate_limit_per_minute=100,
            daily_job_limit=100, max_storage_mb=40, webhook_url=None,
        ))
        record = FileRecord(
            original_name="input.pdf", stored_name="input.pdf",
            content_type="application/pdf", size=target.stat().st_size,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            source_system="rcat-user",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(record)
        db.flush()
        job = JobRecord(
            operation="extract-images", status="queued", requested_by="rcat-user",
            input_file_ids_json=f'["{record.id}"]', params_json="{}",
        )
        db.add(job)
        db.commit()
        return job.id


@pytest.mark.parametrize("multipart,expected", [
    (False, {("bundle", None)}),
    (True, {("bundle", None), ("part", 1), ("part", 2)}),
])
def test_m18_real_worker_persists_zip_and_owner_bound_parts(monkeypatch, tmp_path, multipart, expected):
    job_id = _queued_job(monkeypatch, tmp_path, multipart=multipart)
    output_id = worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "completed" and job.output_file_id == output_id
        links = db.scalars(
            select(JobOutputArtifact).where(JobOutputArtifact.job_id == job_id),
        ).all()
        assert {(link.role, link.ordinal) for link in links} == expected
        for link in links:
            file = db.get(FileRecord, link.file_id)
            assert file.source_system == "rcat-user"
            data = storage.path_for_stored_name(file.stored_name).read_bytes()
            if link.role == "bundle":
                assert file.content_type == "application/zip"
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    assert len(archive.namelist()) == 2 and archive.testzip() is None
            else:
                assert file.content_type in {"image/png", "image/jpeg"}
                with Image.open(io.BytesIO(data)) as image:
                    assert image.size in {(40, 24), (25, 30)}


def test_m18_worker_revoked_feature_fails_without_artifacts(monkeypatch, tmp_path):
    job_id = _queued_job(monkeypatch, tmp_path)
    monkeypatch.setattr(get_settings(), "extract_embedded_images_tools_enabled", False)
    with pytest.raises(ValueError, match="unauthorized"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id,
        )).all() == []
    assert list((tmp_path / "processed").iterdir()) == []


def test_m18_part_upload_failure_compensates_all_files(monkeypatch, tmp_path):
    job_id = _queued_job(monkeypatch, tmp_path)
    normal = worker_tasks.store_staged_file

    def stop_at_second(path, area, filename=None):
        if filename and "page-0002-image-0001." in filename:
            raise OSError("simulated M18 part upload failure")
        return normal(path, area, filename=filename)

    monkeypatch.setattr(worker_tasks, "store_staged_file", stop_at_second)
    with pytest.raises(OSError, match="M18 part upload failure"):
        worker_tasks.process_job(job_id)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id,
        )).all() == []
        assert len(db.scalars(select(FileRecord)).all()) == 1
    assert list((tmp_path / "processed").iterdir()) == []
