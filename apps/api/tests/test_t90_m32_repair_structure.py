"""M32 basic real qpdf structure normalization without false recovery claims."""
from hashlib import sha256
from shutil import which

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_repair_structure import repair_pdf_structure


def fixture(path):
    pdf = canvas.Canvas(str(path), pagesize=(595, 842))
    pdf.drawString(72, 700, "UNALTERED PAGE ONE")
    pdf.showPage()
    pdf.drawString(72, 700, "UNALTERED PAGE TWO")
    pdf.showPage()
    pdf.save()


@pytest.mark.skipif(which("qpdf") is None, reason="requires installed qpdf")
def test_real_qpdf_rewrites_structure_without_page_loss(tmp_path):
    src, dst = tmp_path / "src.pdf", tmp_path / "repair.pdf"
    fixture(src)
    digest = sha256(src.read_bytes()).hexdigest()
    repair_pdf_structure(src, dst)
    assert sha256(src.read_bytes()).hexdigest() == digest
    result = PdfReader(str(dst), strict=True)
    assert len(result.pages) == 2
    assert "UNALTERED PAGE ONE" in result.pages[0].extract_text()
    assert "UNALTERED PAGE TWO" in result.pages[1].extract_text()


def test_repair_rejects_invalid_source_and_inplace(tmp_path):
    source = tmp_path / "notpdf.pdf"
    source.write_bytes(b"not a PDF")
    with pytest.raises(ValueError, match="source"):
        repair_pdf_structure(source, tmp_path / "out.pdf")
    fixture(source)
    with pytest.raises(ValueError, match="separate"):
        repair_pdf_structure(source, source)


def test_repair_rejects_encrypted_source(tmp_path):
    source, locked = tmp_path / "src.pdf", tmp_path / "locked.pdf"
    fixture(source)
    writer = PdfWriter()
    writer.append(str(source))
    writer.encrypt("secret")
    with locked.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(ValueError, match="Encrypted"):
        repair_pdf_structure(locked, tmp_path / "repaired.pdf")
