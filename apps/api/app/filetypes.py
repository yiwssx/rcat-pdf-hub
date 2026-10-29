from pathlib import Path
import zipfile

from fastapi import HTTPException

from app.config import get_settings

PDF = "application/pdf"
SIGNATURE_TYPES = {
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".webp": ("image/webp", (b"RIFF",)),
    ".tif": ("image/tiff", (b"II*\x00", b"MM\x00*")),
    ".tiff": ("image/tiff", (b"II*\x00", b"MM\x00*")),
    ".bmp": ("image/bmp", (b"BM",)),
}
OOXML_ROOTS = {
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "word/"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xl/"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "ppt/"),
}
ODF_TYPES = {
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
}
OLE_TYPES = {
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
    ".ppt": "application/vnd.ms-powerpoint",
}
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _head(path: Path, size: int = 16) -> bytes:
    with path.open("rb") as fh:
        return fh.read(size)


# Strictly bound the *declared* contents before an Office converter opens the
# package. This is a metadata preflight, not a decompression or antivirus scan.
MAX_OFFICE_ZIP_ENTRIES = 2048
MAX_OFFICE_ZIP_UNCOMPRESSED = 256 * 1024 * 1024
MAX_OFFICE_ZIP_ENTRY_BYTES = 64 * 1024 * 1024
MAX_OFFICE_ZIP_EXPANSION = 1000
OOXML_MAIN_PARTS = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
    ".pptx": "ppt/presentation.xml",
}


def _checked_office_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Reject dangerous or implausible Office ZIP member metadata, without extraction.

    Converter sandboxing, AV and runtime/memory limits remain independent gates.
    """
    infos = archive.infolist()
    if not 1 <= len(infos) <= MAX_OFFICE_ZIP_ENTRIES:
        raise ValueError("Office archive contains too many entries")
    seen: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in infos:
        name = info.filename
        # Directories are permitted; traversals, Windows paths, duplicates,
        # symlinks and encrypted/unusual compression are not.
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
        # Macro-enabled binaries are not valid content for macro-free OOXML.
        if name.casefold().endswith("vbaproject.bin") or "/activex/" in ("/" + name.casefold()):
            raise ValueError("Macro/ActiveX components are not allowed in macro-free Office files")
        seen[name.casefold()] = info
    return seen


def _valid_zip_member(path: Path, suffix: str) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = _checked_office_members(archive)
            return ("[content_types].xml" in names
                    and OOXML_MAIN_PARTS[suffix].casefold() in names)
    except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, EOFError):
        return False


def validate_uploaded_file(path: Path, original_name: str) -> str:
    suffix = Path(original_name).suffix.lower()
    head = _head(path)

    if suffix == ".pdf":
        if not head.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="File extension is PDF but the file signature is not PDF")
        return PDF

    # T90-2 high-risk archives are never extracted during upload inspection.
    if suffix in {".zip", ".cbz"}:
        if not get_settings().to_pdf_tools_enabled:
            raise HTTPException(status_code=415, detail="Staged archive conversion disabled")
        if not head.startswith(b"PK\\x03\\x04") or path.stat().st_size > 30 * 1024 * 1024:
            raise HTTPException(status_code=415, detail="Invalid or oversized archive signature")
        if not zipfile.is_zipfile(path):
            raise HTTPException(status_code=415, detail="Invalid image ZIP archive")
        return "application/zip" if suffix == ".zip" else "application/vnd.comicbook+zip"

    if suffix in {".html", ".xml", ".eml"}:
        if not get_settings().to_pdf_tools_enabled:
            raise HTTPException(status_code=415, detail="Staged document conversion disabled")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Staged document exceeds 2 MiB")
        try:
            text = path.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="Only UTF-8 documents are supported") from exc
        if any(ord(char) < 32 and char not in "\\n\\r\\t" for char in text):
            raise HTTPException(status_code=415, detail="Unsafe staged document control character")
        if suffix == ".xml" and not text.lstrip().startswith("<"):
            raise HTTPException(status_code=415, detail="XML source does not contain markup")
        if suffix == ".eml" and ":" not in text[:2000]:
            raise HTTPException(status_code=415, detail="EML missing message headers")
        return {".html": "text/html", ".xml": "application/xml", ".eml": "message/rfc822"}[suffix]

    # T90-2 staged formats are rejected at upload until an operator opts in.
    if suffix in {".txt", ".csv", ".md", ".gif", ".jfif"}:
        if not get_settings().to_pdf_tools_enabled:
            raise HTTPException(status_code=415, detail="Staged conversion upload type is disabled")
        if suffix in {".gif", ".jfif"}:
            valid = (head.startswith((b"GIF87a", b"GIF89a")) if suffix == ".gif"
                     else head.startswith(b"\xff\xd8\xff"))
            if not valid:
                raise HTTPException(status_code=415, detail="Image signature does not match extension")
            return "image/gif" if suffix == ".gif" else "image/jpeg"
        if path.stat().st_size > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Text conversion input exceeds 2 MiB")
        try:
            text = path.read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="Only UTF-8 text is supported") from exc
        if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
            raise HTTPException(status_code=415, detail="Unsafe text control character")
        return {".txt": "text/plain", ".csv": "text/csv", ".md": "text/markdown"}[suffix]

    if suffix in SIGNATURE_TYPES:
        media_type, signatures = SIGNATURE_TYPES[suffix]
        if suffix == ".webp":
            valid = head.startswith(b"RIFF") and head[8:12] == b"WEBP"
        else:
            valid = any(head.startswith(signature) for signature in signatures)
        if not valid:
            raise HTTPException(status_code=415, detail=f"File signature does not match {suffix}")
        return media_type

    if suffix in OOXML_ROOTS:
        media_type, root = OOXML_ROOTS[suffix]
        if not _valid_zip_member(path, suffix):
            raise HTTPException(status_code=415, detail=f"Invalid {suffix} Office document")
        return media_type

    if suffix in ODF_TYPES:
        try:
            with zipfile.ZipFile(path) as archive:
                members = _checked_office_members(archive)
                mimetype_info = members.get("mimetype")
                if mimetype_info is None or mimetype_info.file_size > 256:
                    raise ValueError("Invalid OpenDocument mimetype entry")
                # Never decompress unbounded attacker-controlled mimetype bytes.
                mimetype = archive.read(mimetype_info).decode("ascii").strip()
        except (KeyError, zipfile.BadZipFile, OSError, ValueError, RuntimeError, UnicodeError, EOFError):
            raise HTTPException(status_code=415, detail=f"Invalid {suffix} OpenDocument file")
        if mimetype != ODF_TYPES[suffix]:
            raise HTTPException(status_code=415, detail=f"OpenDocument type does not match {suffix}")
        return ODF_TYPES[suffix]

    if suffix in OLE_TYPES:
        if not head.startswith(OLE_SIGNATURE):
            raise HTTPException(status_code=415, detail=f"Invalid legacy Office document: {suffix}")
        return OLE_TYPES[suffix]

    if suffix == ".rtf":
        if not head.startswith(b"{\\rtf"):
            raise HTTPException(status_code=415, detail="Invalid RTF document")
        return "application/rtf"

    raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix or 'no extension'}")
