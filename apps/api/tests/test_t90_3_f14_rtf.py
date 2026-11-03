"""F14 strict text-only Unicode RTF: PDF, reader and owner tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_rtf import _rtf_escape, pdf_to_text_only_rtf
from app.worker_tasks import _output_spec_for_job


def _pdf(path, *, pages=2, graphics=False, multiple_columns=False):
    c = Canvas(str(path), pagesize=(400, 300))
    for n in range(pages):
        c.drawString(40, 230, f"First paragraph page {n+1}")
        c.drawString(170 if multiple_columns else 40, 200, "Second paragraph")
        if graphics:
            c.rect(35, 70, 200, 60)
        c.showPage()
    c.save()


@pytest.mark.parametrize("pages", [1, 2])
def test_real_pdf_text_to_rtf_with_page_breaks(tmp_path, pages):
    source, output = tmp_path / "source.pdf", tmp_path / "output.rtf"
    _pdf(source, pages=pages)
    original = source.read_bytes()
    pdf_to_text_only_rtf(source, output)
    data = output.read_bytes()
    assert source.read_bytes() == original
    assert data.startswith(b"{\\rtf1\\ansi")
    assert data.rstrip().endswith(b"}")
    assert data.count(b"\\page") == pages-1
    assert data.count(b"First paragraph page") == pages
    assert data.count(b"Second paragraph") == pages
    assert data.count(b"\\par") == pages*2


def test_rtf_escape_escapes_commands_and_unicode():
    output = _rtf_escape(r"{\} ไทย 😀")
    assert r"\{" in output and r"\}" in output and r"\\" in output
    assert r"\u" in output
    assert "ไทย" not in output and "😀" not in output
    assert "\\u" in output


@pytest.mark.parametrize("graphics,columns", [(True, False), (False, True)])
def test_refuses_graphic_pages_and_multicolumn_layout(tmp_path, graphics, columns):
    source = tmp_path / "complex.pdf"
    _pdf(source, graphics=graphics, multiple_columns=columns)
    output = tmp_path / "output.rtf"
    with pytest.raises(ValueError):
        pdf_to_text_only_rtf(source, output)
    assert not output.exists()


def test_encrypted_symlink_and_existing_output_are_rejected(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    symlink = tmp_path / "linked.pdf"
    symlink.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_text_only_rtf(symlink, tmp_path / "linked.rtf")
    dest = tmp_path / "existing.rtf"
    dest.write_bytes(b"prior-information")
    with pytest.raises(ValueError):
        pdf_to_text_only_rtf(source, dest)
    assert dest.read_bytes() == b"prior-information"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("password")
    encrypted = tmp_path / "locked.pdf"
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_text_only_rtf(encrypted, tmp_path / "locked.rtf")


def _record(*, owner="owner-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _post(monkeypatch, record):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, op, ids, params:
            {"op": op, "ids": ids, "params": params, "owner": principal.name},
    )
    return from_pdf.pdf_to_rtf(
        from_pdf.PdfToRtfRequest(file_id="file-rtf"),
        principal=SimpleNamespace(name="owner-a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_default_off_queue_and_rtf_mime(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-rtf") == (".rtf", "application/rtf")
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-rtf")
    with pytest.raises(HTTPException) as exc:
        _post(monkeypatch, _record())
    assert exc.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-rtf") == "heavy"
    assert _post(monkeypatch, _record()) == {
        "op": "pdf-to-rtf", "ids": ["file-rtf"], "params": {}, "owner": "owner-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="owner-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_owner_mime_expiry_size_guards(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as exc:
        _post(monkeypatch, record)
    assert exc.value.status_code == status


def test_request_contract_no_extra_fields():
    with pytest.raises(ValidationError):
        from_pdf.PdfToRtfRequest(file_id="file-rtf", html="<script></script>")
