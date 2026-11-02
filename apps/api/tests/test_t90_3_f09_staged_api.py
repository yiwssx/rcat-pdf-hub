"""F09 staging HTTP/queue contract: actual TIFF engine remains separately tested."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.worker_tasks import _output_spec_for_job


def _record(*, owner="user:one", mime="application/pdf", name="src.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)) if expired else None,
    )


def _submit(monkeypatch, record, *, user="user:one", dpi=96):
    result = {}
    def fake_job(db, principal, operation, ids, params):
        result.update(operation=operation, ids=ids, params=params, owner=principal.name)
        return result
    monkeypatch.setattr(from_pdf, "_create_job", fake_job)
    principal = SimpleNamespace(name=user)
    db = SimpleNamespace(get=lambda model, file_id: record)
    return from_pdf.pdf_to_tiff(from_pdf.PdfToTiffRequest(file_id="file-id", dpi=dpi),
                                principal=principal, db=db)


def test_staged_f09_default_off_and_separate_tiff_output_contract(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "from_pdf_tools_enabled", False)
    with pytest.raises(HTTPException) as exc:
        _submit(monkeypatch, _record())
    assert exc.value.status_code == 404
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-tiff")
    assert _output_spec_for_job("pdf-to-tiff") == (".tiff", "image/tiff")


def test_f09_owned_pdf_can_enqueue_bounded_heavy_job(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "from_pdf_tools_enabled", True)
    payload = _submit(monkeypatch, _record())
    assert payload == {
        "operation": "pdf-to-tiff",
        "ids": ["file-id"],
        "params": {"dpi": 96},
        "owner": "user:one",
    }
    assert queue_class_for_operation("pdf-to-tiff") == "heavy"


@pytest.mark.parametrize("record,user,expected", [
    (_record(owner="user:other"), "user:one", 403),
    (_record(mime="image/png"), "user:one", 415),
    (_record(name="different.bin"), "user:one", 415),
    (_record(expired=True), "user:one", 410),
    (_record(size=30 * 1024 * 1024), "user:one", 413),
])
def test_f09_rejects_nonowner_expired_bad_format_and_budget(monkeypatch, record, user, expected):
    settings = get_settings()
    monkeypatch.setattr(settings, "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as exc:
        _submit(monkeypatch, record, user=user)
    assert exc.value.status_code == expected


@pytest.mark.parametrize("bad", [0, 71, 301, True, 96.5, "96"])
def test_f09_rejects_noninteger_or_out_of_budget_dpi(bad):
    with pytest.raises(ValidationError):
        from_pdf.PdfToTiffRequest(file_id="file-id", dpi=bad)
