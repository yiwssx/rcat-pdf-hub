"""M33 PDF Filler: bounded AcroForm text field editing, development engine.

Only editable text widgets in existing AcroForms are supported. Does NOT
claim secure redaction, digital signatures, automatic flattening, or reliable
Thai glyph appearance without registered embedded form fonts.
Not publicly routed until authenticated job integration is reviewed.
"""
from __future__ import annotations

from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_OUTPUT_BYTES = 48 * 1024 * 1024
MAX_PAGES = 80
MAX_FIELDS = 64
MAX_FIELD_NAME = 128
MAX_VALUE_LENGTH = 1024


def _fields(reader: PdfReader) -> dict:
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page AcroForm PDF unsupported")
    root = reader.trailer["/Root"]
    acroform = root.get("/AcroForm")
    if acroform is None:
        raise ValueError("PDF has no AcroForm")
    resolved = acroform.get_object()
    if not isinstance(resolved, DictionaryObject) or "/XFA" in resolved:
        raise ValueError("XFA forms are unsupported")
    fields = reader.get_fields()
    if not fields or len(fields) > 256:
        raise ValueError("AcroForm has no supported field inventory")
    if any(field.get("/FT") == "/Sig" for field in fields.values()):
        raise ValueError("Signed document forms cannot be modified")
    return fields


def fill_pdf_text_fields(source: Path, output: Path, updates: dict[str, str]) -> None:
    """Fill specifically named existing /Tx fields and verify the saved values."""
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()):
        raise ValueError("AcroForm requires an independent source PDF")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("AcroForm PDF exceeds supported file-size limit")
    if not isinstance(updates, dict) or not 1 <= len(updates) <= MAX_FIELDS:
        raise ValueError("Select between 1 and 64 AcroForm text fields")
    for name, value in updates.items():
        if (not isinstance(name, str) or not 1 <= len(name) <= MAX_FIELD_NAME
                or not re.fullmatch(r"[^\x00-\x1f\x7f]+", name)
                or not isinstance(value, str) or len(value) > MAX_VALUE_LENGTH
                or any(ord(char) < 32 and char not in "\t\n" for char in value)):
            raise ValueError("AcroForm field name or value exceeds limits")
    reader = PdfReader(str(source), strict=True)
    original = _fields(reader)
    if any(name not in original or original[name].get("/FT") != "/Tx"
           for name in updates):
        raise ValueError("Only existing AcroForm text fields may be updated")
    writer = PdfWriter()
    writer.append(reader)
    # pypdf updates the appearance streams for existing text fields;
    # auto_regenerate=False avoids asking the viewer to silently change
    # appearances and prevents PDF reader-dependent values being "saved".
    writer.update_page_form_field_values(None, updates, auto_regenerate=False)
    # Never create a public job artifact until the candidate has passed
    # complete binary/field verification; a rejected PDF leaves no output.
    if output.exists() or output.is_symlink():
        raise ValueError("Cannot overwrite a preexisting PDF artifact")
    with TemporaryDirectory(prefix="pdfhub-acroform-", dir=output.parent) as work:
        candidate = Path(work) / "candidate.pdf"
        with candidate.open("xb") as destination:
            writer.write(destination)
        size = candidate.stat().st_size
        if not 48 <= size <= MAX_OUTPUT_BYTES:
            raise ValueError("Generated AcroForm exceeds output size budget")
        checked = PdfReader(str(candidate), strict=True)
        if checked.is_encrypted or len(checked.pages) != len(reader.pages):
            raise ValueError("Saved AcroForm pages were modified unexpectedly")
        fields = checked.get_fields() or {}
        for name, intended in updates.items():
            if name not in fields or str(fields[name].get("/V", "")) != intended:
                raise ValueError("Saved AcroForm field differs from submitted value")
        # Exclusive create is intentionally used instead of Path.replace(),
        # which could silently replace an existing user/job artifact.
        with candidate.open("rb") as source_bytes, output.open("xb") as destination:
            shutil.copyfileobj(source_bytes, destination, length=1024 * 1024)
        if output.stat().st_size != size:
            raise ValueError("Saved AcroForm was truncated during promotion")
