from pathlib import Path
import zipfile

from fastapi import HTTPException

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


def _valid_zip_member(path: Path, prefix: str) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            return "[Content_Types].xml" in names and any(name.startswith(prefix) for name in names)
    except (zipfile.BadZipFile, OSError):
        return False


def validate_uploaded_file(path: Path, original_name: str) -> str:
    suffix = Path(original_name).suffix.lower()
    head = _head(path)

    if suffix == ".pdf":
        if not head.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="File extension is PDF but the file signature is not PDF")
        return PDF

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
        if not _valid_zip_member(path, root):
            raise HTTPException(status_code=415, detail=f"Invalid {suffix} Office document")
        return media_type

    if suffix in ODF_TYPES:
        try:
            with zipfile.ZipFile(path) as archive:
                mimetype = archive.read("mimetype").decode("ascii", errors="ignore").strip()
        except (KeyError, zipfile.BadZipFile, OSError):
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
