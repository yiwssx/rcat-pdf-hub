"""T30 genuine MIT-licensed CHM (LZX) source -> offline HTML -> PDF.

Fixture: bwhitn/pylibmspack tests/fixtures/sample.chm at immutable source
commit 3cf1091492467ec100f0435e786eb29136ffc080, Git Blob
dca0776bc86f555c8e5ce516959c215e17bf893a (414860 bytes).
Source is fetched/validated by ephemeral Actions HOST; the native Docker
decoder only sees a read-only input and private, internal Gotenberg.
This tests a legitimate CHM subset, not all legacy charset/TOC variants,
RCAT host/SSO, arbitrary Internet fetching or production release.
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
from app.services.to_pdf_chm_native import chm_to_pdf
from app.services.to_pdf_chm_worker import _read_chm  # diagnostic inside isolated CI-only container

SOURCE = Path("/fixtures/sample.chm")
GIT_BLOB = "dca0776bc86f555c8e5ce516959c215e17bf893a"
SIZE = 414860


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def main() -> int:
    result: dict[str, object] = {
        "test": "T30 independent real LZX Microsoft HTML Help to PDF",
        "status": "FAIL",
        "upstream": "bwhitn/pylibmspack sample.chm (MIT)",
        "not_rcat_host_or_thai_charset_certification": True,
    }
    try:
        if SOURCE.is_symlink() or not SOURCE.is_file():
            raise ValueError("Pinned CHM sample is not a regular file")
        src = SOURCE.read_bytes()
        if len(src) != SIZE or git_blob_sha(src) != GIT_BLOB or not src.startswith(b"ITSF"):
            raise ValueError("Real CHM sample failed immutable Git object validation")
        original_sha256 = hashlib.sha256(src).hexdigest()
        # Diagnose the exact accepted/denied archive shape *only within the*
        # unprivileged, network-denied CI native decoder. Never run this
        # ctypes parser in the application's credential-bearing RQ worker.
        try:
            decoded_preview = _read_chm(SOURCE)
            if not decoded_preview.strip():
                raise ValueError("CHM isolated direct parser produced empty HTML")
        except Exception as exc:
            raise ValueError("Public fixture native CHM diagnosis: " + str(exc)[:160]) from exc
        with TemporaryDirectory(prefix="pdfhub-chm-real-") as folder:
            workspace = Path(folder)
            pdf_path = workspace / "sample.pdf"
            chm_to_pdf(SOURCE, pdf_path)
            if not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
                raise ValueError("Real CHM generated absent/blank PDF")
            with pdf_path.open("rb") as stream:
                pdf = PdfReader(stream, strict=True)
                if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 300:
                    raise ValueError("Real CHM PDF has invalid page inventory")
                pages = len(pdf.pages)
                text = "".join(p.extract_text() or "" for p in pdf.pages)
                if len(text.strip()) < 30:
                    raise ValueError("Real CHM PDF lost printable document text")
            prefix = workspace / "first-page"
            proc = subprocess.run(
                ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png",
                 "-scale-to", "420", str(pdf_path), str(prefix)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=30,
            )
            if proc.returncode:
                raise ValueError("Real CHM PDF cannot be rasterized")
            with Image.open(prefix.with_suffix(".png")) as opened:
                rendered = opened.convert("RGB")
                white = Image.new("RGB", rendered.size, "white")
                try:
                    if not ImageChops.difference(rendered, white).getbbox():
                        raise ValueError("Real CHM PDF first page is blank")
                finally:
                    white.close()
                    rendered.close()
            if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != original_sha256:
                raise ValueError("Native CHM importer altered immutable original")
            # A malformed signature-preserving CHM must be refused, not
            # quietly reported as a valid PDF artifact.
            forged = workspace / "spoof.chm"
            forged.write_bytes(b"ITSF" + b"\0" * 200)
            bad_pdf = workspace / "spoof.pdf"
            try:
                chm_to_pdf(forged, bad_pdf)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                if bad_pdf.exists():
                    raise ValueError("Forged CHM left a downloadable PDF")
            else:
                raise ValueError("Forged CHM was accepted")
            result.update(
                status="PASS",
                pages=pages,
                printable_characters=len(text),
                source_sha256=original_sha256,
                pdf_sha256=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                corrupt_fixture_rejected=True,
                nonblank_raster=True,
                network_scope="private-Gotenberg-only",
            )
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        result.update(error_type=type(exc).__name__, reason=str(exc)[:250])
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
