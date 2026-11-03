"""F10: valid ODF text package with real editable PDF paragraph content."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_STORED, ZipFile
from xml.etree import ElementTree as ET
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
from app.services.from_pdf_odt import MIMETYPE, T, pdf_to_editable_text_odt
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, *, pages=2, graphics=False, columns=False):
    canvas = Canvas(str(path), pagesize=(400, 300))
    for number in range(pages):
        canvas.drawString(40, 230, f"Page {number+1} greeting")
        canvas.drawString(150 if columns else 40, 205, "Editable paragraph")
        if graphics:
            canvas.rect(50, 70, 100, 30)
        canvas.showPage()
    canvas.save()


@pytest.mark.parametrize("pages", [1, 2])
def test_real_pdf_to_selectable_odt_paragraphs(tmp_path, pages):
    source, output = tmp_path / "source.pdf", tmp_path / "output.odt"
    _pdf(source, pages=pages)
    original = source.read_bytes()
    pdf_to_editable_text_odt(source, output)
    assert source.read_bytes() == original
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [
            "mimetype", "content.xml", "styles.xml", "META-INF/manifest.xml",
        ]
        assert archive.getinfo("mimetype").compress_type == ZIP_STORED
        assert archive.read("mimetype") == MIMETYPE.encode("ascii")
        document = ET.fromstring(archive.read("content.xml"))
        paragraphs = document.findall(".//{%s}p" % T)
        assert len(paragraphs) == pages * 2
        for number in range(pages):
            assert paragraphs[number*2].text == f"Page {number+1} greeting"
            assert paragraphs[number*2+1].text == "Editable paragraph"
            if number:
                assert any(value == "PageBreak" for value in paragraphs[number*2].attrib.values())
        ET.fromstring(archive.read("META-INF/manifest.xml"))


@pytest.mark.skipif(shutil.which("libreoffice") is None,
                    reason="LibreOffice only available on optional host")
def test_odt_reopens_in_real_libreoffice(tmp_path):
    source, output = tmp_path / "text.pdf", tmp_path / "text.odt"
    _pdf(source, pages=2)
    pdf_to_editable_text_odt(source, output)
    export = tmp_path / "export"
    export.mkdir()
    proc = subprocess.run([
        "libreoffice", "-env:UserInstallation=file:///tmp/pdfhub-t90-f10-testprofile",
        "--headless", "--convert-to", "pdf",
        "--outdir", str(export), str(output),
    ], timeout=30, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    converted = PdfReader(str(export / "text.pdf"))
    assert len(converted.pages) == 2
    assert "Page 1" in (converted.pages[0].extract_text() or "")
    assert "Page 2" in (converted.pages[1].extract_text() or "")


@pytest.mark.parametrize("graphics,columns", [(True, False), (False, True)])
def test_rejects_noneditable_complex_graphics(tmp_path, graphics, columns):
    source, dest = tmp_path / "complex.pdf", tmp_path / "out.odt"
    _pdf(source, graphics=graphics, columns=columns)
    with pytest.raises(ValueError):
        pdf_to_editable_text_odt(source, dest)
    assert not dest.exists()


def test_rejects_symlinks_encryption_and_overwrite(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    link = tmp_path / "alias.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_editable_text_odt(link, tmp_path / "alias.odt")
    old = tmp_path / "old.odt"
    old.write_bytes(b"institutional-information")
    with pytest.raises(ValueError):
        pdf_to_editable_text_odt(source, old)
    assert old.read_bytes() == b"institutional-information"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("password")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_editable_text_odt(locked, tmp_path / "locked.odt")


def _record(*, owner="user-a", mime="application/pdf", name="source.pdf",
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
    return from_pdf.pdf_to_odt(
        from_pdf.PdfToOdtRequest(file_id="odt-file-id"),
        principal=SimpleNamespace(name="user-a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_default_off_output_mime_and_heavy_queue(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-odt") == (
        ".odt", "application/vnd.oasis.opendocument.text",
    )
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-odt")
    with pytest.raises(HTTPException) as err:
        _post(monkeypatch, _record())
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-odt") == "heavy"
    assert _post(monkeypatch, _record()) == {
        "op": "pdf-to-odt", "ids": ["odt-file-id"], "params": {}, "owner": "user-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="user-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.jpg"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_owner_expiry_mime_budget_guards(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _post(monkeypatch, record)
    assert err.value.status_code == status


def test_reject_extra_api_parameters():
    with pytest.raises(ValidationError):
        from_pdf.PdfToOdtRequest(file_id="odt-file-id", url="http://localhost")
