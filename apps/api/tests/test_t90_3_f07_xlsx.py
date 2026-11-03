"""F07: true editable XLSX grid sheets and strict PDF/source guards."""
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
from app.services.from_pdf_xlsx import MIMETYPE, SS, pdf_grid_to_editable_xlsx
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, *, pages=2, grid=True, formula=False):
    c = Canvas(str(path), pagesize=(400, 300))
    for p in range(pages):
        if grid:
            for x in (50, 150, 250):
                c.line(x, 120, x, 240)
            for y in (120, 160, 200, 240):
                c.line(50, y, 250, y)
        for x, y, text in (
            (70, 215, "Name"), (170, 215, "Qty"),
            (70, 175, "=1+1" if formula else f"Apple {p}"),
            (170, 175, "5"), (70, 135, "Pear"), (170, 135, "8"),
        ):
            c.drawString(x, y, text)
        c.showPage()
    c.save()


@pytest.mark.parametrize("pages", [1, 2])
def test_pdf_grid_becomes_true_editable_spreadsheet(tmp_path, pages):
    source, output = tmp_path / "table.pdf", tmp_path / "cells.xlsx"
    _pdf(source, pages=pages)
    original = source.read_bytes()
    pdf_grid_to_editable_xlsx(source, output)
    assert source.read_bytes() == original
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        expected = [
            "[Content_Types].xml", "_rels/.rels",
            "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
        ] + [f"xl/worksheets/sheet{n}.xml" for n in range(1, pages+1)]
        assert archive.namelist() == expected
        assert MIMETYPE.encode() in archive.read("[Content_Types].xml")
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        assert len(book.findall(".//{%s}sheet" % SS)) == pages
        for i in range(1, pages+1):
            sheet = ET.fromstring(archive.read(f"xl/worksheets/sheet{i}.xml"))
            values = [node.text for node in sheet.findall(".//{%s}t" % SS)]
            assert values == ["Name", "Qty", f"Apple {i-1}", "5", "Pear", "8"]


@pytest.mark.skipif(shutil.which("libreoffice") is None,
                    reason="LibreOffice unavailable in backend test image")
def test_xlsx_reopens_in_real_libreoffice(tmp_path):
    source, workbook = tmp_path / "table.pdf", tmp_path / "cells.xlsx"
    _pdf(source, pages=1)
    pdf_grid_to_editable_xlsx(source, workbook)
    folder = tmp_path / "convert"
    folder.mkdir()
    result = subprocess.run([
        "libreoffice", "-env:UserInstallation=file:///tmp/pdfhub-f07-testprofile",
        "--headless", "--convert-to", "pdf", "--outdir", str(folder), str(workbook),
    ], timeout=30, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    pdf = PdfReader(str(folder / "cells.pdf"))
    assert len(pdf.pages) >= 1
    assert "Apple 0" in (pdf.pages[0].extract_text() or "")


@pytest.mark.parametrize("grid,formula", [(False, False), (True, True)])
def test_rejects_unruled_columns_and_spreadsheet_injection(tmp_path, grid, formula):
    source, dest = tmp_path / "bad.pdf", tmp_path / "bad.xlsx"
    _pdf(source, grid=grid, formula=formula)
    with pytest.raises(ValueError):
        pdf_grid_to_editable_xlsx(source, dest)
    assert not dest.exists()


def test_rejects_symlink_encryption_and_prior_output(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source, pages=1)
    link = tmp_path / "link.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_grid_to_editable_xlsx(link, tmp_path / "link.xlsx")
    old = tmp_path / "old.xlsx"
    old.write_bytes(b"preserve")
    with pytest.raises(ValueError):
        pdf_grid_to_editable_xlsx(source, old)
    assert old.read_bytes() == b"preserve"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("password")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_grid_to_editable_xlsx(locked, tmp_path / "locked.xlsx")


def _record(*, owner="owner-a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc)-timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, op, ids, params:
            {"op": op, "ids": ids, "params": params, "owner": principal.name},
    )
    return from_pdf.pdf_to_excel(
        from_pdf.PdfToExcelRequest(file_id="table-id"),
        principal=SimpleNamespace(name="owner-a"),
        db=SimpleNamespace(get=lambda model, ident: record),
    )


def test_default_off_output_mime_and_queue(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-excel") == (".xlsx", MIMETYPE)
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-excel")
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, _record())
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-excel") == "heavy"
    assert _submit(monkeypatch, _record()) == {
        "op": "pdf-to-excel", "ids": ["table-id"], "params": {}, "owner": "owner-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="owner-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=20*1024*1024), 413),
])
def test_owner_expiry_mime_source_budget(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, record)
    assert err.value.status_code == status


def test_strict_request_disallows_other_fields():
    with pytest.raises(ValidationError):
        from_pdf.PdfToExcelRequest(file_id="table-id", url="https://example.org")
