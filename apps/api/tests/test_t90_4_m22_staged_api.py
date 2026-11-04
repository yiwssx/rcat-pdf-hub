"""M22 staged API, owner isolation, strict request schema and disabled routing."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
import pytest

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import pdf_text_overlay
from app.worker_tasks import _output_spec_for_job


def _record(*, owner="teacher-a", name="original.pdf", mime="application/pdf",
            size=1200, expired=False):
    return SimpleNamespace(
        source_system=owner, original_name=name, content_type=mime, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(
        pdf_text_overlay, "_create_job",
        lambda db, principal, operation, file_ids, params: {
            "owner": principal.name,
            "operation": operation,
            "files": file_ids,
            "params": params,
        },
    )
    principal = SimpleNamespace(name="teacher-a")
    db = SimpleNamespace(get=lambda model, file_id: record)
    request = pdf_text_overlay.AddPdfTextRequest(
        file_id="file-1", page=2, x=18.0, y=45.0,
        font_size=12, text="RCAT PDF HUB",
    )
    return pdf_text_overlay.add_pdf_text(request, principal=principal, db=db)


def test_m22_queue_default_off_and_staged_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "pdf_text_overlay_tools_enabled", False)
    assert _output_spec_for_job("add-pdf-text") == (".pdf", "application/pdf")
    with pytest.raises(ValueError):
        queue_class_for_operation("add-pdf-text")
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, _record())
    assert error.value.status_code == 404
    monkeypatch.setattr(get_settings(), "pdf_text_overlay_tools_enabled", True)
    assert queue_class_for_operation("add-pdf-text") == "pdf"
    result = _submit(monkeypatch, _record())
    assert result["owner"] == "teacher-a"
    assert result["operation"] == "add-pdf-text"
    assert result["files"] == ["file-1"]
    assert result["params"] == {
        "page": 2, "x": 18.0, "y": 45.0,
        "font_size": 12, "text": "RCAT PDF HUB",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="different-owner"), 403),
    (_record(expired=True), 410),
    (_record(mime="image/png"), 415),
    (_record(name="source.txt"), 415),
    (_record(size=20 * 1024 * 1024), 413),
])
def test_m22_reject_wrong_owner_expiry_type_or_size(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "pdf_text_overlay_tools_enabled", True)
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, record)
    assert error.value.status_code == status


def test_m22_request_schema_rejects_unsafe_text_and_types():
    base = dict(file_id="file-1", page=1, x=20.0, y=30.0,
                font_size=12, text="Approved ASCII")
    for bad in (
        {"text": "ภาษาไทย"}, {"text": "line\nbreak"},
        {"text": " "}, {"page": True}, {"page": "1"},
        {"font_size": 0}, {"x": float("nan")}, {"x": -1.0},
        {"url": "http://127.0.0.1/"},
    ):
        with pytest.raises(ValidationError):
            pdf_text_overlay.AddPdfTextRequest(**(base | bad))
