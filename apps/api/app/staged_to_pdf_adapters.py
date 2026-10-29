"""T90-2 explicit opt-in conversion dispatch; never part of legacy ADAPTERS."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from fastapi import HTTPException

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services import to_pdf_engine

# Operation -> required persisted MIME and original upload suffix.
STAGED_TO_PDF_INPUTS: Mapping[str, tuple[str, str]] = {
    "txt-to-pdf": ("text/plain", ".txt"),
    "csv-to-pdf": ("text/csv", ".csv"),
    "md-to-pdf": ("text/markdown", ".md"),
    "jfif-to-pdf": ("image/jpeg", ".jfif"),
    "gif-to-pdf": ("image/gif", ".gif"),
    "tiff-to-pdf": ("image/tiff", ".tiff"),
}
STAGED_TO_PDF_OPERATIONS = frozenset(STAGED_TO_PDF_INPUTS)


def checked_source(operation: str, path: Path, *, name: str, mime: str) -> None:
    if operation not in STAGED_TO_PDF_INPUTS:
        raise ValueError("Unsupported staged conversion")
    expected_mime, suffix = STAGED_TO_PDF_INPUTS[operation]
    original_suffix = Path(name).suffix.lower()
    if mime != expected_mime or original_suffix not in (
        (".tif", ".tiff") if suffix == ".tiff" else (suffix,)
    ):
        raise ValueError("Format and persisted MIME do not match the requested conversion")
    try:
        actual_mime = validate_uploaded_file(path, name)
    except HTTPException as exc:
        raise ValueError("Uploaded format signature no longer validates") from exc
    if actual_mime != expected_mime:
        raise ValueError("Uploaded format signature does not match persisted MIME")


def execute_staged_to_pdf_operation(
    operation: str, inputs: list[Path], output: Path, params: dict,
    *, original_name: str, content_type: str,
) -> None:
    if not get_settings().to_pdf_tools_enabled:
        raise RuntimeError("Staged T90-2 tools are disabled")
    if operation not in STAGED_TO_PDF_OPERATIONS or len(inputs) != 1 or params:
        raise ValueError("Unknown staged conversion, input count or parameters")
    checked_source(operation, inputs[0], name=original_name, mime=content_type)
    if operation == "txt-to-pdf":
        to_pdf_engine.text_to_pdf(inputs[0], output)
    elif operation == "csv-to-pdf":
        to_pdf_engine.csv_to_pdf(inputs[0], output)
    elif operation == "md-to-pdf":
        to_pdf_engine.markdown_to_pdf(inputs[0], output)
    else:
        to_pdf_engine.image_frames_to_pdf(
            inputs[0], output, kind=operation.split("-", 1)[0]
        )
