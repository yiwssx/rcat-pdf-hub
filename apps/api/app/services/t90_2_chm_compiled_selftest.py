"""T30: true CHM compiler -> libchm LZX -> independently checked HTML -> PDF.

The source is a deterministic two-chapter HTML help project created by the
Free Pascal 'chmcmd' compiler on the disposable CI host. It is neither a
magic-header spoof nor a mock of CHM decoding. No user document is involved.
CHM parser and renderer execute only within the dedicated, nonroot isolated
Docker test container connected to its private, disposable Gotenberg.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from pypdf import PdfReader
from app.services.to_pdf_chm_native import chm_to_pdf, chm_to_safe_html
from app.services.chm_html_boundary import validate_chm_html_fragment

SOURCE = Path("/fixtures/rcat-chaptered.chm")
EXPECTED = ("RCAT T90 CHM chapter one visible content",
            "RCAT T90 CHM chapter two visible content")


def main() -> int:
    report = {"test": "T30 compiled LZX CHM real source-to-PDF", "status": "FAIL"}
    try:
        if SOURCE.is_symlink() or not SOURCE.is_file():
            raise ValueError("Compiled CHM fixture is missing or unsafe")
        data = SOURCE.read_bytes()
        if not 512 <= len(data) <= 2_000_000 or not data.startswith(b"ITSF"):
            raise ValueError("CHM compiler did not produce a real archive")
        source_sha256 = hashlib.sha256(data).hexdigest()
        # Untrusted native decode takes place ONLY in this independent
        # container, never in the user/credential-bearing queue worker.
        html = validate_chm_html_fragment(chm_to_safe_html(SOURCE))
        if not all(token in html for token in EXPECTED):
            raise ValueError("CHM reader omitted or corrupted a known input chapter")
        if html.index(EXPECTED[0]) > html.index(EXPECTED[1]):
            raise ValueError("CHM TOC chapter order was corrupted")
        with TemporaryDirectory(prefix="chm-compiled-golden-") as temp:
            directory = Path(temp)
            pdf_path = directory / "actual.pdf"
            chm_to_pdf(SOURCE, pdf_path)
            if not pdf_path.is_file() or pdf_path.stat().st_size < 1000:
                raise ValueError("CHM adapter did not create usable PDF")
            with pdf_path.open("rb") as stream:
                pdf = PdfReader(stream, strict=True)
                if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 12:
                    raise ValueError("CHM PDF page count/structure invalid")
                text = " ".join(page.extract_text() or "" for page in pdf.pages)
                if not all(token in text for token in EXPECTED):
                    raise ValueError("CHM PDF did not preserve the source text")
                pages = len(pdf.pages)
            if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_sha256:
                raise ValueError("CHM decoder modified read-only source")
            corrupt = directory / "invalid.chm"
            corrupt.write_bytes(b"ITSF" + b"\x00" * 1024)
            malformed_output = directory / "malformed.pdf"
            try:
                chm_to_pdf(corrupt, malformed_output)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                if malformed_output.exists():
                    raise ValueError("Malformed CHM incorrectly wrote PDF output")
            else:
                raise ValueError("Malformed CHM was accepted")
            report.update(status="PASS", pages=pages,
                          original_sha256=source_sha256,
                          output_sha256=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
                          known_source_chapters=2, decoded_html_verified=True,
                          corrupt_rejected=True, compiled_with="Free Pascal chmcmd",
                          not_rcat_host_or_all_legacy_chm_acceptance=True)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        report.update(error=type(error).__name__, reason=str(error)[:280])
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
