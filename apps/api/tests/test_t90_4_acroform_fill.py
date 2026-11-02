"""M33 genuine AcroForm field fill acceptance (not static PDF overlays)."""
from __future__ import annotations

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.services.pdf_acroform_fill import fill_pdf_text_fields


def _source(path):
    page = Canvas(str(path), pagesize=(400, 300))
    page.setFont("Helvetica", 14)
    page.drawString(40, 240, "RCAT internal PDF form")
    page.acroForm.textfield(
        name="teacher", tooltip="Teacher", x=40, y=180,
        width=220, height=28, value="", borderWidth=1,
    )
    page.showPage()
    page.save()


def test_acroform_round_trip_persists_actual_text_field(tmp_path):
    source, dest = tmp_path / "form.pdf", tmp_path / "filled.pdf"
    _source(source)
    assert "/Tx" == PdfReader(str(source)).get_fields()["teacher"]["/FT"]
    fill_pdf_text_fields(source, dest, {"teacher": "RCAT Teacher"})
    result = PdfReader(str(dest), strict=True)
    assert len(result.pages) == 1
    assert str(result.get_fields()["teacher"]["/V"]) == "RCAT Teacher"
    assert dest.stat().st_size > 400


@pytest.mark.parametrize("fields", [
    {},
    {"unknown-field": "some text"},
    {"teacher": "\x01bad"},
    {"teacher": "A" * 1025},
])
def test_acroform_rejects_invalid_fields(tmp_path, fields):
    source, dest = tmp_path / "form.pdf", tmp_path / "filled.pdf"
    _source(source)
    with pytest.raises(ValueError):
        fill_pdf_text_fields(source, dest, fields)
    assert not dest.exists()


def test_acroform_never_modifies_encrypted_source(tmp_path):
    source, encrypted, dest = (
        tmp_path / "form.pdf", tmp_path / "protected.pdf", tmp_path / "filled.pdf",
    )
    _source(source)
    writer = PdfWriter()
    writer.append(PdfReader(str(source)))
    writer.encrypt("password")
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        fill_pdf_text_fields(encrypted, dest, {"teacher": "any"})
    assert not dest.exists()


def test_acroform_refuses_to_overwrite_existing_output(tmp_path):
    source, dest = tmp_path / "form.pdf", tmp_path / "do-not-touch.pdf"
    _source(source)
    dest.write_bytes(b"existing result")
    with pytest.raises(ValueError, match="overwrite"):
        fill_pdf_text_fields(source, dest, {"teacher": "RCAT"})
    assert dest.read_bytes() == b"existing result"


def test_acroform_rejects_candidate_before_publishing_output(monkeypatch, tmp_path):
    from app.services import pdf_acroform_fill as engine

    original = engine.PdfReader
    attempts = 0

    def checked_reader(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise ValueError("simulated candidate verification rejection")
        return original(*args, **kwargs)

    source, destination = tmp_path / "form.pdf", tmp_path / "published.pdf"
    _source(source)
    monkeypatch.setattr(engine, "PdfReader", checked_reader)
    with pytest.raises(ValueError, match="candidate verification rejection"):
        engine.fill_pdf_text_fields(source, destination, {"teacher": "RCAT"})
    assert not destination.exists(), "Do not publish a rejected PDF"
