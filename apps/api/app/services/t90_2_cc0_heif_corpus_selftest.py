"""T09/T25 independent CC0 HEIC/HEIF -> native PDF corpus in offline Docker.

Fixtures are fetched and SHA256-pinned by the disposable CI HOST, never by
the non-root, cap-dropped, network-denied decoder. No user media or camera
photos. Source: https://heic.fyi/heic-sample-files (CC0 1.0).
Acceptance is intentionally scoped to primary-image text/chart raster,
landscape orientation, safe multi-image behavior and malformed-file rejection.
Does not certify HDR/Display P3/device-specific metadata or RCAT Production.
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
from app.services.to_pdf_heif_native import heif_to_pdf

DIR = Path("/fixtures")
SHA256 = {
    "orientation-6.heic": "80b615ae433d7ec53e9aaaeee081ecd11c0d9931350da13d6ce4e2b363d12c12",
    "generic-mif1-brand.heif": "1c3cb942025bce0d3d45c7d98ecb94846c9da760700d5c025d3e80852027dede",
    "multi-image-burst.heic": "a3f76e9b8552b1deca83b7196bfa637e2742894b7ff2a17deddcef24f010d813",
    "broken-ftyp.heic": "142c0331e97c23ea0e094e9cac529dcba098968ab447a690179d0664790909a9",
    "broken-truncated.heic": "7c95d6452f3dadf6da09a5dce3e05f81d26b6043fee00026fbd67a5158d555e0",
}


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fd:
        while chunk := fd.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _pdf_summary(path: Path, directory: Path, *, orientation: bool = False) -> int:
    with path.open("rb") as fd:
        pdf = PdfReader(fd, strict=True)
        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 8:
            raise ValueError("Decoded PDF is encrypted, empty or excessive")
        pages = len(pdf.pages)
    for i in range(1, pages + 1):
        base = directory / ("rendered-" + str(i))
        run = subprocess.run(
            ["pdftoppm", "-f", str(i), "-l", str(i), "-singlefile",
             "-png", "-scale-to", "450", str(path), str(base)],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if run.returncode != 0:
            raise ValueError("Converted HEIF PDF page could not rasterize")
        with Image.open(base.with_suffix(".png")) as pic:
            rgb = pic.convert("RGB")
            try:
                white = Image.new("RGB", rgb.size, "white")
                try:
                    box = ImageChops.difference(rgb, white).getbbox()
                    if not box:
                        raise ValueError("Converted HEIF PDF has a blank page")
                    colors = rgb.getcolors(maxcolors=rgb.width * rgb.height + 1)
                    if colors is None or len(colors) < 16:
                        raise ValueError("Converted HEIF chart lost image details")
                    if orientation and i == 1:
                        # This external chart has expected upright landscape
                        # dimensions 1200 x 800. Wrong 90-degree rotation must
                        # not produce a portrait image inside the A4 PDF.
                        width, height = box[2] - box[0], box[3] - box[1]
                        if width < height * 1.15:
                            raise ValueError("HEIF orientation-6 decoded portrait rather than landscape")
                finally:
                    white.close()
            finally:
                rgb.close()
    return pages


def main() -> int:
    report: dict[str, object] = {
        "test": "T09/T25 independent CC0 HEIC/HEIF offline source-to-PDF",
        "status": "FAIL",
        "source": "heic.fyi CC0 fixture corpus, published 2026-10-11",
        "not_camera_or_rcat_host_certification": True,
    }
    cases: list[dict[str, object]] = []
    try:
        for filename, expected in SHA256.items():
            source = DIR / filename
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing regular, read-only CC0 fixture: " + filename)
            if _digest(source) != expected:
                raise ValueError("CC0 fixture SHA256 changed: " + filename)

        with TemporaryDirectory(prefix="pdfhub-cc0-heif-") as temp:
            root = Path(temp)
            for filename, expected in SHA256.items():
                source = DIR / filename
                output = root / (filename.replace(".", "-") + ".pdf")
                suffix = source.suffix
                case: dict[str, object] = {
                    "filename": filename,
                    "source_sha256": expected,
                }
                if filename.startswith("broken-"):
                    try:
                        heif_to_pdf(source, output, suffix=suffix)
                    except (ValueError, OSError):
                        if output.exists():
                            raise ValueError("Rejected corrupt HEIC left a partial PDF")
                        case["result"] = "CORRUPT_REJECTED"
                    else:
                        raise ValueError("Corrupt HEIC unexpectedly produced an accepted PDF")
                elif filename.startswith("multi-image-"):
                    try:
                        heif_to_pdf(source, output, suffix=suffix)
                    except (ValueError, OSError):
                        if output.exists():
                            raise ValueError("Rejected HEIC burst left partial PDF")
                        case["result"] = "UNSUPPORTED_FAIL_CLOSED"
                    else:
                        count = _pdf_summary(output, root)
                        if count != 4:
                            raise ValueError("HEIC burst silently dropped image items")
                        case["result"] = "FOUR_IMAGES_RENDERED"
                        case["pdf_sha256"] = _digest(output)
                else:
                    heif_to_pdf(source, output, suffix=suffix)
                    count = _pdf_summary(
                        output, root, orientation=filename == "orientation-6.heic"
                    )
                    if count != 1:
                        raise ValueError("Single-image CC0 fixture gave wrong PDF page count")
                    case["result"] = "PASS"
                    case["pages"] = count
                    case["pdf_sha256"] = _digest(output)
                if _digest(source) != expected:
                    raise ValueError("Input media altered by native converter")
                cases.append(case)
        report["status"] = "PASS"
        report["cases"] = cases
        report["network_disabled"] = True
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        report["error_type"] = type(exc).__name__
        report["reason"] = str(exc)[:240]
        report["cases"] = cases
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
