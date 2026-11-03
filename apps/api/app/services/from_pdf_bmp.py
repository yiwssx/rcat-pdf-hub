"""F17 bounded PDF→BMP: each page becomes a separately named BMP in one ZIP.

Unlike GIF, BMP has no standard multipage container. Return a ZIP of distinct
page images, not one misleading BMP of only the first PDF page. Engineering
stage only; renderer/real institutional fidelity still requires acceptance.
"""
from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
import re
import resource
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_STORED

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_PAGES = 20
MAX_PIXELS_PER_PAGE = 6_000_000
MAX_TOTAL_PIXELS = 40_000_000
MAX_INTERMEDIATE_BYTES = 16 * 1024 * 1024
MAX_BMP_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
MIN_DPI = 72
MAX_DPI = 150


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (35, 36))
    resource.setrlimit(resource.RLIMIT_AS, (900 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_INTERMEDIATE_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def pdf_to_bmp_zip(source: Path, output: Path, *, dpi: int = 96) -> None:
    if type(dpi) is not int or not MIN_DPI <= dpi <= MAX_DPI:
        raise ValueError("BMP DPI must be an integer between 72 and 150")
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("BMP source/destination must be independent regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("BMP source PDF exceeds input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("BMP cannot convert encrypted or excessive-page PDFs")
    total_pixels = 0
    for page in pdf.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if not (math.isfinite(width) and math.isfinite(height)
                and 1 <= width <= 4000 and 1 <= height <= 4000):
            raise ValueError("Invalid PDF page geometry for BMP")
        pixels = math.ceil(width * dpi / 72) * math.ceil(height * dpi / 72)
        total_pixels += pixels
        if pixels > MAX_PIXELS_PER_PAGE or total_pixels > MAX_TOTAL_PIXELS:
            raise ValueError("PDF raster exceeds BMP pixel budget")

    with TemporaryDirectory(prefix="pdfhub-frompdf-bmp-") as temp:
        root = Path(temp)
        try:
            result = subprocess.run(
                ["pdftoppm", "-f", "1", "-l", str(len(pdf.pages)),
                 "-r", str(dpi), "-png", str(source), str(root / "page")],
                shell=False, check=False, timeout=75,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, preexec_fn=_limits,
                env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("BMP rasterizer unavailable or timed out") from exc
        if result.returncode:
            raise ValueError("BMP rasterizer rejected PDF")
        pages: dict[int, Path] = {}
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError("BMP rasterizer generated an unsafe artifact")
            match = re.fullmatch(r"page-(0*[1-9][0-9]*)\.png", path.name)
            if not match:
                raise ValueError("BMP rasterizer generated unexpected artifacts")
            index = int(match.group(1))
            if (index in pages or not 1 <= index <= len(pdf.pages)
                    or not 10 <= path.stat().st_size <= MAX_INTERMEDIATE_BYTES):
                raise ValueError("BMP raster page count/size invalid")
            pages[index] = path
        if set(pages) != set(range(1, len(pdf.pages) + 1)):
            raise ValueError("BMP rasterizer omitted or duplicated pages")

        staged = root / "result.zip"
        with ZipFile(staged, "w", compression=ZIP_STORED, allowZip64=False) as archive:
            for page_no in range(1, len(pdf.pages) + 1):
                try:
                    with Image.open(pages[page_no]) as opened:
                        if (opened.format != "PNG" or opened.n_frames != 1
                                or opened.width * opened.height > MAX_PIXELS_PER_PAGE):
                            raise ValueError("BMP intermediate raster invalid")
                        with opened.convert("RGB") as image:
                            out = BytesIO()
                            image.save(out, format="BMP")
                            binary = out.getvalue()
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                    raise ValueError("BMP rasterized page invalid") from exc
                if not 54 <= len(binary) <= MAX_BMP_BYTES or binary[:2] != b"BM":
                    raise ValueError("BMP frame header or size invalid")
                archive.writestr(f"page-{page_no:04d}.bmp", binary)
                if staged.stat().st_size > MAX_OUTPUT_BYTES:
                    raise ValueError("BMP ZIP aggregate exceeds output budget")
        if not 100 <= staged.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("BMP ZIP output size invalid")
        with ZipFile(staged) as proof:
            expected = [f"page-{i:04d}.bmp" for i in range(1, len(pdf.pages) + 1)]
            if proof.namelist() != expected or proof.testzip() is not None:
                raise ValueError("BMP ZIP contains extra, missing or damaged pages")
            for info in proof.infolist():
                if info.compress_type != ZIP_STORED or not 54 <= info.file_size <= MAX_BMP_BYTES:
                    raise ValueError("BMP ZIP member exceeded format budget")
        if output.exists() or output.is_symlink():
            raise ValueError("BMP destination unexpectedly exists")
        with staged.open("rb") as input_stream, output.open("xb") as dest:
            while chunk := input_stream.read(1024 * 1024):
                dest.write(chunk)
