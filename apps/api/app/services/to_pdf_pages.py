"""T90-2 restricted genuine Apple Pages 4/5 ZIP document preflight.

This permits a supported *document body* (index.xml or Index/Document.iwa).
A QuickLook/Preview.pdf-only package is not sufficient and is rejected.
The pinned LibreOffice/libetonyek converter imports the document itself.
"""
from pathlib import Path
import zipfile

from app.filetypes import _checked_office_members

MAX_PAGES_BYTES = 16 * 1024 * 1024
MAX_PAGES_ENTRIES = 128
MAX_PAGES_UNCOMPRESSED = 32 * 1024 * 1024
MAX_INDEX_BYTES = 12 * 1024 * 1024


def validate_pages_package(source: Path) -> str:
    if not 1024 <= source.stat().st_size <= MAX_PAGES_BYTES:
        raise ValueError("Pages ZIP package outside size bound")
    if not source.read_bytes()[:4] == b"PK\x03\x04":
        raise ValueError("Pages is not a ZIP document")
    try:
        with zipfile.ZipFile(source) as archive:
            members = _checked_office_members(archive)
            if not 1 <= len(members) <= MAX_PAGES_ENTRIES:
                raise ValueError("Pages ZIP entry count exceeds bound")
            total = sum(info.file_size for info in members.values())
            if total > MAX_PAGES_UNCOMPRESSED:
                raise ValueError("Pages ZIP uncompressed content exceeds bound")
            old = members.get("index.xml")
            modern = members.get("Index/Document.iwa")
            if bool(old) == bool(modern):
                raise ValueError("Pages 4/5 document index missing or ambiguous")
            main = old or modern
            if not 0 < main.file_size <= MAX_INDEX_BYTES:
                raise ValueError("Pages document index outside size bound")
            # Verify CRC of all bounded members; no extraction or archive links.
            for entry in members.values():
                if entry.is_dir():
                    continue
                with archive.open(entry) as fh:
                    seen = 0
                    while True:
                        block = fh.read(65536)
                        if not block:
                            break
                        seen += len(block)
                        if seen > entry.file_size:
                            raise ValueError("Pages ZIP member exceeds declared size")
            if old:
                with archive.open(old) as fh:
                    header = fh.read(1024)
                if not header.lstrip().startswith(b"<?xml") and b"<" not in header[:80]:
                    raise ValueError("Pages 4 index lacks XML structure")
                return "Pages4"
            with archive.open(modern) as fh:
                header = fh.read(16)
            if not any(header):
                raise ValueError("Pages 5 IWA document index appears empty")
            return "Pages5"
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as exc:
        raise ValueError("Pages ZIP document invalid or corrupt") from exc
