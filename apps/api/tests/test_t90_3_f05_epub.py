"""F05 EPUB3: actual reflowable HTML, manifest and owner-contract tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_epub import (
    MIMETYPE, XHTML, OPF, DC, pdf_to_reflowable_epub,
)
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, *, pages=2, graphics=False, columns=False):
    pdf = Canvas(str(path), pagesize=(400, 300))
    for n in range(pages):
        pdf.drawString(40, 230, f"Chapter {n+1}")
        pdf.drawString(160 if columns else 40, 200, "Editable text for EPUB")
        if graphics:
            pdf.rect(40, 65, 200, 55)
        pdf.showPage()
    pdf.save()


@pytest.mark.parametrize("pages", [1, 2])
def test_real_pdf_to_epub3_chapters_and_toc(tmp_path, pages):
    source, output = tmp_path / "source.pdf", tmp_path / "book.epub"
    _pdf(source, pages=pages)
    before = source.read_bytes()
    pdf_to_reflowable_epub(source, output)
    assert source.read_bytes() == before
    with ZipFile(output) as archive:
        names = ["mimetype", "META-INF/container.xml",
                 "EPUB/package.opf", "EPUB/nav.xhtml"]
        names.extend(f"EPUB/page-{p:04d}.xhtml" for p in range(1, pages+1))
        assert archive.namelist() == names
        assert archive.testzip() is None
        assert archive.getinfo("mimetype").compress_type == ZIP_STORED
        assert archive.read("mimetype") == MIMETYPE.encode("ascii")
        rootfile = ET.fromstring(archive.read("META-INF/container.xml"))
        assert any(x.attrib.get("full-path") == "EPUB/package.opf"
                   for x in rootfile.iter())
        package = ET.fromstring(archive.read("EPUB/package.opf"))
        assert package.attrib["version"] == "3.0"
        assert len(package.findall(".//{%s}itemref" % OPF)) == pages
        assert package.find(".//{%s}identifier" % DC).text.startswith("urn:uuid:")
        navigation = ET.fromstring(archive.read("EPUB/nav.xhtml"))
        assert len(navigation.findall(".//{%s}a" % XHTML)) == pages
        for n in range(1, pages+1):
            document = ET.fromstring(archive.read(f"EPUB/page-{n:04d}.xhtml"))
            paragraphs = [x.text for x in document.findall(".//{%s}p" % XHTML)]
            assert paragraphs == [f"Chapter {n}", "Editable text for EPUB"]


@pytest.mark.parametrize("graphics,columns", [(True, False), (False, True)])
def test_ambiguous_graphic_and_multicolumn_pdfs_fail_closed(tmp_path, graphics, columns):
    source, output = tmp_path / "bad.pdf", tmp_path / "bad.epub"
    _pdf(source, graphics=graphics, columns=columns)
    with pytest.raises(ValueError):
        pdf_to_reflowable_epub(source, output)
    assert not output.exists()


def test_encrypted_pdf_symlink_and_existing_output_rejected(tmp_path):
    source, output = tmp_path / "plain.pdf", tmp_path / "existing.epub"
    _pdf(source)
    alias = tmp_path / "link.pdf"
    alias.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_reflowable_epub(alias, tmp_path / "link.epub")
    output.write_bytes(b"prior-owner-data")
    with pytest.raises(ValueError):
        pdf_to_reflowable_epub(source, output)
    assert output.read_bytes() == b"prior-owner-data"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_reflowable_epub(locked, tmp_path / "locked.epub")


def _record(*, owner="member-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, operation, ids, params: {
            "operation": operation, "ids": ids, "params": params,
            "owner": principal.name,
        },
    )
    return from_pdf.pdf_to_epub(
        from_pdf.PdfToEpubRequest(file_id="epub-file"),
        principal=SimpleNamespace(name="member-a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_flag_and_owner_scoped_queue_output_contract(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-epub") == (".epub", MIMETYPE)
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-epub")
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, _record())
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-epub") == "heavy"
    assert _submit(monkeypatch, _record()) == {
        "operation": "pdf-to-epub", "ids": ["epub-file"], "params": {},
        "owner": "member-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="member-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_reject_wrong_owner_mime_expiry_and_size(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, record)
    assert err.value.status_code == status


def test_strict_request_disallows_extra_options():
    with pytest.raises(ValidationError):
        from_pdf.PdfToEpubRequest(file_id="epub-file", url="http://localhost")
