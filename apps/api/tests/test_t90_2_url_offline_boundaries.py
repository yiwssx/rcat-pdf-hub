"""T33 URL text importer security and offline-HTML deterministic regressions.

No Internet or Docker required. These tests do not certify the mandatory
host firewall, network graph, real DNS/TLS or print-source fidelity.
"""
from __future__ import annotations

import pytest

from app.services.url_fetch_core import (
    sanitize_fetched_html, validate_public_https_url,
)
from app.services.url_html_boundary import validate_offline_url_html


@pytest.mark.parametrize("bad_url", [
    "http://example.org/",
    "https://localhost/",
    "https://example.local/",
    "https://127.0.0.1/",
    "https://192.168.1.10/",
    "https://user:secret@example.org/",
    "https://example.org:8443/",
    "https://example.org/path?token=x",
    "https://example.org/path#frag",
    "https://example.org/%2fprivate",
    "https://example.org/\\server",
    "https://example.org/\r\nHost:x",
])
def test_url_rejects_nonpublic_or_ambiguous_authorities(bad_url):
    with pytest.raises(ValueError):
        validate_public_https_url(bad_url)


def test_unicode_path_is_encoded_only_at_remote_request_boundary():
    host, path = validate_public_https_url("https://example.org/บทเรียน/ทดสอบ")
    assert host == "example.org"
    assert path.startswith("/%E0%B8%9A")
    assert path.isascii()


def test_normal_html_head_and_void_tags_do_not_hide_body():
    transcript = sanitize_fetched_html(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<link href='https://evil.test/style.css' rel='stylesheet'>"
        "<title>ignored</title></head><body>"
        "<h1>วิทยาลัยเกษตร</h1><p>เนื้อหา</p><br>"
        "<script>fetch('https://evil.test')</script>"
        "</body></html>"
    )
    verified = validate_offline_url_html(transcript)
    assert "วิทยาลัยเกษตร" in verified and "เนื้อหา" in verified
    assert "<h1>" in verified
    assert "<script" not in verified
    assert "evil.test" not in verified
    assert "href" not in verified


@pytest.mark.parametrize("untrusted_html", [
    "<script>alert(1)</script>",
    '<img src="http://127.0.0.1/private">',
    '<a href="file:///etc/passwd">open</a>',
    '<p onclick="alert(1)">unsafe</p>',
    "<iframe src='https://example.org'></iframe>",
    "<svg><script>alert(1)</script></svg>",
    "<!-- unexpected comment --><p>text</p>",
    "<p>missing close",
    "<p><b>mismatched</p></b>",
    "<meta http-equiv='refresh' content='0;URL=http://x'>",
    "<p></p>",
])
def test_privileged_worker_rejects_active_or_malformed_html(untrusted_html):
    with pytest.raises(ValueError):
        validate_offline_url_html(untrusted_html)


def test_safe_html_is_rebuilt_from_escaped_text():
    safe = validate_offline_url_html(
        "<h1>PDF &amp; Thai</h1><p>ทดสอบ &lt;script&gt; as text</p>"
        "<table><tr><td>42</td></tr></table>"
    )
    assert "<h1>PDF &amp; Thai</h1>" in safe
    assert "&lt;script&gt;" in safe
    assert "<table><tr><td>42</td></tr></table>" in safe
    assert "<script>" not in safe
