"""Reviewed, static adapter dispatch for the 13 EXISTING PDF engine operations.

T90-0.15 creates an extensible, explicit seam without enabling any of the
90 planning-only capability registry entries. No reflection, importlib,
client-supplied function names, arbitrary commands or dynamic execution.
The Worker owns scanning, quotas, fencing, storage, audit and job commits.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from app.services import pdf_tools


@dataclass(frozen=True)
class OperationAdapter:
    run: Callable[[list[Path], Path, dict], None]
    min_inputs: int = 1
    max_inputs: int = 1

    def execute(self, inputs: list[Path], output: Path, params: dict) -> None:
        if not self.min_inputs <= len(inputs) <= self.max_inputs:
            raise ValueError(
                f"Operation expects {self.min_inputs} to {self.max_inputs} input files"
            )
        if not isinstance(params, dict):
            raise ValueError("Operation parameters must be an object")
        self.run(inputs, output, params)


def _merge(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.merge(inputs, output)


def _images_to_pdf(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.images_to_pdf(
        inputs, output,
        page_size=params.get("page_size", "auto"),
        fit=params.get("fit", "contain"),
        margin=float(params.get("margin", 18)),
        dpi=int(params.get("dpi", 150)),
    )


def _pdf_to_images(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.pdf_to_images(
        inputs[0], output,
        image_format=params.get("format", "png"),
        dpi=int(params.get("dpi", 150)),
        first_page=int(params.get("first_page", 1)),
        last_page=params.get("last_page"),
    )


def _organize(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.organize(inputs[0], params["pages"], output)


def _split(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.split(inputs[0], params["pages"], output)


def _rotate(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.rotate(inputs[0], int(params["degrees"]), params["pages"], output)


def _compress(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.compress(inputs[0], output)


def _ocr(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.ocr(
        inputs[0], output,
        params.get("languages", "tha+eng"),
        bool(params.get("deskew", True)),
        bool(params.get("rotate_pages", True)),
    )


def _pdfa(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.pdfa(inputs[0], output, params.get("languages", "tha+eng"))


def _office_to_pdf(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.office_to_pdf(inputs[0], output)


def _watermark(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.watermark_text(
        inputs[0], output,
        text=params["text"],
        font_size=float(params.get("font_size", 48)),
        opacity=float(params.get("opacity", 0.18)),
        rotation=float(params.get("rotation", 45)),
        position=params.get("position", "center"),
        margin=float(params.get("margin", 36)),
    )


def _page_numbers(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.add_page_numbers(
        inputs[0], output,
        format_text=params.get("format", "{page} / {total}"),
        start_number=int(params.get("start_number", 1)),
        font_size=float(params.get("font_size", 10)),
        position=params.get("position", "bottom-center"),
        margin=float(params.get("margin", 24)),
    )


def _stamp(inputs: list[Path], output: Path, params: dict) -> None:
    pdf_tools.stamp_pdf(
        inputs[0], inputs[1], output,
        position=params.get("position", "bottom-right"),
        scale=float(params.get("scale", 0.20)),
        margin=float(params.get("margin", 24)),
    )


# Immutable operation identity and allow-listed call sites. Inputs are Paths
# already resolved by the Worker from DB-owned FileRecords; no string eval.
ADAPTERS: Mapping[str, OperationAdapter] = {
    "merge": OperationAdapter(_merge, min_inputs=2, max_inputs=50),
    "organize": OperationAdapter(_organize),
    "split": OperationAdapter(_split),
    "rotate": OperationAdapter(_rotate),
    "compress": OperationAdapter(_compress),
    "ocr": OperationAdapter(_ocr),
    "pdfa": OperationAdapter(_pdfa),
    "office-to-pdf": OperationAdapter(_office_to_pdf),
    "watermark": OperationAdapter(_watermark),
    "page-numbers": OperationAdapter(_page_numbers),
    "stamp": OperationAdapter(_stamp, min_inputs=2, max_inputs=2),
    "images-to-pdf": OperationAdapter(_images_to_pdf, min_inputs=1, max_inputs=100),
    "pdf-to-images": OperationAdapter(_pdf_to_images),
}


def execute_operation(operation: str, inputs: list[Path], output: Path, params: dict) -> None:
    adapter = ADAPTERS.get(operation)
    if adapter is None:
        raise RuntimeError(f"Unsupported operation: {operation}")
    adapter.execute(inputs, output, params)
