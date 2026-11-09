"""M01: genuine, narrowly supported inline PDF text replacement.

Only replaces an existing displayed Tj string in a standard fixed-width Courier
font on one plain PDF page. It does NOT overlay or cover old text. This limited
editor cannot alter arbitrary text, Thai/subset fonts, layout, images, forms,
annotations or encrypted/signed PDFs. Never describe it as secure redaction.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, TextStringObject

MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 24 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT_CHARS = 96
COURIER_FONTS = frozenset({
    "/Courier", "/Courier-Bold", "/Courier-Oblique", "/Courier-BoldOblique",
})
ENCODINGS = frozenset({"/WinAnsiEncoding", "/StandardEncoding"})


def validate_edit(*, page: int, old_text: str, new_text: str) -> None:
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("M01 page outside bound")
    if type(old_text) is not str or type(new_text) is not str:
        raise ValueError("M01 requires text strings")
    if (not 3 <= len(old_text) <= MAX_TEXT_CHARS
            or len(new_text) != len(old_text)
            or old_text == new_text
            or not old_text.strip() or not new_text.strip()
            or any(not 32 <= ord(ch) <= 126 for ch in old_text + new_text)):
        raise ValueError("M01 requires distinct equal-length printable ASCII")


def _digest(path: Path) -> bytes:
    digest = sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def _simple_courier(page, font_name: str) -> bool:
    try:
        resources = page["/Resources"].get_object()
        fonts = resources["/Font"].get_object()
        font = fonts[font_name].get_object()
        basefont = str(font["/BaseFont"])
        subtype = str(font["/Subtype"])
        encoding = str(font.get("/Encoding", "/StandardEncoding"))
        return (subtype == "/Type1" and basefont in COURIER_FONTS
                and encoding in ENCODINGS
                and "/ToUnicode" not in font
                and "/FontDescriptor" not in font)
    except (KeyError, AttributeError, TypeError):
        return False


def replace_pdf_text(source: Path, destination: Path, *,
                     page: int, old_text: str, new_text: str) -> None:
    """Perform exact, single-occurrence same-length text-object replacement."""
    validate_edit(page=page, old_text=old_text, new_text=new_text)
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("M01 source/destination must be distinct regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("M01 PDF input exceeds size budget")
    with source.open("rb") as inp:
        if inp.read(5) != b"%PDF-":
            raise ValueError("M01 PDF signature invalid")
    initial_digest = _digest(source)
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("M01 encrypted or excessive-page PDF unsupported")
    root = reader.trailer["/Root"]
    if root.get("/AcroForm") or root.get("/Perms"):
        raise ValueError("M01 interactive or signed PDF unsupported")
    if page > len(reader.pages):
        raise ValueError("M01 target page does not exist")
    selected = reader.pages[page - 1]
    if (selected.get("/Annots")
            or int(selected.get("/Rotate", 0)) % 360 != 0
            or tuple(selected.cropbox) != tuple(selected.mediabox)):
        raise ValueError("M01 requires plain unrotated, uncropped, annotation-free PDF")
    if selected.get_contents() is None:
        raise ValueError("M01 PDF page has no content stream")

    content = ContentStream(selected.get_contents(), reader)
    active_font: str | None = None
    render_mode = 0
    replaced = False
    for operands, command in content.operations:
        # BT resets text matrices, not the graphics-state text font/render mode.
        # ReportLab may choose a font in one BT block and draw in the next.
        if command == b"Tf" and len(operands) == 2:
            active_font = str(operands[0])
        elif command == b"Tr" and len(operands) == 1:
            render_mode = int(operands[0])
        elif command == b"Tj" and len(operands) == 1:
            value = operands[0]
            if not isinstance(value, TextStringObject) or old_text not in str(value):
                continue
            if str(value).count(old_text) != 1 or replaced:
                raise ValueError("M01 source text is not unique on target page")
            if render_mode != 0 or not active_font or not _simple_courier(selected, active_font):
                raise ValueError("M01 only supports visible standard Courier text")
            operands[0] = TextStringObject(str(value).replace(old_text, new_text, 1))
            replaced = True
        elif command == b"TJ" and len(operands) == 1:
            if any(isinstance(value, TextStringObject) and old_text in str(value)
                   for value in operands[0]):
                raise ValueError("M01 cannot replace text in positioned glyph arrays")

    if not replaced:
        raise ValueError("M01 text not found in one editable Courier text object")

    # A complete fresh output must preserve all pages and keep source untouched.
    writer = PdfWriter(clone_from=reader)
    writer.pages[page - 1].replace_contents(content)
    staged_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-m01-", suffix=".pdf",
            dir=destination.parent, delete=False,
        ) as staged:
            staged_name = staged.name
            writer.write(staged)
        staged_path = Path(staged_name)
        if not 100 <= staged_path.stat().st_size <= MAX_OUTPUT_BYTES:
            raise ValueError("M01 result outside size budget")
        verified = PdfReader(str(staged_path), strict=True)
        if verified.is_encrypted or len(verified.pages) != len(reader.pages):
            raise ValueError("M01 output page inventory invalid")
        after = verified.pages[page - 1].extract_text() or ""
        if new_text not in after or old_text in after:
            raise ValueError("M01 replacement did not survive PDF text extraction")
        if any(
            (verified.pages[index].extract_text() or "")
            != (reader.pages[index].extract_text() or "")
            for index in range(len(reader.pages)) if index != page - 1
        ):
            raise ValueError("M01 unexpectedly modified another page text layer")
        if _digest(source) != initial_digest:
            raise ValueError("M01 source PDF changed during editing")
        staged_path.replace(destination)
        staged_name = None
    finally:
        if staged_name is not None:
            Path(staged_name).unlink(missing_ok=True)
