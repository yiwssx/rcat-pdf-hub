"""M05 translated PDF: real PDF bytes, escaped HTML and fail-closed render."""
from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import pdf_translated_document as document


def _pdf(*lines):
    out = BytesIO()
    document = canvas.Canvas(out)
    for text in lines:
        document.drawString(50, 740, text)
        document.showPage()
    document.save()
    return out.getvalue()


def _source(tmp_path):
    src = tmp_path / "english.pdf"
    src.write_bytes(_pdf("Agriculture students use sensors.", "The teacher explains IoT."))
    return src


def test_real_translated_pdf_content_and_safe_html(tmp_path):
    source = _source(tmp_path)
    before = sha256(source.read_bytes()).digest()
    dest = tmp_path / "translated.pdf"
    calls = []
    html = []

    def translate(text, source_lang, target_lang):
        calls.append((text, source_lang, target_lang))
        return "สวัสดี & <script>alert(1)</script>"

    def renderer(content):
        html.append(content.decode("utf-8"))
        return _pdf("Translated PDF page one", "Translated PDF page two")

    document.translate_pdf_document(
        source, dest, source_language="en", target_language="th",
        translator=translate, renderer=renderer,
    )
    output = PdfReader(str(dest), strict=True)
    assert len(output.pages) == 2
    assert "Translated PDF page one" in (output.pages[0].extract_text() or "")
    assert len(calls) == 2
    assert all(pair[1:] == ("en", "th") for pair in calls)
    assert "students" in calls[0][0] and "teacher" in calls[1][0]
    assert len(html) == 1 and "&lt;script&gt;" in html[0]
    assert "<script>alert(1)</script>" not in html[0]
    assert "Noto Sans Thai" in html[0]
    assert "Translation of source page 1" in html[0]
    assert "Translation of source page 2" in html[0]
    assert sha256(source.read_bytes()).digest() == before


@pytest.mark.parametrize("invalid", ["", " ", None])
def test_empty_model_result_never_writes_pdf(tmp_path, invalid):
    src = _source(tmp_path)
    dst = tmp_path / "missing.pdf"
    with pytest.raises(ValueError, match="response invalid"):
        document.translate_pdf_document(
            src, dst, source_language="en", target_language="th",
            translator=lambda *_: invalid, renderer=lambda *_: _pdf("UNREACHABLE"),
        )
    assert not dst.exists()


def test_bad_render_and_existing_dest_fail_closed(tmp_path):
    source = _source(tmp_path)
    dst = tmp_path / "missing.pdf"
    with pytest.raises(ValueError, match="invalid PDF"):
        document.translate_pdf_document(
            source, dst, source_language="en", target_language="th",
            translator=lambda text, *_: text, renderer=lambda *_: b"Not a PDF",
        )
    assert not dst.exists()
    dst.write_bytes(b"KEEP")
    with pytest.raises(ValueError, match="distinct"):
        document.translate_pdf_document(
            source, dst, source_language="en", target_language="th",
            translator=lambda text, *_: text, renderer=lambda *_: _pdf("Rendered"),
        )
    assert dst.read_bytes() == b"KEEP"


