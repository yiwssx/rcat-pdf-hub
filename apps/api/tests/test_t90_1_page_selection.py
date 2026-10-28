"""T90-1.3: real page extraction, bounded range syntax, and safe deletion.

M07/M16 here produce a *single selected-pages PDF* via existing split;
individual page files / ZIP require a later reviewed multi-output release.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.page_ranges import validated_page_range
from app.schemas import RotateRequest, SplitRequest
from app.services import pdf_tools


def source_pdf(path: Path) -> Path:
    document = canvas.Canvas(str(path))
    for i in range(1, 6):
        document.setPageSize((400 + i * 15, 600 + i * 20))
        document.drawString(60, 520, f"RCAT-PAGE-{i}")
        document.showPage()
    document.save()
    return path


def labels(path: Path) -> list[str]:
    return [(page.extract_text() or "").strip() for page in PdfReader(str(path), strict=True).pages]


@pytest.mark.parametrize("expression", [
    "1", "z", "1-z", "z-1", "5-3", "1,3,5", "2-4,z",
])
def test_reviewed_ranges_preserve_existing_qpdf_order_syntax(expression: str):
    assert validated_page_range(expression) == expression
    assert SplitRequest(file_id="some-file", pages=expression).pages == expression


@pytest.mark.parametrize("expression", [
    "", " ", "0", "0-1", "1-0", ",", "1,", ",1", "1,,2",
    "1--3", "1-2-3", "1;2", "1 2", "Z", "1--z",
    "100001", "1-100001", "999999", "1000000", "1," * 129 + "2",
])
def test_malformed_or_oversized_ranges_fail_before_qpdf(expression: str):
    with pytest.raises(ValueError):
        validated_page_range(expression)
    with pytest.raises(ValidationError):
        SplitRequest(file_id="some-file", pages=expression)
    with pytest.raises(ValidationError):
        RotateRequest(file_id="some-file", pages=expression)


@pytest.mark.skipif(shutil.which("qpdf") is None, reason="qpdf required for binary output")
@pytest.mark.parametrize("expression,want", [
    ("1,3,5", [1, 3, 5]),
    ("2-4", [2, 3, 4]),
    ("5-3", [5, 4, 3]),
    ("1-z", [1, 2, 3, 4, 5]),
])
def test_real_split_preserves_order_text_dimensions_and_source(
    tmp_path: Path, expression: str, want: list[int]
):
    source = source_pdf(tmp_path / "source.pdf")
    output = tmp_path / "selected.pdf"
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    pdf_tools.split(source, expression, output)

    assert output.read_bytes().startswith(b"%PDF-")
    result = PdfReader(str(output), strict=True)
    assert len(result.pages) == len(want)
    assert labels(output) == [f"RCAT-PAGE-{n}" for n in want]
    for page, number in zip(result.pages, want, strict=True):
        assert float(page.mediabox.width) == pytest.approx(400 + number * 15)
        assert float(page.mediabox.height) == pytest.approx(600 + number * 20)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_m14_delete_pages_via_existing_organize_is_non_destructive(tmp_path: Path):
    source = source_pdf(tmp_path / "source.pdf")
    result = tmp_path / "deleted-pages.pdf"
    before = source.read_bytes()
    # Deleting 2 and 4 means retaining 1, 3 and 5; do not rewrite the original.
    pdf_tools.organize(source, [{"page": page, "rotation": 0} for page in (1, 3, 5)], result)
    assert labels(result) == ["RCAT-PAGE-1", "RCAT-PAGE-3", "RCAT-PAGE-5"]
    assert source.read_bytes() == before


def test_m14_refuses_delete_all_and_bad_page_numbers(tmp_path: Path):
    source = source_pdf(tmp_path / "source.pdf")
    output = tmp_path / "invalid.pdf"
    for bad in ([], [{"page": 0, "rotation": 0}], [{"page": 6, "rotation": 0}]):
        with pytest.raises(ValueError):
            pdf_tools.organize(source, bad, output)
        assert not output.exists()


def test_invalid_page_ranges_do_not_invoke_external_binary(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pdf_tools, "_run", lambda *_a, **_kw: pytest.fail("invoked qpdf"))
    for bad in ("0", "1,,2", "100001", "1-z;whoami"):
        with pytest.raises(ValueError):
            pdf_tools.split(tmp_path / "input.pdf", bad, tmp_path / "out.pdf")
