"""T33 exact signed URL fetcher + bounded public HTTPS -> offline PDF E2E.

Runs only in disposable GitHub CI Docker-internal application network; the
separate fetcher has a kernel-host firewall on its static egress bridge.
It checks the real URL-to-PDF adapter, not a fake HTTP response or screenshot.
This is disposable-runner source MAC, NOT an attestation of RCAT's host rules.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from pypdf import PdfReader
from app.services.to_pdf_url import url_to_pdf
from app.services.url_fetch_core import validate_public_https_url

NEGATIVE = ("http://example.org/", "https://localhost/",
            "https://127.0.0.1/", "https://169.254.169.254/latest/meta-data/",
            "https://example.org:8080/", "https://example.org/secret?token=abc",
            "https://user:secret@example.org/", "https://example.internal/")


def main() -> int:
    result: dict[str, object] = {"test": "T33 public HTTPS content-only URL -> real PDF",
                                 "status": "FAIL"}
    try:
        rejected = 0
        for url in NEGATIVE:
            try:
                validate_public_https_url(url)
            except ValueError:
                rejected += 1
            else:
                raise ValueError("Unsafe SSRF/URL pattern escaped validation")
        with TemporaryDirectory(prefix="t90-url-real-ci-") as folder:
            target = Path(folder) / "public-article.pdf"
            url_to_pdf("https://example.org/", target)
            if not target.is_file() or target.stat().st_size < 1000:
                raise ValueError("URL adapter failed to render an actual PDF")
            with target.open("rb") as fd:
                pdf = PdfReader(fd, strict=True)
                if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 10:
                    raise ValueError("URL PDF page count invalid")
                txt = " ".join(page.extract_text() or "" for page in pdf.pages)
                normalized = " ".join(txt.split())
                if "Example Domain" not in normalized:
                    # The public IANA example.org page contains no secrets.
                    # This is a CI-only diagnostic of actual extracted text,
                    # not a log of arbitrary user-provided URLs or documents.
                    raise ValueError("Real public example.org text absent; pdf_extract="
                                     + repr(normalized[:180]))
                pages = len(pdf.pages)
            result.update(status="PASS", pages=pages, unsafe_urls_rejected=rejected,
                          source="https://example.org/",
                          output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                          signed_sidecar=True, strict_pdf=True, no_remote_browser=True,
                          not_rcat_host_firewall_attestation=True)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        result.update(error_type=type(exc).__name__, reason=str(exc)[:250])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
