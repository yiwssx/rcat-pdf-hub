"""F16 PDF-to-animated-GIF generated-PDF functional and owner boundary tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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
from app.services.from_pdf_gif import pdf_to_animated_gif
from app.worker_tasks import _output_spec_for_job


def _two_page_pdf(path: Path) -> None:
    doc = Canvas(str(path), pagesize=(240, 180))
    doc.setFillColorRGB(1, 0, 0)
    doc.rect(10, 10, 95, 90, fill=1)
    doc.showPage()
    doc.setFillColorRGB(0, 0, 1)
    doc.rect(100, 10, 95, 90, fill=1)
    doc.showPage()
    doc.save()


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="Poppler not installed")
def test_real_pdf_pages_to_one_animated_gif_with_exact_frames(tmp_path):
    src = tmp_path / "input.pdf"
    out = tmp_path / "result.gif"
    _two_page_pdf(src)
    original = src.read_bytes()
    pdf_to_animated_gif(src, out, dpi=96, frame_ms=800)
    assert out.read_bytes()[:6] == b"GIF89a"
    assert src.read_bytes() == original
    with Image.open(out) as gif:
        assert gif.format == "GIF" and gif.n_frames == 2
        assert gif.info["loop"] == 0
        assert gif.info["duration"] == 800
        gif.seek(0)
        first = gif.convert("RGB").tobytes()
        gif.seek(1)
        second = gif.convert("RGB").tobytes()
        assert first != second, "Different source-page graphics must remain distinct GIF frames"


@pytest.mark.parametrize("bad", [0, 71, 151, 100.5, True])
def test_reject_invalid_dpi_before_pdf_parse(tmp_path, bad):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    with pytest.raises(ValueError, match="DPI"):
        pdf_to_animated_gif(source, tmp_path / "out.gif", dpi=bad)


@pytest.mark.parametrize("bad", [0, 299, 5001, True, 500.5])
def test_reject_invalid_frame_duration(tmp_path, bad):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    with pytest.raises(ValueError, match="frame duration"):
        pdf_to_animated_gif(source, tmp_path / "out.gif", frame_ms=bad)


def test_reject_symlink_and_encrypted_pdf(tmp_path):
    src = tmp_path / "input.pdf"
    _two_page_pdf(src)
    link = tmp_path / "alias.pdf"
    link.symlink_to(src)
    with pytest.raises(ValueError):
        pdf_to_animated_gif(link, tmp_path / "out.gif")
    writer = PdfWriter()
    writer.append(PdfReader(str(src)))
    writer.encrypt("secret")
    protected = tmp_path / "encrypted.pdf"
    with protected.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="Encrypted"):
        pdf_to_animated_gif(protected, tmp_path / "out.gif")
    assert not (tmp_path / "out.gif").exists()


def _record(*, owner="user:one", mime="application/pdf", name="file.pdf",
            size=1234, expired=False):
    return SimpleNamespace(
        source_system=owner, content_type=mime, original_name=name, size=size,
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)) if expired else None,
    )


def _submit(monkeypatch, record, *, owner="user:one", dpi=96, frame_ms=1200):
    def enqueue(db, principal, operation, ids, params):
        return {"owner": principal.name, "operation": operation, "ids": ids, "params": params}
    monkeypatch.setattr(from_pdf, "_create_job", enqueue)
    return from_pdf.pdf_to_gif(
        from_pdf.PdfToGifRequest(file_id="file-id", dpi=dpi, frame_ms=frame_ms),
        principal=SimpleNamespace(name=owner),
        db=SimpleNamespace(get=lambda model, file_id: record),
    )


def test_default_off_and_output_mime(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "from_pdf_tools_enabled", False)
    with pytest.raises(HTTPException) as e:
        _submit(monkeypatch, _record())
    assert e.value.status_code == 404
    with pytest.raises(ValueError):
        queue_class_for_operation("pdf-to-gif")
    assert _output_spec_for_job("pdf-to-gif") == (".gif", "image/gif")


def test_owner_bound_route_and_heavy_queue(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "from_pdf_tools_enabled", True)
    assert _submit(monkeypatch, _record(), dpi=120, frame_ms=550) == {
        "owner": "user:one", "operation": "pdf-to-gif", "ids": ["file-id"],
        "params": {"dpi": 120, "frame_ms": 550},
    }
    assert queue_class_for_operation("pdf-to-gif") == "heavy"


@pytest.mark.parametrize("record,expected", [
    (_record(owner="user:another"), 403),
    (_record(expired=True), 410),
    (_record(name="fake.bin"), 415),
    (_record(mime="image/png"), 415),
    (_record(size=40 * 1024 * 1024), 413),
])
def test_reject_unowned_expired_wrong_type_or_oversized(monkeypatch, record, expected):
    monkeypatch.setattr(get_settings(), "from_pdf_tools_enabled", True)
    with pytest.raises(HTTPException) as error:
        _submit(monkeypatch, record)
    assert error.value.status_code == expected


@pytest.mark.parametrize("kwargs", [
    {"dpi": 71}, {"dpi": 151}, {"dpi": True},
    {"frame_ms": 299}, {"frame_ms": 5001}, {"frame_ms": "1200"},
])
def test_route_rejects_invalid_options(kwargs):
    with pytest.raises(ValidationError):
        from_pdf.PdfToGifRequest(file_id="file-id", **kwargs)
