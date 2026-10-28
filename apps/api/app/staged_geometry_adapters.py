"""Explicit T90-1.5 geometry adapters. Separate from the 13 legacy operations."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from app.config import get_settings
from app.services.pdf_page_geometry import crop_pdf, resize_pdf

STAGED_GEOMETRY_OPERATIONS = frozenset({"crop-pdf", "resize-pdf"})


def _crop(inputs: list[Path], output: Path, params: dict) -> None:
    if set(params) != {"left", "bottom", "right", "top", "pages"}:
        raise ValueError("Invalid crop parameters")
    crop_pdf(inputs[0], output, left=params["left"], bottom=params["bottom"],
             right=params["right"], top=params["top"], pages=params["pages"])


def _resize(inputs: list[Path], output: Path, params: dict) -> None:
    if set(params) != {"width", "height"}:
        raise ValueError("Invalid resize parameters")
    resize_pdf(inputs[0], output, width=params["width"], height=params["height"])


ADAPTERS: Mapping[str, Callable[[list[Path], Path, dict], None]] = {
    "crop-pdf": _crop,
    "resize-pdf": _resize,
}


def geometry_output_spec(operation: str) -> tuple[str, str]:
    if operation not in STAGED_GEOMETRY_OPERATIONS:
        raise ValueError("Unknown staged geometry operation")
    return ".pdf", "application/pdf"


def execute_staged_geometry_operation(
    operation: str, inputs: list[Path], output: Path, params: dict
) -> None:
    if not get_settings().geometry_tools_enabled:
        raise RuntimeError("Staged geometry tools are disabled")
    if operation not in STAGED_GEOMETRY_OPERATIONS:
        raise ValueError("Unknown staged geometry operation")
    if len(inputs) != 1 or not isinstance(params, dict):
        raise ValueError("Geometry tools require one PDF and validated parameters")
    ADAPTERS[operation](inputs, output, params)
