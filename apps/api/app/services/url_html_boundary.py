"""Second independent HTML trust boundary before Gotenberg/Chromium.

The URL fetcher is exposed to untrusted web content; a compromised sidecar
could still return HMAC-authenticated HTML. The privileged PDF worker MUST NOT
pass that directly into Chromium. This verifier parses an exact, attribute-
free structural subset and rebuilds every text node via html.escape.

No JavaScript, CSS, images, links, protocol handlers, URLs, forms, SVG or
external resource attributes can enter the offline renderer through T33.
"""
from __future__ import annotations

from html import escape
from html.parser import HTMLParser

ALLOWED = frozenset({
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section",
    "article", "span", "strong", "em", "b", "i", "u", "pre",
    "code", "blockquote", "ul", "ol", "li", "table", "thead",
    "tbody", "tr", "td", "th", "br", "hr",
})
VOID = frozenset({"br", "hr"})
MAX_TAGS = 20_000
MAX_DEPTH = 128
MAX_TEXT = 240_000
MAX_MARKUP_BYTES = 3_000_000


class _StrictOfflineHtml(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.count = 0
        self.text_chars = 0
        self.printable = False

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > MAX_TAGS:
            raise ValueError("URL HTML contains too many elements")
        if tag not in ALLOWED or attrs:
            raise ValueError("URL HTML contains an active or attributed element")
        self.parts.append("<" + tag + ">")
        if tag not in VOID:
            self.stack.append(tag)
            if len(self.stack) > MAX_DEPTH:
                raise ValueError("URL HTML nesting exceeds limit")

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID or attrs:
            raise ValueError("URL HTML contains unexpected self-closing element")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack or self.stack[-1] != tag:
            raise ValueError("URL HTML tag boundaries do not match")
        self.stack.pop()
        self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if not data:
            return
        self.text_chars += len(data)
        if self.text_chars > MAX_TEXT:
            raise ValueError("URL HTML printable content exceeds limit")
        if data.strip():
            self.printable = True
        self.parts.append(escape(data, quote=True))

    def handle_comment(self, data):
        raise ValueError("URL HTML contains unsupported comments")

    def handle_decl(self, decl):
        raise ValueError("URL HTML contains document declarations")

    def handle_pi(self, data):
        raise ValueError("URL HTML contains processing instructions")

    def unknown_decl(self, data):
        raise ValueError("URL HTML contains an unsupported declaration")

    def complete(self) -> str:
        self.close()
        if self.stack:
            raise ValueError("URL HTML contains unclosed elements")
        if not self.printable:
            raise ValueError("URL HTML does not contain visible text")
        verified = "".join(self.parts)
        if len(verified.encode("utf-8")) > MAX_MARKUP_BYTES:
            raise ValueError("URL HTML exceeds renderer size limit")
        return verified


def validate_offline_url_html(html: str) -> str:
    """Rebuild an attribute-free rendering fragment without trusting a sidecar.

    Fail closed on every unsupported element/attribute, including data URLs,
    href, src, srcset, CSS, iframe, SVG, script and HTML base/meta changes.
    """
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_MARKUP_BYTES:
        raise ValueError("URL HTML payload is invalid or oversized")
    validator = _StrictOfflineHtml()
    validator.feed(html)
    return validator.complete()
