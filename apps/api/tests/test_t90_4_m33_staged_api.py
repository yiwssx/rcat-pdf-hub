"""M33 default-off form HTTP, owner, request and queue contracts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import pdf_filler
from app.worker_tasks import _output_spec_for_job


def _file(*, owner="user:teacher", mime="application/pdf", name="form.pdf",
          size=1000, expired=False):
    return SimpleNamespace(
        source_system=owner,
        content_type=mime,
        original_name=name,
        size=size,
        expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)) if expired else None,
    )


def _submit(monkeypatch, source, *, owner="user:teacher", updates=None):
    data = updates if updates is not None else {"teacher": "RCAT"}
    result = {}
    def fake_job(db, principal, operation, file_ids, parameters):
        result.update(operation=operation, file_ids=file_ids,
                      params=parameters, owner=principal.name)
        return result
    monkeypatch.setattr(pdf_filler, "_create_job", fake_job)
    db = SimpleNamespace(get=lambda model, file_id: source)
    principal = SimpleNamespace(name=owner)
    req = pdf_filler.PdfFormFillRequest(file_id="form-file", updates=data)
    return pdf_filler.fill_pdf_form(req, principal=principal, db=db)


def test_m33_default_off_hidden_route_and_pdf_output(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "pdf_filler_tools_enabled", False)
    with pytest.raises(HTTPException) as denied:
        _submit(monkeypatch, _file())
    assert denied.value.status_code == 404
    with pytest.raises(ValueError):
        queue_class_for_operation("fill-pdf-form")
    assert _output_spec_for_job("fill-pdf-form") == (".pdf", "application/pdf")


def test_m33_owner_bound_job_has_exact_operation_and_pdf_queue(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "pdf_filler_tools_enabled", True)
    value = _submit(monkeypatch, _file(),
                    updates={"teacher": "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"})
    assert value == {
        "operation": "fill-pdf-form",
        "file_ids": ["form-file"],
        "params": {"updates": {"teacher": "วิทยาลัยเกษตรและเทคโนโลยีร้อยเอ็ด"}},
        "owner": "user:teacher",
    }
    assert queue_class_for_operation("fill-pdf-form") == "pdf"


@pytest.mark.parametrize("source,user,status", [
    (_file(owner="user:other"), "user:teacher", 403),
    (_file(expired=True), "user:teacher", 410),
    (_file(mime="image/png"), "user:teacher", 415),
    (_file(name="not-pdf.txt"), "user:teacher", 415),
    (_file(size=25 * 1024 * 1024), "user:teacher", 413),
    (None, "user:teacher", 404),
])
def test_m33_denies_nonowner_expired_wrong_mime_and_size(monkeypatch, source, user, status):
    monkeypatch.setattr(get_settings(), "pdf_filler_tools_enabled", True)
    with pytest.raises(HTTPException) as denied:
        _submit(monkeypatch, source, owner=user)
    assert denied.value.status_code == status


@pytest.mark.parametrize("updates", [
    {}, {"field": "a" * 1025}, {"field": "bad\x00control"},
    {"bad\nfield": "value"}, {"field": 10}, {"field": None},
])
def test_m33_strict_request_refuses_out_of_bounds_updates(updates):
    with pytest.raises(ValidationError):
        pdf_filler.PdfFormFillRequest(file_id="form-file", updates=updates)


def test_m33_rejects_unknown_payload_parameters():
    with pytest.raises(ValidationError):
        pdf_filler.PdfFormFillRequest(file_id="form-file",
                                     updates={"teacher": "RCAT"}, extra="foo")
