"""Read-only CHM/LZX archive inventory in a constrained helper subprocess.

No CHM member is ever extracted to disk. ctypes matches upstream chm_lib.h
(0.40a; LP64 struct offsets) and only reads normal file members. The parent
process imposes OS resource limits, timeout and an independent output cap.

This is deliberately NOT a released T30 endpoint: native parser security,
sandbox egress, unicode legacy corpora and rendered fidelity need acceptance.
"""
from __future__ import annotations

import base64
import ctypes as C
from html import escape
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

MAX_CHM_BYTES = 20 * 1024 * 1024
MAX_MEMBERS = 512
MAX_HTML_FILES = 80
MAX_HTML_BYTES = 1 * 1024 * 1024
MAX_TOTAL_HTML = 12 * 1024 * 1024
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_TOTAL_IMAGES = 8 * 1024 * 1024
MAX_IMAGES = 32
MAX_RENDER_CHARS = 250_000
MAX_HTML_OUTPUT_BYTES = 16 * 1024 * 1024
IMAGE_MIMES = {
    ".png": ("image/png", "PNG"),
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".webp": ("image/webp", "WEBP"),
    ".gif": ("image/gif", "GIF"),
}
BLOCKED_TAGS = frozenset({
    "script", "style", "iframe", "object", "embed", "frame", "frameset",
    "form", "input", "button", "select", "textarea", "audio", "video",
    "source", "canvas", "template", "head", "meta", "link", "base",
    "param", "track", "area",
})
# HTML5 void elements must never open an active-content suppression subtree:
# older CHM/HTML4 help files commonly put <input>/<meta>/<link> in content
# without a corresponding end tag. Otherwise every later chapter paragraph
# would silently disappear from the generated PDF.
VOID_BLOCKED_TAGS = frozenset({
    "input", "source", "embed", "meta", "link", "base", "param",
    "track", "area",
})
ALLOW_TAGS = frozenset({
    "p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5",
    "h6", "br", "pre", "code", "strong", "b", "em", "i", "u",
    "ul", "ol", "li", "blockquote", "table", "thead", "tbody",
    "tr", "td", "th", "hr", "small", "sup", "sub",
})
VOID_TAGS = frozenset({"br", "hr"})


class CHMUnit(C.Structure):
    _fields_ = [
        ("start", C.c_uint64),
        ("length", C.c_uint64),
        ("space", C.c_int),
        ("flags", C.c_int),
        ("path", C.c_char * 513),
    ]


def _safe_name(raw: str) -> str:
    name = raw.lstrip("/")
    if (not name or len(name) > 510 or name.startswith("/")
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in name)
            or "\\" in name or ":" in name or "%" in name
            or "#" in name or "?" in name
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("CHM member uses an unsafe or ambiguous name")
    return name


def _relative(base: str, href: str) -> str | None:
    target = urlsplit(href)
    if (target.scheme or target.netloc or target.query or not target.path
            or target.path.startswith("//")):
        return None
    # CHM may contain relative links of the form topic.html#subsection.
    raw = unquote(target.path).replace("\\", "/")
    if ":" in raw or "%" in raw:
        return None
    parts = [] if raw.startswith("/") else base.split("/")[:-1]
    for item in raw.lstrip("/").split("/"):
        if item in ("", "."):
            continue
        if item == "..":
            if not parts:
                return None
            parts.pop()
        else:
            try:
                _safe_name(item)
            except ValueError:
                return None
            parts.append(item)
    try:
        return _safe_name("/".join(parts))
    except ValueError:
        return None


def _decode_html(data: bytes) -> str:
    # CHM manuals may be cp1252, cp874 (Thai), Shift_JIS or GBK, not UTF-8.
    first = data[:4096].decode("ascii", errors="ignore").lower()
    found = re.search(r"charset\s*=\s*['\" ]?([a-z0-9_-]+)", first)
    alias = {"windows-874": "cp874", "tis-620": "cp874",
             "windows-1252": "cp1252", "iso-8859-1": "latin1",
             "shift_jis": "shift_jis", "gb2312": "gbk", "gbk": "gbk",
             "utf-8": "utf-8", "utf8": "utf-8"}
    charset = alias.get(found.group(1), None) if found else None
    if found and charset is None:
        raise ValueError("CHM HTML uses unsupported character encoding")
    if not charset:
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            # No declared encoding: refuse a potentially corrupted transcript.
            raise ValueError("CHM legacy HTML has no declared character encoding") from None
    return data.decode(charset, errors="strict")


