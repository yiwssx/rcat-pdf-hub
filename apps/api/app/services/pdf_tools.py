import subprocess
from pathlib import Path

import httpx

from app.config import get_settings

settings = get_settings()


def _run(args: list[str], timeout: int = 1800) -> None:
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "PDF command failed")[-4000:]
        raise RuntimeError(message)


def merge(inputs: list[Path], output: Path) -> None:
    page_args: list[str] = []
    for item in inputs:
        page_args.extend([str(item), "1-z"])
    _run(["qpdf", "--empty", "--pages", *page_args, "--", str(output)])


def split(input_file: Path, pages: str, output: Path) -> None:
    _run(["qpdf", str(input_file), "--pages", ".", pages, "--", str(output)])


def rotate(input_file: Path, degrees: int, pages: str, output: Path) -> None:
    if degrees not in {-270, -180, -90, 90, 180, 270}:
        raise ValueError("degrees must be one of ±90, ±180, ±270")
    sign = "+" if degrees > 0 else ""
    _run(["qpdf", str(input_file), str(output), f"--rotate={sign}{degrees}:{pages}"])


def compress(input_file: Path, output: Path) -> None:
    _run([
        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6", "-dPDFSETTINGS=/ebook",
        "-dNOPAUSE", "-dQUIET", "-dBATCH", "-dDetectDuplicateImages=true",
        f"-sOutputFile={output}", str(input_file),
    ])


def ocr(input_file: Path, output: Path, languages: str, deskew: bool, rotate_pages: bool) -> None:
    args = ["ocrmypdf", "--skip-text", "--optimize", "1", "-l", languages]
    if deskew:
        args.append("--deskew")
    if rotate_pages:
        args.append("--rotate-pages")
    args.extend([str(input_file), str(output)])
    _run(args)


def pdfa(input_file: Path, output: Path, languages: str = "tha+eng") -> None:
    _run(["ocrmypdf", "--skip-text", "--output-type", "pdfa-2", "-l", languages, str(input_file), str(output)])


def office_to_pdf(input_file: Path, output: Path) -> None:
    with input_file.open("rb") as fh:
        response = httpx.post(
            f"{settings.gotenberg_url}/forms/libreoffice/convert",
            files={"files": (input_file.name, fh, "application/octet-stream")},
            timeout=300.0,
        )
    response.raise_for_status()
    output.write_bytes(response.content)
