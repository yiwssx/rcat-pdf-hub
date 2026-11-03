"""F12: bounded PDF -> one isolated SVG per page in an ordered ZIP.

Poppler writes vector-like SVG paths but does not promise editable PDF text.
Never claim arbitrary complex/scanned PDFs become editable SVG text.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import resource
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_PAGES = 12
MAX_SVG_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 72 * 1024 * 1024
SVG_NS = "{http://www.w3.org/2000/svg}"
HREF_NAMES = {"href", "{http://www.w3.org/1999/xlink}href"}
UNSAFE_TAGS = {"script", "foreignObject", "iframe", "object", "embed", "audio", "video", "animate", "set"}
URL_RE = re.compile(r"url\(\s*['\"]?([^\)'\"]+)", re.IGNORECASE)


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    resource.setrlimit(resource.RLIMIT_AS, (900 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_SVG_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _verify_generated_svg(data: bytes) -> None:
    if not 120 <= len(data) <= MAX_SVG_BYTES:
        raise ValueError("SVG output exceeds individual page budget")
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise ValueError("SVG renderer emitted invalid or unsafe XML") from exc
    if root.tag != SVG_NS + "svg":
        raise ValueError("SVG renderer did not emit an SVG document")
    for element in root.iter():
        local = element.tag.split("}")[-1]
        if local in UNSAFE_TAGS:
            raise ValueError("SVG contains active content")
        for key, value in element.attrib.items():
            if key.lower().startswith("on"):
                raise ValueError("SVG event handler disallowed")
            if key in HREF_NAMES and not (
                value.startswith("#") or value.startswith("data:image/png;base64,")
                or value.startswith("data:image/jpeg;base64,")
            ):
                raise ValueError("SVG contains external asset link")
            if any(not link.strip().startswith("#") for link in URL_RE.findall(value)):
                raise ValueError("SVG contains external URL")
        if element.text and any(
            not link.strip().startswith("#") for link in URL_RE.findall(element.text)
        ):
            raise ValueError("SVG stylesheet contains external URL")


def pdf_to_svg_zip(source: Path, output: Path) -> None:
    if (source.is_symlink() or not source.is_file() or source.resolve() == output.resolve()
            or output.exists() or output.is_symlink()):
        raise ValueError("SVG input and output must be separate regular files")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds SVG converter input budget")
    pdf = PdfReader(str(source), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF cannot be exported to SVG")
    for page in pdf.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if not (math.isfinite(width) and math.isfinite(height)
                and 1 <= width <= 4000 and 1 <= height <= 4000):
            raise ValueError("Unsupported PDF page geometry for SVG")

    with TemporaryDirectory(prefix="pdfhub-frompdf-svg-") as folder:
        root = Path(folder)
        result = root / "result.zip"
        with ZipFile(result, "w", compression=ZIP_STORED, allowZip64=False) as bundle:
            for page_no in range(1, len(pdf.pages) + 1):
                page_path = root / f"page-{page_no:04d}.svg"
                try:
                    run = subprocess.run(
                        ["pdftocairo", "-svg", "-f", str(page_no), "-l",
                         str(page_no), str(source), str(page_path)],
                        shell=False, check=False, timeout=50,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        close_fds=True, preexec_fn=_limits,
                        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise ValueError("SVG rendering unavailable or timed out") from exc
                if run.returncode != 0 or not page_path.is_file() or page_path.is_symlink():
                    raise ValueError("PDF page SVG rendering failed")
                if page_path.stat().st_size > MAX_SVG_BYTES:
                    raise ValueError("SVG renderer generated an oversized page")
                page_content = page_path.read_bytes()
                _verify_generated_svg(page_content)
                bundle.writestr(page_path.name, page_content)
                page_path.unlink()
                if result.stat().st_size > MAX_OUTPUT_BYTES:
                    raise ValueError("SVG page ZIP exceeds output budget")
        with ZipFile(result) as proof:
            if (proof.namelist() != [f"page-{n:04d}.svg" for n in range(1, len(pdf.pages) + 1)]
                    or proof.testzip() is not None):
                raise ValueError("SVG archive page inventory or CRC invalid")
            for info in proof.infolist():
                if info.compress_type != ZIP_STORED or not 120 <= info.file_size <= MAX_SVG_BYTES:
                    raise ValueError("SVG archive member exceeds contract")
        if output.exists() or output.is_symlink():
            raise ValueError("SVG destination already exists")
        with result.open("rb") as original, output.open("xb") as destination:
            while chunk := original.read(1024 * 1024):
                destination.write(chunk)
