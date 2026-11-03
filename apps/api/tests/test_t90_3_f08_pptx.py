"""F08: editable PowerPoint XML, readable slides, owner and fail-closed tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas
import pytest

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_pptx import (
    MIMETYPE, P, A, pdf_to_editable_text_pptx,
)
from app.worker_tasks import _output_spec_for_job


def _source(path: Path, *, count=2, graphical=False, columns=False):
    canvas = Canvas(str(path), pagesize=(400, 300))
    for n in range(count):
        canvas.drawString(40, 230, f"Source page {n+1}")
        canvas.drawString(150 if columns else 40, 200, "Editable slide text")
        if graphical:
            canvas.rect(40, 80, 150, 40)
        canvas.showPage()
    canvas.save()


@pytest.mark.parametrize("count", [1, 2])
def test_real_pdf_to_editable_powerpoint_slides(tmp_path, count):
    original, output = tmp_path / "source.pdf", tmp_path / "slides.pptx"
    _source(original, count=count)
    before = original.read_bytes()
    pdf_to_editable_text_pptx(original, output)
    assert original.read_bytes() == before
    with ZipFile(output) as archive:
        expected = [
            "[Content_Types].xml", "_rels/.rels",
            "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels",
        ] + [f"ppt/slides/slide{i}.xml" for i in range(1, count+1)]
        assert archive.namelist() == expected
        assert archive.testzip() is None
        assert MIMETYPE.encode() in archive.read("[Content_Types].xml")
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        assert len(presentation.findall(".//{%s}sldId" % P)) == count
        for n in range(1, count+1):
            slide = ET.fromstring(archive.read(f"ppt/slides/slide{n}.xml"))
            values = [x.text for x in slide.findall(".//{%s}t" % A)]
            assert slide.findall(".//{%s}normAutofit" % A)
            assert values == [f"Source page {n}", "Editable slide text"]


def test_can_open_in_python_pptx_if_installed(tmp_path):
    pptx = pytest.importorskip("pptx")
    source, output = tmp_path / "source.pdf", tmp_path / "slides.pptx"
    _source(source)
    pdf_to_editable_text_pptx(source, output)
    presentation = pptx.Presentation(str(output))
    assert len(presentation.slides) == 2
    assert presentation.slides[0].shapes[0].text.startswith("Source page 1")


@pytest.mark.skipif(shutil.which("libreoffice") is None,
                    reason="LibreOffice not installed on API CI host")
def test_pptx_reopens_as_two_real_pdf_slides(tmp_path):
    source, output = tmp_path / "source.pdf", tmp_path / "slides.pptx"
    _source(source)
    pdf_to_editable_text_pptx(source, output)
    converted = tmp_path / "converted"
    converted.mkdir()
    result = subprocess.run([
        "libreoffice", "-env:UserInstallation=file:///tmp/pdfhub-t90-f08-testprofile",
        "--headless", "--convert-to", "pdf", "--outdir", str(converted), str(output),
    ], check=False, timeout=35, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    result_pdf = PdfReader(str(converted / "slides.pdf"))
    assert len(result_pdf.pages) == 2
    for index in range(2):
        assert f"Source page {index+1}" in (result_pdf.pages[index].extract_text() or "")


@pytest.mark.parametrize("graphical,columns", [(True, False), (False, True)])
def test_reject_graphic_and_multicolumn_documents(tmp_path, graphical, columns):
    source, output = tmp_path / "complex.pdf", tmp_path / "bad.pptx"
    _source(source, graphical=graphical, columns=columns)
    with pytest.raises(ValueError):
        pdf_to_editable_text_pptx(source, output)
    assert not output.exists()


def test_reject_more_than_twenty_lines_per_slide(tmp_path):
    source, output = tmp_path / "long.pdf", tmp_path / "too_long.pptx"
    canvas = Canvas(str(source), pagesize=(400, 300))
    for n in range(21):
        canvas.drawString(40, 280-n*10, f"Line {n+1}")
    canvas.showPage()
    canvas.save()
    with pytest.raises(ValueError):
        pdf_to_editable_text_pptx(source, output)
    assert not output.exists()


def test_reject_overlong_text_that_could_clip_on_slide(tmp_path):
    source, output = tmp_path / "wide.pdf", tmp_path / "wide.pptx"
    canvas = Canvas(str(source), pagesize=(400, 300))
    canvas.drawString(40, 230, "W" * 130)
    canvas.showPage()
    canvas.save()
    with pytest.raises(ValueError, match="overflow"):
        pdf_to_editable_text_pptx(source, output)
    assert not output.exists()


def test_encrypted_symlink_and_overwrite_guard(tmp_path):
    source = tmp_path / "source.pdf"
    _source(source)
    link = tmp_path / "alias.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_editable_text_pptx(link, tmp_path / "alias.pptx")
    output = tmp_path / "existing.pptx"
    output.write_bytes(b"original-file")
    with pytest.raises(ValueError):
        pdf_to_editable_text_pptx(source, output)
    assert output.read_bytes() == b"original-file"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    encrypted = tmp_path / "locked.pdf"
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_editable_text_pptx(encrypted, tmp_path / "locked.pptx")


def _record(*, owner="member-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, op, ids, params: {
            "operation": op, "ids": ids, "params": params, "owner": principal.name,
        },
    )
    return from_pdf.pdf_to_ppt(
        from_pdf.PdfToPptRequest(file_id="slide-source"),
        principal=SimpleNamespace(name="member-a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_default_off_and_owner_queue_mime(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-ppt") == (".pptx", MIMETYPE)
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-ppt")
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, _record())
    assert error.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-ppt") == "heavy"
    assert _submit(monkeypatch, _record()) == {
        "operation": "pdf-to-ppt", "ids": ["slide-source"],
        "params": {}, "owner": "member-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="member-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_owner_mime_expiry_input_budget(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, record)
    assert error.value.status_code == status


def test_invalid_extra_request_field_rejected():
    with pytest.raises(ValidationError):
        from_pdf.PdfToPptRequest(file_id="slide-source", remote_url="http://localhost")
