"""M25/M26/M29 real binary source and safety-claim regression."""
from hashlib import sha256

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services.pdf_markup import markup_pdf, validate_markup


def _source(path):
    pdf = canvas.Canvas(str(path), pagesize=(595, 842))
    pdf.drawString(80, 700, "INTERNAL CONFIDENTIAL CONTENT")
    pdf.showPage()
    pdf.drawString(70, 690, "SECOND PAGE")
    pdf.showPage()
    pdf.save()


@pytest.mark.parametrize(("mode", "text", "subtype"), [
    ("annotation", "Review this page", "/FreeText"),
    ("highlight", "", "/Highlight"),
])
def test_m25_m26_write_actual_pdf_annotation(tmp_path, mode, text, subtype):
    src, dst = tmp_path / "source.pdf", tmp_path / "result.pdf"
    _source(src)
    digest = sha256(src.read_bytes()).hexdigest()
    markup_pdf(src, dst, mode=mode, page=1, x=72, y=690,
               width=250, height=35, text=text)
    assert sha256(src.read_bytes()).hexdigest() == digest
    pdf = PdfReader(str(dst), strict=True)
    assert len(pdf.pages) == 2
    assert len(pdf.pages[0]["/Annots"]) == 1
    assert str(pdf.pages[0]["/Annots"][0].get_object()["/Subtype"]) == subtype
    assert not pdf.pages[1].get("/Annots")


def test_m29_whiteout_is_visible_not_secure_redaction(tmp_path):
    src, dst = tmp_path / "source.pdf", tmp_path / "result.pdf"
    _source(src)
    markup_pdf(src, dst, mode="whiteout", page=1, x=70, y=680,
               width=400, height=50, text="")
    pdf = PdfReader(str(dst), strict=True)
    assert len(pdf.pages) == 2
    assert not pdf.pages[0].get("/Annots")
    # Underlying original text MUST remain: no false secure-redaction claim.
    assert "INTERNAL CONFIDENTIAL CONTENT" in pdf.pages[0].extract_text()


def test_markup_rejects_non_ascii_and_hidden_text():
    with pytest.raises(ValueError, match="ASCII"):
        validate_markup(mode="annotation", page=1, x=10, y=10,
                        width=100, height=30, text="สวัสดี")
    with pytest.raises(ValueError, match="hidden"):
        validate_markup(mode="whiteout", page=1, x=10, y=10,
                        width=100, height=30, text="secret")
    with pytest.raises(ValueError, match="rectangle"):
        validate_markup(mode="highlight", page=1, x=-3, y=10,
                        width=100, height=30)
