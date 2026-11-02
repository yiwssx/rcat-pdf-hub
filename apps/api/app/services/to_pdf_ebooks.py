"""T90-2 bounded FictionBook 2 and EPUB ebook readers with inline bitmap art.

Retains ordered textual chapters and declared embedded PNG/JPEG/WebP/GIF
images using validated, length-limited data URLs. Never fetches network,
executes script/CSS, extracts archives or follows external filesystem links.
Original ebook typography/CSS/pagination is not faithfully reconstructed.
"""
from __future__ import annotations

import base64
import binascii
from html import escape
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import zipfile

from PIL import Image, UnidentifiedImageError

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_BOOK_BYTES = 20 * 1024 * 1024
MAX_ZIP_ENTRIES = 256
MAX_ZIP_EXPANDED_BYTES = 30 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 8 * 1024 * 1024
MAX_BOOK_CHARS = 200_000
MAX_BOOK_NODES = 12000
MAX_CHAPTERS = 60
MAX_EMBEDDED_IMAGE_BYTES = 4 * 1024 * 1024
MAX_EMBEDDED_IMAGE_TOTAL = 12 * 1024 * 1024
MAX_EMBEDDED_IMAGES = 32
MAX_EMBEDDED_IMAGE_PIXELS = 8_000_000
MAX_RENDERED_HTML_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_MIMES = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
}


def _embedded_image_uri(payload: bytes, mime: str) -> str:
    """Decode and validate declared internal raster before browser rendering.

    The returned data URL cannot resolve to the network or local filesystem.
    Reject animations to avoid silently losing secondary frames, and enforce
    per-image decoded-pixel and encoded-byte caps.
    """
    if mime not in ALLOWED_IMAGE_MIMES or not 0 < len(payload) <= MAX_EMBEDDED_IMAGE_BYTES:
        raise ValueError("Unsupported or oversized embedded ebook image")
    try:
        with Image.open(BytesIO(payload)) as bitmap:
            w, h = bitmap.size
            if (bitmap.format != ALLOWED_IMAGE_MIMES[mime]
                    or getattr(bitmap, "n_frames", 1) != 1
                    or not 0 < w * h <= MAX_EMBEDDED_IMAGE_PIXELS
                    or max(w, h) > 10_000):
                raise ValueError("Embedded ebook image format, frames or geometry unsupported")
            bitmap.load()
    except (UnidentifiedImageError, OSError, EOFError, Image.DecompressionBombError) as exc:
        raise ValueError("Invalid embedded ebook image") from exc
    return "data:" + mime + ";base64," + base64.b64encode(payload).decode("ascii")


def _image_figure(uri: str) -> str:
    # Only an internally validated data: bitmap URI reaches this function.
    return '<figure class="book-image"><img alt="" src="' + uri + '"></figure>'


def _tag(node) -> str:
    return str(node.tag).rsplit("}", 1)[-1].lower()


def _xml(data: bytes):
    if len(data) > MAX_ZIP_MEMBER_BYTES:
        raise ValueError("Ebook XML member too large")
    try:
        return SafeET.fromstring(data)
    except (SafeET.ParseError, DefusedXmlException, UnicodeError, ValueError) as exc:
        raise ValueError("Invalid or unsafe ebook XML") from exc


def _nodes_within_limits(root) -> None:
    stack = [(root, 1)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_BOOK_NODES or depth > 64 or len(node.attrib) > 60:
            raise ValueError("Ebook XML complexity exceeds limits")
        stack.extend((child, depth + 1) for child in node)


def _plain_text(node) -> str:
    return " ".join("".join(node.itertext()).split())


# Discard non-print content and every descendant (including nested text).
# Untrusted ebook HTML is never copied as HTML: every output element and
# attribute is freshly constructed from a finite allowlist.
_NON_PRINT_TAGS = frozenset({
    "script", "style", "head", "template", "noscript", "iframe", "object",
    "embed", "canvas", "form", "input", "button", "select", "textarea",
    "audio", "video", "source", "track", "meta", "link",
})
_BLOCK_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "subtitle", "li", "pre",
    "v", "text-author", "cite", "dt", "dd",
})
_CONTAINER_TAGS = frozenset({
    "body", "section", "div", "article", "main", "nav", "header",
    "footer", "aside", "blockquote", "poem", "stanza", "epigraph",
    "title", "ul", "ol", "dl", "figure", "figcaption",
})


