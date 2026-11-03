"""M14/M15: real page content/order, strict bad-page refusal and owner gates."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
import pytest
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import manage_page_tools
from app.services.pdf_page_selection import select_pdf_pages
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, count=4):
    canvas = Canvas(str(path), pagesize=(250, 160))
    for number in range(1, count+1):
        canvas.drawString(28, 90, f"Unique source page {number}")
        canvas.showPage()
    canvas.save()


@pytest.mark.parametrize("operation,pages,expected", [
    ("delete", [2, 4], [1, 3]),
    ("delete", [1, 2, 3], [4]),
    ("reorder", [4, 2, 1, 3], [4, 2, 1, 3]),
    ("reorder", [1, 2, 3, 4], [1, 2, 3, 4]),
])
def test_real_pdf_selection_preserves_correct_page_contents(
    tmp_path, operation, pages, expected,
):
    source = tmp_path / "source.pdf"
    output = tmp_path / "selected.pdf"
    _pdf(source)
    before = source.read_bytes()
    select_pdf_pages(source, output, operation=operation, pages=pages)
    assert source.read_bytes() == before
    result = PdfReader(str(output), strict=True)
    assert len(result.pages) == len(expected)
    for n, page in zip(expected, result.pages):
        assert f"Unique source page {n}" in (page.extract_text() or "")


@pytest.mark.parametrize("operation,pages", [
    ("delete", [1, 1]), ("delete", [0]), ("delete", [5]),
    ("delete", [1, 2, 3, 4]), ("delete", [True]),
    ("reorder", [4, 3, 2]), ("reorder", [4, 3, 2, 2]),
    ("reorder", [0, 1, 2, 3]), ("reorder", [1, 2, 3, 5]),
    ("reorder", [1, 2, 3, "4"]),
])
def test_invalid_pages_fail_without_output(tmp_path, operation, pages):
    source = tmp_path / "source.pdf"
    _pdf(source)
    output = tmp_path / "unsafe.pdf"
    with pytest.raises(ValueError):
        select_pdf_pages(source, output, operation=operation, pages=pages)
    assert not output.exists()


def test_encrypted_symlink_and_existing_output_refused(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    link = tmp_path / "link.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        select_pdf_pages(link, tmp_path / "link-output.pdf",
                         operation="delete", pages=[1])
    prior = tmp_path / "prior.pdf"
    prior.write_bytes(b"do-not-overwrite")
    with pytest.raises(ValueError):
        select_pdf_pages(source, prior, operation="delete", pages=[1])
    assert prior.read_bytes() == b"do-not-overwrite"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        select_pdf_pages(locked, tmp_path / "decrypted.pdf",
                         operation="reorder", pages=[1, 2, 3, 4])


def _record(*, owner="member-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _post(monkeypatch, rec, op):
    monkeypatch.setattr(
        manage_page_tools, "_create_job",
        lambda db, principal, operation, ids, params:
            {"operation": operation, "ids": ids, "params": params,
             "owner": principal.name},
    )
    principal = SimpleNamespace(name="member-a")
    db = SimpleNamespace(get=lambda model, fid: rec)
    if op == "delete-pdf-pages":
        return manage_page_tools.delete_pages(
            manage_page_tools.DeletePagesRequest(file_id="file-id", pages=[2]),
            principal=principal, db=db,
        )
    return manage_page_tools.reorder_pages(
        manage_page_tools.ReorderPagesRequest(file_id="file-id",
                                              order=[2, 1]),
        principal=principal, db=db,
    )


@pytest.mark.parametrize("op", ["delete-pdf-pages", "reorder-pdf-pages"])
def test_default_off_and_authorized_queue_workflow(monkeypatch, op):
    monkeypatch.setattr(get_settings(), "manage_page_tools_enabled", False)
    assert _output_spec_for_job(op) == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation(op)
    with pytest.raises(HTTPException) as error:
        _post(monkeypatch, _record(), op)
    assert error.value.status_code == 404
    monkeypatch.setattr(get_settings(), "manage_page_tools_enabled", True)
    assert queue_class_for_operation(op) == "pdf"
    result = _post(monkeypatch, _record(), op)
    assert result["operation"] == op and result["owner"] == "member-a"
    assert result["params"]["pages"] == (
        [2] if op == "delete-pdf-pages" else [2, 1]
    )


@pytest.mark.parametrize("record,status", [
    (_record(owner="member-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="wrong.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=25 * 1024 * 1024), 413),
])
def test_user_ownership_expiry_mime_budget(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "manage_page_tools_enabled", True)
    for op in ("delete-pdf-pages", "reorder-pdf-pages"):
        with pytest.raises(HTTPException) as error:
            _post(monkeypatch, record, op)
        assert error.value.status_code == status


def test_page_request_schema_is_strict():
    with pytest.raises(ValidationError):
        manage_page_tools.DeletePagesRequest(file_id="a", pages=[True])
    with pytest.raises(ValidationError):
        manage_page_tools.ReorderPagesRequest(file_id="a", order=["1", 2])
    with pytest.raises(ValidationError):
        manage_page_tools.DeletePagesRequest(
            file_id="a", pages=[1], url="http://127.0.0.1",
        )