class _TOC(HTMLParser):
    def __init__(self, toc_path: str):
        super().__init__(convert_charrefs=True)
        self.toc_path = toc_path
        self.order: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "param":
            return
        props = dict(attrs)
        if (props.get("name") or "").casefold() == "local":
            candidate = props.get("value") or ""
            # CHM toc references have a scheme variation; only local paths.
            candidate = candidate.split("::/", 1)[-1]
            resolved = _relative(self.toc_path, candidate)
            if resolved:
                self.order.append(resolved.casefold())


class _Chapter(HTMLParser):
    """Rebuild HTML with matching, identity-aware tags and local-only links.

    CHM HTML frequently contains malformed/misnested tags. A mismatched closing
    element must never pop an unrelated link or printable element and produce
    a plausible but structurally corrupted PDF. Skip active-content subtrees
    without interpreting their text as safe prose.
    """

    def __init__(self, chapter_path: str, anchors: dict[str, str], image_reader):
        super().__init__(convert_charrefs=True)
        self.chapter_path = chapter_path
        self.anchors = anchors
        self.image_reader = image_reader
        self.parts: list[str] = []
        self.hidden: list[str] = []
        self.opened: list[tuple[str, str]] = []
        self.text_chars = 0
        self.tag_count = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self.tag_count += 1
        if self.tag_count > 20_000:
            raise ValueError("CHM chapter HTML tag count exceeds limit")
        if len(self.opened) + len(self.hidden) > 128:
            raise ValueError("CHM chapter HTML nesting exceeds limit")
        if self.hidden:
            if tag in BLOCKED_TAGS and tag not in VOID_BLOCKED_TAGS:
                self.hidden.append(tag)
            return
        if tag in BLOCKED_TAGS:
            if tag not in VOID_BLOCKED_TAGS:
                self.hidden.append(tag)
            return
        props = dict(attrs)
        if tag == "img":
            resource = _relative(self.chapter_path, props.get("src") or "")
            if resource:
                image = self.image_reader(resource)
                if image:
                    self.parts.append(image)
            return
        if tag == "a":
            resource = _relative(self.chapter_path, props.get("href") or "")
            destination = self.anchors.get(resource.casefold()) if resource else None
            if destination:
                self.parts.append('<a href="#' + destination + '">')
                self.opened.append(("a", "a"))
            else:
                self.opened.append(("a", ""))
            return
        if tag in ALLOW_TAGS:
            # Retain legal container types instead of mapping nested divs
            # to invalid nested paragraphs.
            self.parts.append("<" + tag + ">")
            if tag not in VOID_TAGS:
                self.opened.append((tag, tag))

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in BLOCKED_TAGS:
            if tag in VOID_BLOCKED_TAGS:
                self.handle_starttag(tag, attrs)
                return
            raise ValueError("CHM active HTML self-closing tag is ambiguous")
        self.handle_starttag(tag, attrs)
        if tag in ALLOW_TAGS and tag not in VOID_TAGS or tag == "a":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in VOID_BLOCKED_TAGS:
            return
        if self.hidden:
            if tag in BLOCKED_TAGS:
                if self.hidden[-1] != tag:
                    raise ValueError("CHM active HTML subtree is misnested")
                self.hidden.pop()
            return
        if tag in BLOCKED_TAGS:
            raise ValueError("CHM active HTML closing tag unmatched")
        if tag not in ALLOW_TAGS and tag != "a":
            return
        if tag in VOID_TAGS:
            return
        match = next(
            (i for i in range(len(self.opened) - 1, -1, -1)
             if self.opened[i][0] == tag), None,
        )
        if match is None:
            # Unmatched closing safe HTML is common in legacy manuals.
            # It does NOT pop any unrelated tag/anchor.
            return
        while len(self.opened) > match:
            _, output_tag = self.opened.pop()
            if output_tag:
                self.parts.append("</" + output_tag + ">")

    def handle_data(self, data):
        if not self.hidden and data:
            self.text_chars += len(data)
            if self.text_chars > MAX_RENDER_CHARS:
                raise ValueError("CHM chapter text exceeds character limit")
            self.parts.append(escape(data))

    def render(self):
        self.close()
        if self.hidden:
            raise ValueError("CHM HTML has unterminated active content")
        while self.opened:
            _, output_tag = self.opened.pop()
            if output_tag:
                self.parts.append("</" + output_tag + ">")
        return "".join(self.parts)


