"""M14/M15: genuine PDF page deletion and complete-page reordering.

Rebuild a new PDF with only explicitly selected pypdf page objects.
Not a secure-redaction guarantee for arbitrary contents or attachments.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_OUTPUT_BYTES = 48 * 1024 * 1024
MAX_PAGES = 120


def select_pdf_pages(
    source: Path, destination: Path, *,
    operation: str, pages: list[int],
) -> None:
    if operation not in {"delete", "reorder"}:
        raise ValueError("Unsupported page-selection operation")
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("Source/destination must be distinct regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF page-selection input exceeds budget")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")
    page_count = len(reader.pages)
    if (not isinstance(pages, list)
            or not 1 <= len(pages) <= MAX_PAGES
            or any(type(i) is not int or not 1 <= i <= page_count for i in pages)
            or len(set(pages)) != len(pages)):
        raise ValueError("Duplicate, missing or out-of-range PDF page indices")
    if operation == "delete":
        removed = set(pages)
        selected = [index for index in range(1, page_count+1)
                    if index not in removed]
        if not selected:
            raise ValueError("Cannot delete every PDF page")
    else:
        if set(pages) != set(range(1, page_count+1)):
            raise ValueError("Reordering must include each original page exactly once")
        selected = pages

    writer = PdfWriter()
    for number in selected:
        writer.add_page(reader.pages[number-1])
    # Rebuild from selected pages only, without copying original global metadata
    # or named attachments. Do not assert this is cryptographic data erasure.
    with TemporaryDirectory(prefix="pdfhub-page-selection-") as temp:
        staged = Path(temp) / "selected.pdf"
        with staged.open("xb") as stream:
            writer.write(stream)
        if not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("Selected PDF output exceeds budget")
        result = PdfReader(str(staged), strict=True)
        if result.is_encrypted or len(result.pages) != len(selected):
            raise ValueError("Selected PDF page inventory was corrupted")
        for original_no, output_page in zip(selected, result.pages):
            original_page = reader.pages[original_no-1]
            original_content = original_page.get_contents()
            copied_content = output_page.get_contents()
            before = original_content.get_data() if original_content else b""
            after = copied_content.get_data() if copied_content else b""
            if before != after:
                raise ValueError("PDF page contents changed during selection")
        with staged.open("rb") as src, destination.open("xb") as dest:
            while chunk := src.read(1024 * 1024):
                dest.write(chunk)
