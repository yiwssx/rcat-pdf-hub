"""T90-2 restricted *ASCII* DXF 2D geometry; fail closed on any other CAD entity.

Only ENTITIES/LINE/CIRCLE is supported, with no XREF, BLOCK, text,
external data, colors, layers or arbitrary CAD interpreter.
This is deliberately not full DXF or engineering-drawing fidelity.
"""
from __future__ import annotations

from io import BytesIO
from math import isfinite
from pathlib import Path
import re

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

MAX_DXF_BYTES = 1024 * 1024
MAX_DXF_ENTITIES = 2000
MAX_DXF_PAIRS = 20000
MAX_COORD = 100_000.0
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
LAYER = re.compile(r"[A-Za-z0-9_.$-]{1,64}\Z")
HANDLE = re.compile(r"[0-9A-Fa-f]{1,16}\Z")


def _coordinate(value: str) -> float:
    if len(value) > 32 or NUMBER.fullmatch(value) is None:
        raise ValueError("DXF must use finite decimal coordinates")
    coord = float(value)
    if not isfinite(coord) or abs(coord) > MAX_COORD:
        raise ValueError("DXF coordinate exceeds permitted bounds")
    return coord


def parse_dxf(source: Path) -> list[tuple[str, tuple[float, ...]]]:
    """Decode a strict ASCII DXF with a single ENTITIES section only."""
    size = source.stat().st_size
    if not 0 < size <= MAX_DXF_BYTES:
        raise ValueError("DXF exceeds the 1 MiB ASCII subset limit")
    try:
        text = source.read_bytes().decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Only ASCII DXF is accepted") from exc
    if any(ord(ch) < 32 and ch not in "\n\r" for ch in text):
        raise ValueError("DXF contains binary or control bytes")
    lines = text.splitlines()
    if len(lines) % 2 or len(lines) // 2 > MAX_DXF_PAIRS:
        raise ValueError("Malformed or oversized DXF group-code pairs")
    pairs: list[tuple[int, str]] = []
    for idx in range(0, len(lines), 2):
        code = lines[idx].strip()
        value = lines[idx + 1].strip()
        if not code.isascii() or not code.isdecimal() or len(code) > 3:
            raise ValueError("Invalid DXF group code")
        if len(value) > 256:
            raise ValueError("DXF group value too long")
        pairs.append((int(code), value))
    if pairs[:2] != [(0, "SECTION"), (2, "ENTITIES")]:
        raise ValueError("Only a single DXF ENTITIES section is supported")
    idx = 2
    shapes: list[tuple[str, tuple[float, ...]]] = []
    while idx < len(pairs):
        if pairs[idx] == (0, "ENDSEC"):
            if pairs[idx + 1:] != [(0, "EOF")] or not shapes:
                raise ValueError("DXF must end with ENDSEC/EOF and contain geometry")
            return shapes
        entity = pairs[idx]
        if entity not in ((0, "LINE"), (0, "CIRCLE")):
            raise ValueError("Unsupported DXF entity; no external references permitted")
        idx += 1
        props: dict[int, float] = {}
        metadata: set[int] = set()
        while idx < len(pairs) and pairs[idx][0] != 0:
            code, value = pairs[idx]
            idx += 1
            if code in (5, 8):
                if code in metadata or not (HANDLE if code == 5 else LAYER).fullmatch(value):
                    raise ValueError("Invalid DXF handle or layer metadata")
                metadata.add(code)
            elif code in (10, 20, 11, 21, 30, 31, 40):
                if code in props:
                    raise ValueError("Ambiguous repeated DXF coordinate")
                props[code] = _coordinate(value)
            else:
                # Refuse: attributes, nested references, XDATA, unsupported geometry,
                # styling or object handles. Never silently drop these.
                raise ValueError("DXF attribute is outside the safe 2D subset")
        if entity[1] == "LINE":
            if not {10, 20, 11, 21} <= props.keys() or set(props) - {10, 20, 11, 21, 30, 31}:
                raise ValueError("DXF LINE requires two 2D points")
            if props.get(30, 0) != 0 or props.get(31, 0) != 0:
                raise ValueError("Only 2D DXF is supported")
            vals = (props[10], props[20], props[11], props[21])
            if vals[:2] == vals[2:]:
                raise ValueError("Zero-length DXF line")
        else:
            if not {10, 20, 40} <= props.keys() or set(props) - {10, 20, 40, 30}:
                raise ValueError("DXF CIRCLE requires center and radius")
            if props.get(30, 0) != 0 or props[40] <= 0:
                raise ValueError("Only finite nonzero-radius 2D circles are supported")
            vals = (props[10], props[20], props[40])
        shapes.append((entity[1], vals))
        if len(shapes) > MAX_DXF_ENTITIES:
            raise ValueError("DXF entity count exceeds 2000")
    raise ValueError("DXF missing ENDSEC/EOF")


def restricted_dxf_to_pdf(source: Path, output: Path) -> None:
    """Create one vector PDF page, never modifying the source."""
    if source.resolve() == output.resolve():
        raise ValueError("Source and output must differ")
    shapes = parse_dxf(source)
    bounds: list[tuple[float, float]] = []
    for kind, coords in shapes:
        if kind == "LINE":
            bounds.extend(((coords[0], coords[1]), (coords[2], coords[3])))
        else:
            x, y, r = coords
            bounds.extend(((x - r, y - r), (x + r, y + r)))
    min_x = min(p[0] for p in bounds)
    min_y = min(p[1] for p in bounds)
    width = max(max(p[0] for p in bounds) - min_x, 0.001)
    height = max(max(p[1] for p in bounds) - min_y, 0.001)
    paper = landscape(A4) if width > height else A4
    margin = 40.0
    scale = min((paper[0] - 2 * margin) / width,
                (paper[1] - 2 * margin) / height)
    # Center geometry without interpreting layers, units or external resources.
    x_offset = (paper[0] - width * scale) / 2 - min_x * scale
    y_offset = (paper[1] - height * scale) / 2 - min_y * scale
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=paper, pageCompression=1, invariant=1)
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.8)
    for kind, values in shapes:
        if kind == "LINE":
            x1, y1, x2, y2 = values
            pdf.line(x1 * scale + x_offset, y1 * scale + y_offset,
                     x2 * scale + x_offset, y2 * scale + y_offset)
        else:
            x, y, r = values
            pdf.circle(x * scale + x_offset, y * scale + y_offset,
                       r * scale, stroke=1, fill=0)
    pdf.showPage()
    pdf.save()
    data = buffer.getvalue()
    reader = PdfReader(BytesIO(data), strict=True)
    if not data.startswith(b"%PDF-") or reader.is_encrypted or len(reader.pages) != 1:
        raise ValueError("DXF rendering did not produce a valid PDF")
    output.write_bytes(data)
