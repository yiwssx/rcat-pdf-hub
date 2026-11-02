"""CHM helper-to-worker second trust boundary regressions (not run here)."""
from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from app.services.chm_html_boundary import validate_chm_html_fragment


def _png_data() -> str:
    picture = Image.new("RGBA", (3, 2), (75, 140, 130, 100))
    try:
        sink = BytesIO()
        picture.save(sink, format="PNG")
        return base64.b64encode(sink.getvalue()).decode("ascii")
    finally:
        picture.close()


def test_chm_safe_chapter_anchors_and_embedded_png():
    encoded = _png_data()
    source = (
        '<section class="chm-chapter" id="chm-topic-1">'
        '<h2>สารบัญ</h2><p><a href="#chm-topic-2">บทที่ 2</a></p></section>'
        '<section class="chm-chapter" id="chm-topic-2">'
        '<h2>เนื้อหา</h2><img class="book-image" '
        'src="data:image/png;base64,' + encoded + '" alt=""></section>'
    )
    html = validate_chm_html_fragment(source)
    assert "สารบัญ" in html and "บทที่ 2" in html
    assert '<a href="#chm-topic-2">' in html
    assert encoded in html
    assert html.count('<section class="chm-chapter"') == 2


@pytest.mark.parametrize("html", [
    '<section class="chm-chapter" id="chm-topic-1"><script>evil()</script></section>',
    '<section class="chm-chapter" id="chm-topic-1"><img src="https://site.test/a.png"></section>',
    '<section class="chm-chapter" id="chm-topic-1"><a href="file:///etc/passwd">file</a></section>',
    '<section class="chm-chapter" id="chm-topic-1"><a href="#chm-topic-9">missing</a></section>',
    '<section class="chm-chapter" id="chm-topic-1"><p onclick="bad()">X</p></section>',
    '<section class="chm-chapter" id="chm-topic-1"><style>@import url(a)</style></section>',
    '<section class="chm-chapter" id="chm-topic-1"><p>unclosed</section>',
    '<section class="chm-chapter" id="chm-topic-1"><img class="book-image" src="data:text/html;base64,WA==" alt=""></section>',
    '<section class="chm-chapter" id="chm-topic-1"><iframe src="https://site.test"></iframe></section>',
    '<section class="chm-chapter" id="chm-topic-1"><p>Duplicate</p></section>' +
    '<section class="chm-chapter" id="chm-topic-1"><p>Second</p></section>',
])
def test_chm_rejects_unsafe_structures(html):
    with pytest.raises(ValueError):
        validate_chm_html_fragment(html)
