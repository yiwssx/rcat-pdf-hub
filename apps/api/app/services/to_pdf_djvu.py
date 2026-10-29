"""Fail-closed, single-page, self-contained DjVu to PDF (T90-2).

Uses Debian-maintained DjVuLibre's ddjvu under a separate, time/CPU/memory
and output-size capped subprocess. No shell, external references, indirect or
multipage DjVu, unbounded metadata streams, or production flag activation.

The structural preflight is NOT an AV scan or an independent kernel sandbox.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import resource
import struct
import subprocess

from app.services.to_pdf_engine import _checked_pdf

MAX_DJVU_BYTES = 8 * 1024 * 1024
MAX_CHUNKS = 128
MAX_OUTPUT_BYTES = 40 * 1024 * 1024
MAX_RLIMIT_AS = 768 * 1024 * 1024
MAX_TIME_SECONDS = 20
SUPPORTED_RASTER_CHUNKS = frozenset({
    b"Sjbz", b"BG44", b"FG44", b"BGjp", b"FGjp", b"Smmr", b"BG2k", b"FG2k",
})
BLOCKED_CHUNKS = frozenset({b"INCL", b"DIRM", b"NAVM", b"FORM"})


def validate_single_page_djvu(source: Path) -> tuple[str, ...]:
    """Inspect bounded IFF chunk headers without passing data to native codecs."""
    size = source.stat().st_size
    if not 32 <= size <= MAX_DJVU_BYTES:
        raise ValueError("DjVu source size outside 8 MiB bound")
    data = source.read_bytes()
    if data[:8] != b"AT&TFORM" or data[12:16] != b"DJVU":
        raise ValueError("Only self-contained single-page DJVU FORM is supported")
    declared = struct.unpack_from(">I", data, 8)[0]
    if declared != size - 12:
        raise ValueError("DjVu IFF FORM size does not match source bytes")
    offset = 16
    chunks = []
    seen_info = False
    image_chunks = 0
    while offset < size:
        if len(chunks) >= MAX_CHUNKS or size - offset < 8:
            raise ValueError("Too many or truncated DjVu IFF chunks")
        kind = data[offset:offset + 4]
        length = struct.unpack_from(">I", data, offset + 4)[0]
        if (kind in BLOCKED_CHUNKS or not all(32 <= byte <= 126 for byte in kind)
                or length > MAX_DJVU_BYTES or offset + 8 + length > size):
            raise ValueError("DjVu IFF contains external, nested or oversized data")
        if kind == b"INFO":
            if seen_info or length < 10 or length > 32:
                raise ValueError("Invalid or duplicate DjVu INFO header")
            width, height = struct.unpack_from(">HH", data, offset + 8)
            if not 1 <= width <= 4096 or not 1 <= height <= 4096:
                raise ValueError("DjVu page geometry exceeds pixel limit")
            if width * height > 8_000_000:
                raise ValueError("DjVu decoded pixel count exceeds 8M")
            seen_info = True
        if kind in SUPPORTED_RASTER_CHUNKS:
            image_chunks += 1
        chunks.append(kind.decode("ascii"))
        end = offset + 8 + length
        if length & 1 and end < size:
            # Internal IFF chunks require a zero-byte alignment pad.
            if data[end] != 0:
                raise ValueError("DjVu IFF chunk has invalid alignment padding")
            offset = end + 1
        else:
            # A final odd-length chunk is permitted without physical padding,
            # as some DjVuLibre writers do not append a terminal pad byte.
            offset = end
    if offset != size or not seen_info or image_chunks == 0:
        raise ValueError(
            f"DjVu missing INFO/raster or malformed IFF chunks "
            f"(chunks={chunks!r}, offset={offset}, size={size})"
        )
    return tuple(chunks)


def _set_decoder_limits() -> None:
    """Limit native decoder process, not the API host worker."""
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_RLIMIT_AS, MAX_RLIMIT_AS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def restricted_djvu_to_pdf(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("DjVu source and output must differ")
    validate_single_page_djvu(source)
    # Only the decoder sees untrusted native format data. A private
    # temporary copy blocks any attempt to read adjacent upload files.
    with TemporaryDirectory(prefix="pdfhub-djvu-") as directory:
        folder = Path(directory)
        staged = folder / "image.djvu"
        staged.write_bytes(source.read_bytes())
        converted = folder / "result.pdf"
        cmd = [
            "/usr/bin/ddjvu", "-format=pdf", "-page=1",
            str(staged), str(converted),
        ]
        try:
            done = subprocess.run(
                cmd, cwd=folder,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": str(folder),
                     "TMPDIR": str(folder)},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=MAX_TIME_SECONDS,
                check=False, start_new_session=True, preexec_fn=_set_decoder_limits,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Unavailable or resource-bounded DjVu decoder failed") from exc
        if done.returncode or not converted.is_file():
            raise ValueError("DjVu decoder rejected the single-page document")
        if not 0 < converted.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("DjVu decoder returned oversized or empty PDF")
        _checked_pdf(converted.read_bytes(), output)
