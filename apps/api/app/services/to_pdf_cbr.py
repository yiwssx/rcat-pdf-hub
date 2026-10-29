"""Strict single-volume RAR4 *stored* images-only CBR subset.

A real RAR4 container with method 0x30 (store), no encryption, no split,
no Unicode paths, no compression or native unrar. This is NOT a general CBR
decoder (RAR5 and compressed RAR4 deliberately fail closed).
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import re
import struct
import zipfile
import zlib

RAR4_MAGIC = b"Rar!\x1a\x07\x00"
MAX_ARCHIVE = 25 * 1024 * 1024
MAX_TOTAL_IMAGES = 24 * 1024 * 1024
MAX_ENTRY_BYTES = 12 * 1024 * 1024
MAX_IMAGES = 64
EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def _header(data: bytes, pos: int) -> tuple[int, int, int]:
    if pos + 7 > len(data):
        raise ValueError("Truncated RAR4 block")
    checksum, kind, flags, headsize = struct.unpack_from("<HBHH", data, pos)
    if headsize < 7 or pos + headsize > len(data):
        raise ValueError("RAR4 block size is invalid")
    if (zlib.crc32(data[pos + 2:pos + headsize]) & 0xFFFF) != checksum:
        raise ValueError("RAR4 header CRC mismatch")
    return kind, flags, headsize


def read_stored_rar4_images(source: Path) -> list[tuple[str, bytes]]:
    size = source.stat().st_size
    if not 48 <= size <= MAX_ARCHIVE:
        raise ValueError("RAR4 CBR input exceeds bounded size")
    data = source.read_bytes()
    if not data.startswith(RAR4_MAGIC):
        raise ValueError("Only RAR4 v1.5–4.x containers are accepted")
    pos = len(RAR4_MAGIC)
    kind, flags, headsize = _header(data, pos)
    if kind != 0x73 or flags != 0 or headsize != 13:
        raise ValueError("RAR4 must have a simple nonencrypted single-volume main header")
    if data[pos + 7:pos + 13] != b"\x00" * 6:
        raise ValueError("RAR4 main header has unexpected features")
    pos += headsize
    files: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    total = 0
    while pos < len(data):
        kind, flags, headsize = _header(data, pos)
        if kind == 0x7B:
            if flags != 0 or headsize != 7 or pos + headsize != len(data):
                raise ValueError("RAR4 end block malformed or has trailing content")
            if not files:
                raise ValueError("CBR contains no image entries")
            return files
        if kind != 0x74 or flags != 0x8000 or headsize < 33:
            raise ValueError("Only simple RAR4 stored, nonencrypted image files allowed")
        packed, unpacked, host, file_crc, timestamp, unp_ver, method, name_size, attr = (
            struct.unpack_from("<IIBIIBBHI", data, pos + 7)
        )
        if (packed != unpacked or not 0 < packed <= MAX_ENTRY_BYTES
                or method != 0x30 or host not in (0, 2, 3)
                or unp_ver not in (15, 20, 29, 36)
                or not 1 <= name_size <= 120
                or headsize != 32 + name_size
                or (attr & 0x10 if host != 3 else attr & 0o040000)):
            raise ValueError("RAR4 requires bounded regular stored image files")
        rawname = data[pos + 32:pos + headsize]
        try:
            name = rawname.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("RAR4 filename must use safe ASCII") from exc
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", name)
                or ".." in name or name.casefold() in seen
                or Path(name).suffix.casefold() not in EXTENSIONS):
            raise ValueError("RAR4 entry is not an allowed unique image filename")
        seen.add(name.casefold())
        start = pos + headsize
        end = start + packed
        total += unpacked
        if total > MAX_TOTAL_IMAGES or end > len(data) or len(files) >= MAX_IMAGES:
            raise ValueError("RAR4 archive data or image count exceeds limits")
        payload = data[start:end]
        if zlib.crc32(payload) != file_crc:
            raise ValueError("RAR4 stored file CRC mismatch")
        files.append((name, payload))
        pos = end
    raise ValueError("RAR4 end-of-archive marker missing")


def rar4_stored_cbr_to_pdf(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("CBR source and output must differ")
    images = read_stored_rar4_images(source)
    with TemporaryDirectory(prefix="pdfhub-cbr-rar4-") as folder:
        interim = Path(folder) / "images.cbz"
        with zipfile.ZipFile(interim, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, payload in images:
                archive.writestr(name, payload)
        from app.services.to_pdf_engine import archive_images_to_pdf
        archive_images_to_pdf(interim, output, kind="cbz")
