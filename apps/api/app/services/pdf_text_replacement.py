"""M01: genuine, narrowly supported inline PDF text replacement.

Edits a visible Tj substring in built-in Courier/Helvetica/Times Type1
fonts. Proportional replacements use a TJ displacement preserving subsequent
text advance. Does not overlay old text or edit Thai/Unicode/subset fonts,
images, forms, annotations or encrypted/signed PDFs. Not redaction.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, FloatObject, NumberObject, TextStringObject
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


def _demonstrated_glyphs(content: ContentStream) -> dict[str, set[str]]:
    """Characters visibly used with each font resource on the selected page.

    This is a conservative font-coverage witness for simple embedded fonts:
    the editor never introduces a glyph not already present in that font.
    """
    known: dict[str, set[str]] = {}
    current: str | None = None
    render_mode = 0
    inside = False
    stack: list[tuple[str | None, int]] = []
    for args, operator in content.operations:
        if operator == b"q":
            stack.append((current, render_mode))
        elif operator == b"Q" and stack:
            current, render_mode = stack.pop()
        elif operator == b"BT":
            inside = True
        elif operator == b"ET":
            inside = False
        elif operator == b"Tf" and len(args) == 2:
            current = str(args[0])
        elif operator == b"Tr" and len(args) == 1:
            render_mode = int(args[0])
        elif inside and render_mode == 0 and current and operator in {b"Tj", b"TJ"}:
            if operator == b"Tj" and len(args) == 1:
                parts = args
            elif operator == b"TJ" and len(args) == 1 and isinstance(args[0], ArrayObject):
                parts = args[0]
            else:
                continue
            for chunk in parts:
                if isinstance(chunk, TextStringObject):
                    known.setdefault(current, set()).update(str(chunk))
    return known


def _single_byte_ascii(part: TextStringObject) -> bool:
    """Enforce exact identity between displayed ASCII and PDF byte codes."""
    if not str(part).isascii():
        return False
    try:
        return part.original_bytes == str(part).encode("ascii")
    except (UnicodeEncodeError, AttributeError, ValueError):
        return False


def _embedded_widths(page, font_name: str, old: str, new: str,
                     glyphs: dict[str, set[str]]) -> dict[str, float] | None:
    """Support only witnessed 1-byte ASCII TrueType with explicit identity CMap.

    No name-based font substitution or guess about missing subset glyphs.
    Only chars already displayed in this page's very same font resource may
    be reused, and the source's explicit widths drive advance compensation.
    """
    try:
        fonts = page["/Resources"].get_object()["/Font"].get_object()
        font = fonts[font_name].get_object()
        if str(font["/Subtype"]) != "/TrueType":
            return None
        if str(font.get("/Encoding", "/WinAnsiEncoding")) != "/WinAnsiEncoding":
            return None
        descriptor = font["/FontDescriptor"].get_object()
        if "/FontFile2" not in descriptor:
            return None
        if "/ToUnicode" not in font:
            return None
        mapping = font["/ToUnicode"].get_object().get_data()
        if len(mapping) > 64 * 1024 or b"beginbfchar" not in mapping or b"beginbfrange" in mapping:
            return None
        pairs = re.findall(rb"<([0-9A-Fa-f]{2})>\s*<([0-9A-Fa-f]{4})>", mapping)
        if len(pairs) > 256:
            return None
        identity = {int(code, 16) for code, uni in pairs if int(code, 16) == int(uni, 16)}
        first, last = int(font["/FirstChar"]), int(font["/LastChar"])
        widths = font["/Widths"].get_object()
        if not 0 <= first <= last <= 255 or len(widths) != last - first + 1:
            return None
        chars = set(old + new)
        seen = glyphs.get(font_name, set())
        if (not chars.issubset(seen)
                or any(ord(char) not in identity or not 32 <= ord(char) <= 126
                       for char in chars)):
            return None
        result = {char: float(widths[ord(char) - first]) for char in chars
                  if first <= ord(char) <= last}
        if len(result) != len(chars) or any(not 0 < width <= 2000 for width in result.values()):
            return None
        return result
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
        return None


def _metrics(page, font_name: str | None, old: str, new: str,
             glyphs: dict[str, set[str]]) -> tuple[str | None, dict[str, float] | None]:
    if font_name is None:
        return None, None
    standard = _standard_font_name(page, font_name)
    if standard:
        return standard, None
    widths = _embedded_widths(page, font_name, old, new, glyphs)
    return ("embedded-ttf", widths) if widths is not None else (None, None)


def _width_delta(old: str, new: str, font: str,
                 widths: dict[str, float] | None) -> int:
    if widths is not None:
        return round(sum(widths[ch] for ch in new) - sum(widths[ch] for ch in old))
    return round(pdfmetrics.stringWidth(new, font, 1000)
                 - pdfmetrics.stringWidth(old, font, 1000))


def _rewrite_tj(segments: ArrayObject, old: str, new: str, font: str,
                widths: dict[str, float] | None) -> ArrayObject:
    """Retain existing kerning offsets; repair each changed segment's advance."""
    if len(segments) > 64:
        raise ValueError("M01 TJ array exceeds bounded operator complexity")
    texts = [str(part) for part in segments if isinstance(part, TextStringObject)]
    if len(texts) < 1 or len(texts) > 32:
        raise ValueError("M01 TJ array has no supported text fragments")
    joined = "".join(texts)
    if joined.count(old) != 1:
        raise ValueError("M01 text is not unique within positioned glyph array")
    begin = joined.index(old)
    end = begin + len(old)
    # Do not interpret whitespace created by large positioning jumps as a
    # contiguous word: only ordinary sub-glyph kerning may split an edit.
    cursor = 0
    for part in segments:
        if isinstance(part, TextStringObject):
            cursor += len(part)
        elif isinstance(part, (NumberObject, FloatObject)):
            if begin < cursor < end and abs(float(part)) > 120:
                raise ValueError("M01 cannot edit across a wide TJ positioning gap")
        else:
            raise ValueError("M01 unsupported TJ operand")
    answer = ArrayObject()
    cursor = 0
    for part in segments:
        if not isinstance(part, TextStringObject):
            answer.append(part)
            continue
        text = str(part)
        if font == "embedded-ttf" and not _single_byte_ascii(part):
            raise ValueError("M01 embedded font uses non-ASCII PDF text bytes")
        from_index = max(begin, cursor)
        to_index = min(end, cursor + len(text))
        if from_index < to_index:
            left = from_index - cursor
            right = to_index - cursor
            replacement = new[from_index - begin:to_index - begin]
            old_fragment = text[left:right]
            if old_fragment.count(" ") != replacement.count(" "):
                raise ValueError("M01 TJ fragment would change word spacing")
            revised = text[:left] + replacement + text[right:]
            answer.append(TextStringObject(revised))
            delta = _width_delta(old_fragment, replacement, font, widths)
            if delta:
                answer.append(NumberObject(delta))
        else:
            answer.append(part)
        cursor += len(text)
    return answer


