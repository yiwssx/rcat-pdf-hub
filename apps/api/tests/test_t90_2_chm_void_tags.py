"""Regression: ordinary CHM HTML void tags do not suppress printable text.

Native chmlib is not needed: exercise the exact HTML sanitizer that will run
inside the restricted CHM reader process.
"""
from __future__ import annotations

import pytest

from app.services.to_pdf_chm_worker import _Chapter


@pytest.mark.parametrize("void_markup", [
    "<input type='hidden' value='ignored'>",
    "<meta charset='utf-8'>",
    "<link href='https://malicious.test/style.css' rel='stylesheet'>",
    "<source src='https://malicious.test/remote.webm'>",
    "<embed src='https://malicious.test/thing.swf'>",
    "<param name='movie' value='https://malicious.test/thing'>",
    "<track src='https://malicious.test/captions'>",
    "<area href='https://malicious.test'>",
    "<base href='https://malicious.test/'>",
    "<input type='hidden' value='ignored'/>",
])
def test_blocked_html5_void_does_not_hide_following_chapter(void_markup):
    chapter = _Chapter("chapters/topic.html", {}, lambda _target: "")
    chapter.feed("<h1>บทเรียน</h1>" + void_markup + "<p>เนื้อหาภาษาไทย</p>")
    actual = chapter.render()
    assert "<h1>บทเรียน</h1>" in actual
    assert "<p>เนื้อหาภาษาไทย</p>" in actual
    assert "malicious.test" not in actual


def test_nested_void_inside_blocked_head_does_not_leave_hidden_stack():
    chapter = _Chapter("topic.html", {}, lambda _target: "")
    chapter.feed(
        "<head><meta charset='utf-8'><link rel='stylesheet' href='http://x'>"
        "</head><p>ข้อความต้องปรากฏ</p>"
    )
    assert "<p>ข้อความต้องปรากฏ</p>" in chapter.render()


def test_nonvoid_script_text_is_never_printed():
    chapter = _Chapter("topic.html", {}, lambda _target: "")
    chapter.feed("<script>DROP_THIS</script><p>KEEP_THIS</p>")
    text = chapter.render()
    assert "DROP_THIS" not in text
    assert "KEEP_THIS" in text
