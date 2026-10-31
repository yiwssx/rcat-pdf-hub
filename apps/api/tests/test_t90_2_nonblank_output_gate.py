"""T90-2: reject silent blank conversion despite structurally valid PDF.

Regression for genuine Microsoft Works import returning a blank PDF with 200.
Does NOT assert complete layout/typographic equivalence to source.
"""
from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import to_pdf_engine


def _document(kind: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(595.28, 841.89))
    if kind == "text":
        pdf.drawString(48, 760, "Actual converted content")
    elif kind == "vector":
        pdf.setFillColorRGB(0.2, 0.3, 0.4)
        pdf.rect(40, 80, 80, 80, fill=1, stroke=0)
    elif kind == "invisible":
        pdf.setFillColorRGB(1, 1, 1)
        pdf.drawString(48, 760, "Invisible white text")
    elif kind == "delayed":
        pdf.showPage()
        pdf.showPage()
        pdf.drawString(48, 760, "Content after blank cover pages")
    elif kind != "blank":
        raise ValueError(kind)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.mark.parametrize("kind", ["blank", "invisible"])
def test_structurally_valid_but_blank_pdf_must_fail_closed(tmp_path, kind):
    content = _document(kind)
    assert content.startswith(b"%PDF-")
    assert len(PdfReader(BytesIO(content), strict=True).pages) == 1
    target = tmp_path / "output.pdf"
    with pytest.raises(ValueError, match="blank or invisible"):
        to_pdf_engine._checked_pdf(content, target)
    assert not target.exists()


@pytest.mark.parametrize("kind,pages", [
    ("text", 1),
    ("vector", 1),
    ("delayed", 3),
])
def test_real_rendered_content_passes_even_without_extracted_text(tmp_path, kind, pages):
    content = _document(kind)
    target = tmp_path / "output.pdf"
    to_pdf_engine._checked_pdf(content, target)
    assert target.read_bytes() == content
    assert len(PdfReader(str(target), strict=True).pages) == pages


def test_office_200_blank_pdf_does_not_persist_artifact(monkeypatch, tmp_path):
    source = tmp_path / "actual-wps-like-source"
    source.write_bytes(b"Nonempty external Office source")
    baseline = source.read_bytes()

    class Reply:
        content = _document("blank")

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, files):
            assert url.endswith("/forms/libreoffice/convert")
            assert files["files"][0] == "document.doc"
            return Reply()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", FakeClient)
    output = tmp_path / "result.pdf"
    with pytest.raises(ValueError, match="blank or invisible"):
        to_pdf_engine.office_document_to_pdf(source, output, original_suffix=".doc")
    assert not output.exists()
    assert source.read_bytes() == baseline


def test_chromium_200_blank_pdf_does_not_persist_artifact(monkeypatch, tmp_path):
    class Reply:
        content = _document("blank")

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, files, data):
            assert data["preferCssPageSize"] == "true"
            assert files["files"][0] == "index.html"
            return Reply()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", FakeClient)
    output = tmp_path / "blank.pdf"
    with pytest.raises(ValueError, match="blank or invisible"):
        to_pdf_engine._html_to_pdf("<p>Expected real text</p>", output)
    assert not output.exists()
