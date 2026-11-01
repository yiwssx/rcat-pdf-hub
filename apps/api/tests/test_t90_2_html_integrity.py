"""T90-2 HTML integrity: never claim successful PDF after truncated HTML.

Script/style/head HTML constructs are stripped, not executed. If their
boundaries are ambiguous, reject the document instead of silently discarding
printable text and emitting a valid-looking but incomplete PDF.
"""
import pytest

from app.services import to_pdf_engine


@pytest.mark.parametrize("html", [
    "<h1>Visible introduction</h1><script>alert(1)",
    "<p>Visible introduction</p><style>body{color:red}",
    "<p>Visible introduction</p><head>hidden",
    "<p>Visible introduction</p><script>secret</style><p>last page</p>",
    "<p>Visible introduction</p><script>secret</script></script><p>last page</p>",
    "<p>Visible introduction</p><style/><p>last page</p>",
    "<p>Visible introduction</p><head/><p>last page</p>",
    "<p>Visible introduction</p><script/><p>last page</p>",
])
def test_ambiguous_filtered_html_is_rejected_not_truncated(monkeypatch, tmp_path, html):
    source = tmp_path / "document.html"
    source.write_text(html, encoding="utf-8")
    output = tmp_path / "wrong.pdf"

    def should_not_render(*args):
        pytest.fail("An incomplete HTML document must never reach Gotenberg")

    monkeypatch.setattr(to_pdf_engine, "_html_to_pdf", should_not_render)
    with pytest.raises(ValueError, match="filtered element"):
        to_pdf_engine.html_to_pdf(source, output)
    assert not output.exists()


def test_well_formed_filtered_html_retains_printable_content(monkeypatch, tmp_path):
    source = tmp_path / "safe.html"
    source.write_text(
        "<head><style>body{background:url(http://127.0.0.1/secret)}</style></head>"
        "<h1>ต้นฉบับ</h1>"
        "<script>fetch('http://169.254.169.254/')</script>"
        "<p>ข้อความท้ายเอกสาร RCAT</p>",
        encoding="utf-8",
    )
    sent = []
    monkeypatch.setattr(
        to_pdf_engine, "_html_to_pdf", lambda markup, target: sent.append(markup)
    )
    to_pdf_engine.html_to_pdf(source, tmp_path / "safe.pdf")
    assert len(sent) == 1
    result = sent[0]
    assert "<h1>ต้นฉบับ</h1>" in result
    assert "<p>ข้อความท้ายเอกสาร RCAT</p>" in result
    assert "127.0.0.1" not in result
    assert "169.254.169.254" not in result


def test_supported_xhtml_selfclosing_text_tags_preserve_following_content(monkeypatch, tmp_path):
    source = tmp_path / "safe.html"
    source.write_text(
        "<h2>ต้นเรื่อง</h2><br/><p>ข้อความต่อท้าย</p><hr/><p>จบ</p>",
        encoding="utf-8",
    )
    seen = []
    monkeypatch.setattr(
        to_pdf_engine, "_html_to_pdf", lambda body, output: seen.append(body)
    )
    to_pdf_engine.html_to_pdf(source, tmp_path / "result.pdf")
    assert seen == [
        "<h2>ต้นเรื่อง</h2><br><p>ข้อความต่อท้าย</p><hr><p>จบ</p>"
    ]
