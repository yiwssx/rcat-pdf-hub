"""T25 HEIF real native-toolchain → actual PDF conversion acceptance smoke.

Runs in a disposable, non-root, cap-dropped, NO-NETWORK native-only image with
the pinned libheif 1.23.7 decoder. Creates a real uncompressed HEIF fixture,
decodes it through the application's *actual* conversion entry point, checks
PDF structure and page count. It is not a claim about camera HEIC fidelity.
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

from app.services.to_pdf_heif_native import heif_to_pdf, _checked_heif_container

ENCODER = "/opt/pdfhub/heif/bin/heif-enc"


def main() -> int:
    status = {"test": "T25 real HEIF codec-to-PDF", "result": "BLOCKED"}
    try:
        with TemporaryDirectory(prefix="t90-heif-real-") as root:
            folder = Path(root)
            original = folder / "reference.png"
            source = folder / "sample.heif"
            output = folder / "converted.pdf"
            image = Image.new("RGB", (128, 80))
            for y in range(80):
                for x in range(128):
                    image.putpixel((x, y), ((x * 2) % 256, (y * 3) % 256, (x + y) % 256))
            image.save(original)
            image.close()
            proc = subprocess.run(
                [ENCODER, "-U", str(original), "-o", str(source)],
                capture_output=True, text=True, check=False, timeout=25,
            )
            if proc.returncode != 0:
                raise ValueError("Pinned libheif cannot encode independent HEIF fixture")
            _checked_heif_container(source, suffix=".heif")
            heif_to_pdf(source, output, suffix=".heif")
            with output.open("rb") as stream:
                reader = PdfReader(stream, strict=True)
                if reader.is_encrypted or len(reader.pages) != 1:
                    raise ValueError("Application generated wrong HEIF PDF page inventory")
            if output.stat().st_size < 500 or not output.read_bytes().startswith(b"%PDF-"):
                raise ValueError("Application emitted invalid or blank HEIF PDF")
            # A valid PDF header/page count alone cannot detect a blank output.
            # Rasterize the actual converter result and prove the reference
            # gradient survived the native codec-to-PDF rendering pipeline.
            rendered = folder / "proof"
            proof = subprocess.run(
                ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png",
                 "-scale-to", "420", str(output), str(rendered)],
                capture_output=True, check=False, timeout=25,
            )
            if proof.returncode != 0:
                raise ValueError("Generated HEIF PDF could not be visually rasterized")
            with Image.open(rendered.with_suffix(".png")) as image_proof:
                rgb = image_proof.convert("RGB")
                try:
                    background = Image.new("RGB", rgb.size, "white")
                    try:
                        if not ImageChops.difference(rgb, background).getbbox():
                            raise ValueError("Generated HEIF PDF page is visually blank")
                        colors = rgb.getcolors(maxcolors=rgb.width * rgb.height + 1)
                        if colors is None or len(colors) < 20:
                            raise ValueError("Generated HEIF PDF lost source image detail")
                    finally:
                        background.close()
                finally:
                    rgb.close()
            status = {
                "test": "T25 real HEIF codec-to-PDF",
                "result": "PASS",
                "pages": 1,
                "source": "generated lossless 128x80 uncompressed HEIF",
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "visible_raster_checked": True,
                "note": "Generated fixture only; NOT a true external HEIC/HEIF corpus or production API certification",
            }
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        status["result"] = "FAIL"
        status["error_category"] = type(exc).__name__
        status["reason"] = str(exc)[:180]
    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
