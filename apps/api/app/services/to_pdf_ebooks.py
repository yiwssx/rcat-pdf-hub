"""T90-2 text-only FictionBook 2 and EPUB ebook readers.

No executable content, CSS, images, fonts, network requests, external XML
entities, archive extraction or filesystem paths from untrusted documents.
This is a constrained text transcription, not complete ebook layout fidelity.
"""
from __future__ import annotations

from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import zipfile

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_BOOK_BYTES = 20 * 1024 * 1024
MAX_ZIP_ENTRIES = 256
MAX_ZIP_EXPANDED_BYTES = 30 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 8 * 1024 * 1024
MAX_BOOK_CHARS = 200_000
MAX_BOOK_NODES = 12000
MAX_CHAPTERS = 60


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


def _paragraphs(root, *, max_nodes: int = 12000) -> list[str]:
    parts = []
    count = 0
    for node in root.iter():
        count += 1
        if count > max_nodes:
            raise ValueError("Ebook chapter exceeds node count")
        name = _tag(node)
        if name in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "subtitle"}:
            text = _plain_text(node)
            if text:
                tag = "h2" if name in {"h1", "h2", "subtitle"} else (
                    "h3" if name in {"h3", "h4", "h5", "h6"} else "p"
                )
                parts.append(f"<{tag}>" + escape(text) + f"</{tag}>")
    return parts


def _bounded_html(parts: list[str], *, title: str = "") -> str:
    body = ("<h1>" + escape(title[:500]) + "</h1>") if title.strip() else ""
    body += "".join(parts)
    if not parts or len(body) > MAX_BOOK_CHARS * 6:
        raise ValueError("Ebook text absent or exceeds output bounds")
    return body


def fb2_to_safe_html(source: Path) -> str:
    """FictionBook2 plain body/title only; embedded images intentionally omitted."""
    if not 0 < source.stat().st_size <= MAX_BOOK_BYTES:
        raise ValueError("FB2 input exceeds staged limits")
    root = _xml(source.read_bytes())
    if _tag(root) != "fictionbook":
        raise ValueError("Not a FictionBook2 document")
    _nodes_within_limits(root)
    book_title = ""
    for node in root.iter():
        if _tag(node) == "book-title":
            book_title = _plain_text(node)[:500]
            break
    blocks = []
    for body in root:
        if _tag(body) == "body":
            blocks.extend(_paragraphs(body))
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


def epub_to_safe_html(source: Path) -> str:
    """EPUB 2/3 text spine reader. Ignores images, CSS, scripts and links."""
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
            for node in opf.iter():
                if _tag(node) == "item":
                    identity = node.attrib.get("id", "")
                    if not identity or identity in manifest:
                        raise ValueError("Duplicate or empty EPUB manifest id")
                    if node.attrib.get("media-type") == "application/xhtml+xml":
                        manifest[identity] = _member_href(
                            opf_path, node.attrib.get("href", "")
                        )
            refs = [n.attrib.get("idref", "") for n in opf.iter()
                    if _tag(n) == "itemref"]
            if not 1 <= len(refs) <= MAX_CHAPTERS:
                raise ValueError("EPUB text spine length outside limits")
            parts = []
            for ref in refs:
                if ref not in manifest:
                    raise ValueError("EPUB spine references absent XHTML")
                chapter = _xml(read_member(manifest[ref]))
                _nodes_within_limits(chapter)
                if _tag(chapter) != "html":
                    raise ValueError("EPUB spine resource is not XHTML")
                bodies = [node for node in chapter.iter() if _tag(node) == "body"]
                if len(bodies) != 1:
                    raise ValueError("EPUB XHTML body missing or ambiguous")
                parts.extend(_paragraphs(bodies[0]))
                if len(parts) > 3000:
                    raise ValueError("EPUB paragraph count exceeds limits")
            return _bounded_html(parts, title=title)
    except (zipfile.BadZipFile, OSError, EOFError, RuntimeError) as exc:
        raise ValueError("Invalid EPUB container") from exc