def _paragraphs(root, *, max_nodes: int = 12000, image_resolver=None) -> list[str]:
    """Reconstruct ordered textual/illustration blocks without duplicating text.

    XHTML/FB2 layout is reduced to deterministic headings, paragraphs,
    bounded tables, list items, verse and illustrations. Paragraphs containing
    inline images are split around the picture so the text before and after
    is never lost. Inline source styling and dangerous attributes are dropped.
    """
    if sum(1 for _ in root.iter()) > max_nodes:
        raise ValueError("Ebook chapter exceeds node count")
    parts: list[str] = []

    def image_markup(node) -> str:
        if image_resolver is None:
            raise ValueError("Embedded ebook images require a validated resolver")
        return image_resolver(node)

    def inline_tokens(node):
        """Return ordered text/image tokens; never return raw input markup."""
        result = []
        if node.text:
            result.append(("text", node.text))
        for child in node:
            kind = _tag(child)
            if kind in _NON_PRINT_TAGS:
                pass
            elif kind in {"image", "img"}:
                markup = image_markup(child)
                if markup:
                    result.append(("image", markup))
            elif kind == "svg":
                raise ValueError("SVG illustrations require a separate safe renderer")
            else:
                result.extend(inline_tokens(child))
            if child.tail:
                result.append(("text", child.tail))
        return result

    def write_text(tokens, *, tag="p", prefix=""):
        # Split around illustrations so an image cannot become an invalid
        # descendant of <p>, <h2>, or a printable list item.
        buffer: list[str] = [prefix] if prefix else []
        for kind, value in [*tokens, ("end", "")]:
            if kind == "text":
                buffer.append(value)
                continue
            rendered = " ".join("".join(buffer).split())
            if rendered:
                parts.append(f"<{tag}>" + escape(rendered) + f"</{tag}>")
            buffer = []
            if kind == "image":
                parts.append(value)

    def render_table(node):
        """Basic cells, rows and headings; no imported CSS or hyperlinks."""
        rows = [row for row in node.iter() if _tag(row) == "tr"]
        if not 1 <= len(rows) <= 500:
            raise ValueError("Ebook table has no printable rows or exceeds limits")
        parts.append("<table>")
        captions = [child for child in node if _tag(child) == "caption"]
        if len(captions) > 1:
            raise ValueError("Ebook table has ambiguous captions")
        if captions:
            parts.append("<caption>")
            for token_kind, value in inline_tokens(captions[0]):
                if token_kind == "image":
                    parts.append(value)
                else:
                    parts.append(escape(value))
            parts.append("</caption>")
        parts.append("<tbody>")
        for row in rows:
            cells = [child for child in row if _tag(child) in {"td", "th"}]
            if not 1 <= len(cells) <= 24:
                raise ValueError("Ebook table column count outside limits")
            parts.append("<tr>")
            for cell in cells:
                tag = "th" if _tag(cell) == "th" else "td"
                # Deliberately drop colspan, rowspan, styles and links rather
                # than propagating untrusted attributes into browser markup.
                parts.append("<" + tag + ">")
                cell_tokens = inline_tokens(cell)
                text_buf = []
                for token_kind, value in [*cell_tokens, ("end", "")]:
                    if token_kind == "text":
                        text_buf.append(value)
                    else:
                        value_text = " ".join("".join(text_buf).split())
                        if value_text:
                            parts.append(escape(value_text))
                        text_buf = []
                        if token_kind == "image":
                            parts.append(value)
                parts.append("</" + tag + ">")
            parts.append("</tr>")
        parts.append("</tbody></table>")

    def walk(node, *, heading=False, item_prefix=""):
        name = _tag(node)
        if name in _NON_PRINT_TAGS:
            return
        if name in {"image", "img"}:
            markup = image_markup(node)
            if markup:
                parts.append(markup)
            return
        if name == "svg":
            raise ValueError("SVG illustrations require a separate safe renderer")
        if name == "table":
            render_table(node)
            return
        if name == "empty-line":
            parts.append('<p class="book-spacer"></p>')
            return
        if name in _BLOCK_TAGS:
            if heading or name in {"h1", "h2", "subtitle"}:
                tag = "h2"
            elif name in {"h3", "h4", "h5", "h6"}:
                tag = "h3"
            elif name == "pre":
                tag = "pre"
            elif name == "v":
                tag = "p"
            else:
                tag = "p"
            write_text(inline_tokens(node), tag=tag, prefix=item_prefix)
            return

        if name in {"ul", "ol"}:
            counter = 0
            for child in node:
                if _tag(child) == "li":
                    counter += 1
                    prefix = f"{counter}. " if name == "ol" else "• "
                    walk(child, item_prefix=prefix)
                else:
                    walk(child)
            return

        if name == "blockquote":
            parts.append("<blockquote>")
        # EPUB <div> and FB2 <section>/<title> may contain direct text plus
        # nested printable blocks. Flush those direct runs at block
        # boundaries, never call itertext() on both parent and children.
        direct = [("text", node.text)] if node.text else []
        for child in node:
            kind = _tag(child)
            if kind in _NON_PRINT_TAGS:
                pass
            elif (kind in _BLOCK_TAGS or kind in _CONTAINER_TAGS
                  or kind in {"img", "image", "table", "svg", "empty-line"}):
                write_text(direct, tag="h2" if heading else "p")
                direct = []
                walk(child, heading=(name == "title"))
            else:
                direct.extend(inline_tokens(child))
            if child.tail:
                direct.append(("text", child.tail))
        write_text(direct, tag="h2" if heading else "p")
        if name == "blockquote":
            parts.append("</blockquote>")

    walk(root)
    return parts


