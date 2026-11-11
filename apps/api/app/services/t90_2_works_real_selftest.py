"""T34 real upstream Microsoft Works 3.0–6.0 -> ODT -> PDF through native sidecar.

All four fixtures are immutable LibreOffice/WriterPerfect test data from:
https://github.com/LibreOffice/core/tree/fac2bcb8ce6c81bda79b624e000c293fcdf1e7e4/writerperfect/qa/unit/data/writer/libwps/pass
Fetched on the disposable CI HOST by exact commit, Git blob checked, mounted
read-only into a non-root, cap-dropped native-only Docker container. The
decoder can talk only to a private, CI-local Gotenberg instance, not Internet.
This checks *accepted readable subset*, not full original Works layout, Thai
font fidelity, RCAT operator/host approval or general WPS Office compatibility.
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

from app.services.to_pdf_wps_native import wps_works_to_pdf

FIXTURES = {
    "Works_3.0.wps": (3584, "74f46091e6683e8ae1b1d0240ea695d29b44a84f"),
    "Works_4.5.wps": (4608, "65c25a002dd51fba883d7903f1c376a8b4cb619d"),
    "Works_5.0.wps": (6144, "97bb269f36513bee813010256c422a69fe21349b"),
    "Works_6.0.wps": (13824, "d0a40c4c0300e4c6b4b5f975994b065cb4d6278f"),
}
FIXTURE_DIR = Path("/fixtures")
MAX_PDF_BYTES = 40 * 1024 * 1024


def _blob_sha1(blob: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(blob)).encode("ascii") + b"\0" + blob).hexdigest()


def _pdf_proof(path: Path, workspace: Path, ordinal: int) -> dict:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-") or not 1000 <= len(data) <= MAX_PDF_BYTES:
        raise ValueError("Works converter returned an invalid or empty PDF")
    with path.open("rb") as fd:
        pdf = PdfReader(fd, strict=True)
        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 40:
            raise ValueError("Works converted PDF page inventory is invalid")
        page_count = len(pdf.pages)
        text = "".join(page.extract_text() or "" for page in pdf.pages)
        if len(text.strip()) < 5:
            raise ValueError("Works converted PDF has no readable text")
    prefix = workspace / f"works-{ordinal}-page1"
    job = subprocess.run(
        ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png",
         "-scale-to", "420", str(path), str(prefix)],
        timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    if job.returncode:
        raise ValueError("Works converted PDF cannot be rasterized")
    with Image.open(prefix.with_suffix(".png")) as preview:
        rgb = preview.convert("RGB")
        white = Image.new("RGB", rgb.size, "white")
        try:
            if not ImageChops.difference(rgb, white).getbbox():
                raise ValueError("Works converted PDF page is visually blank")
        finally:
            white.close()
            rgb.close()
    return {"pages": page_count, "pdf_sha256": hashlib.sha256(data).hexdigest(),
            "text_characters": len(text)}


def main() -> int:
    summary: dict[str, object] = {
        "test": "T34 actual LibreOffice upstream Works WPS -> ODT -> PDF",
        "status": "FAIL", "cases": [], "not_a_rcat_host_or_typography_certificate": True,
    }
    cases: list[dict] = []
    try:
        with TemporaryDirectory(prefix="pdfhub-real-works-") as directory:
            folder = Path(directory)
            for i, (filename, (expected_bytes, expected_blob)) in enumerate(FIXTURES.items()):
                source = FIXTURE_DIR / filename
                if source.is_symlink() or not source.is_file():
                    raise ValueError("Works source is not a regular read-only fixture")
                payload = source.read_bytes()
                if len(payload) != expected_bytes or _blob_sha1(payload) != expected_blob:
                    raise ValueError("Pinned upstream Works sample changed: " + filename)
                target = folder / f"{i}-works.pdf"
                item: dict[str, object] = {
                    "source": filename,
                    "git_blob": expected_blob,
                    "source_sha256": hashlib.sha256(payload).hexdigest(),
                }
                try:
                    wps_works_to_pdf(source, target)
                    item.update(result="PASS", **_pdf_proof(target, folder, i))
                except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                    # Nonblank result is mandatory; unsupported Works variants
                    # remain visibly unsupported and are NOT silently skipped.
                    if target.exists():
                        target.unlink()
                    item.update(result="UNSUPPORTED", reason=str(exc)[:160])
                if hashlib.sha256(source.read_bytes()).hexdigest() != item["source_sha256"]:
                    raise ValueError("Works fixture unexpectedly changed")
                cases.append(item)

            # Neither a bad synthetic file nor a WPS Office extension spoof
            # may produce a claimed success by accidentally writing blank ODT.
            forged = folder / "invalid.wps"
            forged.write_bytes(b"invalid Microsoft Works format" * 50)
            invalid_out = folder / "invalid.pdf"
            try:
                wps_works_to_pdf(forged, invalid_out)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                if invalid_out.exists():
                    raise ValueError("Forged WPS left an output PDF")
                cases.append({"source": "invalid.wps", "result": "CORRUPT_REJECTED"})
            else:
                raise ValueError("Forged WPS produced an accepted PDF")

        if not any(case.get("result") == "PASS" for case in cases):
            raise ValueError("No authentic Works version produced a nonblank PDF")
        summary.update(status="PASS", cases=cases, network_scope="isolated-private-Gotenberg-only")
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        summary.update(error_type=type(exc).__name__, reason=str(exc)[:240], cases=cases)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