def _operator_texts(content: ContentStream) -> list[str]:
    """String fragments joined only within a single PDF text operator."""
    result = []
    for parts, command in content.operations:
        if command == b"Tj" and len(parts) == 1 and isinstance(parts[0], TextStringObject):
            result.append(str(parts[0]))
        elif command == b"TJ" and len(parts) == 1 and isinstance(parts[0], ArrayObject):
            result.append("".join(str(value) for value in parts[0]
                                  if isinstance(value, TextStringObject)))
    return result



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
    glyphs = _demonstrated_glyphs(content)
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
        elif command in {b"Tj", b"TJ"} and len(operands) == 1:
            if command == b"Tj" and isinstance(operands[0], TextStringObject):
                visible = str(operands[0])
            elif command == b"TJ" and isinstance(operands[0], ArrayObject):
                visible = "".join(str(part) for part in operands[0]
                                  if isinstance(part, TextStringObject))
            else:
                continue
            if old_text not in visible:
                continue
            if visible.count(old_text) != 1 or replaced:
                raise ValueError("M01 source text is not unique on target page")
            font, widths = _metrics(selected, active_font, old_text, new_text, glyphs)
            if not in_text or render_mode != 0 or font is None:
                raise ValueError(
                    "M01 requires a visible supported built-in or witnessed embedded TrueType font"
                )
            if command == b"Tj":
                part = operands[0]
                if font == "embedded-ttf" and not _single_byte_ascii(part):
                    raise ValueError("M01 embedded font uses non-ASCII PDF text bytes")
                original = str(part)
                if "/" + font in COURIER_FONTS:
                    operands[0] = TextStringObject(original.replace(old_text, new_text, 1))
                else:
                    position = original.index(old_text)
                    before = original[:position] + new_text
                    after = original[position + len(old_text):]
                    array = ArrayObject([TextStringObject(before)])
                    delta = _width_delta(old_text, new_text, font, widths)
                    if delta:
                        array.append(NumberObject(delta))
                    if after:
                        array.append(TextStringObject(after))
                    content.operations[op_index] = ([array], b"TJ")
            else:
                content.operations[op_index] = ([
                    _rewrite_tj(operands[0], old_text, new_text, font, widths)
                ], b"TJ")
            replaced = True

    if not replaced:
        raise ValueError("M01 text not found in one safely editable PDF text operator")

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
        # TJ arrays may be rendered with intentional kerning gaps. Verify
        # the exact live glyph fragments after write, as well as extracted
        # text, instead of trusting a fabricated answer string.
        persisted = ContentStream(verified.pages[page - 1].get_contents(), verified)
        tokens = _operator_texts(persisted)
        if not any(new_text in text for text in tokens) or any(
            old_text in text for text in tokens
        ) or not after.strip():
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
