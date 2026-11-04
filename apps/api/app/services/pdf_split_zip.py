"""M07: genuine bounded per-page PDF ZIP export for the selected page range.

This is an opt-in *new* operation; it does not modify legacy PDF split.
Only ordinary, non-encrypted/unsigned, non-form PDFs are accepted. Source
pages may contain Thai text, but visual Thai fidelity remains unverified.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo, ZIP_STORED
import shutil

from pypdf import PdfReader, PdfWriter

from app.page_ranges import validated_page_range
from app.services.output_artifacts import StagedPage

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_PARTS_BYTES = 64 * 1024 * 1024
MAX_SOURCE_PAGES = 200
MAX_PARTS = 80


def selected_page_numbers(expression: str, page_count: int) -> list[int]:
    """Resolve qpdf-compatible page syntax to unique one-based page indexes."""
    validated_page_range(expression)
    if type(page_count) is not int or not 1 <= page_count <= MAX_SOURCE_PAGES:
        raise ValueError("PDF source page count exceeds split limit")
    selected: list[int] = []
    seen: set[int] = set()
    for segment in expression.split(","):
        ends = segment.split("-")
        first = page_count if ends[0] == "z" else int(ends[0])
        last = page_count if ends[-1] == "z" else int(ends[-1])
        if not 1 <= first <= page_count or not 1 <= last <= page_count:
            raise ValueError("Split page index is outside source PDF")
        step = 1 if last >= first else -1
        for number in range(first, last + step, step):
            if number in seen:
                raise ValueError("Duplicate page selected for ZIP export")
            seen.add(number)
            selected.append(number)
            if len(selected) > MAX_PARTS:
                raise ValueError("Too many PDF parts requested")
    if not selected:
        raise ValueError("No PDF pages selected")
    return selected


def _source_document(source: Path) -> PdfReader:
    if source.is_symlink() or not source.is_file():
        raise ValueError("Split source must be a regular PDF")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("Split source PDF exceeds size budget")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_SOURCE_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")
    root = reader.trailer["/Root"]
    if root.get("/AcroForm") or root.get("/Perms"):
        raise ValueError("Signed or interactive PDF forms are unsupported")
    if any(page.get("/Annots") for page in reader.pages):
        raise ValueError("Annotated PDFs need independent fidelity acceptance")
    return reader


def _stream(page) -> bytes:
    contents = page.get_contents()
    return contents.get_data() if contents else b""


def _part_name(ordinal: int, source_page: int) -> str:
    return f"part-{ordinal:04d}-page-{source_page:04d}.pdf"


def make_split_pdf_zip(source: Path, destination: Path, *, pages: str) -> None:
    """Write a ZIP of authentic single-page PDFs, source untouched."""
    if (source.resolve() == destination.resolve() or destination.exists()
            or destination.is_symlink()):
        raise ValueError("Split output must be a distinct new file")
    reader = _source_document(source)
    selected = selected_page_numbers(pages, len(reader.pages))
    with TemporaryDirectory(prefix="pdfhub-m07-") as temp:
        tmp = Path(temp)
        archive_path = tmp / "split.zip"
        combined = 0
        with ZipFile(archive_path, mode="x", allowZip64=False) as archive:
            for ordinal, number in enumerate(selected, start=1):
                output_part = tmp / _part_name(ordinal, number)
                writer = PdfWriter()
                writer.add_page(reader.pages[number - 1])
                with output_part.open("xb") as stream:
                    writer.write(stream)
                if not output_part.read_bytes().startswith(b"%PDF-"):
                    raise ValueError("Split part has invalid PDF signature")
                rebuilt = PdfReader(str(output_part), strict=True)
                if rebuilt.is_encrypted or len(rebuilt.pages) != 1:
                    raise ValueError("Split part PDF inventory corrupted")
                original = reader.pages[number - 1]
                copied = rebuilt.pages[0]
                if (_stream(original) != _stream(copied)
                        or tuple(original.mediabox) != tuple(copied.mediabox)
                        or tuple(original.cropbox) != tuple(copied.cropbox)):
                    raise ValueError("Split part page content or geometry changed")
                size = output_part.stat().st_size
                combined += size
                if not 100 <= size <= MAX_PARTS_BYTES or combined > MAX_PARTS_BYTES:
                    raise ValueError("Split PDF part output exceeds byte budget")
                name = _part_name(ordinal, number)
                member = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                member.compress_type = ZIP_STORED
                member.external_attr = 0o100644 << 16
                archive.writestr(member, output_part.read_bytes())
                if archive_path.stat().st_size > MAX_BUNDLE_BYTES:
                    raise ValueError("Split PDF ZIP exceeds byte budget")
        if not 100 <= archive_path.stat().st_size <= MAX_BUNDLE_BYTES:
            raise ValueError("Split PDF ZIP exceeds byte budget")
        with ZipFile(archive_path) as result:
            if len(result.infolist()) != len(selected) or result.testzip() is not None:
                raise ValueError("Split PDF ZIP is not intact")
        with archive_path.open("rb") as inp, destination.open("xb") as out:
            shutil.copyfileobj(inp, out, length=1024 * 1024)


def stage_split_pdf_parts(bundle: Path, staging_dir: Path, *,
                          pages: list[int], max_bytes: int = MAX_PARTS_BYTES
                          ) -> list[StagedPage]:
    """Validate only our generated ZIP, then stage real owner-scoped PDF parts."""
    if (not pages or len(pages) > MAX_PARTS or len(set(pages)) != len(pages)
            or type(max_bytes) is not int or max_bytes < 1):
        raise ValueError("Invalid split artifact manifest bounds")
    if (bundle.is_symlink() or not bundle.is_file()
            or bundle.stat().st_size > MAX_BUNDLE_BYTES):
        raise ValueError("Invalid generated split ZIP")
    staging_dir.mkdir(parents=True, exist_ok=False)
    staged: list[StagedPage] = []
    total = 0
    with ZipFile(bundle) as archive:
        members = archive.infolist()
        if len(members) != len(pages):
            raise ValueError("Split ZIP part count differs from page selection")
        for ordinal, (number, info) in enumerate(zip(pages, members, strict=True), start=1):
            name = _part_name(ordinal, number)
            mode = (info.external_attr >> 16) & 0o170000
            if (info.filename != name or info.is_dir()
                    or (info.flag_bits & 1)
                    or mode not in (0, 0o100000)
                    or info.file_size < 100 or info.file_size > max_bytes - total):
                raise ValueError("Unsafe split ZIP entry")
            part = staging_dir / name
            with archive.open(info, "r") as inp, part.open("xb") as out:
                while chunk := inp.read(min(1024 * 1024, max_bytes - total + 1)):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Split PDF part bytes exceed budget")
                    out.write(chunk)
            if not part.read_bytes().startswith(b"%PDF-"):
                raise ValueError("Split ZIP part is not a PDF")
            actual = PdfReader(str(part), strict=True)
            if actual.is_encrypted or len(actual.pages) != 1:
                raise ValueError("Split ZIP contains invalid page PDF")
            staged.append(StagedPage(
                path=part, display_name=name,
                content_type="application/pdf", ordinal=ordinal,
            ))
    return staged
