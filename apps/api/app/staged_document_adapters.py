"""Explicit, separately gated T90-1.4 document-data adapters.

Do not add these to the 13 legacy ADAPTERS or Phase-0 public registry.
The worker checks the rollout flag again before dispatch. Tests opt in only
in an isolated environment. No dynamic imports, reflection or client code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from app.config import get_settings
from app.services import pdf_document_data

STAGED_DOCUMENT_OPERATIONS = frozenset({
    "edit-metadata", "extract-text", "remove-metadata",
})


def _edit(inputs: list[Path], output: Path, params: dict) -> None:
    changes = params.get("changes")
    if not isinstance(changes, dict):
        raise ValueError("Invalid document metadata changes")
    pdf_document_data.edit_document_info(inputs[0], output, changes)


def _extract(inputs: list[Path], output: Path, params: dict) -> None:
    if params:
        raise ValueError("Text extraction does not accept extra parameters")
    pdf_document_data.extract_searchable_text(inputs[0], output)


def _remove(inputs: list[Path], output: Path, params: dict) -> None:
    if params:
        raise ValueError("Metadata removal does not accept extra parameters")
    pdf_document_data.remove_document_info_and_xmp(inputs[0], output)


STAGED_ADAPTERS: Mapping[str, Callable[[list[Path], Path, dict], None]] = {
    "edit-metadata": _edit,
    "extract-text": _extract,
    "remove-metadata": _remove,
}


def execute_staged_document_operation(
    operation: str, inputs: list[Path], output: Path, params: dict
) -> None:
    if not get_settings().document_data_tools_enabled:
        raise RuntimeError("Staged document-data tools are disabled")
    if operation not in STAGED_DOCUMENT_OPERATIONS:
        raise ValueError("Unknown staged document operation")
    if len(inputs) != 1 or not isinstance(params, dict):
        raise ValueError("Staged operation requires one input and validated parameters")
    STAGED_ADAPTERS[operation](inputs, output, params)


def staged_output_spec(operation: str) -> tuple[str, str]:
    if operation not in STAGED_DOCUMENT_OPERATIONS:
        raise ValueError("Unsupported staged document output operation")
    if operation == "extract-text":
        return (".txt", "text/plain; charset=utf-8")
    return (".pdf", "application/pdf")