def test_local_pdf_renderer_no_proxy_redirect_or_user_control(monkeypatch):
    pdf = _pdf("Internal renderer output")
    seen = {}

    class Response:
        status_code = 200
        headers = {"content-type": "application/pdf"}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def iter_bytes(self):
            yield pdf[:100]
            yield pdf[100:]

    class FakeClient:
        def __init__(self, **kwargs): seen.update(kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def stream(self, method, path, **kwargs):
            seen.update(method=method, path=path, form=kwargs)
            return Response()

    monkeypatch.setattr(document.httpx, "Client", FakeClient)
    html = document._html_document(["สวัสดี"], "en", "th")
    assert document._render_local_pdf(html) == pdf
    assert seen["base_url"] == "http://gotenberg:3000"
    assert seen["trust_env"] is False and seen["follow_redirects"] is False
    assert seen["path"] == "/forms/chromium/convert/html"
    assert seen["form"]["files"]["files"][0] == "index.html"


def test_bad_renderer_status_refused(monkeypatch):
    class Response:
        status_code = 302
        headers = {"content-type": "text/html"}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def iter_bytes(self): yield b"redirect"

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def stream(self, *args, **kwargs): return Response()

    monkeypatch.setattr(document.httpx, "Client", Client)
    with pytest.raises(ValueError, match="unavailable"):
        document._render_local_pdf(document._html_document(["Safe text"], "en", "th"))


def test_pdf_job_contract_and_separate_flag_gated_rq(monkeypatch):
    from app import queue, worker_tasks
    assert worker_tasks._output_spec_for_job("translate-pdf-document") == (
        ".pdf", "application/pdf",
    )
    assert worker_tasks._output_spec_for_job("translate-pdf-text") == (
        ".txt", "text/plain; charset=utf-8",
    )
    initial = queue.settings
    monkeypatch.setattr(queue, "settings", initial.model_copy(update={
        "pdf_translation_tools_enabled": False,
    }))
    with pytest.raises(ValueError, match="Unsupported"):
        queue.queue_class_for_operation("translate-pdf-document")
    monkeypatch.setattr(queue, "settings", initial.model_copy(update={
        "pdf_translation_tools_enabled": True,
    }))
    assert queue.queue_class_for_operation("translate-pdf-document") == "heavy"



def test_bilingual_pdf_review_preserves_exact_extracted_source_and_translation(tmp_path):
    source = _source(tmp_path)
    digest = sha256(source.read_bytes()).digest()
    output = tmp_path / "bilingual.pdf"
    rendered_html = []
    model_calls = []

    def translate(text, source_lang, target_lang):
        model_calls.append((text, source_lang, target_lang))
        return "คำแปล & <script>unsafe()</script>"

    def render(payload):
        rendered_html.append(payload.decode("utf-8"))
        return _pdf("Bilingual page one", "Bilingual page two")

    document.translate_pdf_document(
        source, output, source_language="en", target_language="th",
        translator=translate, renderer=render, layout="bilingual",
    )
    result = PdfReader(str(output), strict=True)
    assert len(result.pages) == 2
    assert model_calls and len(model_calls) == 2
    html = rendered_html[0]
    assert html.count('class="m05-source"') == 2
    assert html.count('class="m05-translated"') == 2
    assert html.index("Agriculture students use sensors.") < html.index("คำแปล")
    assert html.index("The teacher explains IoT.") < html.rindex("คำแปล")
    assert "&lt;script&gt;unsafe()&lt;/script&gt;" in html
    assert "<script>unsafe()</script>" not in html
    assert "Translation of source page 1" in html
    assert "Translation of source page 2" in html
    assert sha256(source.read_bytes()).digest() == digest


def test_bilingual_source_and_model_text_are_both_escaped():
    html = document._html_document(
        ["แปลภาษา & <script>bad()</script>"], "en", "th",
        source_pages=['source & <img src="https://example.com/a" onerror="run()">'],
    ).decode("utf-8")
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "&lt;img src=&quot;https://example.com/a&quot;" in html
    assert '<img src="https://example.com/a"' not in html
    assert 'onerror="run()"' not in html


@pytest.mark.parametrize("invalid", [
    "unknown", "", "BILINGUAL", True, None,
])
def test_m05_pdf_rejects_invalid_layout_before_translation(tmp_path, invalid):
    source = _source(tmp_path)
    target = tmp_path / "invalid-layout.pdf"
    calls = []
    with pytest.raises(ValueError, match="layout"):
        document.translate_pdf_document(
            source, target, source_language="en", target_language="th",
            translator=lambda *args: calls.append(args) or "not reached",
            renderer=lambda *_: _pdf("not reached"), layout=invalid,
        )
    assert calls == [] and not target.exists()


@pytest.mark.parametrize("source_pages", [
    [],
    ["only first"],
    ["valid first", " "],
    ["valid first", "a" * 3001],
])
def test_bilingual_pdf_requires_usable_page_aligned_source(source_pages):
    with pytest.raises(ValueError, match="bilingual"):
        document._html_document(["first translated", "second translated"],
                                "en", "th", source_pages=source_pages)


def test_m05_request_schema_rejects_unapproved_bilingual_modes():
    from pydantic import ValidationError
    from app.routers.pdf_private_translation import TranslatePdfRequest

    payload = dict(file_id="a-source-file", source_language="en", target_language="th")
    assert TranslatePdfRequest(**payload).layout is None
    assert TranslatePdfRequest(**payload, layout="bilingual").layout == "bilingual"
    with pytest.raises(ValidationError):
        TranslatePdfRequest(**payload, layout="external")
    with pytest.raises(ValidationError):
        TranslatePdfRequest(**payload, unexpected="unsafe")
