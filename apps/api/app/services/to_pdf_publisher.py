"""Strict bounded CFB/Publisher container preflight for staged import.

This is a *structural* header/directory guard, NOT an antivirus scan nor a
complete libmspub format validator. LibreOffice executes in the existing
unprivileged, network-isolated Gotenberg container. The default flag stays OFF.
"""
from __future__ import annotations

from pathlib import Path
from struct import unpack_from

MAX_PUB_BYTES = 7 * 1024 * 1024
CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
FREE = 0xFFFFFFFF
END = 0xFFFFFFFE
FAT_MARK = 0xFFFFFFFD


def _ole_sector(data: bytes, number: int, sector_size: int) -> bytes:
    start = 512 + number * sector_size
    end = start + sector_size
    if number >= (len(data) - 512) // sector_size or end > len(data):
        raise ValueError("Publisher OLE sector points outside file")
    return data[start:end]


def validate_publisher_ole(source: Path) -> tuple[str, ...]:
    """Reject spoofed/invalid OLE headers, FAT loops and empty directory trees.

    This limited subset accepts v3 CFB 512-byte sector files with the regular
    FAT stored directly in the header DIFAT and no chained DIFAT sectors.
    Larger/complex CFB variants fail closed rather than risking native parsing.
    """
    size = source.stat().st_size
    if not 1536 <= size <= MAX_PUB_BYTES or size % 512:
        raise ValueError("Publisher input size or sector alignment unsupported")
    data = source.read_bytes()
    if data[:8] != CFB_SIGNATURE:
        raise ValueError("Publisher input is not an OLE compound file")
    major = unpack_from("<H", data, 26)[0]
    byte_order = unpack_from("<H", data, 28)[0]
    sector_shift = unpack_from("<H", data, 30)[0]
    mini_shift = unpack_from("<H", data, 32)[0]
    fat_count = unpack_from("<I", data, 44)[0]
    directory = unpack_from("<I", data, 48)[0]
    difat_count = unpack_from("<I", data, 72)[0]
    sector_count = (size - 512) // 512
    if (major != 3 or byte_order != 0xFFFE or sector_shift != 9
            or mini_shift != 6 or not 1 <= fat_count <= 109
            or difat_count != 0 or directory >= sector_count):
        raise ValueError("Unsupported Publisher OLE header and allocation tables")
    fat_positions = [unpack_from("<I", data, 76 + n * 4)[0]
                     for n in range(fat_count)]
    if len(set(fat_positions)) != len(fat_positions) or any(
            n >= sector_count for n in fat_positions):
        raise ValueError("Invalid Publisher OLE FAT entries")
    fat = []
    for number in fat_positions:
        if number == directory:
            raise ValueError("Publisher OLE directory overlaps FAT sector")
        sector = _ole_sector(data, number, 512)
        fat.extend(unpack_from("<128I", sector))
    if any(fat[number] != FAT_MARK for number in fat_positions):
        raise ValueError("Publisher OLE FAT sector marker mismatch")
    seen = set()
    directory_parts = []
    current = directory
    while current != END:
        if (current in seen or current >= sector_count or
                current in fat_positions or len(seen) >= 64):
            raise ValueError("Publisher OLE invalid directory chain")
        seen.add(current)
        directory_parts.append(_ole_sector(data, current, 512))
        if current >= len(fat):
            raise ValueError("Publisher OLE FAT chain entry outside FAT")
        current = fat[current]
    names = []
    root_count = 0
    streams = 0
    for block in directory_parts:
        for offset in range(0, len(block), 128):
            record = block[offset:offset + 128]
            entry_type = record[66]
            if entry_type == 0:
                continue
            name_len = unpack_from("<H", record, 64)[0]
            if (entry_type not in (1, 2, 5) or name_len < 4
                    or name_len > 64 or name_len % 2):
                raise ValueError("Publisher OLE directory name or type invalid")
            try:
                name = record[:name_len - 2].decode("utf-16-le")
            except UnicodeDecodeError as exc:
                raise ValueError("Publisher OLE directory has invalid Unicode name") from exc
            if not name or record[name_len - 2:name_len] != b"\x00\x00":
                raise ValueError("Publisher OLE directory name missing terminator")
            names.append(name)
            root_count += entry_type == 5
            streams += entry_type == 2
    if root_count != 1 or streams == 0:
        raise ValueError("Publisher OLE is missing root storage or document streams")
    return tuple(names)



def validate_publisher_pdf_pages(pdf: bytes) -> tuple[int, ...]:
    """Fail closed for any visually blank Publisher output page.

    LibreOffice's Publisher import can produce formally valid, rasterizable
    pages with no content. Unlike the shared converter's any-page ink test,
    this strictly bounded PUB subset requires visible ink on *every* page.
    Intentionally blank original pages are outside the accepted subset.
    This does NOT establish geometry, text, font or original-page fidelity.
    """
    import pypdfium2 as pdfium

    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-") or len(pdf) > 40 * 1024 * 1024:
        raise ValueError("Publisher converter returned invalid PDF")
    try:
        document = pdfium.PdfDocument(pdf)
        try:
            count = len(document)
            if not 1 <= count <= 24:
                raise ValueError("Publisher PDF page count exceeds bounded subset")
            visible = []
            for index in range(count):
                page = document[index]
                try:
                    width, height = page.get_size()
                    if not (1 <= width <= 14400 and 1 <= height <= 14400):
                        raise ValueError("Publisher PDF page dimensions unsupported")
                    scale = min(700.0 / max(width, height),
                                max(0.5, 96.0 / max(width, height)))
                    bitmap = page.render(scale=scale, grayscale=True)
                    try:
                        grayscale = bitmap.to_pil().convert("L")
                        try:
                            pixels = grayscale.histogram()
                        finally:
                            grayscale.close()
                        if sum(pixels[:245]) < 10:
                            raise ValueError(
                                f"Publisher PDF page {index + 1} rendered blank; "
                                "source page fidelity cannot be confirmed"
                            )
                        visible.append(index + 1)
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            return tuple(visible)
        finally:
            document.close()
    except ValueError:
        raise
    except Exception:
        raise ValueError("Publisher PDF output could not be visually checked") from None
