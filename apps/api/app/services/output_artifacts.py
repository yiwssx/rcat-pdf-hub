"""Bounded extraction of our own PDF raster ZIP into individual result artifacts.

Not a generic ZIP upload converter. Never trust archived paths or declared lengths.
The existing generated ZIP remains the backwards-compatible primary result.
"""
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

PAGE_ENTRY = re.compile(r"page-([0-9]{4,})\.(png|jpg)\Z")
MAX_ARTIFACTS = 200


@dataclass(frozen=True)
class StagedPage:
    path: Path
    display_name: str
    content_type: str
    ordinal: int


def stage_raster_pages(
    bundle: Path, staging_dir: Path, *, first_page: int, max_bytes: int
) -> list[StagedPage]:
    """Validate a generated raster ZIP and extract its ordered image members.

    Only page-NNNN.png/jpg basenames, exact sequence, bounded count and total
    uncompressed bytes are accepted. All extraction uses fixed local basenames.
    """
    if first_page < 1 or max_bytes < 1:
        raise ValueError("Invalid raster extraction limits")
    staging_dir.mkdir(parents=True, exist_ok=True)
    pages: list[StagedPage] = []
    total = 0
    try:
        with zipfile.ZipFile(bundle) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_ARTIFACTS:
                raise ValueError("Raster ZIP page count is outside allowed bounds")
            expected = first_page
            extension = None
            for info in infos:
                match = PAGE_ENTRY.fullmatch(info.filename)
                if not match or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Unsafe or unexpected raster ZIP member")
                page_no = int(match.group(1))
                if page_no != expected:
                    raise ValueError("Raster ZIP pages must be ordered and contiguous")
                ext = match.group(2)
                if extension is not None and ext != extension:
                    raise ValueError("Mixed raster formats in output archive")
                extension = ext
                remaining = max_bytes - total
                if info.file_size > remaining:
                    raise ValueError("Raster output byte limit exceeded")
                name = f"page-{page_no:04d}.{ext}"
                dest = staging_dir / name
                with archive.open(info, "r") as inp, dest.open("xb") as out:
                    while chunk := inp.read(min(1024 * 1024, remaining + 1)):
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("Raster output byte limit exceeded")
                        remaining = max_bytes - total
                        out.write(chunk)
                try:
                    with Image.open(dest) as img:
                        if img.format != ("PNG" if ext == "png" else "JPEG"):
                            raise ValueError("Raster file content does not match extension")
                        img.verify()
                except (UnidentifiedImageError, OSError) as exc:
                    raise ValueError("Invalid raster image generated") from exc
                pages.append(StagedPage(
                    path=dest, display_name=name,
                    content_type="image/png" if ext == "png" else "image/jpeg",
                    ordinal=len(pages) + 1,
                ))
                expected += 1
    except Exception:
        for page in staging_dir.iterdir():
            if page.is_file():
                page.unlink(missing_ok=True)
        raise
    return pages
