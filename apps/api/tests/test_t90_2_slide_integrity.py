"""T90-2: preserve full PPTX/ODP slide counts before publishing PDF.

A nonblank page or HTTP 200 is not evidence that *all* slides survived.
Synthetic ZIP packages exercise parser limits; pinned live Gotenberg QA tests
already verify two authentic Thai slides and text order separately.
"""
from io import BytesIO
from zipfile import ZipFile

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import to_pdf_engine
from app.services.to_pdf_slide_integrity import expected_slide_pages


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
O_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
D_NS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"


def _presentation(tmp_path, suffix, slides=2, *, broken_xml=False):
    source = tmp_path / ("slides" + suffix)
    if suffix == ".pptx":
        children = "".join(f'<p:sldId id="{256 + i}"/>' for i in range(slides))
        xml = (
            f'<p:presentation xmlns:p="{P_NS}"><p:sldIdLst>'
            f'{children}</p:sldIdLst></p:presentation>'
        )
        name = "ppt/presentation.xml"
    else:
        children = "".join(f'<draw:page draw:name="slide{i}"/>' for i in range(slides))
        xml = (
            f'<office:document-content xmlns:office="{O_NS}" xmlns:draw="{D_NS}">'
            f'<office:body><office:presentation>{children}'
            f'</office:presentation></office:body></office:document-content>'
        )
        name = "content.xml"
    with ZipFile(source, "w") as archive:
        archive.writestr(name, (xml + "<") if broken_xml else xml)
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.presentation")
    return source


def _pdf(pages: int) -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream)
    for index in range(pages):
        c.drawString(55, 760, f"RCAT slide {index + 1}")
        c.showPage()
    c.save()
    return stream.getvalue()


@pytest.mark.parametrize("suffix", [".pptx", ".odp"])
def test_slide_count_inventory_reads_source_without_mutation(tmp_path, suffix):
    source = _presentation(tmp_path, suffix, 2)
    original = source.read_bytes()
    assert expected_slide_pages(source, original_suffix=suffix) == 2
    assert source.read_bytes() == original
    assert expected_slide_pages(source, original_suffix=".doc") is None


@pytest.mark.parametrize("suffix", [".pptx", ".odp"])
@pytest.mark.parametrize("output_pages", [1, 3])
def test_real_parser_refuses_silent_slide_loss_or_duplication(
    monkeypatch, tmp_path, suffix, output_pages,
):
    source = _presentation(tmp_path, suffix, 2)
    original = source.read_bytes()
    output = tmp_path / "result.pdf"

    class Reply:
        content = _pdf(output_pages)

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, files):
            assert url.endswith("/forms/libreoffice/convert")
            assert files["files"][0] == "document" + suffix
            return Reply()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    with pytest.raises(ValueError, match="lost or added pages"):
        to_pdf_engine.office_document_to_pdf(source, output, original_suffix=suffix)
    assert not output.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("suffix", [".pptx", ".odp"])
def test_matching_slide_count_success(monkeypatch, tmp_path, suffix):
    source = _presentation(tmp_path, suffix, 2)
    expected = _pdf(2)

    class Reply:
        content = expected

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, files):
            return Reply()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    output = tmp_path / "result.pdf"
    to_pdf_engine.office_document_to_pdf(source, output, original_suffix=suffix)
    assert output.read_bytes() == expected
    assert len(PdfReader(str(output)).pages) == 2


@pytest.mark.parametrize("suffix", [".pptx", ".odp"])
@pytest.mark.parametrize("slides", [0, 301])
def test_absent_or_unbounded_slide_inventory_fails_closed(tmp_path, suffix, slides):
    source = _presentation(tmp_path, suffix, slides)
    with pytest.raises(ValueError, match="slide count"):
        expected_slide_pages(source, original_suffix=suffix)


@pytest.mark.parametrize("suffix", [".pptx", ".odp"])
def test_malformed_presentation_xml_fails_before_renderer(monkeypatch, tmp_path, suffix):
    source = _presentation(tmp_path, suffix, broken_xml=True)
    monkeypatch.setattr(to_pdf_engine.httpx, "Client", lambda **kwargs: pytest.fail(
        "Gotenberg must never receive ambiguous source slide inventory"
    ))
    with pytest.raises(ValueError, match="invalid or unsafe"):
        to_pdf_engine.office_document_to_pdf(
            source, tmp_path / "out.pdf", original_suffix=suffix
        )
    assert not (tmp_path / "out.pdf").exists()


@pytest.mark.parametrize("suffix", [".pptx", ".odp"])
def test_xxe_presentation_xml_fails_closed(tmp_path, suffix):
    source = _presentation(tmp_path, suffix)
    with ZipFile(source) as archive:
        data = archive.read("ppt/presentation.xml" if suffix == ".pptx" else "content.xml")
    xml = b'<!DOCTYPE doc [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>' + data
    with ZipFile(source, "w") as archive:
        archive.writestr("ppt/presentation.xml" if suffix == ".pptx" else "content.xml", xml)
    with pytest.raises(ValueError):
        expected_slide_pages(source, original_suffix=suffix)
