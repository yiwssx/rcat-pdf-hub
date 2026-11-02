"""F17 PDF→BMP page ZIP: generated functional PDF and lifecycle gates."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import shutil

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.config import get_settings
from app.queue import queue_class_for_operation
from app.routers import from_pdf
from app.services.from_pdf_bmp import pdf_to_bmp_zip
from app.worker_tasks import _output_spec_for_job


def _pdf(path: Path, count=2):
    canvas = Canvas(str(path), pagesize=(210, 150))
    for n in range(count):
        canvas.setFillColorRGB(1 if n % 2 == 0 else 0, 0, 1 if n % 2 else 0)
        canvas.rect(10+n, 10, 90, 90, stroke=0, fill=1)
        canvas.showPage()
    canvas.save()


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler unavailable")
@pytest.mark.parametrize("count", [2, 10])
def test_generated_pdf_to_ordered_multi_bmp_zip(tmp_path, count):
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.zip"
    _pdf(source, count)
    unchanged = source.read_bytes()
    pdf_to_bmp_zip(source, output, dpi=72)
    assert source.read_bytes() == unchanged
    assert output.read_bytes()[:4] == b"PK\x03\x04"
    with ZipFile(output) as archive:
        assert archive.namelist() == [f"page-{i:04d}.bmp" for i in range(1, count+1)]
        assert archive.testzip() is None
        colors = []
        for name in archive.namelist():
            blob = archive.read(name)
            assert blob[:2] == b"BM"
            with Image.open(BytesIO(blob)) as image:
                assert image.format == "BMP" and image.size == (210, 150)
                colors.append(image.convert("RGB").tobytes())
        assert colors[0] != colors[1]


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler unavailable")
def test_zero_padded_page_filenames_work_for_tiff_and_gif(tmp_path):
    # Poppler outputs page-01.png through page-10.png for 10-page sources.
    # F09 and F16 must not reject a valid page inventory on leading zeros.
    from app.services.from_pdf_tiff import pdf_to_multipage_tiff
    from app.services.from_pdf_gif import pdf_to_animated_gif
    source = tmp_path / "ten.pdf"
    _pdf(source, count=10)
    tiff = tmp_path / "ten.tiff"
    gif = tmp_path / "ten.gif"
    pdf_to_multipage_tiff(source, tiff, dpi=72)
    pdf_to_animated_gif(source, gif, dpi=72)
    with Image.open(tiff) as image:
        assert image.n_frames == 10
    with Image.open(gif) as image:
        assert image.n_frames == 10


@pytest.mark.parametrize("dpi", [0, 71, 151, True, 100.5])
def test_invalid_dpi_rejected(tmp_path, dpi):
    f = tmp_path / "input.pdf"
    f.write_bytes(b"bad")
    with pytest.raises(ValueError, match="DPI"):
        pdf_to_bmp_zip(f, tmp_path / "out.zip", dpi=dpi)


def test_reject_encrypted_and_symlinked_pdf(tmp_path):
    f = tmp_path / "input.pdf"
    _pdf(f)
    link = tmp_path / "alias.pdf"
    link.symlink_to(f)
    with pytest.raises(ValueError):
        pdf_to_bmp_zip(link, tmp_path / "out.zip")
    writer = PdfWriter()
    writer.append(PdfReader(str(f)))
    writer.encrypt("p")
    protected = tmp_path / "encrypted.pdf"
    with protected.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="encrypted"):
        pdf_to_bmp_zip(protected, tmp_path / "out.zip")
    assert not (tmp_path / "out.zip").exists()


def _record(*, owner="user:a", mime="application/pdf", name="source.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record):
    def job(db, principal, operation, ids, params):
        return {"operation": operation, "file_ids": ids, "params": params, "owner": principal.name}
    monkeypatch.setattr(from_pdf, "_create_job", job)
    return from_pdf.pdf_to_bmp(
        from_pdf.PdfToBmpRequest(file_id="file-id"),
        principal=SimpleNamespace(name="user:a"),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_default_disabled_and_zip_artifact_contract(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", False)
    assert _output_spec_for_job("pdf-to-bmp") == (".zip", "application/zip")
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-bmp")
    with pytest.raises(HTTPException) as e:
        _submit(monkeypatch, _record())
    assert e.value.status_code == 404


def test_owner_scoped_queue_and_result_contract(monkeypatch):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    assert queue_class_for_operation("pdf-to-bmp") == "heavy"
    assert _submit(monkeypatch, _record()) == {
        "operation": "pdf-to-bmp", "file_ids": ["file-id"],
        "params": {"dpi": 96}, "owner": "user:a",
    }


@pytest.mark.parametrize("record,status", [
    (_record(owner="user:b"), 403),
    (_record(mime="image/png"), 415),
    (_record(name="source.bin"), 415),
    (_record(expired=True), 410),
    (_record(size=30 * 1024 * 1024), 413),
])
def test_malicious_or_unauthorized_source_rejected(monkeypatch, record, status):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, record)
    assert error.value.status_code == status


@pytest.mark.parametrize("bad", [0, 71, 151, True, "96", 96.5])
def test_strict_api_dpi_validation(bad):
    with pytest.raises(ValidationError):
        from_pdf.PdfToBmpRequest(file_id="file-id", dpi=bad)
