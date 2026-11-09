"""M32 bounded PDF structure recovery using installed qpdf.

This repairs/rebuilds PDF object and xref structure where qpdf can decode it;
it cannot reconstruct missing content, recover encryption keys, undo deleted
pages or guarantee forensic integrity of severely damaged documents.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader

from app.services.pdf_tools import _run

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 48 * 1024 * 1024
MAX_PAGES = 200


def _try_reader(path: Path) -> PdfReader | None:
    try:
        return PdfReader(str(path), strict=False)
    except Exception:
        return None


def repair_pdf_structure(source: Path, destination: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("M32 repair input and output must be separate regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("M32 source exceeds structural repair limits")
    with source.open("rb") as inp:
        if inp.read(5) != b"%PDF-":
            raise ValueError("M32 only accepts identifiable PDF input")
    source_reader = _try_reader(source)
    if source_reader is not None:
        if source_reader.is_encrypted:
            raise ValueError("Encrypted PDF repair requires an authorized password workflow")
        try:
            if (source_reader.trailer["/Root"].get("/Perms")
                    or source_reader.trailer["/Root"].get("/AcroForm")):
                raise ValueError("Signed or interactive PDF forms require specialist recovery")
            if not 1 <= len(source_reader.pages) <= MAX_PAGES:
                raise ValueError("M32 input page count exceeds budget")
        except (KeyError, TypeError):
            source_reader = None

    with TemporaryDirectory(prefix="pdfhub-m32-repair-") as scratch:
        candidate = Path(scratch) / "rebuilt.pdf"
        # qpdf normally performs xref recovery, and never runs external scripts.
        # --warning-exit-0 tolerates recoverable warnings; parse and inspect
        # the output independently before making the artifact visible.
        _run([
            "qpdf", "--warning-exit-0", "--object-streams=disable",
            "--stream-data=compress", str(source), str(candidate),
        ], timeout=180)
        if (not candidate.is_file()
                or not 100 <= candidate.stat().st_size <= MAX_OUTPUT_BYTES):
            raise ValueError("M32 rebuilt PDF outside output budget")
        with candidate.open("rb") as fh:
            if fh.read(5) != b"%PDF-":
                raise ValueError("M32 repair produced a non-PDF file")
        output = PdfReader(str(candidate), strict=True)
        if output.is_encrypted or not 1 <= len(output.pages) <= MAX_PAGES:
            raise ValueError("M32 repair output unreadable or excessive")
        root = output.trailer["/Root"]
        if root.get("/Perms") or root.get("/AcroForm"):
            raise ValueError("M32 repair cannot certify signed or interactive forms")
        if source_reader is not None:
            if len(source_reader.pages) != len(output.pages):
                raise ValueError("M32 repair unexpectedly lost source pages")
            for before, after in zip(source_reader.pages, output.pages, strict=True):
                if (tuple(before.mediabox) != tuple(after.mediabox)
                        or tuple(before.cropbox) != tuple(after.cropbox)):
                    raise ValueError("M32 repair changed page geometry")
                lhs = before.get_contents()
                rhs = after.get_contents()
                if (lhs.get_data() if lhs else b"") != (rhs.get_data() if rhs else b""):
                    raise ValueError("M32 repair changed PDF page content streams")
        candidate.replace(destination)
