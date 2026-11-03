"""F01/F11: real PDF inventory, bounded OCR/PDF-A and owner/flag checks."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services import pdf_tools
from app.services.from_pdf_ocr_pdfa import convert_accessible_pdf
from app.worker_tasks import _output_spec_for_job


def _source(path: Path, pages: int = 2) -> None:
    c = Canvas(str(path), pagesize=(240, 180))
    for n in range(pages):
        c.drawString(25, 105, f"Original PDF source page {n + 1}")
        c.showPage()
    c.save()


def test_f01_real_pdf_keeps_page_count(monkeypatch, tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "ocr.pdf"
    _source(source, pages=2)
    captured = []
    def engine(pdf, dest, languages, deskew, rotate_pages):
        captured.append((languages, deskew, rotate_pages))
        shutil.copyfile(pdf, dest)
    monkeypatch.setattr(pdf_tools, "ocr", engine)
    before = source.read_bytes()
    convert_accessible_pdf(
        source, output, kind="ocr", languages="tha+eng",
        deskew=True, rotate_pages=False,
    )
    assert captured == [("tha+eng", True, False)]
    assert len(PdfReader(str(output)).pages) == 2
    assert source.read_bytes() == before


def test_f11_refuses_pdfa_without_xmp_and_cleans_output(monkeypatch, tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "pdfa.pdf"
    _source(source)
    monkeypatch.setattr(pdf_tools, "pdfa", lambda pdf, dest, languages:
                        shutil.copyfile(pdf, dest))
    with pytest.raises(ValueError, match="PDF/A-2"):
        convert_accessible_pdf(source, output, kind="pdfa-2")
    assert not output.exists()


def test_reject_page_loss_and_never_keep_partial_output(monkeypatch, tmp_path):
    source, output = tmp_path / "original.pdf", tmp_path / "lossy.pdf"
    single = tmp_path / "one.pdf"
    _source(source, pages=2)
    _source(single, pages=1)
    monkeypatch.setattr(pdf_tools, "ocr", lambda pdf, dest, **kwargs:
                        shutil.copyfile(single, dest))
    with pytest.raises(ValueError, match="page inventory"):
        convert_accessible_pdf(source, output, kind="ocr")
    assert not output.exists()


def test_encrypted_pdf_symlink_and_existing_output_protected(tmp_path):
    source = tmp_path / "source.pdf"
    _source(source)
    symlink = tmp_path / "source-link.pdf"
    symlink.symlink_to(source)
    with pytest.raises(ValueError):
        convert_accessible_pdf(symlink, tmp_path / "alias.pdf", kind="ocr")
    existing = tmp_path / "existing.pdf"
    existing.write_bytes(b"owner-original")
    with pytest.raises(ValueError):
        convert_accessible_pdf(source, existing, kind="ocr")
    assert existing.read_bytes() == b"owner-original"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    protected = tmp_path / "encrypted.pdf"
    with protected.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        convert_accessible_pdf(protected, tmp_path / "result.pdf", kind="ocr")


@pytest.mark.parametrize("kwargs", [
    {"kind": "unknown"}, {"kind": "ocr", "languages": "eng;rm"},
    {"kind": "ocr", "deskew": "true"}, {"kind": "pdfa-2", "rotate_pages": True},
])
def test_reject_unrecognized_or_unsafe_parameters(tmp_path, kwargs):
    source = tmp_path / "source.pdf"
    _source(source)
    with pytest.raises(ValueError):
        convert_accessible_pdf(source, tmp_path / "result.pdf", **kwargs)


@pytest.mark.skipif(shutil.which("ocrmypdf") is None,
                    reason="OCRmyPDF binary unavailable in host environment")
def test_true_pdfa2_xmp_from_ocrmypdf(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "archival.pdf"
    _source(source, pages=1)
    convert_accessible_pdf(
        source, output, kind="pdfa-2", languages="eng",
    )
    assert len(PdfReader(str(output), strict=True).pages) == 1
    assert output.stat().st_size > 100


def _record(*, owner="member-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _post(monkeypatch, record, operation):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, op, ids, params:
            {"operation": op, "ids": ids, "params": params, "owner": principal.name},
    )
    principal = SimpleNamespace(name="member-a")
    db = SimpleNamespace(get=lambda model, ident: record)
    if operation == "pdf-to-ocr":
        return from_pdf.pdf_to_ocr(
            from_pdf.PdfOcrRequest(file_id="source-id"),
            principal=principal, db=db,
        )
    return from_pdf.pdf_to_pdfa(
        from_pdf.PdfArchiveRequest(file_id="source-id"),
        principal=principal, db=db,
    )


@pytest.mark.parametrize("operation", ["pdf-to-ocr", "pdf-to-pdfa"])
def test_default_off_and_heavy_queue_mime(monkeypatch, operation):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job(operation) == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation(operation)
    with pytest.raises(HTTPException) as err:
        _post(monkeypatch, _record(), operation)
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation(operation) == "heavy"
    submitted = _post(monkeypatch, _record(), operation)
    assert submitted["operation"] == operation
    assert submitted["ids"] == ["source-id"]
    assert submitted["owner"] == "member-a"
    assert submitted["params"]["languages"] == "tha+eng"


@pytest.mark.parametrize("record,status", [
    (_record(owner="member-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="image.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=21*1024*1024), 413),
])
def test_owner_expiry_mime_and_source_limit(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    for operation in ("pdf-to-ocr", "pdf-to-pdfa"):
        with pytest.raises(HTTPException) as err:
            _post(monkeypatch, record, operation)
        assert err.value.status_code == status


def test_request_schemas_fail_closed():
    with pytest.raises(ValidationError):
        from_pdf.PdfOcrRequest(file_id="source-id", languages="spa")
    with pytest.raises(ValidationError):
        from_pdf.PdfArchiveRequest(file_id="source-id", url="http://localhost")
