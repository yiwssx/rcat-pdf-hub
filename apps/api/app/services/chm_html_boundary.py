"""Independent trusted-worker HTML boundary for low-trust native CHM reader.

CHM reader runs untrusted compressed content via ctypes/libchm inside a network-
denied sandbox. A compromised reader might return valid JSON holding arbitrary
HTML. Worker MUST reconstruct and authorize the fragment before Chromium.

Allowed extra CHM features over URL transcripts: same-document anchors and
bounded, locally decoded inline image data. No network/file/script/CSS paths.
"""
from __future__ import annotations

import base64
import binascii
from html import escape
from html.parser import HTMLParser
from io import BytesIO
import re

from PIL import Image, UnidentifiedImageError

BASE_ELEMENTS = frozenset({
    "p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5",
    "h6", "br", "pre", "code", "strong", "b", "em", "i", "u",
    "ul", "ol", "li", "blockquote", "table", "thead", "tbody",
    "tr", "td", "th", "hr", "small", "sup", "sub",
})
VOID = frozenset({"br", "hr", "img"})
MAX_HTML_BYTES = 16 * 1024 * 1024
MAX_TAGS = 80_000
MAX_CHARS = 250_000
MAX_DEPTH = 128
MAX_IMAGES = 32
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024
MIME_FORMATS = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/gif": "GIF",
    "image/webp": "WEBP",
}
TOPIC = re.compile(r"chm-topic-[1-9][0-9]{0,3}\Z")
DATA_IMAGE = re.compile(r"data:(image/(?:png|jpeg|gif|webp));base64,([A-Za-z0-9+/]+={0,2})\Z")


class _CHMFragment(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.topic_ids: set[str] = set()
        self.links: set[str] = set()
        self.tags = 0
        self.chars = 0
        self.images = 0
        self.image_bytes = 0
        self.printable = False

    def handle_starttag(self, tag, attrs):
        self.tags += 1
        if self.tags > MAX_TAGS or len(self.stack) > MAX_DEPTH:
            raise ValueError("CHM fragment complexity exceeds limit")
        if tag not in BASE_ELEMENTS | {"a", "img"}:
            raise ValueError("CHM reader returned prohibited HTML element")
        props = dict(attrs)
        if len(props) != len(attrs):
            raise ValueError("CHM fragment repeats HTML attributes")
        if tag == "section":
            if not props:
                self.parts.append("<section>")
            elif (set(props) == {"class", "id"}
                    and props["class"] == "chm-chapter"
                    and isinstance(props["id"], str)
                    and TOPIC.fullmatch(props["id"])
                    and props["id"] not in self.topic_ids):
                topic = props["id"]
                self.topic_ids.add(topic)
                self.parts.append('<section class="chm-chapter" id="' + topic + '">')
            else:
                raise ValueError("CHM section contains unsupported attributes")
        elif tag == "a":
            if (set(props) != {"href"} or not isinstance(props["href"], str)
                    or not props["href"].startswith("#")
                    or not TOPIC.fullmatch(props["href"][1:])):
                raise ValueError("CHM link is not a bounded internal topic")
            topic = props["href"][1:]
            self.links.add(topic)
            self.parts.append('<a href="#' + topic + '">')
        elif tag == "img":
            if (set(props) != {"class", "src", "alt"}
                    or props["class"] != "book-image" or props["alt"] != ""
                    or not isinstance(props["src"], str)):
                raise ValueError("CHM illustration attributes are unsafe")
            image = DATA_IMAGE.fullmatch(props["src"])
            if image is None:
                raise ValueError("CHM illustration may only embed a local data URI")
            mime, encoded = image.groups()
            if len(encoded) > (MAX_IMAGE_BYTES * 4 + 2) // 3 + 8:
                raise ValueError("CHM illustration base64 exceeds limit")
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError("CHM illustration base64 is invalid") from exc
            self.images += 1
            self.image_bytes += len(decoded)
            if (self.images > MAX_IMAGES or not 0 < len(decoded) <= MAX_IMAGE_BYTES
                    or self.image_bytes > MAX_TOTAL_IMAGE_BYTES):
                raise ValueError("CHM illustration inventory exceeds limits")
            try:
                with Image.open(BytesIO(decoded)) as picture:
                    if (picture.format != MIME_FORMATS[mime]
                            or getattr(picture, "n_frames", 1) != 1
                            or not 0 < picture.width * picture.height <= 8_000_000):
                        raise ValueError("CHM image type, frame count or dimensions invalid")
                    picture.verify()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError("CHM illustration is corrupt") from exc
            # Construct a fixed trusted attribute schema; no remote resources.
            self.parts.append('<img class="book-image" src="data:' + mime
                              + ';base64,' + encoded + '" alt="">')
        else:
            if props:
                raise ValueError("CHM element contains unexpected attributes")
            self.parts.append("<" + tag + ">")
        if tag not in VOID:
            self.stack.append(tag)
            if len(self.stack) > MAX_DEPTH:
                raise ValueError("CHM HTML nesting exceeds supported limit")

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID:
            raise ValueError("CHM self-closing non-void element is unsafe")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack or self.stack[-1] != tag:
            raise ValueError("CHM reader returned mismatched HTML")
        self.stack.pop()
        self.parts.append("</" + tag + ">")

    def handle_data(self, data):
        if data:
            self.chars += len(data)
            if self.chars > MAX_CHARS:
                raise ValueError("CHM reader returned too much printable text")
            if data.strip():
                self.printable = True
            self.parts.append(escape(data))

    def handle_comment(self, data):
        raise ValueError("CHM fragment contains unexpected HTML comments")

    def handle_decl(self, decl):
        raise ValueError("CHM fragment contains document declarations")

    def handle_pi(self, data):
        raise ValueError("CHM fragment contains processing instructions")

    def unknown_decl(self, data):
        raise ValueError("CHM fragment contains unknown declarations")

    def finish(self) -> str:
        self.close()
        if self.stack or not self.printable:
            raise ValueError("CHM fragment is unclosed or has no printable text")
        if self.links - self.topic_ids:
            raise ValueError("CHM fragment references missing internal topics")
        verified = "".join(self.parts)
        if len(verified.encode("utf-8")) > MAX_HTML_BYTES:
            raise ValueError("CHM fragment output exceeds limits")
        return verified


def validate_chm_html_fragment(payload: str) -> str:
    if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("CHM reader output HTML is invalid or oversized")
    checker = _CHMFragment()
    checker.feed(payload)
    return checker.finish()
