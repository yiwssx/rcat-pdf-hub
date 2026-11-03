"""F03/F04: real multi-page Poppler images, ZIP inventory and owner scope."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import shutil
from types import SimpleNamespace
from zipfile import ZipFile

from PIL import Image
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_raster import pdf_to_raster_page_zip
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, *, pages=2):
    c = Canvas(str(path), pagesize=(210, 150))
    for number in range(pages):
        c.setFillColorRGB(1 if number % 2 == 0 else 0, 0,
                          1 if number % 2 else 0)
        c.rect(20, 20, 90, 90, fill=1, stroke=0)
        c.drawString(10, 120, f"Unique page {number+1}")
        c.showPage()
    c.save()


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler unavailable")
@pytest.mark.parametrize("fmt,pages", [
    ("jpg", 2), ("jpg", 10), ("png", 2), ("png", 10),
])
def test_generated_pdf_exports_exact_pages_and_real_images(tmp_path, fmt, pages):
    source, output = tmp_path / "source.pdf", tmp_path / "result.zip"
    _pdf(source, pages=pages)
    original = source.read_bytes()
    pdf_to_raster_page_zip(source, output, fmt=fmt, dpi=72)
    assert source.read_bytes() == original
    assert output.read_bytes()[:4] == b"PK\x03\x04"
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == [
            f"page-{i:04d}.{fmt}" for i in range(1, pages+1)
        ]
        pixel_bytes = []
        for name in archive.namelist():
            blob = archive.read(name)
            with Image.open(BytesIO(blob)) as image:
                assert image.format == ("JPEG" if fmt == "jpg" else "PNG")
                assert image.size == (210, 150)
                pixel_bytes.append(image.convert("RGB").tobytes())
        assert pixel_bytes[0] != pixel_bytes[1]


@pytest.mark.parametrize("fmt", ["bmp", "", "jpeg", "svg"])
def test_unsupported_format_rejected_before_render(tmp_path, fmt):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"not pdf")
    with pytest.raises(ValueError, match="PNG/JPG"):
        pdf_to_raster_page_zip(source, tmp_path / "out.zip", fmt=fmt)


@pytest.mark.parametrize("dpi", [0, 71, 201, True, "96", 96.25])
def test_invalid_dpi_fails_before_render(tmp_path, dpi):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"not pdf")
    with pytest.raises(ValueError, match="DPI"):
        pdf_to_raster_page_zip(source, tmp_path / "out.zip", fmt="png", dpi=dpi)


def test_refuse_encrypted_source_symlink_and_output_replacement(tmp_path):
    source = tmp_path / "source.pdf"
    _pdf(source)
    alias = tmp_path / "linked.pdf"
    alias.symlink_to(source)
    with pytest.raises(ValueError):
        pdf_to_raster_page_zip(alias, tmp_path / "alias.zip", fmt="png")
    dest = tmp_path / "original-output.zip"
    dest.write_bytes(b"original-owner-data")
    with pytest.raises(ValueError):
        pdf_to_raster_page_zip(source, dest, fmt="jpg")
    assert dest.read_bytes() == b"original-owner-data"
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("secret")
    encrypted = tmp_path / "encrypted.pdf"
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_raster_page_zip(encrypted, tmp_path / "encrypted.zip", fmt="jpg")


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
            {"operation": op, "ids": ids, "params": params, "owner": principal.name},
    )
    route = from_pdf.pdf_to_jpg if operation == "pdf-to-jpg" else from_pdf.pdf_to_png
    return route(
        from_pdf.PdfToRasterRequest(file_id="source-id"),
        principal=SimpleNamespace(name="owner-a"),
        db=SimpleNamespace(get=lambda model, ident: record),
    )


@pytest.mark.parametrize("operation", ["pdf-to-jpg", "pdf-to-png"])
def test_default_off_and_heavy_queue_uses_zip_mime(monkeypatch, operation):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job(operation) == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation(operation)
    with pytest.raises(HTTPException) as err:
        _submit(monkeypatch, _record(), operation)
    assert err.value.status_code == 404
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation(operation) == "heavy"
    assert _submit(monkeypatch, _record(), operation) == {
        "operation": operation, "ids": ["source-id"],
        "params": {"dpi": 96}, "owner": "owner-a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="owner-b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="image.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=25*1024*1024), 413),
])
def test_owner_expiry_mime_budget_check_on_both_routes(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    for operation in ("pdf-to-jpg", "pdf-to-png"):
        with pytest.raises(HTTPException) as err:
            _submit(monkeypatch, record, operation)
        assert err.value.status_code == status


@pytest.mark.parametrize("invalid", [0, 71, 201, True, 95.7, "96"])
def test_api_dpi_is_strict(invalid):
    with pytest.raises(ValidationError):
        from_pdf.PdfToRasterRequest(file_id="source-id", dpi=invalid)
