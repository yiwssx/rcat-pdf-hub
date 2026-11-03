"""F02/F06: actual editable Word DOCX packaging and verified source refusal."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import shutil
import subprocess

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_docx import pdf_to_editable_text_docx, MIMETYPE, W
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, *, pages=2, graphics=False, columns=False):
    c = Canvas(str(path), pagesize=(400, 300))
    for n in range(pages):
        c.drawString(40, 230, f"Source page {n+1}")
        c.drawString(140 if columns else 40, 205, "Editable document text")
        if graphics:
            c.line(50, 70, 150, 70)
        c.showPage()
    c.save()


@pytest.mark.parametrize("pages", [1, 2])
def test_pdf_to_genuinely_editable_docx_xml(tmp_path, pages):
    source, output = tmp_path / "source.pdf", tmp_path / "text.docx"
    _pdf(source, pages=pages)
    original = source.read_bytes()
    pdf_to_editable_text_docx(source, output)
    assert source.read_bytes() == original
    with ZipFile(output) as archive:
        assert archive.namelist() == [
            "[Content_Types].xml", "_rels/.rels", "word/document.xml",
        ]
        assert archive.testzip() is None
        assert MIMETYPE.encode() in archive.read("[Content_Types].xml")
        root = ET.fromstring(archive.read("word/document.xml"))
        text = [element.text for element in root.findall(".//{%s}t" % W)]
        assert text == [
            part for n in range(pages)
            for part in (f"Source page {n+1}", "Editable document text")
        ]
        breaks = root.findall(".//{%s}br" % W)
        assert len(breaks) == pages-1


@pytest.mark.skipif(shutil.which("libreoffice") is None,
                    reason="LibreOffice not included in backend test image")
def test_docx_can_reopen_in_real_libreoffice(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "text.docx"
    _pdf(source, pages=2)
    pdf_to_editable_text_docx(source, output)
    folder = tmp_path / "convert"
    folder.mkdir()
    result = subprocess.run([
        "libreoffice", "-env:UserInstallation=file:///tmp/pdfhub-f06-testprofile",
        "--headless", "--convert-to", "pdf", "--outdir", str(folder), str(output),
    ], timeout=30, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    pdf = PdfReader(str(folder / "text.pdf"))
    assert len(pdf.pages) == 2
    assert "Source page 1" in (pdf.pages[0].extract_text() or "")
    assert "Source page 2" in (pdf.pages[1].extract_text() or "")


@pytest.mark.parametrize("graphics,columns", [(True, False), (False, True)])
def test_refuse_graphics_and_multiple_columns(tmp_path, graphics, columns):
    source = tmp_path / "complex.pdf"
    _pdf(source, graphics=graphics, columns=columns)
    out = tmp_path / "bad.docx"
    with pytest.raises(ValueError):
        pdf_to_editable_text_docx(source, out)
    assert not out.exists()


def test_reject_symlink_overwrite_and_encrypted_source(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    link = tmp_path / "link.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_editable_text_docx(link, tmp_path / "link.docx")
    destination = tmp_path / "existing.docx"
    destination.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        pdf_to_editable_text_docx(source, destination)
    assert destination.read_bytes() == b"preserve"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_editable_text_docx(locked, tmp_path / "locked.docx")


def _record(*, owner="owner-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record, operation):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, op, ids, params:
            {"op": op, "ids": ids, "params": params, "owner": principal.name},
    )
    route = from_pdf.pdf_to_word if operation == "pdf-to-word" else from_pdf.pdf_to_docx
    return route(
        from_pdf.PdfToDocxRequest(file_id="source-id"),
        principal=SimpleNamespace(name="owner-a"),
        db=SimpleNamespace(get=lambda model, ident: record),
    )


@pytest.mark.parametrize("operation", ["pdf-to-word", "pdf-to-docx"])
def test_two_distinct_routes_same_true_docx_contract(monkeypatch, operation):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job(operation) == (
        ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    with pytest.raises(ValueError):
        queue_class_for_operation(operation)
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, _record(), operation)
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation(operation) == "heavy"
    assert _submit(monkeypatch, _record(), operation) == {
        "op": operation, "ids": ["source-id"], "params": {}, "owner": "owner-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="owner-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_docx_owner_mime_expiry_and_size_guard(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    for operation in ("pdf-to-word", "pdf-to-docx"):
        with pytest.raises(HTTPException) as err:
            _submit(monkeypatch, record, operation)
        assert err.value.status_code == status


def test_reject_extra_docx_api_fields():
    with pytest.raises(ValidationError):
        from_pdf.PdfToDocxRequest(file_id="source-id", url="http://127.0.0.1")
