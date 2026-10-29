"""Shared, bounded Office/Pages ZIP metadata validation (no cyclic imports)."""
import zipfile

MAX_OFFICE_ZIP_ENTRIES = 2048
MAX_OFFICE_ZIP_UNCOMPRESSED = 256 * 1024 * 1024
MAX_OFFICE_ZIP_ENTRY_BYTES = 64 * 1024 * 1024
MAX_OFFICE_ZIP_EXPANSION = 1000


def _checked_office_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Reject malformed, duplicate, active or adversarial archive entries."""
    infos = archive.infolist()
    if not 1 <= len(infos) <= MAX_OFFICE_ZIP_ENTRIES:
        raise ValueError("Office archive contains too many entries")
    seen: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in infos:
        name = info.filename
        parts = name.rstrip("/").split("/")
        mode = (info.external_attr >> 16) & 0o170000
        if (
            not name or name.startswith("/") or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in parts)
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or name.casefold() in seen
            or mode not in (0, 0o100000, 0o040000)
            or (mode == 0o040000 and not info.is_dir())
            or info.flag_bits & 1
            or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            or info.file_size > MAX_OFFICE_ZIP_ENTRY_BYTES
            or info.file_size > (info.compress_size + 1024) * MAX_OFFICE_ZIP_EXPANSION
        ):
            raise ValueError("Unsafe Office archive entry")
        total += info.file_size
        if total > MAX_OFFICE_ZIP_UNCOMPRESSED:
            raise ValueError("Office archive expands beyond allowed size")
        if name.casefold().endswith("vbaproject.bin") or "/activex/" in ("/" + name.casefold()):
            raise ValueError("Macro/ActiveX components are not allowed in macro-free Office files")
        seen[name.casefold()] = info
    return seen
