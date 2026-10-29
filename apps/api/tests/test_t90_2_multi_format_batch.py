"""T90-2 combined format batch: binary checks and fail-closed inputs.

Mocks only Gotenberg transport for Office/text (real conversion needs its
isolated Compose golden corpus before any VERIFIED/RELEASED designation).
"""
from __future__ import annotations

from io import BytesIO
import zipfile

import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.routers import to_pdf
from app.services import to_pdf_engine
from app.staged_to_pdf_adapters import STAGED_TO_PDF_INPUTS, execute_staged_to_pdf_operation


def _pdf() -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(80, 750, "RCAT")
    c.showPage()
    c.save()
    return buf.getvalue()


def _png(color: str) -> bytes:
    img = Image.new("RGB", (70, 50), color)
    buf = BytesIO()
    try:
        img.save(buf, format="PNG")
    finally:
        img.close()
    return buf.getvalue()


@pytest.mark.parametrize("operation,mime,suffix", [
    ("doc-to-pdf", "application/msword", ".doc"),
    ("docx-to-pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    ("xls-to-pdf", "application/vnd.ms-excel", ".xls"),
    ("xlsx-to-pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    ("ppt-to-pdf", "application/vnd.ms-powerpoint", ".ppt"),
    ("pptx-to-pdf", "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    ("odt-to-pdf", "application/vnd.oasis.opendocument.text", ".odt"),
    ("ods-to-pdf", "application/vnd.oasis.opendocument.spreadsheet", ".ods"),
    ("odp-to-pdf", "application/vnd.oasis.opendocument.presentation", ".odp"),
    ("rtf-to-pdf", "application/rtf", ".rtf"),
    ("pub-to-pdf", "application/x-mspublisher", ".pub"),
])
def test_office_static_routers_and_gotenberg_binary_guards(monkeypatch, tmp_path, operation, mime, suffix):
    assert STAGED_TO_PDF_INPUTS[operation] == (mime, suffix)
    assert any(route.path.endswith("/" + operation.removesuffix("-to-pdf"))
               for route in to_pdf.router.routes)
    calls = []
    class Response:
        content = _pdf()
        def raise_for_status(self): pass
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"] == 300.0
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, url, *, files):
            assert url.endswith("/forms/libreoffice/convert")
            name, data, ctype = files["files"]
            calls.append((name, data.read(), ctype))
            return Response()
    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    source = tmp_path / ("opaque-storage-" + operation)
    source.write_bytes(b"staged bytes")
    original = source.read_bytes()
    out = tmp_path / "output.pdf"
    to_pdf_engine.office_document_to_pdf(source, out, original_suffix=suffix)
    assert len(PdfReader(str(out), strict=True).pages) == 1
    assert calls == [("document" + suffix, original, "application/octet-stream")]
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match="differ"):
        to_pdf_engine.office_document_to_pdf(source, source, original_suffix=suffix)
    with pytest.raises(ValueError, match="Unsupported"):
        to_pdf_engine.office_document_to_pdf(source, out, original_suffix=".exe")


@pytest.mark.parametrize("kind,extension,fmt", [
    ("jpg", ".jpg", "JPEG"), ("jpeg", ".jpeg", "JPEG"),
    ("png", ".png", "PNG"), ("webp", ".webp", "WEBP"), ("bmp", ".bmp", "BMP"),
])
def test_real_staged_image_conversions_and_magic(monkeypatch, tmp_path, kind, extension, fmt):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    image = Image.new("RGB", (140, 80), "red")
    source = tmp_path / ("image" + extension)
    try:
        image.save(source, format=fmt)
    finally:
        image.close()
    mime = STAGED_TO_PDF_INPUTS[kind + "-to-pdf"][0]
    assert validate_uploaded_file(source, source.name) == mime
    original = source.read_bytes()
    out = tmp_path / "out.pdf"
    execute_staged_to_pdf_operation(kind + "-to-pdf", [source], out, {},
                                    original_name=source.name, content_type=mime)
    assert len(PdfReader(str(out), strict=True).pages) == 1
    assert source.read_bytes() == original
    source.write_bytes(b"%PDF-1.7\nspoof")
    with pytest.raises(HTTPException) as err:
        validate_uploaded_file(source, source.name)
    assert err.value.status_code == 415


@pytest.mark.parametrize("suffix,mime,payload", [
    (".html", "text/html", "<h1>สวัสดี</h1><p>RCAT</p>"),
    (".xml", "application/xml", '<?xml version="1.0"?><root><name>ภาษาไทย</name></root>'),
    (".eml", "message/rfc822", "From: teacher@rcat.ac.th\nTo: staff@rcat.ac.th\nSubject: ทดสอบ\nContent-Type: text/plain; charset=utf-8\n\nสวัสดี RCAT"),
])
def test_local_only_text_format_to_printable_markup(monkeypatch, tmp_path, suffix, mime, payload):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / ("source" + suffix)
    source.write_text(payload, encoding="utf-8")
    assert validate_uploaded_file(source, source.name) == mime
    sent = []
    def render(body, output):
        sent.append(body)
        output.write_bytes(_pdf())
    monkeypatch.setattr(to_pdf_engine, "_html_to_pdf", render)
    out = tmp_path / "output.pdf"
    kind = {".html": "html", ".xml": "xml", ".eml": "eml"}[suffix]
    execute_staged_to_pdf_operation(kind + "-to-pdf", [source], out, {},
                                    original_name=source.name, content_type=mime)
    assert sent and "RCAT" in sent[0] if suffix != ".xml" else bool(sent)
    assert "<script" not in sent[0].lower()
    assert "<iframe" not in sent[0].lower()
    assert len(PdfReader(str(out)).pages) == 1


def test_html_strips_remote_fetches_css_and_script_content(monkeypatch, tmp_path):
    source = tmp_path / "remote.html"
    source.write_text(
        "<head><style>body{background:url(http://127.0.0.1/)}</style></head>"
        "<script>fetch('http://169.254.169.254/')</script>"
        "<h2 onload='fetch(1)'>หัวข้อ</h2>"
        "<img src='http://127.0.0.1/private'>"
        "<a href='https://example.com'>safe text</a>", encoding="utf-8")
    parts = []
    monkeypatch.setattr(to_pdf_engine, "_html_to_pdf",
                        lambda body, dst: parts.append(body))
    to_pdf_engine.html_to_pdf(source, tmp_path / "out.pdf")
    html = parts[0].lower()
    assert "<h2>หัวข้อ</h2>" in html
    assert "safe text" in html
    assert "169.254.169.254" not in html
    assert "127.0.0.1" not in html
    for element in ("<script", "<style", "<img", "<a ", "onload", "href=", "src="):
        assert element not in html


@pytest.mark.parametrize("payload", [
    "<!DOCTYPE root [<!ENTITY secret SYSTEM 'file:///etc/passwd'>]><root>&secret;</root>",
    "<?xml-stylesheet href='http://127.0.0.1' ?><root/>",
    "<root><bad></root>",
    "not xml",
])
def test_xml_rejects_entities_stylesheets_malformed(monkeypatch, tmp_path, payload):
    source = tmp_path / "bad.xml"
    source.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        to_pdf_engine.xml_to_pdf(source, tmp_path / "out.pdf")


def test_eml_multipart_html_attachment_never_rendered(monkeypatch, tmp_path):
    source = tmp_path / "letter.eml"
    source.write_text(
        "From: admin@rcat.ac.th\nSubject: อนุมัติ\nMIME-Version: 1.0\n"
        "Content-Type: multipart/mixed; boundary=abc\n\n"
        "--abc\nContent-Type: text/plain; charset=utf-8\n\n"
        "ข้อความปลอดภัย\n--abc\n"
        "Content-Type: text/html\nContent-Disposition: attachment\n\n"
        "<script>fetch('http://127.0.0.1')</script>\n--abc--\n",
        encoding="utf-8",
    )
    rendered = []
    monkeypatch.setattr(to_pdf_engine, "_html_to_pdf",
                        lambda html, target: rendered.append(html))
    to_pdf_engine.eml_to_pdf(source, tmp_path / "out.pdf")
    assert "ข้อความปลอดภัย" in rendered[0]
    assert "fetch(" not in rendered[0]


@pytest.mark.parametrize("extension,mime", [
    (".cbz", "application/vnd.comicbook+zip"), (".zip", "application/zip"),
])
def test_real_archive_pages_in_natural_order_and_immutability(monkeypatch, tmp_path, extension, mime):
    source = tmp_path / ("comic" + extension)
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("pictures/10.png", _png("blue"))
        z.writestr("pictures/2.png", _png("red"))
        z.writestr("ComicInfo.xml", "<ComicInfo></ComicInfo>")
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(source, source.name) == mime
    original = source.read_bytes()
    out = tmp_path / "archive.pdf"
    kind = extension[1:]
    execute_staged_to_pdf_operation(kind + "-to-pdf", [source], out, {},
                                    original_name=source.name, content_type=mime)
    pdf = PdfReader(str(out), strict=True)
    assert len(pdf.pages) == 2
    assert source.read_bytes() == original
    colors = []
    for page in pdf.pages:
        embedded = Image.open(BytesIO(page.images[0].data))
        try:
            colors.append(embedded.convert("RGB").getpixel((35, 25)))
        finally:
            embedded.close()
    assert colors[0][0] > colors[0][2]  # red (2) precedes blue (10)
    assert colors[1][2] > colors[1][0]


@pytest.mark.parametrize("entry", [
    "../escape.png", "/absolute.png", "C:/windows/file.png", "file.svg", "bad.exe",
])
def test_archive_denies_unsafe_members(monkeypatch, tmp_path, entry):
    source = tmp_path / "unsafe.cbz"
    with zipfile.ZipFile(source, "w") as z:
        z.writestr(entry, _png("blue"))
    with pytest.raises(ValueError):
        to_pdf_engine.archive_images_to_pdf(source, tmp_path / "output.pdf", kind="cbz")
    assert not (tmp_path / "output.pdf").exists()


def test_archive_rejects_zip_bombs_without_reading_members(monkeypatch, tmp_path):
    source = tmp_path / "bomb.cbz"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("one.png", b"0" * (12 * 1024 * 1024))
    with pytest.raises(ValueError, match="expansion"):
        to_pdf_engine.archive_images_to_pdf(source, tmp_path / "bad.pdf", kind="cbz")
    assert not (tmp_path / "bad.pdf").exists()
