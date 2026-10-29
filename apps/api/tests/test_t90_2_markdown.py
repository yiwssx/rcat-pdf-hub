"""T90-2.2 Markdown: safe Thai CommonMark and deterministic binary gates."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from markdown_it import MarkdownIt
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services import to_pdf_engine
from app.staged_to_pdf_adapters import execute_staged_to_pdf_operation


def _one_page_pdf() -> bytes:
    payload = BytesIO()
    document = canvas.Canvas(payload)
    document.drawString(30, 750, "RCAT Markdown contract")
    document.showPage()
    document.save()
    return payload.getvalue()


def test_commonmark_thai_tables_code_and_raw_html_escaped(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "thai.md"
    source.write_text(
        "# หัวข้อภาษาไทย\n\n**ตัวหนา** และ `โค้ด`\n\n"
        "| วิชา | คะแนน |\n| --- | --- |\n| คอมพิวเตอร์ | 90 |\n\n"
        "<script>alert(1)</script>\n\n"
        "![remote](http://127.0.0.1/internal)\n"
        "[link](https://example.com)\n"
        "<img src='http://127.0.0.1/internal'>\n",
        encoding="utf-8",
    )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    posted = []
    class Response:
        content = _one_page_pdf()
        def raise_for_status(self): pass
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"] == 180.0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, *, files):
            assert url == get_settings().gotenberg_url.rstrip("/") + "/forms/chromium/convert/html"
            html = files["files"][1].decode("utf-8")
            posted.append(html)
            return Response()
    monkeypatch.setattr(to_pdf_engine.httpx, "Client", FakeClient)
    result = tmp_path / "out.pdf"
    execute_staged_to_pdf_operation(
        "md-to-pdf", [source], result, {},
        original_name=source.name, content_type="text/markdown",
    )
    assert len(PdfReader(str(result), strict=True).pages) == 1
    assert posted and "<h1>หัวข้อภาษาไทย</h1>" in posted[0]
    assert "<table>" in posted[0] and "<strong>ตัวหนา</strong>" in posted[0]
    assert "<script>" not in posted[0] and "<img " not in posted[0]
    assert "<a " not in posted[0] and "<iframe" not in posted[0]
    assert "&lt;script&gt;" in posted[0] and "&lt;img" in posted[0]
    assert "Content-Security-Policy" in posted[0]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("payload", [
    "<iframe src='http://169.254.169.254/latest/meta-data/'>",
    "<svg onload=alert(1)>",
    "[x](javascript:alert(1))",
    "![img](file:///etc/passwd)",
    "<script>fetch('http://127.0.0.1/')</script>",
    "<a href='http://localhost'>link</a>",
])
def test_markdown_no_executable_links_images_or_resource_fetches(
    monkeypatch, tmp_path, payload
):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    file = tmp_path / "input.md"
    file.write_text("# Test\n" + payload + "\n", encoding="utf-8")
    fragments = []
    monkeypatch.setattr(to_pdf_engine, "_html_to_pdf",
                        lambda html, target: fragments.append(html))
    to_pdf_engine.markdown_to_pdf(file, tmp_path / "test.pdf")
    assert len(fragments) == 1
    fragment = fragments[0].lower()
    for active in ("<img ", "<script", "<iframe", "<svg", "<a ", "<object"):
        assert active not in fragment


@pytest.mark.parametrize("value", ["", "  \n  ", "\x00", "\ufffd" * 200001])
def test_markdown_rejects_empty_control_and_oversized(monkeypatch, tmp_path, value):
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    source = tmp_path / "text.md"
    source.write_text(value, encoding="utf-8")
    with pytest.raises(ValueError):
        to_pdf_engine.markdown_to_pdf(source, tmp_path / "out.pdf")
    assert not (tmp_path / "out.pdf").exists()


def test_markdown_source_is_immutable_and_disabled_by_default(monkeypatch, tmp_path):
    source = tmp_path / "safe.md"
    source.write_text("# ภาษาไทย\n\n- หนึ่ง\n- สอง", encoding="utf-8")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="differ"):
        to_pdf_engine.markdown_to_pdf(source, source)
    assert source.read_bytes() == before
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_to_pdf_operation(
            "md-to-pdf", [source], tmp_path / "out.pdf", {},
            original_name=source.name, content_type="text/markdown",
        )
    with pytest.raises(Exception):
        validate_uploaded_file(source, source.name)


def test_no_upstream_fetch_directives_in_markdown_renderer_configuration():
    text = "![photo](https://example.com/p.png) [link](https://example.com)"
    renderer = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
    renderer.disable(["link", "autolink", "image"])
    html = renderer.render(text)
    assert "<img" not in html and "<a " not in html
