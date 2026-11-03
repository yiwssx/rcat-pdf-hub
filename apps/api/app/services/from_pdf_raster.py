"""F03/F04: PDF -> an ordered, complete PNG/JPEG-per-page ZIP.

Refuse truncation and unexpected Poppler output; no first-page-only fallback.
Engineering-stage implementation, not RCAT visual production acceptance.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import resource
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_PAGES = 20
MAX_PIXELS_PER_PAGE = 6_000_000
MAX_TOTAL_PIXELS = 40_000_000
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 96 * 1024 * 1024
MIN_DPI = 72
MAX_DPI = 200


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (35, 36))
    resource.setrlimit(resource.RLIMIT_AS, (900 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_IMAGE_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def pdf_to_raster_page_zip(
    source: Path, output: Path, *, fmt: str, dpi: int = 96,
) -> None:
    if fmt not in {"png", "jpg"}:
        raise ValueError("Only PNG/JPG output is supported")
    if type(dpi) is not int or not MIN_DPI <= dpi <= MAX_DPI:
        raise ValueError("Raster DPI must be an integer between 72 and 200")
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("Raster source/destination must be independent files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds raster converter source budget")
    document = PdfReader(str(source), strict=True)
    if document.is_encrypted or not 1 <= len(document.pages) <= MAX_PAGES:
        raise ValueError("Encrypted/excessive-page PDF cannot be rasterized")
    total_pixels = 0
    for page in document.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        if (not math.isfinite(w) or not math.isfinite(h)
                or not 1 <= w <= 4000 or not 1 <= h <= 4000):
            raise ValueError("Unsupported PDF page geometry for raster")
        pixels = math.ceil(w*dpi/72) * math.ceil(h*dpi/72)
        total_pixels += pixels
        if pixels > MAX_PIXELS_PER_PAGE or total_pixels > MAX_TOTAL_PIXELS:
            raise ValueError("Raster pixel budget exceeded")

    with TemporaryDirectory(prefix="pdfhub-frompdf-raster-") as folder:
        root = Path(folder)
        command = [
            "pdftoppm", "-f", "1", "-l", str(len(document.pages)),
            "-r", str(dpi), "-png" if fmt == "png" else "-jpeg",
            str(source), str(root / "page"),
        ]
        try:
            run = subprocess.run(
                command, shell=False, check=False, timeout=75,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, preexec_fn=_limits,
                env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Raster renderer unavailable or timed out") from exc
        if run.returncode:
            raise ValueError("Raster renderer rejected PDF")

        frames: dict[int, Path] = {}
        pattern = re.compile(rf"page-(0*[1-9][0-9]*)\.{fmt}")
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Raster renderer generated an unsafe file")
            match = pattern.fullmatch(path.name)
            if not match:
                raise ValueError("Raster renderer generated unexpected output")
            page_no = int(match.group(1))
            if (page_no in frames or not 1 <= page_no <= len(document.pages)
                    or not 12 <= path.stat().st_size <= MAX_IMAGE_BYTES):
                raise ValueError("Raster renderer omitted, duplicated or exceeded a page")
            with Image.open(path) as image:
                expected = "PNG" if fmt == "png" else "JPEG"
                if (image.format != expected or getattr(image, "n_frames", 1) != 1
                        or image.width * image.height > MAX_PIXELS_PER_PAGE):
                    raise ValueError("Raster page MIME, size or frame count invalid")
                try:
                    image.verify()
                except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
                    raise ValueError("Raster image integrity rejected") from exc
            frames[page_no] = path
        if set(frames) != set(range(1, len(document.pages)+1)):
            raise ValueError("Raster renderer lost or added PDF pages")

        staged = root / "result.zip"
        with ZipFile(staged, "w", compression=ZIP_STORED, allowZip64=False) as archive:
            for page_no in range(1, len(document.pages)+1):
                name = f"page-{page_no:04d}.{fmt}"
                archive.write(frames[page_no], arcname=name)
                if staged.stat().st_size > MAX_OUTPUT_BYTES:
                    raise ValueError("Raster ZIP aggregate exceeds output budget")
        if not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("Raster ZIP output size invalid")
        with ZipFile(staged) as proof:
            expected = [
                f"page-{i:04d}.{fmt}" for i in range(1, len(document.pages)+1)
            ]
            if proof.namelist() != expected or proof.testzip() is not None:
                raise ValueError("Raster ZIP page order/integrity invalid")
            for member in proof.infolist():
                if (member.compress_type != ZIP_STORED
                        or not 12 <= member.file_size <= MAX_IMAGE_BYTES):
                    raise ValueError("Raster ZIP contains invalid member")
        with staged.open("rb") as initial, output.open("xb") as destination:
            while chunk := initial.read(1024*1024):
                destination.write(chunk)
