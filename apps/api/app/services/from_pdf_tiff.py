"""F09 PDF -> multipage TIFF: bounded implementation (engineering only).

Not routed until owner-scoped API/queue/output-MIME contracts are added.
This engine deliberately refuses encrypted, excessive or malformed PDFs.
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
MAX_PAGES = 40
MAX_PIXELS_PER_PAGE = 20_000_000
MAX_TOTAL_PIXELS = 100_000_000
MAX_INTERMEDIATE = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MIN_DPI = 72
MAX_DPI = 300


def _child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (35, 36))
    resource.setrlimit(resource.RLIMIT_AS, (900 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_INTERMEDIATE,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def pdf_to_multipage_tiff(source: Path, output: Path, *, dpi: int = 150) -> None:
    if type(dpi) is not int or not MIN_DPI <= dpi <= MAX_DPI:
        raise ValueError("TIFF DPI must be an integer between 72 and 300")
    if source.resolve() == output.resolve() or source.is_symlink() or not source.is_file():
        raise ValueError("PDF source must be an independent regular file")
    if not 16 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds TIFF converter input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF is unsupported")
    total_pixels = 0
    for page in pdf.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if not (math.isfinite(width) and math.isfinite(height)
                and 1 <= width <= 4000 and 1 <= height <= 4000):
            raise ValueError("PDF page geometry is unsupported")
        pixels = math.ceil(width * dpi / 72) * math.ceil(height * dpi / 72)
        total_pixels += pixels
        if pixels > MAX_PIXELS_PER_PAGE or total_pixels > MAX_TOTAL_PIXELS:
            raise ValueError("PDF raster dimensions exceed TIFF budget")

    with TemporaryDirectory(prefix="pdfhub-frompdf-tiff-") as folder:
        root = Path(folder)
        prefix = root / "page"
        try:
            result = subprocess.run([
                "pdftoppm", "-f", "1", "-l", str(len(pdf.pages)),
                "-r", str(dpi), "-png", str(source), str(prefix),
            ], shell=False, check=False, timeout=75,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, preexec_fn=_child_limits,
                env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("PDF TIFF rasterizer is unavailable or exceeded limits") from exc
        if result.returncode:
            raise ValueError("PDF rasterization rejected the document")
        files = sorted(root.iterdir(), key=lambda p: p.name)
        by_number: dict[int, Path] = {}
        for path in files:
            if path.is_symlink() or not path.is_file():
                raise ValueError("TIFF rasterizer produced unsafe page output")
            match = re.fullmatch(r"page-(0*[1-9][0-9]*)\.png", path.name)
            if not match:
                raise ValueError("TIFF rasterizer produced unexpected artifact")
            number = int(match.group(1))
            if number in by_number or not 1 <= number <= len(pdf.pages):
                raise ValueError("PDF raster output page numbering is invalid")
            if not 10 <= path.stat().st_size <= MAX_INTERMEDIATE:
                raise ValueError("PDF raster output exceeds per-page limits")
            by_number[number] = path
        if set(by_number) != set(range(1, len(pdf.pages) + 1)):
            raise ValueError("Rasterized PDF omitted or duplicated pages")
        frames = []
        try:
            for number in range(1, len(pdf.pages) + 1):
                try:
                    with Image.open(by_number[number]) as frame:
                        if (frame.format != "PNG" or getattr(frame, "n_frames", 1) != 1
                                or frame.width * frame.height > MAX_PIXELS_PER_PAGE):
                            raise ValueError("Native PNG intermediate failed inspection")
                        frames.append(frame.convert("RGB"))
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                    raise ValueError("Rasterized page is invalid") from exc
            temporary = root / "candidate.tiff"
            frames[0].save(
                temporary, format="TIFF", save_all=True,
                append_images=frames[1:], compression="tiff_lzw", dpi=(dpi, dpi),
            )
            if not 32 <= temporary.stat().st_size <= MAX_OUTPUT_BYTES:
                raise ValueError("Multipage TIFF output violates size limits")
            with Image.open(temporary) as proof:
                if proof.format != "TIFF" or getattr(proof, "n_frames", 1) != len(pdf.pages):
                    raise ValueError("Multipage TIFF output lost or added pages")
                for i in range(len(pdf.pages)):
                    proof.seek(i)
                    if proof.width <= 0 or proof.height <= 0:
                        raise ValueError("Multipage TIFF output contains invalid image")
            if output.exists() or output.is_symlink():
                raise ValueError("TIFF output path cannot overwrite an existing artifact")
            with temporary.open("rb") as handle, output.open("xb") as destination:
                while chunk := handle.read(1024 * 1024):
                    destination.write(chunk)
        finally:
            for frame in frames:
                frame.close()
