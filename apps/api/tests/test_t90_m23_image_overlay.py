"""M23 genuine PDF+image binary test and guarded source/scope behavior."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.main import app as production_app
from app.queue import queue_class_for_operation
from app.routers import pdf_image_overlay
from app.services.pdf_image_overlay import add_image_to_pdf, validate_image_overlay


def _pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(320, 200))
    for n in range(1, 3):
        c.drawString(20, 140, f"Original page {n}")
        c.showPage()
    c.save()


def test_m23_real_embedded_image_preserves_source_and_other_pages(tmp_path):
    source = tmp_path / "original.pdf"
    image = tmp_path / "photo.png"
    target = tmp_path / "result.pdf"
    _pdf(source)
    Image.new("RGB", (80, 40), (210, 90, 40)).save(image)
    before_pdf = source.read_bytes()
    before_image = image.read_bytes()

    add_image_to_pdf(source, image, target, page=2, x=30.0, y=25.0,
                     width=120.0, height=60.0)
    assert target.read_bytes().startswith(b"%PDF-")
    assert source.read_bytes() == before_pdf
    assert image.read_bytes() == before_image
    original = PdfReader(str(source), strict=True)
    result = PdfReader(str(target), strict=True)
    assert len(original.pages) == len(result.pages) == 2
    assert "Original page 1" in result.pages[0].extract_text()
    before = original.pages[0].get_contents()
    after = result.pages[0].get_contents()
    assert (before.get_data() if before else b"") == (after.get_data() if after else b"")
    assert "/XObject" in result.pages[1]["/Resources"]


@pytest.mark.parametrize("params", [
    {"page": True, "x": 30, "y": 20, "width": 40, "height": 20},
    {"page": 0, "x": 30, "y": 20, "width": 40, "height": 20},
    {"page": 1, "x": float("nan"), "y": 20, "width": 40, "height": 20},
    {"page": 1, "x": 30, "y": 20, "width": 0, "height": 20},
    {"page": 1, "x": 30, "y": 20, "width": 40, "height": 9000},
])
def test_m23_rejects_invalid_parameters(params):
    with pytest.raises(ValueError):
        validate_image_overlay(**params)


def test_m23_rejects_unsafe_pdf_and_output_clobber(tmp_path):
    pdf, image, dest = (tmp_path / name for name in ("in.pdf", "im.jpg", "out.pdf"))
    _pdf(pdf)
    Image.new("RGB", (40, 20), (0, 60, 240)).save(image, "JPEG")
    writer = PdfWriter()
    writer.append(PdfReader(str(pdf)))
    writer.pages[0].rotate(90)
    with pdf.open("wb") as output:
        writer.write(output)
    with pytest.raises(ValueError, match="rotated"):
        add_image_to_pdf(pdf, image, dest, page=1, x=20, y=20, width=40, height=20)
    assert not dest.exists()
    _pdf(pdf)
    dest.write_bytes(b"do-not-clobber")
    with pytest.raises(ValueError, match="must not exist"):
        add_image_to_pdf(pdf, image, dest, page=1, x=20, y=20, width=40, height=20)
    assert dest.read_bytes() == b"do-not-clobber"


def _file(ident, owner, name, mime, size=600):
    return SimpleNamespace(
        id=ident, source_system=owner, original_name=name,
        content_type=mime, size=size, expires_at=None,
    )


def test_m23_routes_and_queue_default_off_and_scope(monkeypatch):
    settings = get_settings()
    assert settings.pdf_image_overlay_tools_enabled is False
    assert not any(r.path == "/api/v1/pdf/advanced/add-image" for r in production_app.routes)
    with pytest.raises(ValueError):
        queue_class_for_operation("add-pdf-image")
    monkeypatch.setattr(settings, "pdf_image_overlay_tools_enabled", True)
    assert queue_class_for_operation("add-pdf-image") == "pdf"

    pdf = _file("p1", "user:owner", "file.pdf", "application/pdf")
    img = _file("i1", "user:owner", "file.png", "image/png")
    items = {"p1": pdf, "i1": img}
    db = SimpleNamespace(get=lambda model, ident: items.get(ident))
    principal = SimpleNamespace(name="user:owner")
    request = pdf_image_overlay.AddPdfImageRequest(
        file_id="p1", image_file_id="i1", page=1,
        x=20.0, y=20.0, width=100.0, height=60.0,
    )
    enqueued = []
    monkeypatch.setattr(pdf_image_overlay, "_create_job",
                        lambda db, principal, operation, files, params: (
                            enqueued.append((operation, files, params)) or {"queued": True}
                        ))
    result = pdf_image_overlay.add_pdf_image(req=request, principal=principal, db=db)
    assert result == {"queued": True}
    assert enqueued == [("add-pdf-image", ["p1", "i1"], {
        "page": 1, "x": 20.0, "y": 20.0, "width": 100.0, "height": 60.0,
    })]
    items["i1"] = _file("i1", "user:other", "file.png", "image/png")
    with pytest.raises(HTTPException) as denied:
        pdf_image_overlay.add_pdf_image(req=request, principal=principal, db=db)
    assert denied.value.status_code == 403
    assert len(enqueued) == 1


def test_m23_rejects_schema_and_disabled_submit(monkeypatch):
    base = dict(file_id="p1", image_file_id="i1", page=1,
                x=20.0, y=20.0, width=60.0, height=40.0)
    for wrong in (
        {"page": True}, {"file_id": "i1"}, {"x": float("inf")},
        {"width": 0}, {"image_file_id": ""}, {"url": "https://example.test"},
    ):
        with pytest.raises(ValidationError):
            pdf_image_overlay.AddPdfImageRequest(**(base | wrong))
    monkeypatch.setattr(get_settings(), "pdf_image_overlay_tools_enabled", False)
    records = {
        "p1": _file("p1", "user:owner", "file.pdf", "application/pdf"),
        "i1": _file("i1", "user:owner", "file.png", "image/png"),
    }
    with pytest.raises(HTTPException) as denied:
        pdf_image_overlay.add_pdf_image(
            req=pdf_image_overlay.AddPdfImageRequest(**base),
            principal=SimpleNamespace(name="user:owner"),
            db=SimpleNamespace(get=lambda model, ident: records.get(ident)),
        )
    assert denied.value.status_code == 404
