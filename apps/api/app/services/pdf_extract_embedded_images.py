"""M18: bounded extraction of embedded PDF images, not page rasterization.

Supports PNG and JPEG image objects only. Other object encodings fail closed
until their codec/colour fidelity is separately accepted. ZIP members and
individually stored artifacts have deterministic, server-created basenames.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile, ZipInfo
import re
import shutil
import warnings

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from app.services.output_artifacts import StagedPage

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_PAGES = 200
MAX_IMAGES = 80
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 30_000_000

_MEMBER = re.compile(r"page-([0-9]{4})-image-([0-9]{4})\.(png|jpg)\Z")


def _validate_image(blob: bytes, ext: str) -> None:
    if not 50 <= len(blob) <= MAX_IMAGE_BYTES:
        raise ValueError("M18 image byte size unsupported")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(blob)) as image:
                if image.format != ("PNG" if ext == "png" else "JPEG"):
                    raise ValueError("M18 image format mismatch")
                width, height = image.size
                if width < 1 or height < 1 or width * height > MAX_PIXELS:
                    raise ValueError("M18 image pixel budget exceeded")
                image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("M18 invalid or excessive embedded image") from exc


def _safe_source(source: Path, output: Path) -> PdfReader:
    if (source.is_symlink() or not source.is_file()
            or output.exists() or output.is_symlink()
            or source.resolve() == output.resolve()):
        raise ValueError("M18 requires a regular source and new destination")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("M18 PDF size limit exceeded")
    with source.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("M18 input is not PDF")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_SOURCE_PAGES:
        raise ValueError("M18 encrypted or excessive-page PDF unsupported")
    return reader


def _safe_member(page: int, image: int, ext: str) -> str:
    return f"page-{page:04d}-image-{image:04d}.{ext}"


def extract_embedded_images_zip(source: Path, output: Path) -> None:
    """Write a bounded ZIP containing the original PDF's extracted image objects.

    A PDF image's pypdf-decoded format may differ from its internal XObject
    byte compression. No page screenshots, artificial image content or OCR.
    """
    reader = _safe_source(source, output)
    with TemporaryDirectory(prefix="pdfhub-m18-") as temp:
        bundle = Path(temp) / "embedded-images.zip"
        count = 0
        combined = 0
        with ZipFile(bundle, mode="x", compression=ZIP_STORED, allowZip64=False) as archive:
            for page_no, page in enumerate(reader.pages, 1):
                for page_index, image in enumerate(page.images, 1):
                    count += 1
                    if count > MAX_IMAGES:
                        raise ValueError("M18 exceeds image count limit")
                    source_ext = image.name.rsplit(".", 1)[-1].lower()
                    ext = "jpg" if source_ext in {"jpg", "jpeg"} else source_ext
                    if ext not in {"png", "jpg"}:
                        raise ValueError("M18 unsupported embedded image format")
                    blob = image.data
                    if len(blob) > MAX_IMAGE_BYTES - combined:
                        raise ValueError("M18 embedded images exceed byte budget")
                    _validate_image(blob, ext)
                    combined += len(blob)
                    name = _safe_member(page_no, page_index, ext)
                    if not _MEMBER.fullmatch(name):
                        raise ValueError("M18 output member invalid")
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_STORED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, blob)
                    if bundle.stat().st_size > MAX_ARCHIVE_BYTES:
                        raise ValueError("M18 ZIP exceeds byte budget")
        if count == 0:
            raise ValueError("M18 found no embedded images; use page rasterization")
        if not 50 <= bundle.stat().st_size <= MAX_ARCHIVE_BYTES:
            raise ValueError("M18 ZIP size unsupported")
        with ZipFile(bundle) as check:
            if len(check.infolist()) != count or check.testzip() is not None:
                raise ValueError("M18 ZIP integrity verification failed")
        with bundle.open("rb") as src, output.open("xb") as dest:
            shutil.copyfileobj(src, dest, length=1024 * 1024)


def stage_embedded_image_parts(
    bundle: Path, staging_dir: Path, *,
    max_bytes: int = MAX_IMAGE_BYTES,
) -> list[StagedPage]:
    """Inspect only our generated ZIP; stage server-named owner-bound images."""
    if (bundle.is_symlink() or not bundle.is_file()
            or not 50 <= bundle.stat().st_size <= MAX_ARCHIVE_BYTES
            or type(max_bytes) is not int or not 1 <= max_bytes <= MAX_IMAGE_BYTES):
        raise ValueError("M18 artifact bounds invalid")
    staging_dir.mkdir(parents=True, exist_ok=True)
    if any(staging_dir.iterdir()):
        raise ValueError("M18 artifact staging directory must be empty")
    staged: list[StagedPage] = []
    total = 0
    last_page = 0
    last_index = 0
    try:
        with ZipFile(bundle) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_IMAGES:
                raise ValueError("M18 artifact count outside limit")
            for ordinal, info in enumerate(infos, 1):
                match = _MEMBER.fullmatch(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if (not match or info.is_dir() or (info.flag_bits & 1)
                        or mode not in (0, 0o100000)
                        or info.compress_type != ZIP_STORED):
                    raise ValueError("M18 unsafe ZIP member")
                page, index, ext = int(match[1]), int(match[2]), match[3]
                if (not 1 <= page <= MAX_SOURCE_PAGES
                        or (page == last_page and index != last_index + 1)
                        or (page < last_page or (page > last_page and index != 1))
                        or info.file_size < 50 or info.file_size > max_bytes - total):
                    raise ValueError("M18 ZIP image sequence/size invalid")
                last_page, last_index = page, index
                dest = staging_dir / info.filename
                with archive.open(info) as inp, dest.open("xb") as out:
                    while chunk := inp.read(min(1024 * 1024, max_bytes - total + 1)):
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("M18 image byte budget exceeded")
                        out.write(chunk)
                _validate_image(dest.read_bytes(), ext)
                staged.append(StagedPage(
                    path=dest, display_name=info.filename,
                    content_type="image/png" if ext == "png" else "image/jpeg",
                    ordinal=ordinal,
                ))
    except Exception:
        for member in staged:
            member.path.unlink(missing_ok=True)
        raise
    return staged
