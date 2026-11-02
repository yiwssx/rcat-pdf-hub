"""F16: bounded PDF page animation to one GIF (engineering-only, default OFF).

This is an animated raster preview, NOT a searchable/editable PDF conversion.
One input PDF page becomes one full GIF frame. Identical frames that the encoder
collapses are rejected rather than silently losing source-page inventory.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import resource
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_PAGES = 20
MAX_PIXELS_PER_PAGE = 6_000_000
MAX_TOTAL_PIXELS = 40_000_000
MAX_INTERMEDIATE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 48 * 1024 * 1024
MIN_DPI = 72
MAX_DPI = 150
MIN_FRAME_MS = 300
MAX_FRAME_MS = 5000


def _child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (35, 36))
    resource.setrlimit(resource.RLIMIT_AS, (900 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_INTERMEDIATE_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def pdf_to_animated_gif(
    source: Path, output: Path, *, dpi: int = 96, frame_ms: int = 1200,
) -> None:
    if type(dpi) is not int or not MIN_DPI <= dpi <= MAX_DPI:
        raise ValueError("GIF DPI must be an integer between 72 and 150")
    if type(frame_ms) is not int or not MIN_FRAME_MS <= frame_ms <= MAX_FRAME_MS:
        raise ValueError("GIF frame duration must be an integer between 300 and 5000 ms")
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()):
        raise ValueError("GIF source must be an independent regular PDF")
    if (output.exists() or output.is_symlink()
            or not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES):
        raise ValueError("GIF output must be new; PDF source exceeds input budget")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF cannot be animated")

    total = 0
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if not (math.isfinite(width) and math.isfinite(height)
                and 1 <= width <= 4000 and 1 <= height <= 4000):
            raise ValueError("Invalid PDF page geometry for GIF")
        count = math.ceil(width * dpi / 72) * math.ceil(height * dpi / 72)
        total += count
        if count > MAX_PIXELS_PER_PAGE or total > MAX_TOTAL_PIXELS:
            raise ValueError("PDF raster page exceeds GIF memory budget")

    with TemporaryDirectory(prefix="pdfhub-frompdf-gif-") as temp:
        root = Path(temp)
        prefix = root / "page"
        try:
            result = subprocess.run(
                ["pdftoppm", "-f", "1", "-l", str(len(reader.pages)),
                 "-r", str(dpi), "-png", str(source), str(prefix)],
                shell=False, check=False, timeout=75,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, preexec_fn=_child_limits,
                env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("GIF rasterizer unavailable or timed out") from exc
        if result.returncode != 0:
            raise ValueError("PDF rasterizer rejected GIF conversion")
        pages: dict[int, Path] = {}
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError("GIF rasterizer generated an unsafe artifact")
            match = re.fullmatch(r"page-([1-9][0-9]*)\.png", path.name)
            if not match:
                raise ValueError("GIF rasterizer generated unexpected artifacts")
            index = int(match.group(1))
            if (index in pages or not 1 <= index <= len(reader.pages)
                    or not 10 <= path.stat().st_size <= MAX_INTERMEDIATE_BYTES):
                raise ValueError("GIF rasterized page numbering or size invalid")
            pages[index] = path
        if set(pages) != set(range(1, len(reader.pages) + 1)):
            raise ValueError("GIF rasterizer omitted/duplicated source pages")

        frames: list[Image.Image] = []
        try:
            for i in range(1, len(reader.pages) + 1):
                try:
                    with Image.open(pages[i]) as image:
                        if (image.format != "PNG" or getattr(image, "n_frames", 1) != 1
                                or image.width * image.height > MAX_PIXELS_PER_PAGE):
                            raise ValueError("Invalid GIF intermediate raster")
                        # GIF is 256-color, opaque output. This explicit palette
                        # quantization is lossy; never claim full RGB fidelity.
                        with image.convert("RGB") as rgb:
                            frames.append(rgb.quantize(
                                colors=256, method=Image.Quantize.MEDIANCUT,
                            ))
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                    raise ValueError("Invalid raster page for GIF") from exc
            tmp = root / "result.gif"
            frames[0].save(
                tmp, format="GIF", save_all=True, append_images=frames[1:],
                duration=frame_ms, loop=0, disposal=2, optimize=False,
            )
            if not 32 <= tmp.stat().st_size <= MAX_OUTPUT_BYTES:
                raise ValueError("GIF output size violates quota")
            with Image.open(tmp) as proof:
                if proof.format != "GIF" or proof.n_frames != len(reader.pages):
                    raise ValueError("GIF output lost PDF pages, including duplicate frames")
                for index in range(proof.n_frames):
                    proof.seek(index)
                    if proof.width <= 0 or proof.height <= 0:
                        raise ValueError("GIF output frame geometry is invalid")
            if output.exists() or output.is_symlink():
                raise ValueError("GIF destination unexpectedly exists")
            with tmp.open("rb") as inp, output.open("xb") as destination:
                while chunk := inp.read(1024 * 1024):
                    destination.write(chunk)
        finally:
            for frame in frames:
                frame.close()
