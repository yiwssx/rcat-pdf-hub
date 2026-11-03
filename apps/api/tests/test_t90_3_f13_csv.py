"""F13 grid-only PDF to CSV: true PDF content tests, no guessed columns."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_csv import pdf_to_csv_zip
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, *, pages=1, grid=True, inner=True, formula=False):
    c = Canvas(str(path), pagesize=(400, 300))
    for p in range(pages):
        if grid:
            for x in ((50, 150, 250) if inner else (50, 250)):
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


@pytest.mark.parametrize("pages", [1, 3])
def test_real_ruled_table_to_complete_csv_zip(tmp_path, pages):
    source, output = tmp_path / "table.pdf", tmp_path / "table.zip"
    _pdf(source, pages=pages)
    original = source.read_bytes()
    pdf_to_csv_zip(source, output)
    assert source.read_bytes() == original
    assert output.read_bytes()[:4] == b"PK\x03\x04"
    with ZipFile(output) as archive:
        assert archive.namelist() == [
            f"page-{n:04d}.csv" for n in range(1, pages+1)
        ]
        assert archive.testzip() is None
        for n, name in enumerate(archive.namelist()):
            csv_text = archive.read(name).decode("utf-8-sig")
            data = list(csv.reader(StringIO(csv_text)))
            assert data == [["Name", "Qty"], [f"Apple {n}", "5"], ["Pear", "8"]]


@pytest.mark.parametrize("grid,inner,formula", [
    (False, False, False), (True, False, False), (True, True, True),
])
def test_reject_non_table_missing_grid_and_formula(tmp_path, grid, inner, formula):
    source = tmp_path / "table.pdf"
    _pdf(source, grid=grid, inner=inner, formula=formula)
    output = tmp_path / "fail.zip"
    with pytest.raises(ValueError):
        pdf_to_csv_zip(source, output)
    assert not output.exists()


def test_preexisting_output_encrypted_pdf_and_symlink_rejected(tmp_path):
    source = tmp_path / "table.pdf"
    _pdf(source)
    link = tmp_path / "alias.pdf"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_csv_zip(link, tmp_path / "alias.zip")
    output = tmp_path / "existing.zip"
    output.write_bytes(b"preserve-prior-output")
    with pytest.raises(ValueError):
        pdf_to_csv_zip(source, output)
    assert output.read_bytes() == b"preserve-prior-output"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("credential")
    protected = tmp_path / "encrypted.pdf"
    with protected.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_csv_zip(protected, tmp_path / "encrypted.zip")


def _record(*, owner="owner-a", mime="application/pdf", name="table.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)) if expired else None,
    )


def _post(monkeypatch, record):
    monkeypatch.setattr(
        from_pdf, "_create_job",
        lambda db, principal, op, ids, params:
            {"op": op, "ids": ids, "params": params, "owner": principal.name},
    )
    return from_pdf.pdf_to_csv(
        from_pdf.PdfToCsvRequest(file_id="table-file-id"),
        principal=SimpleNamespace(name="owner-a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_flag_queue_and_binary_contract(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-csv") == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-csv")
    with pytest.raises(HTTPException) as err:
        _post(monkeypatch, _record())
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-csv") == "heavy"
    assert _post(monkeypatch, _record()) == {
        "op": "pdf-to-csv", "ids": ["table-file-id"], "params": {}, "owner": "owner-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="owner-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="table.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=20 * 1024 * 1024), 413),
])
def test_bad_owner_mime_expiry_and_size(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as err:
        _post(monkeypatch, record)
    assert err.value.status_code == status


def test_reject_request_parameter_injection():
    with pytest.raises(ValidationError):
        from_pdf.PdfToCsvRequest(file_id="table-file-id", url="http://localhost")