def _read_chm(path: Path) -> str:
    size = path.stat().st_size
    if not 128 <= size <= MAX_CHM_BYTES:
        raise ValueError("CHM file-size limit invalid")
    with path.open("rb") as stream:
        if stream.read(4) != b"ITSF":
            raise ValueError("CHM ITSF signature is missing")
    library = C.CDLL("libchm.so.1")
    enum_callback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(CHMUnit), C.c_void_p)
    library.chm_open.argtypes = [C.c_char_p]
    library.chm_open.restype = C.c_void_p
    library.chm_close.argtypes = [C.c_void_p]
    library.chm_enumerate.argtypes = [C.c_void_p, C.c_int, enum_callback, C.c_void_p]
    library.chm_enumerate.restype = C.c_int
    library.chm_retrieve_object.argtypes = [
        C.c_void_p, C.POINTER(CHMUnit), C.POINTER(C.c_ubyte),
        C.c_uint64, C.c_int64,
    ]
    library.chm_retrieve_object.restype = C.c_int64

    handle = library.chm_open(bytes(path))
    if not handle:
        raise ValueError("Native CHM decoder cannot open archive")
    try:
        members: dict[str, CHMUnit] = {}
        html_paths: list[str] = []
        toc_paths: list[str] = []
        names_seen: set[str] = set()
        total_html = 0
        failure = []
        enumerated_count = 0

        @enum_callback
        def collect(_handle, unit_pointer, _context):
            nonlocal total_html, enumerated_count
            unit = unit_pointer.contents
            try:
                enumerated_count += 1
                if enumerated_count > MAX_MEMBERS:
                    raise ValueError("CHM archive member inventory exceeds limit")
                raw = bytes(unit.path).split(b"\0", 1)[0]
                if not raw:
                    raise ValueError("CHM member name is missing")
                # Genuine CHM archives contain internal /#SYSTEM, ::DataSpace,
                # /$FIftiMain and directory entries. These are not printable
                # files and must never be presented to Chromium. Select only
                # the already-allowlisted document/image suffixes first.
                # All selected printable paths still undergo exact strict
                # traversal/encoding/duplicate/size validation below.
                try:
                    decoded = raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise ValueError("CHM member name is not UTF-8") from exc
                suffix = Path(decoded).suffix.lower()
                if suffix not in {".html", ".htm", ".hhc", ".hhk", *IMAGE_MIMES}:
                    return 1
                name = _safe_name(decoded)
                folded = name.casefold()
                if folded in names_seen:
                    raise ValueError("CHM printable member names overlap")
                names_seen.add(folded)
                if unit.space not in (0, 1):
                    raise ValueError("CHM member uses unsupported storage")
                size_limit = MAX_IMAGE_BYTES if suffix in IMAGE_MIMES else MAX_HTML_BYTES
                if not 0 < unit.length <= size_limit:
                    raise ValueError("CHM content member exceeds byte limit")
                if suffix in {".html", ".htm", ".hhc", ".hhk"}:
                    total_html += unit.length
                    if total_html > MAX_TOTAL_HTML:
                        raise ValueError("CHM decoded HTML total exceeds limits")
                # Copy structure: the C pointer is only valid during callback.
                snapshot = CHMUnit()
                C.memmove(C.byref(snapshot), unit_pointer, C.sizeof(CHMUnit))
                members[folded] = snapshot
                if suffix in {".html", ".htm"}:
                    html_paths.append(name)
                elif suffix == ".hhc":
                    toc_paths.append(name)
                return 1  # CHM_ENUMERATOR_CONTINUE
            except Exception as exc:
                failure.append(str(exc))
                return 0  # CHM_ENUMERATOR_FAILURE

        # CHM_ENUMERATE_NORMAL | CHM_ENUMERATE_FILES = 1 | 8.
        enumerated = library.chm_enumerate(handle, 9, collect, None)
        if failure:
            raise ValueError(failure[0])
        if enumerated == 0:
            raise ValueError("CHM archive file enumeration failed")
        if not 1 <= len(html_paths) <= MAX_HTML_FILES:
            raise ValueError("CHM HTML page inventory missing or excessive")

        def retrieve(name: str) -> bytes:
            unit = members[name.casefold()]
            if unit.length > MAX_HTML_BYTES and Path(name).suffix.lower() not in IMAGE_MIMES:
                raise ValueError("CHM member read exceeds limit")
            size = int(unit.length)
            buffer = (C.c_ubyte * size)()
            received = library.chm_retrieve_object(handle, C.byref(unit), buffer, 0, size)
            if received != size:
                raise ValueError("CHM LZX member truncated or could not be decoded")
            return bytes(buffer)

        ordered = []
        for toc_path in sorted(toc_paths, key=str.casefold)[:2]:
            parsed = _TOC(toc_path)
            parsed.feed(_decode_html(retrieve(toc_path)))
            ordered.extend(parsed.order)
        normal = {name.casefold(): name for name in html_paths}
        selected: list[str] = []
        seen: set[str] = set()
        for name in [*ordered, *sorted(normal, key=str.casefold)]:
            key = name.casefold()
            if key in normal and key not in seen:
                selected.append(normal[key])
                seen.add(key)
        if not selected:
            raise ValueError("CHM has no printable HTML chapters")

        anchors = {name.casefold(): f"chm-topic-{i+1}" for i, name in enumerate(selected)}
        images_used: set[str] = set()
        total_images = 0
        rendered_chars = 0

        def render_image(resource: str) -> str:
            nonlocal total_images
            key = resource.casefold()
            unit = members.get(key)
            if unit is None or Path(resource).suffix.lower() not in IMAGE_MIMES:
                return ""  # Unsupported or missing member: do not fetch remote.
            if key not in images_used:
                total_images += unit.length
                images_used.add(key)
                if len(images_used) > MAX_IMAGES or total_images > MAX_TOTAL_IMAGES:
                    raise ValueError("CHM internal image inventory exceeds limits")
            payload = retrieve(resource)
            suffix = Path(resource).suffix.lower()
            mime, expected = IMAGE_MIMES[suffix]
            try:
                with Image.open(BytesIO(payload)) as picture:
                    w, h = picture.size
                    if (picture.format != expected or getattr(picture, "n_frames", 1) != 1
                            or not 0 < w * h <= 8_000_000):
                        raise ValueError("CHM image is unsupported or animated")
                    picture.load()
            except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
                raise ValueError("CHM embedded image invalid") from exc
            uri = "data:" + mime + ";base64," + base64.b64encode(payload).decode("ascii")
            return '<img class="book-image" src="' + uri + '" alt="">'

        chapters = []
        for name in selected:
            source = _decode_html(retrieve(name))
            renderer = _Chapter(name, anchors, render_image)
            renderer.feed(source)
            body = renderer.render()
            rendered_chars += renderer.text_chars
            if rendered_chars > MAX_RENDER_CHARS:
                raise ValueError("CHM total printable text exceeds limits")
            if body.strip():
                section_id = anchors[name.casefold()]
                label = escape(Path(name).stem[:150])
                chapters.append('<section class="chm-chapter" id="' + section_id +
                                '"><h2>' + label + '</h2>' + body + '</section>')
        if not chapters:
            raise ValueError("CHM rendered body contains no printable text")
        document = "".join(chapters)
        if len(document.encode("utf-8")) > MAX_HTML_OUTPUT_BYTES:
            raise ValueError("CHM rendered HTML exceeds output limit")
        return document
    finally:
        library.chm_close(handle)


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        document = _read_chm(Path(sys.argv[1]))
        sys.stdout.write(json.dumps({"html": document}, ensure_ascii=False))
        return 0
    except Exception as exc:
        sys.stderr.write((str(exc) or type(exc).__name__)[:300])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
