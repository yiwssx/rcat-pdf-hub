"""T09 externally authored HEVC HEIC fixture => PDF in isolated Docker.

The fixture is fetched by GitHub Actions HOST, checksum-pinned by Git blob,
then mounted READ-ONLY inside Docker with --network none and --cap-drop ALL.
This module itself has no network and cannot fetch arbitrary user URLs.

This single upstream developer fixture is not a camera corpus or full release.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops
from pypdf import PdfReader

from app.services.to_pdf_heif_native import _checked_heif_container, heif_to_pdf

EXTERNAL_HEIC = Path("/fixtures/rainbow-451x461.heic")
EXPECTED_BYTES = 7080


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while data := source.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def main() -> int:
    status = {"test": "T09 independent upstream HEIC-to-PDF", "result": "BLOCKED"}
    try:
        if EXTERNAL_HEIC.is_symlink() or not EXTERNAL_HEIC.is_file():
            raise ValueError("A pinned, read-only, upstream HEIC fixture is required")
        if EXTERNAL_HEIC.stat().st_size != EXPECTED_BYTES:
            raise ValueError("Pinned external HEIC length differs")
        before = _sha256(EXTERNAL_HEIC)
        _checked_heif_container(EXTERNAL_HEIC, suffix=".heic")
        with TemporaryDirectory(prefix="t90-real-external-heic-") as temp:
            output = Path(temp) / "output.pdf"
            heif_to_pdf(EXTERNAL_HEIC, output, suffix=".heic")
            with output.open("rb") as source:
                reader = PdfReader(source, strict=True)
                if reader.is_encrypted or len(reader.pages) != 1:
                    raise ValueError("External HEIC PDF page count differs")
            if output.stat().st_size < 500:
                raise ValueError("External HEIC generated empty PDF")
            preview = Path(temp) / "page"
            job = subprocess.run(
                ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png",
                 "-scale-to", "420", str(output), str(preview)],
                capture_output=True, check=False, timeout=25,
            )
            if job.returncode != 0:
                raise ValueError("External HEIC PDF was not rasterizable")
            with Image.open(preview.with_suffix(".png")) as opened:
                rgb = opened.convert("RGB")
                try:
                    white = Image.new("RGB", rgb.size, "white")
                    try:
                        if not ImageChops.difference(rgb, white).getbbox():
                            raise ValueError("External HEIC PDF looks blank")
                        unique = rgb.getcolors(maxcolors=rgb.width * rgb.height + 1)
                        if unique is None or len(unique) < 20:
                            raise ValueError("External HEIC PDF lost chart colors")
                    finally:
                        white.close()
                finally:
                    rgb.close()
            if _sha256(EXTERNAL_HEIC) != before:
                raise ValueError("Read-only upstream HEIC unexpectedly changed")
            status = {
                "test": "T09 independent upstream HEIC-to-PDF",
                "result": "PASS",
                "fixture": "strukturag/libheif tests/data/rainbow-451x461.heic at v1.23.7",
                "source_git_blob": "6691f50f39bd69871a2abe284de2ef9f5243bc66",
                "source_sha256": before,
                "output_sha256": _sha256(output),
                "pages": 1,
                "visible_raster_checked": True,
                "network_disabled": True,
                "note": "Upstream developer sample only; no HEIC phone-photo corpus, orientation/ICC, RCAT owner or production certification.",
            }
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        status.update(result="FAIL", error_category=type(exc).__name__,
                      reason=str(exc)[:200])
    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
