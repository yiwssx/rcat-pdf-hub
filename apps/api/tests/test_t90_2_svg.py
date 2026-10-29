"""T90-2 T16 restricted SVG: source safety, safe vector markup, auth and PDF artifacts."""
from __future__ import annotations

import hashlib
from io import BytesIO

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services import to_pdf_engine
from app.services.to_pdf_svg import safe_svg_markup
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation


def _pdf_bytes():
    stream = BytesIO()
    c = canvas.Canvas(stream)
    c.drawString(35, 750, "RCAT SVG")
    c.showPage()
    c.save()
    return stream.getvalue()


def _sample_svg():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" '
        'viewBox="0 0 400 300">'
        '<g fill="#13ad90" opacity="0.8">'
        '<rect x="10" y="20" width="160" height="80"/>'
        '<circle cx="200" cy="80" r="40" stroke="black" stroke-width="3"/>'
        '<path d="M 10 180 L 180 200 Z" fill="blue"/>'
        '</g><text x="30" y="240" font-size="22" fill="#123456">'
        'วิทยาลัยเกษตร <tspan dx="4">ร้อยเอ็ด</tspan> &amp; PDF</text>'
        '</svg>'
    )


def test_safe_svg_geometry_and_thai_text_preserved_without_untrusted_css(tmp_path):
    source = tmp_path / "original.svg"
    source.write_text(_sample_svg(), encoding="utf-8")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    html = safe_svg_markup(source)
    assert "<svg " in html and 'viewBox="0 0 400 300"' in html
    assert "Noto Sans Thai" in html and "วิทยาลัยเกษตร" in html
    assert "ร้อยเอ็ด" in html and "&amp; PDF" in html
    assert "<path " in html and "<circle " in html
    for token in ("<script", "<style", "onload=", "href=", "<foreignObject", "url(", "font-face", "<image"):
        assert token not in html
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_svg_flagged_upload_to_pdf_binary_and_immutable(monkeypatch, tmp_path):
    source = tmp_path / "image.svg"
    source.write_text(_sample_svg(), encoding="utf-8")
    before = source.read_bytes()
    with pytest.raises(HTTPException) as disabled:
        validate_uploaded_file(source, source.name)
    assert disabled.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(source, source.name) == "image/svg+xml"
    markup = []

    class Reply:
        content = _pdf_bytes()

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["timeout"] == 180.0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, files):
            assert url.endswith("/forms/chromium/convert/html")
            assert files["files"][0] == "index.html"
            markup.append(files["files"][1].decode("utf-8"))
            return Reply()

    monkeypatch.setattr(to_pdf_engine.httpx, "Client", Client)
    output = tmp_path / "out.pdf"
    execute_staged_to_pdf_operation(
        "svg-to-pdf", [source], output, {},
        original_name=source.name, content_type="image/svg+xml",
    )
    assert len(PdfReader(str(output), strict=True).pages) == 1
    assert markup and 'Content-Security-Policy' in markup[0]
    assert "วิทยาลัยเกษตร" in markup[0]
    assert source.read_bytes() == before
    with pytest.raises(ValueError, match="persisted MIME"):
        checked_source("svg-to-pdf", source, name=source.name, mime="text/plain")
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_to_pdf_operation(
            "svg-to-pdf", [source], tmp_path / "no.pdf", {},
            original_name=source.name, content_type="image/svg+xml",
        )


@pytest.mark.parametrize("unsafe", [
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><image href="http://169.254.169.254/latest"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="30" height="30" onload="fetch(1)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="30" height="30" style="fill:url(http://127.0.0.1)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><body/></foreignObject></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><use href="#known"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="x"/></defs></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="30" height="30" fill="url(http://127.0.0.1/secret)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="30" height="30" filter="url(#shadow)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><text x="3" y="5" font-family="http://evil">Hi</text></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="999999999999999999999999" height="4"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="-10" height="40"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><g transform="translate(10)"><circle r="30"/></g></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect xmlns:evil="http://bad/" evil:data="yes" width="3"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><path d="javascript:alert(1)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><circle r="15"/><svg><circle r="2"/></svg></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1"/><a href="file:///etc/passwd"/></svg>',
    '<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"><text>&x;</text></svg>',
    '<?xml-stylesheet href="http://127.0.0.1/"?><svg xmlns="http://www.w3.org/2000/svg"><rect width="2"/></svg>',
])
def test_reject_all_unsafe_svg_markup_without_output(tmp_path, unsafe):
    path = tmp_path / "unsafe.svg"
    path.write_text(unsafe, encoding="utf-8")
    with pytest.raises(ValueError):
        safe_svg_markup(path)


@pytest.mark.parametrize("candidate", [
    "<html><div>Hello</div></html>",
    "not svg",
    '<svg><rect width="1" height="2" fill="#eeeeeeee"/></svg>',
    '<svg><circle cx="3" r="NaN"/></svg>',
    '<svg><polygon points="10,20 30"/></svg>',
    '<svg><rect width="30" height="10" opacity="1.5"/></svg>',
    '<svg><text x="5">hello<script>bad</script></text></svg>',
])
def test_reject_malformed_or_unsupported_svg_source(tmp_path, candidate):
    source = tmp_path / "bad.svg"
    source.write_text(candidate, encoding="utf-8")
    with pytest.raises(ValueError):
        safe_svg_markup(source)


def test_svg_node_depth_and_document_limits(tmp_path):
    path = tmp_path / "huge.svg"
    path.write_text("<svg>" + ("<g>" * 25) + "<rect width='1' height='1'/>"
                    + ("</g>" * 25) + "</svg>", encoding="utf-8")
    with pytest.raises(ValueError, match="depth"):
        safe_svg_markup(path)
    path.write_text("<svg>" + ("<rect width='1' height='1'/>" * 650) + "</svg>",
                    encoding="utf-8")
    with pytest.raises(ValueError, match="count"):
        safe_svg_markup(path)
    path.write_text("<svg>" + "<rect width='1' height='1'/>" + (" " * (3*1024*1024))
                    + "</svg>", encoding="utf-8")
    with pytest.raises(ValueError, match="2 MiB"):
        safe_svg_markup(path)


def test_svg_in_place_conversion_rejected_without_touching_source(tmp_path):
    source = tmp_path / "untouched.svg"
    source.write_text(_sample_svg(), encoding="utf-8")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="differ"):
        to_pdf_engine.svg_to_pdf(source, source)
    assert source.read_bytes() == before
