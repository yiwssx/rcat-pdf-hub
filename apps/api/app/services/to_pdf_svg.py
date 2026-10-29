"""T90-2 SVG geometric/text subset rendered as vetted inline SVG.

The uploaded document is NEVER given to Chromium. A new SVG document is
constructed exclusively from known-safe elements and validated primitive
attributes. No stylesheets, scripts, foreign objects, fonts from file, URLs,
references, filters, gradients, images or arbitrary SVG markup.
"""
from __future__ import annotations

from html import escape
from math import isfinite
from pathlib import Path
import re

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

SVG_NS = "http://www.w3.org/2000/svg"
MAX_SVG_BYTES = 2 * 1024 * 1024
MAX_SVG_ELEMENTS = 600
MAX_SVG_DEPTH = 20
MAX_SVG_TEXT = 20_000
MAX_PATH_CHARS = 20_000

GROUPS = frozenset({"svg", "g"})
SHAPES = frozenset({"rect", "circle", "ellipse", "line", "polyline", "polygon", "path"})
TEXT = frozenset({"text", "tspan"})
ALLOWED = GROUPS | SHAPES | TEXT
COMMON = frozenset({"fill", "stroke", "stroke-width", "fill-opacity", "stroke-opacity", "opacity"})
GEOMETRY = {
    "svg": frozenset({"width", "height", "viewBox"}),
    "g": frozenset(),
    "rect": frozenset({"x", "y", "width", "height", "rx", "ry"}),
    "circle": frozenset({"cx", "cy", "r"}),
    "ellipse": frozenset({"cx", "cy", "rx", "ry"}),
    "line": frozenset({"x1", "y1", "x2", "y2"}),
    "polyline": frozenset({"points"}),
    "polygon": frozenset({"points"}),
    "path": frozenset({"d"}),
    "text": frozenset({"x", "y", "font-size", "text-anchor"}),
    "tspan": frozenset({"x", "y", "dx", "dy", "font-size"}),
}
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
NUM_LIST = re.compile(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:[\s,]+[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)*\s*\Z")
PATH_CHARS = re.compile(r"[MLHVCSQTAZmlhvcsqtaz0-9eE.,+\-\s]*\Z")
PAINT = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\Z")
NAMED_PAINT = frozenset({
    "none", "black", "white", "red", "green", "blue", "yellow",
    "orange", "purple", "gray", "grey", "navy", "teal", "transparent",
})
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 600


def _numbers(value: str, *, minimum: int = 1, maximum: int = 4) -> list[float]:
    if len(value) > 256 or not NUM_LIST.fullmatch(value):
        raise ValueError("Invalid SVG numeric coordinate list")
    values = re.split(r"[\s,]+", value.strip())
    if not minimum <= len(values) <= maximum:
        raise ValueError("Unsupported SVG coordinate count")
    numbers = [float(x) for x in values]
    if any(not isfinite(x) or abs(x) > 100_000 for x in numbers):
        raise ValueError("SVG coordinates exceed bounds")
    return numbers


def _number(value: str) -> float:
    if len(value) > 40 or NUMBER.fullmatch(value) is None:
        raise ValueError("Invalid SVG numeric attribute")
    number = float(value)
    if not isfinite(number) or abs(number) > 100_000:
        raise ValueError("SVG numeric coordinate outside bounds")
    return number


def _attribute(key: str, value: str) -> str:
    if key in {"fill", "stroke"}:
        if value not in NAMED_PAINT and not PAINT.fullmatch(value):
            raise ValueError("SVG paint only supports solid colors")
    elif key == "text-anchor":
        if value not in {"start", "middle", "end"}:
            raise ValueError("Invalid SVG text anchor")
    elif key == "viewBox":
        values = _numbers(value, minimum=4, maximum=4)
        if values[2] <= 0 or values[3] <= 0:
            raise ValueError("Invalid SVG viewBox dimensions")
    elif key == "points":
        if len(value) > MAX_PATH_CHARS:
            raise ValueError("SVG polygon points too long")
        values = _numbers(value, minimum=4, maximum=2000)
        if len(values) % 2:
            raise ValueError("SVG polygon points must have x/y pairs")
    elif key == "d":
        if not 0 < len(value) <= MAX_PATH_CHARS or not PATH_CHARS.fullmatch(value):
            raise ValueError("Invalid SVG path commands")
        # Path strings cannot contain CSS functions, references or arbitrary text.
        if not re.search(r"[Mm]", value):
            raise ValueError("SVG path must start with a move command")
        if len(re.findall(r"[A-Za-z]", value)) > 500:
            raise ValueError("SVG path command count exceeds limits")
    else:
        number = _number(value)
        if key in {"width", "height", "rx", "ry", "r", "stroke-width", "font-size"} and number < 0:
            raise ValueError("SVG dimensions must be nonnegative")
        if key in {"opacity", "fill-opacity", "stroke-opacity"} and not 0 <= number <= 1:
            raise ValueError("SVG opacity outside 0..1")
        if key in {"width", "height", "font-size"} and number > 4096:
            raise ValueError("SVG dimensions exceed 4096")
    return value


def safe_svg_markup(source: Path) -> str:
    """Convert strictly validated SVG XML into a newly built safe inline SVG."""
    if not 0 < source.stat().st_size <= MAX_SVG_BYTES:
        raise ValueError("SVG input outside 2 MiB limit")
    raw = source.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("SVG must be UTF-8 XML") from exc
    if any(ord(c) < 32 and c not in "\t\r\n" for c in text):
        raise ValueError("SVG has invalid control characters")
    try:
        root = SafeET.fromstring(text)
    except (SafeET.ParseError, DefusedXmlException, UnicodeError, ValueError) as exc:
        raise ValueError("SVG XML unsafe or malformed") from exc

    def tagname(value: str) -> str:
        if value.startswith("{"):
            uri, _, name = value[1:].partition("}")
            if uri != SVG_NS:
                raise ValueError("Foreign SVG namespace rejected")
            return name
        return value

    if tagname(root.tag) != "svg":
        raise ValueError("SVG root must be svg")
    count, chars = 0, 0

    def walk(node, depth: int, *, in_text: bool = False) -> str:
        nonlocal count, chars
        count += 1
        if count > MAX_SVG_ELEMENTS or depth > MAX_SVG_DEPTH:
            raise ValueError("SVG element count/depth exceeds limits")
        name = tagname(node.tag)
        if name not in ALLOWED or (name == "svg" and depth != 1):
            raise ValueError("Unsupported SVG element or unsafe active content")
        if in_text and name not in TEXT:
            raise ValueError("SVG text cannot contain geometric children")
        if name in SHAPES and len(node):
            raise ValueError("SVG shapes cannot contain child elements")
        if name in TEXT and any(tagname(child.tag) not in TEXT for child in node):
            raise ValueError("SVG text contains unsupported child")
        attrs = {}
        for raw_key, value in node.attrib.items():
            if raw_key.startswith("{"):
                raise ValueError("Namespaced SVG attributes and external references rejected")
            if raw_key not in COMMON | GEOMETRY[name]:
                raise ValueError("Unsupported SVG attribute (including links/style/events)")
            attrs[raw_key] = _attribute(raw_key, value)
        if name == "svg":
            attrs.setdefault("width", str(DEFAULT_WIDTH))
            attrs.setdefault("height", str(DEFAULT_HEIGHT))
            attrs.setdefault("viewBox", f"0 0 {attrs['width']} {attrs['height']}")
            attrs["xmlns"] = SVG_NS
        elif name in TEXT:
            attrs["font-family"] = "Noto Sans Thai, Sarabun, sans-serif"
        elif node.text and node.text.strip():
            raise ValueError("SVG geometry cannot contain unbounded text")
        if len(node) and name in SHAPES:
            raise ValueError("SVG shape children rejected")
        parts = ["<", name]
        for key, val in sorted(attrs.items()):
            parts.append(f' {key}="{escape(val, quote=True)}"')
        parts.append(">")
        if node.text and name in TEXT:
            chars += len(node.text)
            if chars > MAX_SVG_TEXT:
                raise ValueError("SVG text character limit exceeded")
            parts.append(escape(node.text))
        for child in node:
            parts.append(walk(child, depth + 1, in_text=(name in TEXT)))
            if child.tail:
                if name not in TEXT and child.tail.strip():
                    raise ValueError("SVG geometry contains forbidden trailing text")
                if name in TEXT:
                    chars += len(child.tail)
                    if chars > MAX_SVG_TEXT:
                        raise ValueError("SVG text character limit exceeded")
                    parts.append(escape(child.tail))
        parts.extend(["</", name, ">"])
        return "".join(parts)

    result = walk(root, 1)
    if count <= 1:
        raise ValueError("SVG has no printable shapes or text")
    return result
