"""M05 private model translation has true page input and fail-closed IO."""
from hashlib import sha256

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_private_translation import (
    _translate_local, translate_pdf_text, validate_languages,
)


def sample(tmp_path):
    source = tmp_path / "source.pdf"
    doc = canvas.Canvas(str(source))
    doc.drawString(40, 730, "Welcome to the agriculture college.")
    doc.showPage()
    doc.drawString(40, 730, "The irrigation system monitors water temperature.")
    doc.save()
    return source


def test_pdf_text_is_submitted_to_internal_model_and_written_by_page(tmp_path):
    src = sample(tmp_path)
    hash_before = sha256(src.read_bytes()).hexdigest()
    calls = []

    def real_provider(text, source, target):
        calls.append((text, source, target))
        return "แปลจริง: " + text

    out = tmp_path / "translated.txt"
    translate_pdf_text(src, out, source_language="en", target_language="th",
                       translator=real_provider)
    text = out.read_text("utf-8")
    assert len(calls) == 2
    assert "Welcome" in calls[0][0]
    assert "irrigation" in calls[1][0]
    assert all(c[1:] == ("en", "th") for c in calls)
    assert "[Page 1]" in text and "[Page 2]" in text
    assert "แปลจริง:" in text and "no original PDF layout" in text
    assert sha256(src.read_bytes()).hexdigest() == hash_before


@pytest.mark.parametrize("source,target", [
    ("th", "th"), ("en", "en"), ("auto", "th"), ("th", "fr"),
    (None, "en"), (0, "th"),
])
def test_invalid_language_pairs_rejected(source, target):
    with pytest.raises(ValueError):
        validate_languages(source, target)


def test_failure_never_leaves_fake_artifact(tmp_path):
    source = sample(tmp_path)
    dest = tmp_path / "result.txt"

    def unavailable(*args):
        raise ValueError("Internal translation model unavailable")

    with pytest.raises(ValueError, match="unavailable"):
        translate_pdf_text(source, dest, source_language="en", target_language="th",
                           translator=unavailable)
    assert not dest.exists()
    with pytest.raises(ValueError, match="response invalid"):
        translate_pdf_text(source, dest, source_language="en", target_language="th",
                           translator=lambda *args: "")
    assert not dest.exists()


def test_rejects_encrypted_pdf_and_existing_output(tmp_path):
    src = sample(tmp_path)
    out = tmp_path / "existing.txt"
    out.write_text("KEEP", encoding="utf-8")
    with pytest.raises(ValueError, match="distinct"):
        translate_pdf_text(src, out, source_language="en", target_language="th",
                           translator=lambda text, *_: text)
    assert out.read_text() == "KEEP"
    with pytest.raises(ValueError, match="distinct"):
        translate_pdf_text(src, src, source_language="en", target_language="th",
                           translator=lambda text, *_: text)
    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    for page in PdfReader(str(src)).pages:
        writer.add_page(page)
    writer.encrypt("secret")
    with encrypted.open("wb") as stream:
        writer.write(stream)
    with pytest.raises(ValueError, match="Encrypted"):
        translate_pdf_text(encrypted, tmp_path / "never.txt",
                           source_language="en", target_language="th",
                           translator=lambda text, *_: text)


def test_scanned_page_and_oversized_source_refused(tmp_path):
    blank = tmp_path / "blank.pdf"
    doc = canvas.Canvas(str(blank)); doc.showPage(); doc.save()
    with pytest.raises(ValueError, match="selectable text"):
        translate_pdf_text(blank, tmp_path / "empty.txt", source_language="en",
                           target_language="th", translator=lambda *_: "translated")
    from app.services.pdf_private_translation import MAX_SOURCE_BYTES
    large = tmp_path / "oversize.pdf"
    with large.open("wb") as handle:
        handle.write(b"%PDF-")
        handle.seek(MAX_SOURCE_BYTES)
        handle.write(b"X")
    with pytest.raises(ValueError, match="budget"):
        translate_pdf_text(large, tmp_path / "large.txt", source_language="en",
                           target_language="th", translator=lambda *_: "translated")


def test_model_transport_is_internal_proxy_free_and_nonredirecting(monkeypatch):
    import app.services.pdf_private_translation as service
    seen = {}
    class FakeResponse:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def iter_bytes(self):
            yield b'{"translatedText":"'
            yield "สวัสดี".encode("utf-8")
            yield b'"}'
    class FakeClient:
        def __init__(self, **kwargs): seen.update(kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def stream(self, method, path, *, json, headers):
            seen.update(method=method, path=path, payload=json)
            return FakeResponse()
    monkeypatch.setattr(service.httpx, "Client", FakeClient)
    assert _translate_local("Hello", "en", "th") == "สวัสดี"
    assert seen["base_url"] == "http://pdf-translate:5000"
    assert seen["trust_env"] is False
    assert seen["follow_redirects"] is False
    assert seen["payload"] == {"q": "Hello", "source": "en", "target": "th", "format": "text"}


def test_queue_gate_off_by_default(monkeypatch):
    from app import queue
    original = queue.settings
    monkeypatch.setattr(queue, "settings", original.model_copy(update={
        "pdf_translation_tools_enabled": False,
    }))
    with pytest.raises(ValueError, match="Unsupported"):
        queue.queue_class_for_operation("translate-pdf-text")
    monkeypatch.setattr(queue, "settings", original.model_copy(update={
        "pdf_translation_tools_enabled": True,
    }))
    assert queue.queue_class_for_operation("translate-pdf-text") == "heavy"
