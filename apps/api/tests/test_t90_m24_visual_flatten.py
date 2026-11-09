"""M24 basic real visual-flatten binary acceptance and negative source guards."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from shutil import which

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_flatten_visual import visual_flatten_pdf


def _source(path: Path):
    pdf = canvas.Canvas(str(path), pagesize=(595, 842))
    pdf.drawString(80, 760, "visible-page-one")
    pdf.showPage()
    pdf.drawString(80, 700, "visible-page-two")
    pdf.showPage()
    pdf.save()


@pytest.mark.skipif(which("pdftoppm") is None, reason="requires pinned Poppler renderer")
def test_m24_real_two_page_image_only_output(tmp_path):
    source = tmp_path / "source.pdf"
    target = tmp_path / "flatten.pdf"
    _source(source)
    digest = sha256(source.read_bytes()).hexdigest()
    visual_flatten_pdf(source, target)
    assert source.read_bytes().startswith(b"%PDF-")
    assert sha256(source.read_bytes()).hexdigest() == digest
    assert target.read_bytes().startswith(b"%PDF-")
    result = PdfReader(str(target), strict=True)
    assert len(result.pages) == 2
    assert all(not (page.extract_text() or "").strip() for page in result.pages)
    assert all(not page.get("/Annots") for page in result.pages)
    assert all(abs(float(page.mediabox.width) - 595) < 1 for page in result.pages)


def test_m24_rejects_bad_source_and_inplace_output(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-not-a-real-document")
    with pytest.raises(Exception):
        visual_flatten_pdf(source, tmp_path / "out.pdf")
    _source(source)
    with pytest.raises(ValueError, match="distinct"):
        visual_flatten_pdf(source, source)


def test_m24_rejects_encrypted_pdf(tmp_path):
    original = tmp_path / "source.pdf"
    encrypted = tmp_path / "encrypted.pdf"
    _source(original)
    writer = PdfWriter()
    writer.append(str(original))
    writer.encrypt("secret-password")
    with encrypted.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(ValueError, match="encrypted"):
        visual_flatten_pdf(encrypted, tmp_path / "flatten.pdf")
