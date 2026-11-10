"""M01: genuine, narrowly supported inline PDF text replacement.

Edits a visible Tj substring in built-in Courier/Helvetica/Times Type1
fonts. Proportional replacements use a TJ displacement preserving subsequent
text advance. Does not overlay old text or edit Thai/Unicode/subset fonts,
images, forms, annotations or encrypted/signed PDFs. Not redaction.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, NumberObject, TextStringObject
from reportlab.pdfbase import pdfmetrics

MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 24 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT_CHARS = 96
COURIER_FONTS = frozenset({
    "/Courier", "/Courier-Bold", "/Courier-Oblique", "/Courier-BoldOblique",
})
PROPORTIONAL_FONTS = frozenset({
    "/Helvetica", "/Helvetica-Bold", "/Helvetica-Oblique", "/Helvetica-BoldOblique",
    "/Times-Roman", "/Times-Bold", "/Times-Italic", "/Times-BoldItalic",
})
SUPPORTED_FONTS = COURIER_FONTS | PROPORTIONAL_FONTS
ENCODINGS = frozenset({"/WinAnsiEncoding", "/StandardEncoding"})


def validate_edit(*, page: int, old_text: str, new_text: str) -> None:
    if type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("M01 page outside bound")
    if type(old_text) is not str or type(new_text) is not str:
        raise ValueError("M01 requires text strings")
    if (not 3 <= len(old_text) <= MAX_TEXT_CHARS
            or len(new_text) != len(old_text)
            or old_text == new_text
            # Equal glyph and space counts preserve Tc/Tw text spacing.
            or old_text.count(" ") != new_text.count(" ")
            or not old_text.strip() or not new_text.strip()
            or any(not 32 <= ord(ch) <= 126 for ch in old_text + new_text)):
        raise ValueError("M01 requires distinct equal-length printable ASCII")


def _digest(path: Path) -> bytes:
    digest = sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def _standard_font_name(page, font_name: str) -> str | None:
    try:
        resources = page["/Resources"].get_object()
        fonts = resources["/Font"].get_object()
        font = fonts[font_name].get_object()
        basefont = str(font["/BaseFont"])
        subtype = str(font["/Subtype"])
        encoding = str(font.get("/Encoding", "/StandardEncoding"))
        # AFM widths are valid only for unmodified built-in Type1 metrics.
        if (subtype == "/Type1" and basefont in SUPPORTED_FONTS
                and encoding in ENCODINGS
                and not any(key in font for key in (
                    "/ToUnicode", "/FontDescriptor", "/Widths", "/FirstChar",
                    "/LastChar", "/FontFile", "/FontFile2", "/FontFile3",
                ))):
            return basefont[1:]
        return None
    except (KeyError, AttributeError, TypeError):
        return None


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
    in_text = False
    graphics_stack: list[tuple[str | None, int]] = []
    replaced = False
    for op_index, (operands, command) in enumerate(content.operations):
        # PDF text font/render mode persist across BT/ET. q/Q save and restore
        # graphics state, including those text-state parameters.
        if command == b"q":
            graphics_stack.append((active_font, render_mode))
        elif command == b"Q":
            if not graphics_stack:
                raise ValueError("M01 unmatched PDF graphics state restore")
            active_font, render_mode = graphics_stack.pop()
        elif command == b"BT":
            in_text = True
        elif command == b"ET":
            in_text = False
        elif command == b"Tf" and len(operands) == 2:
            active_font = str(operands[0])
        elif command == b"Tr" and len(operands) == 1:
            render_mode = int(operands[0])
        elif command == b"Tj" and len(operands) == 1:
            value = operands[0]
            if not isinstance(value, TextStringObject) or old_text not in str(value):
                continue
            if str(value).count(old_text) != 1 or replaced:
                raise ValueError("M01 source text is not unique on target page")
            font = _standard_font_name(selected, active_font) if active_font else None
            if not in_text or render_mode != 0 or font is None:
                raise ValueError(
                    "M01 only supports visible built-in Courier, Helvetica or Times text"
                )
            original = str(value)
            if "/" + font in COURIER_FONTS:
                # Existing Courier Tj format stays unchanged.
                operands[0] = TextStringObject(original.replace(old_text, new_text, 1))
            else:
                # Positive TJ number moves the text cursor backward by
                # thousandths of the font size. Same character/space counts
                # cancel Tc/Tw; the following text remains at the same X.
                compensation = round(
                    pdfmetrics.stringWidth(new_text, font, 1000)
                    - pdfmetrics.stringWidth(old_text, font, 1000)
                )
                start = original.index(old_text)
                prefix_and_edit = original[:start] + new_text
                suffix = original[start + len(old_text):]
                array = ArrayObject([TextStringObject(prefix_and_edit)])
                if compensation:
                    array.append(NumberObject(compensation))
                if suffix:
                    array.append(TextStringObject(suffix))
                content.operations[op_index] = ([array], b"TJ")
            replaced = True
        elif command == b"TJ" and len(operands) == 1:
            if any(isinstance(value, TextStringObject) and old_text in str(value)
                   for value in operands[0]):
                raise ValueError("M01 cannot replace text in positioned glyph arrays")

    if not replaced:
        raise ValueError("M01 text not found in one editable built-in font text object")

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
