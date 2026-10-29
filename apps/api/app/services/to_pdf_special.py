"""Narrow, fail-closed T90-2 specialist file converters.

AI: only native PDF-compatible Illustrator files, never PostScript/EPS.
XPS: only Glyphs-only fixed-page text transcription, not original layout.
Neither adapter launches a decoder, fetches external references or extracts ZIPs.
"""
from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED, BadZipFile
import math

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader, PdfWriter

AI_MAX_BYTES = 16 * 1024 * 1024
AI_MAX_PAGES = 64
XPS_MAX_BYTES = 12 * 1024 * 1024
XPS_MAX_MEMBERS = 128
XPS_MAX_EXPANDED = 20 * 1024 * 1024
XPS_MEMBER_MAX = 2 * 1024 * 1024
XPS_MAX_PAGES = 24
XPS_MAX_CHARS = 100_000
XPS_NAMESPACE = "http://schemas.microsoft.com/xps/2005/06"
RELS_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"


def _distinct(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("Source and output must differ")


def _ai_pdf_reader(source: Path) -> PdfReader:
    """Read ONLY Illustrator PDF-compatibility streams, not arbitrary .ai scripts."""
    if not 0 < source.stat().st_size <= AI_MAX_BYTES:
        raise ValueError("PDF-compatible Illustrator input exceeds 16 MiB limit")
    payload = source.read_bytes()
    if not payload.startswith(b"%PDF-"):
        raise ValueError("Only PDF-compatible Illustrator .ai files are supported")
    try:
        reader = PdfReader(BytesIO(payload), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= AI_MAX_PAGES:
            raise ValueError("Encrypted, empty or oversized Illustrator PDF is unsupported")
        root = reader.trailer["/Root"].get_object()
        for key in ("/OpenAction", "/AA", "/Names", "/AcroForm", "/AF",
                    "/Collection", "/Perms"):
            if key in root:
                raise ValueError("Illustrator PDF contains active or embedded content")
        for page in reader.pages:
            if any(key in page for key in ("/Annots", "/AA", "/B", "/PresSteps")):
                raise ValueError("Illustrator PDF page contains active content")
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            if (not math.isfinite(width) or not math.isfinite(height)
                    or not 18 <= width <= 5000 or not 18 <= height <= 5000):
                raise ValueError("Illustrator PDF contains unsupported page bounds")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Malformed Illustrator PDF-compatible stream") from exc
    return reader


def pdf_compatible_ai_to_pdf(source: Path, output: Path) -> None:
    """Rebuild page tree without source catalog, actions or document metadata."""
    _distinct(source, output)
    reader = _ai_pdf_reader(source)
    try:
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buffer = BytesIO()
        writer.write(buffer)
        # The common PDF output gate checks strict parseability and bounds.
        from app.services.to_pdf_engine import _checked_pdf
        _checked_pdf(buffer.getvalue(), output)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to rebuild PDF-compatible Illustrator pages") from exc


def _safe_name(name: str) -> str:
    """Package-local, unambiguous path; no percent-encoded or remote references."""
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or "%" in name or "?" in name or "#" in name
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("XPS contains unsafe or external package path")
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("XPS contains path traversal or ambiguous package path")
    return name


def _relative(base: str, target: str) -> str:
    if target.startswith("/"):
        return _safe_name(target[1:])
    target = _safe_name(target)
    return _safe_name(str(PurePosixPath(base).parent / target))


def _xml(payload: bytes):
    if len(payload) > XPS_MEMBER_MAX:
        raise ValueError("XPS XML resource exceeds bounds")
    try:
        return SafeET.fromstring(payload)
    except (SafeET.ParseError, DefusedXmlException, ValueError) as exc:
        raise ValueError("Malformed or unsafe XPS XML") from exc


def _tag(node, namespace: str) -> str:
    value = str(node.tag)
    prefix = "{" + namespace + "}"
    if not value.startswith(prefix):
        raise ValueError("Unsupported XPS XML namespace")
    return value[len(prefix):]


def xps_to_safe_html(source: Path) -> str:
    """Bounded, ordered Glyphs-only XPS text *transcription*.

    Reject vector paths, images, canvases, transforms, markup expansion,
    resource dictionaries and all remote references rather than quietly
    corrupting complex documents. Page size and original typography are lost.
    """
    if not 0 < source.stat().st_size <= XPS_MAX_BYTES:
        raise ValueError("XPS input exceeds 12 MiB limit")
    try:
        with ZipFile(source) as archive:
            infos = archive.infolist()
            if not 3 <= len(infos) <= XPS_MAX_MEMBERS:
                raise ValueError("XPS archive entry count outside bounds")
            files = {}
            total = 0
            for info in infos:
                name = _safe_name(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if (name.casefold() in files or mode not in (0, 0o100000, 0o040000)
                        or (mode == 0o040000 and not info.is_dir())
                        or info.flag_bits & 1
                        or info.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                        or info.file_size > XPS_MEMBER_MAX
                        or info.file_size > (info.compress_size + 1024) * 100):
                    raise ValueError("XPS ZIP member is unsafe or duplicated")
                total += info.file_size
                if total > XPS_MAX_EXPANDED:
                    raise ValueError("XPS expanded content exceeds bounds")
                if not info.is_dir():
                    files[name.casefold()] = info

            def read(name: str) -> bytes:
                info = files.get(_safe_name(name).casefold())
                if info is None:
                    raise ValueError("XPS required package part is missing")
                data = archive.read(info)
                if len(data) != info.file_size:
                    raise ValueError("XPS resource length mismatch")
                return data

            read("[Content_Types].xml")
            rels = _xml(read("_rels/.rels"))
            if _tag(rels, RELS_NAMESPACE) != "Relationships":
                raise ValueError("XPS root relationships missing")
            representations = [
                node for node in rels
                if _tag(node, RELS_NAMESPACE) == "Relationship"
                and node.attrib.get("Type", "").endswith("/fixedrepresentation")
                and node.attrib.get("TargetMode", "Internal") == "Internal"
            ]
            if len(representations) != 1:
                raise ValueError("XPS requires exactly one local fixed representation")
            seq_path = _relative("", representations[0].attrib.get("Target", ""))
            seq = _xml(read(seq_path))
            if _tag(seq, XPS_NAMESPACE) != "FixedDocumentSequence":
                raise ValueError("XPS fixed document sequence missing")
            if not 1 <= len(seq) <= 8:
                raise ValueError("XPS document count outside bounds")
            page_paths = []
            for node in seq:
                if _tag(node, XPS_NAMESPACE) != "DocumentReference":
                    raise ValueError("Unsupported XPS document sequence")
                doc_path = _relative(seq_path, node.attrib.get("Source", ""))
                doc = _xml(read(doc_path))
                if _tag(doc, XPS_NAMESPACE) != "FixedDocument":
                    raise ValueError("XPS fixed document missing")
                for page in doc:
                    if _tag(page, XPS_NAMESPACE) != "PageContent":
                        raise ValueError("Unsupported XPS document child")
                    if len(page):
                        raise ValueError("XPS complex PageContent is unsupported")
                    page_paths.append(_relative(doc_path, page.attrib.get("Source", "")))
                    if len(page_paths) > XPS_MAX_PAGES:
                        raise ValueError("XPS page count exceeds 24")
            if not page_paths:
                raise ValueError("Empty XPS fixed document")
            parts = []
            total_chars = 0
            for page_path in page_paths:
                root = _xml(read(page_path))
                if _tag(root, XPS_NAMESPACE) != "FixedPage":
                    raise ValueError("Invalid XPS fixed page")
                glyphs = []
                for node in root:
                    if _tag(node, XPS_NAMESPACE) != "Glyphs" or len(node):
                        raise ValueError("XPS vectors, images, canvases or resources unsupported")
                    if any(a in node.attrib for a in (
                        "Indices", "RenderTransform", "Clip", "OpacityMask",
                        "IsSideways", "NavigateUri", "FixedPage.NavigateUri",
                    )):
                        raise ValueError("XPS complex glyph layout or links unsupported")
                    value = node.attrib.get("UnicodeString", "")
                    if (not value or len(value) > 10_000 or
                            any(ord(c) < 32 and c not in "\n\r\t" for c in value)):
                        raise ValueError("XPS glyph UnicodeString invalid or oversized")
                    if any(token in node.attrib.get("FontUri", "").lower()
                           for token in ("http:", "https:", "file:", "..", "\\")):
                        raise ValueError("Remote XPS font source is unsupported")
                    total_chars += len(value)
                    if total_chars > XPS_MAX_CHARS:
                        raise ValueError("XPS exceeds transcript character limit")
                    glyphs.append("<p>" + escape(value) + "</p>")
                if not glyphs:
                    raise ValueError("XPS page has no supported Unicode glyphs")
                parts.append("<section>" + "".join(glyphs) + "</section>")
            return ('<style>section{break-after:page}section:last-child{break-after:auto}</style>'
                    + "".join(parts))
    except (BadZipFile, OSError, RuntimeError, EOFError, KeyError) as exc:
        raise ValueError("Malformed XPS package") from exc


def restricted_xps_to_pdf(source: Path, output: Path) -> None:
    _distinct(source, output)
    content = xps_to_safe_html(source)
    from app.services.to_pdf_engine import _html_to_pdf
    _html_to_pdf(content, output)
