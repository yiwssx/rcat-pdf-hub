"""T90-2 T04/T31 ebook text-only contract, ZIP/XML abuse, PDF binary and flags."""
from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services import to_pdf_ebooks, to_pdf_engine
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation


def _epub(path, *, chapter=None, opf=None, extras=None, mimetype=b"application/epub+zip"):
    container = (
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OPS/package.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    )
    opf = opf or (
        '<package xmlns="http://www.idpf.org/2007/opf">'
        '<metadata><title>คู่มือภาษาไทย</title></metadata>'
        '<manifest><item id="c1" href="chapter-1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="c2" href="chapter-2.xhtml" media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="c2"/><itemref idref="c1"/></spine></package>'
    )
    chapter = chapter or (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
        '<h1>บทแรก</h1><p>สวัสดี RCAT &amp; เกษตร</p>'
        '<script>fetch("http://169.254.169.254")</script>'
        '<img src="http://127.0.0.1/private"/></body></html>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OPS/package.opf", opf)
        archive.writestr("OPS/chapter-1.xhtml", chapter.replace("บทแรก", "บทหนึ่ง"))
        archive.writestr("OPS/chapter-2.xhtml", chapter.replace("บทแรก", "บทสอง"))
        for name, data in extras or []:
            archive.writestr(name, data)


def _fb2(path, *, body=None):
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        '<description><title-info><book-title>เรื่องภาษาไทย</book-title>'
        '</title-info></description><body><section>'
        '<title><p>บทที่หนึ่ง</p></title>'
        + (body or '<p>เนื้อหา สวัสดี &amp; เกษตร</p>'
           '<p>&lt;script&gt;fetch("http://127.0.0.1")&lt;/script&gt;</p>')
        + '</section></body></FictionBook>',
        encoding="utf-8",
    )


def _pdf_bytes():
    out = BytesIO()
    doc = canvas.Canvas(out)
    doc.drawString(40, 710, "Ebook staged PDF contract")
    doc.showPage()
    doc.save()
    return out.getvalue()


def test_epub_spine_order_thai_escapes_scripts_and_never_fetches(tmp_path):
    source = tmp_path / "book.epub"
    _epub(source)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    html = to_pdf_ebooks.epub_to_safe_html(source)
    assert "คู่มือภาษาไทย" in html
    assert html.index("บทสอง") < html.index("บทหนึ่ง")
    assert "สวัสดี RCAT &amp; เกษตร" in html
    assert "169.254.169.254" not in html
    assert "127.0.0.1" not in html
    assert "<script" not in html and "<img" not in html
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_fictionbook_title_paragraphs_and_escaped_content(tmp_path):
    source = tmp_path / "book.fb2"
    _fb2(source)
    html = to_pdf_ebooks.fb2_to_safe_html(source)
    assert "<h1>เรื่องภาษาไทย</h1>" in html
    assert "บทที่หนึ่ง" in html and "สวัสดี &amp; เกษตร" in html
    assert "<script" not in html and "&lt;script&gt;" in html


@pytest.mark.parametrize("suffix,mime,make", [
    (".epub", "application/epub+zip", _epub),
    (".fb2", "application/x-fictionbook+xml", _fb2),
])
def test_flagged_upload_and_binary_pdf_output(monkeypatch, tmp_path, suffix, mime, make):
    path = tmp_path / ("source" + suffix)
    make(path)
    original = path.read_bytes()
    with pytest.raises(HTTPException) as rejected:
        validate_uploaded_file(path, path.name)
    assert rejected.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(path, path.name) == mime
    sent = []
    class Reply:
        content = _pdf_bytes()
        def raise_for_status(self): pass
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"] == 180.0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, *, files, data):
            assert data == {"preferCssPageSize": "true"}
            assert url.endswith("/forms/chromium/convert/html")
            markup = files["files"][1].decode("utf-8")
            assert "Content-Security-Policy" in markup
            sent.append(markup)
            return Reply()
    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    output = tmp_path / "book.pdf"
    operation = suffix[1:] + "-to-pdf"
    execute_staged_to_pdf_operation(
        operation, [path], output, {},
        original_name=path.name, content_type=mime,
    )
    assert len(PdfReader(str(output), strict=True).pages) == 1
    assert sent and "ภาษาไทย" in sent[0]
    assert original == path.read_bytes()
    with pytest.raises(ValueError, match="persisted MIME"):
        checked_source(operation, path, name=path.name, mime="text/plain")
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_to_pdf_operation(
            operation, [path], tmp_path / "no.pdf", {},
            original_name=path.name, content_type=mime,
        )


