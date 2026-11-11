"""F15 real classic MOBI6 binary, guarded route, queue and failure tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from hashlib import sha256
from pydantic import ValidationError

import pytest
from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_mobi import _mobi6_bytes, pdf_to_legacy_mobi
from app.services.to_pdf_mobi import mobi_to_safe_html
from app.worker_tasks import _output_spec_for_job

MIME = "application/x-mobipocket-ebook"


def _pdf(path: Path, *, pages=2, graphics=False, columns=False):
    canvas = Canvas(str(path), pagesize=(400, 300))
    for index in range(pages):
        canvas.drawString(40, 230, f"Page {index + 1}")
        canvas.drawString(160 if columns else 40, 200, "Safe MOBI text")
        if graphics:
            canvas.rect(40, 65, 200, 55)
        canvas.showPage()
    canvas.save()


def test_real_mobi6_palmdb_writer_utf8_thai_and_long_record(tmp_path):
    long_text = "ภาษาไทย เกษตรอัจฉริยะ " * 250
    blob = _mobi6_bytes([long_text, "English & <escaped>"])
    source = tmp_path / "book.mobi"
    source.write_bytes(blob)
    assert blob[60:68] == b"BOOKMOBI"
    assert blob.count(b"MOBI") >= 2
    html = mobi_to_safe_html(source)
    assert "ภาษาไทย เกษตรอัจฉริยะ" in html
    assert "English &amp; &lt;escaped&gt;" in html


def test_pdf_to_authentic_mobi6_source_immutable_and_readable(tmp_path):
    source = tmp_path / "source.pdf"
    target = tmp_path / "converted.mobi"
    _pdf(source, pages=2)
    digest = sha256(source.read_bytes()).hexdigest()
    pdf_to_legacy_mobi(source, target)
    data = target.read_bytes()
    assert target.suffix == ".mobi" and data[60:68] == b"BOOKMOBI"
    transcript = mobi_to_safe_html(target)
    assert "Page 1" in transcript and "Page 2" in transcript
    assert transcript.index("Page 1") < transcript.index("Page 2")
    assert "Safe MOBI text" in transcript
    assert sha256(source.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("graphics,columns", [(True, False), (False, True)])
def test_mobi_rejects_complex_pdfs_without_artifacts(tmp_path, graphics, columns):
    source, target = tmp_path / "complex.pdf", tmp_path / "book.mobi"
    _pdf(source, graphics=graphics, columns=columns)
    with pytest.raises(ValueError):
        pdf_to_legacy_mobi(source, target)
    assert not target.exists()


def test_mobi_rejects_symlink_existing_and_encrypted_source(tmp_path):
    source, output = tmp_path / "input.pdf", tmp_path / "prior.mobi"
    _pdf(source)
    output.write_bytes(b"prior-user-data")
    with pytest.raises(ValueError):
        pdf_to_legacy_mobi(source, output)
    assert output.read_bytes() == b"prior-user-data"
    alias = tmp_path / "alias.pdf"
    alias.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_legacy_mobi(alias, tmp_path / "symlink.mobi")
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    encrypted = tmp_path / "encrypted.pdf"
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="encrypted"):
        pdf_to_legacy_mobi(encrypted, tmp_path / "encrypted.mobi")


def _record(*, owner="member-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(from_pdf, "_create_job",
                        lambda db, principal, operation, ids, params: {
                            "operation": operation, "ids": ids,
                            "params": params, "owner": principal.name,
                        })
    return from_pdf.pdf_to_mobi(
        from_pdf.PdfToMobiRequest(file_id="mobi-file"),
        principal=SimpleNamespace(name="member-a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_mobi_flag_owner_queue_and_exact_artifact_mime(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-mobi") == (".mobi", MIME)
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-mobi")
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, _record())
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-mobi") == "heavy"
    assert _submit(monkeypatch, _record()) == {
        "operation": "pdf-to-mobi", "ids": ["mobi-file"],
        "params": {}, "owner": "member-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="other"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.txt"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_mobi_rejects_wrong_owner_type_expiry_and_size(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, record)
    assert err.value.status_code == status


def test_mobi_request_rejects_arbitrary_params_or_url():
    with pytest.raises(ValidationError):
        from_pdf.PdfToMobiRequest(file_id="mobi-file", url="https://example.com")


def test_mobi_refuses_empty_and_oversized_text():
    with pytest.raises(ValueError):
        _mobi6_bytes([])
    with pytest.raises(ValueError):
        _mobi6_bytes(["x" * 250_000])
