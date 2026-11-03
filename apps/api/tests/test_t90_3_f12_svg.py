"""F12 PDF-to-SVG ZIP: real Poppler page checks and owner/queue guards."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import shutil

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_svg import pdf_to_svg_zip, _verify_generated_svg
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, pages: int = 2) -> None:
    canvas = Canvas(str(path), pagesize=(210, 150))
    for i in range(pages):
        canvas.setFont("Helvetica", 14)
        canvas.drawString(25, 85, f"Page {i+1}: distinct text")
        canvas.line(20, 40 + i, 170, 40 + i)
        canvas.showPage()
    canvas.save()


@pytest.mark.skipif(shutil.which("pdftocairo") is None, reason="Poppler is unavailable")
@pytest.mark.parametrize("pages", [2, 10])
def test_pdf_to_svg_preserves_all_pages_in_order(tmp_path, pages):
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.zip"
    _pdf(source, pages)
    original = source.read_bytes()
    pdf_to_svg_zip(source, output)
    assert source.read_bytes() == original
    assert output.read_bytes()[:4] == b"PK\x03\x04"
    with ZipFile(output) as bundle:
        assert bundle.namelist() == [f"page-{n:04d}.svg" for n in range(1, pages + 1)]
        assert bundle.testzip() is None
        data = [bundle.read(name) for name in bundle.namelist()]
        for item in data:
            assert b"<svg " in item
            _verify_generated_svg(item)
        assert data[0] != data[1]


@pytest.mark.parametrize("malicious", [
    b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><script>1</script></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://attacker.invalid/e"/></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><rect style="fill:url(https://attacker.invalid/e)"/></svg>',
])
def test_unsafe_svg_is_rejected(malicious):
    # Small inputs are rejected by size or content checks; never accepted.
    with pytest.raises(ValueError):
        _verify_generated_svg(malicious)


def test_refuses_symlink_preexisting_output_and_encryption(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    link = tmp_path / "link.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_svg_zip(link, tmp_path / "result.zip")
    dest = tmp_path / "old.zip"
    dest.write_bytes(b"institutional-output")
    with pytest.raises(ValueError):
        pdf_to_svg_zip(source, dest)
    assert dest.read_bytes() == b"institutional-output"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    encrypted = tmp_path / "locked.pdf"
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_svg_zip(encrypted, tmp_path / "locked.zip")
    assert not (tmp_path / "locked.zip").exists()


def _record(*, owner="owner-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc) - timedelta(days=2)) if expired else None,
    )


def _post(monkeypatch, record):
    monkeypatch.setattr(from_pdf, "_create_job", lambda db, principal, op, ids, params:
                        {"op": op, "file_ids": ids, "params": params, "owner": principal.name})
    return from_pdf.pdf_to_svg(
        from_pdf.PdfToSvgRequest(file_id="file-id"),
        principal=SimpleNamespace(name="owner-a"),
        db=SimpleNamespace(get=lambda model, ident: record),
    )


def test_feature_flag_output_mime_and_heavy_queue(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-svg") == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-svg")
    with pytest.raises(HTTPException) as error:
        _post(monkeypatch, _record())
    assert error.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-svg") == "heavy"
    assert _post(monkeypatch, _record()) == {
        "op": "pdf-to-svg", "file_ids": ["file-id"], "params": {}, "owner": "owner-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="owner-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=25 * 1024 * 1024), 413),
])
def test_owner_expiry_mime_budget_guards(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as exc:
        _post(monkeypatch, record)
    assert exc.value.status_code == status


def test_no_extra_request_fields():
    with pytest.raises(ValidationError):
        from_pdf.PdfToSvgRequest(file_id="file-id", url="https://not-allowed.invalid")