@pytest.mark.parametrize("entry", [
    "../evil.xhtml", "OPS/../../escape.xhtml", "/abs.xhtml",
    "C:/win/path", r"OPS\backslash.xhtml",
])
def test_epub_blocks_zip_slip_even_for_unused_resources(tmp_path, entry):
    source = tmp_path / "unsafe.epub"
    _epub(source, extras=[(entry, "<p>unsafe</p>")])
    with pytest.raises(ValueError, match="Unsafe EPUB entry"):
        to_pdf_ebooks.epub_to_safe_html(source)


def test_epub_rejects_duplicate_casefold_and_encrypted_entry(tmp_path):
    path = tmp_path / "duplicate.epub"
    _epub(path, extras=[("ops/chapter-1.xhtml", "<html/>")])
    with pytest.raises(ValueError, match="duplicated"):
        to_pdf_ebooks.epub_to_safe_html(path)
    _epub(path, extras=[("META-INF/encryption.xml", '<encryption/>')])
    with pytest.raises(ValueError, match="Encrypted"):
        to_pdf_ebooks.epub_to_safe_html(path)


@pytest.mark.parametrize("bad_href", [
    "http://127.0.0.1/secret.xhtml", "//example.com/chapter.xhtml",
    "../private.xhtml", "chapter-1.xhtml#section", "file:///etc/passwd",
    "%2e%2e/escape.xhtml", "C:/windows/private.xhtml",
])
def test_epub_rejects_remote_or_unsafe_spine_urls(tmp_path, bad_href):
    path = tmp_path / "remote.epub"
    opf = (
        '<package><manifest><item id="c1" href="'
        + bad_href
        + '" media-type="application/xhtml+xml"/></manifest>'
          '<spine><itemref idref="c1"/></spine></package>'
    )
    _epub(path, opf=opf)
    with pytest.raises(ValueError):
        to_pdf_ebooks.epub_to_safe_html(path)


@pytest.mark.parametrize("location", ["chapter", "fb2"])
def test_ebook_blocks_dtd_external_entities(tmp_path, location):
    payload = (
        '<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]>'
        '<html><body><p>&ext;</p></body></html>'
    )
    if location == "chapter":
        path = tmp_path / "evil.epub"
        _epub(path, chapter=payload)
        with pytest.raises(ValueError, match="XML"):
            to_pdf_ebooks.epub_to_safe_html(path)
    else:
        path = tmp_path / "evil.fb2"
        path.write_text(
            '<!DOCTYPE FictionBook [<!ENTITY ext SYSTEM "file:///etc/passwd">]>'
            '<FictionBook><body><section><p>&ext;</p></section></body></FictionBook>',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="XML"):
            to_pdf_ebooks.fb2_to_safe_html(path)


def test_epub_rejects_decompression_bomb_from_metadata(tmp_path):
    path = tmp_path / "bomb.epub"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("OPS/giant.xhtml", "A" * (9 * 1024 * 1024))
        archive.writestr("META-INF/container.xml", "<container/>")
    with pytest.raises(ValueError, match="Unsafe or duplicated"):
        to_pdf_ebooks.epub_to_safe_html(path)


def test_epub_rejects_bad_magic_and_not_actual_epub(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    path = tmp_path / "fake.epub"
    path.write_bytes(b"this is not an epub")
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(path, path.name)
    assert exc.value.status_code == 415
    _epub(path, mimetype=b"application/zip")
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(path, path.name)
    assert exc.value.status_code == 415


def test_fb2_rejects_wrong_root_and_binary_payload(tmp_path):
    path = tmp_path / "wrong.fb2"
    path.write_text("<html><body><p>not FictionBook</p></body></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="FictionBook2"):
        to_pdf_ebooks.fb2_to_safe_html(path)
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="XML"):
        to_pdf_ebooks.fb2_to_safe_html(path)


@pytest.mark.parametrize("kind", ["epub", "fb2"])
def test_ebook_refuses_in_place_and_keeps_input_bytes(tmp_path, kind):
    path = tmp_path / ("source." + kind)
    _epub(path) if kind == "epub" else _fb2(path)
    before = path.read_bytes()
    fn = to_pdf_engine.epub_to_pdf if kind == "epub" else to_pdf_engine.fb2_to_pdf
    with pytest.raises(ValueError, match="differ"):
        fn(path, path)
    assert path.read_bytes() == before
