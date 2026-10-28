"""T90-1.4 STAGED PDF operations: document Info/XMP and searchable text.

These functions are deliberately NOT bound to a route, worker adapter, or the
90-tool runtime registry. T90-0's reviewed 13-operation allowlist stays intact.

"remove_metadata" has a deliberately narrow contract: document Info and
catalog/page XMP streams. It is NOT redaction, removal of annotations, PDF
signatures, embedded files, images, content, or all possible private data.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Mapping

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

_INFO_FIELDS: dict[str, str] = {
    "title": "/Title",
    "author": "/Author",
    "subject": "/Subject",
    "keywords": "/Keywords",
}
_MAX_FIELD_CHARS = 512
_MAX_PAGES = 1000
_MAX_CONTENT_STREAM_BYTES = 16 * 1024 * 1024
_MAX_TEXT_BYTES = 8 * 1024 * 1024


def _distinct_paths(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("PDF input and output paths must differ")


def _read_pdf(source: Path) -> PdfReader:
    with source.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("Expected a PDF file signature")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs require a separate authorized unlock workflow")
    if not 1 <= len(reader.pages) <= _MAX_PAGES:
        raise ValueError("PDF page count outside staged 1–1000 bound")
    return reader


def _write_atomic(writer: PdfWriter, destination: Path) -> None:
    """Write beside the final path; never leave a partial output on error."""
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-t90-", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as handle:
            path = handle.name
            writer.write(handle)
        verified = PdfReader(path, strict=True)
        if verified.is_encrypted or len(verified.pages) == 0:
            raise ValueError("Generated PDF failed validation")
        os.replace(path, destination)
        path = None
    finally:
        if path is not None:
            Path(path).unlink(missing_ok=True)


def edit_document_info(
    source: Path, destination: Path, changes: Mapping[str, str | None]
) -> None:
    """Edit only the four explicitly offered /Info keys; None deletes a key.

    Reject source PDFs with XMP rather than leaving conflicting XMP values,
    silently erasing other XMP properties, or claiming XMP synchronization.
    """
    _distinct_paths(source, destination)
    if not isinstance(changes, Mapping) or not changes or any(
        key not in _INFO_FIELDS for key in changes
    ):
        raise ValueError("Provide one or more supported Info metadata fields")
    for value in changes.values():
        if value is not None and (
            not isinstance(value, str)
            or len(value) > _MAX_FIELD_CHARS
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise ValueError("Invalid document Info metadata value")
    reader = _read_pdf(source)
    if reader.root_object.get("/Metadata") is not None or any(
        page.get("/Metadata") is not None for page in reader.pages
    ):
        raise ValueError("PDF has XMP metadata; synchronized editing is not yet supported")
    writer = PdfWriter(clone_from=reader)
    updates = {_INFO_FIELDS[key]: value for key, value in changes.items() if value is not None}
    if updates:
        writer.add_metadata(updates)
    if any(value is None for value in changes.values()):
        info = writer._info.get_object()
        for field, value in changes.items():
            if value is None:
                info.pop(NameObject(_INFO_FIELDS[field]), None)
    _write_atomic(writer, destination)


def remove_document_info_and_xmp(source: Path, destination: Path) -> None:
    """Remove document Info and root/page XMP; do NOT claim complete sanitization."""
    _distinct_paths(source, destination)
    reader = _read_pdf(source)
    writer = PdfWriter(clone_from=reader)
    # A new empty Info object is used rather than None because versions of
    # pypdf's orphan collector require a non-null writer._info reference.
    writer.metadata = {}
    writer._root_object.pop(NameObject("/Metadata"), None)
    for page in writer.pages:
        page.pop(NameObject("/Metadata"), None)
    # Removed XMP streams are otherwise often emitted as orphaned PDF objects.
    writer.compress_identical_objects()
    _write_atomic(writer, destination)
    result = PdfReader(str(destination), strict=True)
    if result.metadata or result.root_object.get("/Metadata") is not None or any(
        page.get("/Metadata") is not None for page in result.pages
    ):
        destination.unlink(missing_ok=True)
        raise ValueError("PDF metadata clearing verification failed")


def extract_searchable_text(source: Path, destination: Path) -> None:
    """Produce UTF-8 text from an existing text layer, NOT OCR.

    A scanned, image-only PDF raises a useful error rather than returning an
    apparently successful but blank file. Page form-feed markers preserve page
    boundaries; line and column reading order is not a guaranteed semantic order.
    """
    _distinct_paths(source, destination)
    reader = _read_pdf(source)
    extracted: list[str] = []
    used = 0
    found_text = False
    for index, page in enumerate(reader.pages, 1):
        contents = page.get_contents()
        if contents is not None and len(contents.get_data()) > _MAX_CONTENT_STREAM_BYTES:
            raise ValueError(f"Page {index} content stream exceeds 16 MiB safety cap")
        text = page.extract_text() or ""
        found_text |= bool(text.strip())
        used += len(text.encode("utf-8"))
        if used > _MAX_TEXT_BYTES:
            raise ValueError("Extracted text exceeds 8 MiB safety cap")
        extracted.append(text)
    if not found_text:
        raise ValueError("No searchable text layer found; OCR is required")
    output = "\n\f\n".join(extracted).encode("utf-8")
    if len(output) > _MAX_TEXT_BYTES:
        raise ValueError("Extracted text exceeds 8 MiB safety cap")
    path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-t90-", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as handle:
            path = handle.name
            handle.write(output)
        os.replace(path, destination)
        path = None
    finally:
        if path is not None:
            Path(path).unlink(missing_ok=True)
