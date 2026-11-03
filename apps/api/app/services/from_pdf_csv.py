"""F13: conservative PDF ruled-table pages -> UTF-8 CSV files in one ZIP.

Only pages consisting of a fully ruled, axis-aligned rectangular table with
selectable single-line cells are accepted. Never infer columns from whitespace.
"""
from __future__ import annotations

import csv
from io import StringIO
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile

from pypdf import PdfReader
from pypdf.generic import ContentStream

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_PAGES = 6
MAX_ROWS = 60
MAX_COLUMNS = 12
MAX_CELLS = 500
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
EPS = 1.0


def _lines(page, reader):
    segments = []
    pending = []
    point = None
    for args, op in ContentStream(page.get_contents(), reader).operations:
        if op == b"cm" and any(
            abs(float(value) - expected) > .001
            for value, expected in zip(args, (1, 0, 0, 1, 0, 0))
        ):
            raise ValueError("PDF table uses unsupported transformed graphics")
        if op == b"m":
            point = (float(args[0]), float(args[1]))
        elif op == b"l" and point is not None:
            next_point = (float(args[0]), float(args[1]))
            pending.append((*point, *next_point))
            point = next_point
        elif op == b"re":
            x, y, w, h = map(float, args)
            pending.extend([
                (x, y, x+w, y), (x, y+h, x+w, y+h),
                (x, y, x, y+h), (x+w, y, x+w, y+h),
            ])
        elif op in (b"S", b"s"):
            segments.extend(pending)
            pending = []
            point = None
        elif op in (b"n", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"):
            pending = []
            point = None
    vertical = []
    horizontal = []
    for x1, y1, x2, y2 in segments:
        if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
            raise ValueError("PDF table has nonfinite coordinates")
        if abs(x1-x2) < .01 and abs(y1-y2) >= 10:
            vertical.append((round(x1, 2), min(y1, y2), max(y1, y2)))
        elif abs(y1-y2) < .01 and abs(x1-x2) >= 10:
            horizontal.append((round(y1, 2), min(x1, x2), max(x1, x2)))
        elif abs(x1-x2) >= .01 or abs(y1-y2) >= .01:
            raise ValueError("PDF contains unsupported non-grid strokes")
    xs = sorted({x for x, _, _ in vertical})
    ys = sorted({y for y, _, _ in horizontal})
    if not 3 <= len(xs) <= MAX_COLUMNS+1 or not 3 <= len(ys) <= MAX_ROWS+1:
        raise ValueError("PDF must contain a 2+-column and 2+-row grid")
    if (not all(xs[i+1]-xs[i] >= 12 for i in range(len(xs)-1))
            or not all(ys[i+1]-ys[i] >= 12 for i in range(len(ys)-1))):
        raise ValueError("PDF table grid cells are too narrow")
    for x in xs:
        if not any(
            px == x and a <= ys[0]+EPS and b >= ys[-1]-EPS
            for px, a, b in vertical
        ):
            raise ValueError("PDF table has missing vertical grid rule")
    for y in ys:
        if not any(
            py == y and a <= xs[0]+EPS and b >= xs[-1]-EPS
            for py, a, b in horizontal
        ):
            raise ValueError("PDF table has missing horizontal grid rule")
    if (any(a < ys[0]-EPS or b > ys[-1]+EPS for _, a, b in vertical)
            or any(a < xs[0]-EPS or b > xs[-1]+EPS for _, a, b in horizontal)):
        raise ValueError("PDF contains other drawings outside the table")
    return xs, ys


def _table(page, reader):
    if int(page.get("/Rotate", 0)) % 360:
        raise ValueError("Rotated PDF table pages unsupported")
    xs, ys = _lines(page, reader)
    rows, cols = len(ys)-1, len(xs)-1
    cells = [["" for _ in range(cols)] for _ in range(rows)]
    fragments = []

    def visitor(text, cm, tm, font, font_size):
        content = text.strip("\r\n")
        if not content.strip():
            return
        if "\n" in content or "\r" in content or len(content) > 240:
            raise ValueError("Multiline or oversized PDF cell is unsupported")
        if any(
            abs(float(v) - expected) > .001
            for v, expected in zip(cm, (1, 0, 0, 1, 0, 0))
        ):
            raise ValueError("Transformed PDF table text unsupported")
        fragments.append((float(tm[4]), float(tm[5]), content.strip()))

    page.extract_text(visitor_text=visitor)
    if not fragments:
        raise ValueError("No selectable PDF table text")
    for x, y, value in fragments:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Invalid PDF text location")
        col = next(
            (i for i in range(cols) if xs[i]+EPS <= x <= xs[i+1]-EPS), None
        )
        bottom_row = next(
            (i for i in range(rows) if ys[i]+EPS <= y <= ys[i+1]-EPS), None
        )
        if col is None or bottom_row is None:
            raise ValueError("Text outside the table; refuse lossy CSV")
        row = rows-1-bottom_row
        if cells[row][col]:
            raise ValueError("Ambiguous PDF fragments in one table cell")
        if value.lstrip().startswith(("=", "+", "-", "@")):
            raise ValueError("Unsafe CSV spreadsheet formula-like cell")
        cells[row][col] = value
    if any(not cell for cell in cells[0]) or any(
        not any(row) for row in cells[1:]
    ):
        raise ValueError("PDF table header or row is incomplete")
    return cells


def pdf_to_csv_zip(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("CSV source/destination must be independent files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds CSV extractor input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF table unsupported")
    with TemporaryDirectory(prefix="pdfhub-frompdf-csv-") as folder:
        staged = Path(folder) / "result.zip"
        total_cells = 0
        with ZipFile(staged, "w", compression=ZIP_STORED, allowZip64=False) as archive:
            for page_no, page in enumerate(pdf.pages, 1):
                width, height = float(page.mediabox.width), float(page.mediabox.height)
                if (not math.isfinite(width) or not math.isfinite(height)
                        or not 1 <= width <= 4000
                        or not 1 <= height <= 4000):
                    raise ValueError("Unsupported PDF table dimensions")
                if page.get("/Resources", {}).get("/XObject"):
                    raise ValueError("Embedded PDF objects unsupported in text-only CSV")
                rows = _table(page, pdf)
                total_cells += len(rows) * len(rows[0])
                if total_cells > MAX_CELLS:
                    raise ValueError("Too many table cells to export")
                stream = StringIO(newline="")
                writer = csv.writer(stream, lineterminator="\r\n")
                writer.writerows(rows)
                content = stream.getvalue().encode("utf-8-sig")
                if not 6 <= len(content) <= 1024 * 1024:
                    raise ValueError("CSV page exceeds output budget")
                archive.writestr(f"page-{page_no:04d}.csv", content)
                if staged.stat().st_size > MAX_OUTPUT_BYTES:
                    raise ValueError("CSV ZIP exceeds output budget")
        with ZipFile(staged) as proof:
            expected = [f"page-{i:04d}.csv" for i in range(1, len(pdf.pages)+1)]
            if proof.namelist() != expected or proof.testzip() is not None:
                raise ValueError("CSV ZIP page inventory/CRC invalid")
        with staged.open("rb") as handle, output.open("xb") as destination:
            while chunk := handle.read(1024 * 1024):
                destination.write(chunk)
