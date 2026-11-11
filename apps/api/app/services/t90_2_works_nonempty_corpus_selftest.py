"""T34 genuine Microsoft Works corpus inspection + true source to nonblank PDF.

Read upstream libwps OSS-Fuzz WPS seed corpus downloaded by a disposable CI
host, not a private user file. Every archive entry is bounded and written
as a canonical, non-user-controlled filename in the isolated native container
with no Internet access and private Gotenberg only.

Do NOT count an empty ODT, failed source, renamed DOC or WPS Office content as
a successful Microsoft Works converter. A successful case must be verified
by both libwps wps2text and the actual wps2odt->Gotenberg->PDF path.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile

from pypdf import PdfReader
from app.services.to_pdf_wps_native import wps_works_to_pdf

CORPUS = Path("/fixtures/wpsfuzzer_seed_corpus.zip")
MAX_ARCHIVE = 600_000
MAX_MEMBERS = 150
MAX_ENTRY = 2_000_000
MAX_TOTAL = 10_000_000
MAX_CANDIDATES = 42


def source_text(path: Path) -> str:
    check = subprocess.run(
        ["/usr/bin/wps2text", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=False, timeout=12,
    )
    if check.returncode or len(check.stdout) > 1_000_000:
        return ""
    return check.stdout.decode("utf-8", errors="replace").strip()


def main() -> int:
    record: dict[str, object] = {
        "test": "T34 upstream real Microsoft Works nonempty document to PDF",
        "status": "FAIL",
        "corpus": "libwps SourceForge wpsfuzzer_seed_corpus.zip",
        "no_redistribution_or_production_change": True,
    }
    try:
        if CORPUS.is_symlink() or not CORPUS.is_file() or not 100 < CORPUS.stat().st_size <= MAX_ARCHIVE:
            raise ValueError("Published Works corpus missing or oversized")
        archive_sha = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
        if archive_sha != "95c919a7506f6be30d90c100df6f5fa29bcf9e75a1bbef7a509de65b42e5aa5a":
            raise ValueError("Published Microsoft Works source corpus changed")
        results: list[dict[str, object]] = []
        successes = 0
        readable = 0
        with TemporaryDirectory(prefix="works-real-sources-") as tmp, ZipFile(CORPUS) as archive:
            folder = Path(tmp)
            entries = archive.infolist()
            if not 1 <= len(entries) <= MAX_MEMBERS:
                raise ValueError("OSS-Fuzz archive has unexpected member inventory")
            total = 0
            candidates = 0
            for item in entries:
                if item.is_dir() or not item.filename.lower().endswith(".wps"):
                    continue
                if (item.flag_bits & 0x1 or stat.S_ISLNK(item.external_attr >> 16)
                    or not 16 <= item.file_size <= MAX_ENTRY or item.compress_size == 0
                    or item.file_size > 100 * item.compress_size):
                    raise ValueError("Corpus entry violates safe compressed document policy")
                total += item.file_size
                if total > MAX_TOTAL:
                    raise ValueError("Corpus uncompressed data exceeds safe budget")
                if candidates >= MAX_CANDIDATES:
                    break
                candidates += 1
                name = f"works-original-{candidates:03d}.wps"
                src = folder / name
                src.write_bytes(archive.read(item))
                before = hashlib.sha256(src.read_bytes()).hexdigest()
                raw = source_text(src)
                if len(raw) < 12:
                    results.append({"source_id": candidates, "result": "NO_REFERENCE_TEXT",
                                    "source_sha256": before})
                    continue
                readable += 1
                dst = folder / (name + ".pdf")
                try:
                    wps_works_to_pdf(src, dst)
                    with dst.open("rb") as fd:
                        pdf = PdfReader(fd, strict=True)
                        if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 20:
                            raise ValueError("Works PDF page structure invalid")
                        printed = " ".join(page.extract_text() or "" for page in pdf.pages)
                        if len(printed.strip()) < 12:
                            raise ValueError("Works source-to-PDF dropped printable text")
                        # Reproduce positive printable characters rather than
                        # relying on blank pages, image-only or magic headers.
                        normalized = set(raw.split())
                        overlap = [w for w in normalized if len(w) >= 5 and w in printed]
                        if not overlap:
                            raise ValueError("No readable source words survived PDF text extraction")
                        page_count = len(pdf.pages)
                    successes += 1
                    results.append({"source_id": candidates, "result": "PASS",
                                    "source_sha256": before,
                                    "pdf_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
                                    "pages": page_count, "matched_source_words": len(overlap)})
                except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                    results.append({"source_id": candidates, "result": "UNSUPPORTED",
                                    "reason": str(exc)[:100], "source_sha256": before})
                if hashlib.sha256(src.read_bytes()).hexdigest() != before:
                    raise ValueError("Native Works reader unexpectedly modified source")
                if successes >= 4:
                    break
        record.update(corpus_sha256=archive_sha, scanned=candidates,
                      readable=readable, converted=successes, cases=results[:MAX_CANDIDATES])
        if successes < 1:
            raise ValueError("No independently readable Microsoft Works original produced a verified PDF")
        record["status"] = "PASS"
        record["not_all_works_generations_or_rcat_certification"] = True
    except (BadZipFile, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        record.update(error_type=type(exc).__name__, reason=str(exc)[:240])
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0 if record["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