def _bounded_html(parts: list[str], *, title: str = "") -> str:
    body = ("<h1>" + escape(title[:500]) + "</h1>") if title.strip() else ""
    body += "".join(parts)
    text_html_bytes = sum(len(item) for item in parts if not item.startswith("<figure "))
    if (not parts or text_html_bytes > MAX_BOOK_CHARS * 6
            or len(body.encode("utf-8")) > MAX_RENDERED_HTML_BYTES):
        raise ValueError("Ebook content absent or exceeds output bounds")
    return body


def fb2_to_safe_html(source: Path) -> str:
    """FictionBook2 ordered text and referenced, declared inline bitmaps."""
    if not 0 < source.stat().st_size <= MAX_BOOK_BYTES:
        raise ValueError("FB2 input exceeds staged limits")
    root = _xml(source.read_bytes())
    if _tag(root) != "fictionbook":
        raise ValueError("Not a FictionBook2 document")
    _nodes_within_limits(root)
    book_title = ""
    binaries = {}
    for node in root:
        if _tag(node) == "binary":
            identity = node.attrib.get("id", "")
            if not identity or identity in binaries:
                raise ValueError("FB2 embedded image ids are missing or duplicated")
            binaries[identity] = node
    for node in root.iter():
        if _tag(node) == "book-title":
            book_title = _plain_text(node)[:500]
            break

    count = 0
    total = 0

    def resolve_fb2_image(node) -> str:
        nonlocal count, total
        links = [v for k, v in node.attrib.items() if k == "href" or k.endswith("}href")]
        if len(links) != 1 or not links[0].startswith("#"):
            raise ValueError("FB2 image reference must be an internal identifier")
        target = binaries.get(links[0][1:])
        if target is None:
            raise ValueError("FB2 referenced image is absent")
        count += 1
        if count > MAX_EMBEDDED_IMAGES:
            raise ValueError("FB2 embedded image count exceeds limits")
        encoded = "".join("".join(target.itertext()).split())
        if not encoded or len(encoded) > (MAX_EMBEDDED_IMAGE_BYTES * 4 // 3 + 8):
            raise ValueError("FB2 embedded image is oversized")
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("FB2 image base64 is malformed") from exc
        total += len(payload)
        if total > MAX_EMBEDDED_IMAGE_TOTAL:
            raise ValueError("FB2 embedded image total exceeds limits")
        return _image_figure(_embedded_image_uri(payload, target.attrib.get("content-type", "")))

    blocks = []
    # The cover typically lives in <description><title-info><coverpage>
    # rather than <body>. Include it as the first printable illustration.
    for element in root.iter():
        if _tag(element) == "coverpage":
            blocks.extend(_paragraphs(element, image_resolver=resolve_fb2_image))
    for body in root:
        if _tag(body) == "body":
            blocks.extend(_paragraphs(body, image_resolver=resolve_fb2_image))
    if len(blocks) > 3000:
        raise ValueError("FictionBook paragraph count exceeds limits")
    return _bounded_html(blocks, title=book_title)


def _safe_member_path(name: str) -> str:
    if not name or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError("Unsafe EPUB entry path")
    if name.startswith("/") or "\\" in name or ":" in name:
        raise ValueError("Unsafe EPUB entry path")
    parts = name.rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Unsafe EPUB entry path")
    return name


def _member_href(opf_path: str, href: str) -> str:
    url = urlsplit(href)
    if url.scheme or url.netloc or url.query or url.fragment or not url.path:
        raise ValueError("Remote or ambiguous EPUB manifest reference")
    decoded = unquote(url.path)
    _safe_member_path(decoded)
    combined = str(PurePosixPath(opf_path).parent / decoded)
    return _safe_member_path(combined)


def _image_member_href(chapter_path: str, href: str) -> str:
    """Resolve normal EPUB ../Images links without escaping ZIP root.

    Existing OPF/spine manifest references remain strictly normalized. Only
    image references may walk upward inside the already-validated package.
    """
    url = urlsplit(href)
    if (url.scheme or url.netloc or url.query or url.fragment
            or not url.path or url.path.startswith("/")):
        raise ValueError("EPUB image contains an external or ambiguous path")
    raw_path = unquote(url.path)
    if "\\" in raw_path or ":" in raw_path or "%" in raw_path:
        raise ValueError("EPUB image reference path unsafe")
    parts = chapter_path.split("/")[:-1]
    for segment in raw_path.split("/"):
        if segment == "..":
            if not parts:
                raise ValueError("EPUB image escaped package root")
            parts.pop()
        elif segment == ".":
            continue
        else:
            _safe_member_path(segment)
            parts.append(segment)
    return _safe_member_path("/".join(parts))


def epub_to_safe_html(source: Path) -> str:
    """EPUB 2/3 ordered text spine with local, manifest-declared bitmap images."""
    if not 0 < source.stat().st_size <= MAX_BOOK_BYTES:
        raise ValueError("EPUB input exceeds staged limits")
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if not 3 <= len(infos) <= MAX_ZIP_ENTRIES:
                raise ValueError("EPUB archive entry count exceeds limits")
            members = {}
            total = 0
            for info in infos:
                name = _safe_member_path(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if (name.casefold() in members
                        or mode not in (0, 0o100000, 0o040000)
                        or (mode == 0o040000 and not info.is_dir())
                        or info.flag_bits & 1
                        or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                        or info.file_size > MAX_ZIP_MEMBER_BYTES
                        or info.file_size > (info.compress_size + 1024) * 200):
                    raise ValueError("Unsafe or duplicated EPUB entry")
                total += info.file_size
                if total > MAX_ZIP_EXPANDED_BYTES:
                    raise ValueError("EPUB archive expansion exceeds limits")
                members[name.casefold()] = info
            if "meta-inf/encryption.xml" in members:
                raise ValueError("Encrypted EPUB content is not supported")

            def read_member(name: str) -> bytes:
                member = members.get(_safe_member_path(name).casefold())
                if member is None or member.is_dir():
                    raise ValueError("Required EPUB resource missing")
                payload = archive.read(member)
                if len(payload) != member.file_size:
                    raise ValueError("EPUB member size mismatch")
                return payload

            if read_member("mimetype") != b"application/epub+zip":
                raise ValueError("EPUB media type mismatch")
            container = _xml(read_member("META-INF/container.xml"))
            _nodes_within_limits(container)
            rootfiles = [n for n in container.iter() if _tag(n) == "rootfile"]
            if len(rootfiles) != 1:
                raise ValueError("EPUB must declare exactly one OPF package")
            opf_path = _safe_member_path(rootfiles[0].attrib.get("full-path", ""))
            if not opf_path.lower().endswith(".opf"):
                raise ValueError("EPUB OPF file type mismatch")
            opf = _xml(read_member(opf_path))
            _nodes_within_limits(opf)
            if _tag(opf) != "package":
                raise ValueError("Invalid EPUB package document")
            title = next((_plain_text(x) for x in opf.iter() if _tag(x) == "title"), "")
            manifest = {}
            bitmap_parts = {}
            cover_ids: set[str] = set()
            for node in opf.iter():
                if _tag(node) == "item":
                    identity = node.attrib.get("id", "")
                    if not identity or identity in manifest:
                        raise ValueError("Duplicate or empty EPUB manifest id")
                    mime = node.attrib.get("media-type", "")
                    if mime == "application/xhtml+xml" or mime in ALLOWED_IMAGE_MIMES:
                        target = _member_href(opf_path, node.attrib.get("href", ""))
                        manifest[identity] = (mime, target)
                        if mime in ALLOWED_IMAGE_MIMES:
                            if target.casefold() in bitmap_parts:
                                raise ValueError("Duplicated EPUB image resource")
                            bitmap_parts[target.casefold()] = mime
                    else:
                        manifest[identity] = (mime, "")
                    # EPUB3: properties="cover-image" can contain several
                    # space-separated feature tokens.
                    if "cover-image" in node.attrib.get("properties", "").split():
                        cover_ids.add(identity)
                elif _tag(node) == "meta" and node.attrib.get("name") == "cover":
                    # EPUB2: metadata points at an image manifest ID, not
                    # an arbitrary path or URL.
                    identity = node.attrib.get("content", "")
                    if not identity:
                        raise ValueError("EPUB2 cover manifest ID is missing")
                    cover_ids.add(identity)
            if len(cover_ids) > 1:
                raise ValueError("EPUB contains conflicting cover declarations")
            cover_id = next(iter(cover_ids)) if cover_ids else ""
            refs = [n.attrib.get("idref", "") for n in opf.iter()
                    if _tag(n) == "itemref"]
            if not 1 <= len(refs) <= MAX_CHAPTERS:
                raise ValueError("EPUB text spine length outside limits")
            parts = []
            image_count = 0
            image_total = 0
            used_images: set[str] = set()

            def render_declared_bitmap(resource: str, declared_mime: str) -> str:
                nonlocal image_count, image_total
                image_count += 1
                if image_count > MAX_EMBEDDED_IMAGES:
                    raise ValueError("EPUB embedded image count exceeds limits")
                payload = read_member(resource)
                image_total += len(payload)
                if image_total > MAX_EMBEDDED_IMAGE_TOTAL:
                    raise ValueError("EPUB embedded image total exceeds limits")
                used_images.add(resource.casefold())
                return _image_figure(_embedded_image_uri(payload, declared_mime))

            for ref in refs:
                if ref not in manifest or manifest[ref][0] != "application/xhtml+xml":
                    raise ValueError("EPUB spine references absent XHTML")
                chapter_path = manifest[ref][1]
                chapter = _xml(read_member(chapter_path))
                _nodes_within_limits(chapter)
                if _tag(chapter) != "html":
                    raise ValueError("EPUB spine resource is not XHTML")
                bodies = [node for node in chapter.iter() if _tag(node) == "body"]
                if len(bodies) != 1:
                    raise ValueError("EPUB XHTML body missing or ambiguous")
                if any(_tag(node) in {"svg", "object", "video", "audio", "iframe"}
                       for node in bodies[0].iter()):
                    raise ValueError("EPUB contains unsupported embedded media")

                def resolve_epub_image(node) -> str:
                    if "srcset" in node.attrib:
                        raise ValueError("EPUB external or responsive images unsupported")
                    src = node.attrib.get("src", "")
                    url = urlsplit(src)
                    if url.scheme or url.netloc or src.startswith("//"):
                        # Preserve legacy offline-only behavior: remote image
                        # references are omitted, never dereferenced or
                        # passed to Chromium, not treated as local assets.
                        return ""
                    resource = _image_member_href(chapter_path, src)
                    declared_mime = bitmap_parts.get(resource.casefold())
                    if declared_mime is None:
                        raise ValueError("EPUB image is undeclared or unsupported")
                    return render_declared_bitmap(resource, declared_mime)

                parts.extend(_paragraphs(bodies[0], image_resolver=resolve_epub_image))
                if len(parts) > 3000:
                    raise ValueError("EPUB paragraph count exceeds limits")
            # EPUB2 / EPUB3 cover images need not be included in the ordered
            # XHTML spine. Include only a declared, absent cover to avoid
            # rendering the same front page twice.
            if cover_id:
                record = manifest.get(cover_id)
                if record is None or record[0] not in ALLOWED_IMAGE_MIMES:
                    raise ValueError("EPUB cover image is not a supported manifest bitmap")
                cover_mime, cover_path = record
                if cover_path.casefold() not in used_images:
                    parts.insert(0, render_declared_bitmap(cover_path, cover_mime))
            return _bounded_html(parts, title=title)
    except (zipfile.BadZipFile, OSError, EOFError, RuntimeError) as exc:
        raise ValueError("Invalid EPUB container") from exc
