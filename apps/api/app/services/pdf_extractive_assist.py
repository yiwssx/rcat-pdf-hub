"""M03 extractive PDF summary and M06 quoted document evidence search.

No LLM, network, secret prompts or invented answers: outputs are verifiable
excerpts with page numbers, not abstractive summaries or conversational AI.
Scanned PDFs require the separately available OCR tool.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pypdf import PdfReader

MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT_BYTES = 512 * 1024
MAX_STREAM_BYTES = 8 * 1024 * 1024
MAX_SNIPPETS = 8
MAX_OUTPUT_BYTES = 24 * 1024
TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}|[\u0e00-\u0e7f]{2,}", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


def _load(source: Path) -> list[tuple[int, str]]:
    if source.is_symlink() or not source.is_file():
        raise ValueError("Source must be a regular PDF file")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds extractive assistant source size cap")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Invalid PDF signature")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or large PDF unsupported")
    extracted: list[tuple[int, str]] = []
    total = 0
    for number, page in enumerate(reader.pages, 1):
        contents = page.get_contents()
        if contents is not None and len(contents.get_data()) > MAX_STREAM_BYTES:
            raise ValueError("PDF page content stream over budget")
        raw = page.extract_text() or ""
        total += len(raw.encode("utf-8"))
        if total > MAX_TEXT_BYTES:
            raise ValueError("Extracted text exceeds budget")
        for line in raw.splitlines():
            cleaned = " ".join(line.split()).strip()
            if len(cleaned) < 12:
                continue
            # Preserve the original text, including Thai glyphs and numbers.
            # No semantic sentence reconstruction or invented connective text.
            for i in range(0, len(cleaned), 340):
                part = cleaned[i:i + 340]
                if len(part) >= 12:
                    extracted.append((number, part))
                    if len(extracted) >= 1800:
                        break
            if len(extracted) >= 1800:
                break
        if len(extracted) >= 1800:
            break
    if not extracted:
        raise ValueError("No selectable text layer; run OCR first")
    return extracted


def _summary(rows: list[tuple[int, str]]) -> list[tuple[int, str]]:
    frequency = Counter(token for _, text in rows for token in set(_tokens(text)))
    scored = []
    for index, (page, fragment) in enumerate(rows):
        terms = set(_tokens(fragment))
        # Distinctiveness and occurrence across page passages; no new content.
        score = sum(min(8, frequency[token]) for token in terms) / max(1, len(terms))
        score += 2 / (1 + index / 12)
        scored.append((score, index))
    selected = sorted(index for _, index in sorted(scored, reverse=True)[:MAX_SNIPPETS])
    return [rows[index] for index in selected]


def _evidence(rows: list[tuple[int, str]], question: str) -> list[tuple[int, str]]:
    if type(question) is not str or not 3 <= len(question.strip()) <= 250:
        raise ValueError("Question must be between 3 and 250 characters")
    if any(ord(c) < 32 for c in question):
        raise ValueError("Question contains control characters")
    terms = set(_tokens(question))
    if not terms:
        raise ValueError("Question has no searchable words")
    phrase = question.casefold().strip()
    ranked = []
    for index, (_, fragment) in enumerate(rows):
        found = set(_tokens(fragment))
        matches = len(terms.intersection(found))
        if phrase in fragment.casefold():
            matches += len(terms) + 2
        if matches:
            ranked.append((matches, -index, index))
    return [rows[item[2]] for item in sorted(ranked, reverse=True)[:MAX_SNIPPETS]]


def analyze_pdf(source: Path, destination: Path, *,
                mode: str, question: str = "") -> None:
    """Write bounded UTF-8 evidence with page citations and immutable source."""
    if type(mode) is not str or mode not in {"summary", "evidence"}:
        raise ValueError("Unsupported M03/M06 mode")
    if type(question) is not str or (mode == "summary" and question):
        raise ValueError("Unexpected question for extractive summary")
    if source.resolve() == destination.resolve() or destination.exists() or destination.is_symlink():
        raise ValueError("Source and output must be separate new files")
    # Enforce source budget BEFORE hashing (do not read oversized uploads into memory).
    if source.is_symlink() or not source.is_file() or not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds extractive assistant source size cap")
    before = sha256(source.read_bytes()).digest()
    rows = _load(source)
    found = _summary(rows) if mode == "summary" else _evidence(rows, question)
    title = (
        "EXTRACTIVE PDF SUMMARY / สรุปแบบคัดข้อความจากต้นฉบับ\n"
        if mode == "summary"
        else "PDF EVIDENCE SEARCH / ค้นหลักฐานตามคำถาม\n"
    )
    caveat = (
        "Content below is extracted verbatim from page text and may omit context.\n"
        "Not AI reasoning, translation, OCR, legal certification or an answer guarantee.\n\n"
    )
    body = "".join("[Page " + str(page) + "] " + excerpt + "\n\n"
                   for page, excerpt in found)
    if not found:
        body = "No matching quoted evidence found in the available text layer.\n"
    result = (title + caveat + body).encode("utf-8")
    if not 10 <= len(result) <= MAX_OUTPUT_BYTES:
        raise ValueError("Extractive result exceeds output budget")
    with TemporaryDirectory(prefix="pdfhub-m03-m06-", dir=destination.parent) as temp:
        staged = Path(temp) / "result.txt"
        staged.write_bytes(result)
        if sha256(source.read_bytes()).digest() != before:
            raise ValueError("Input PDF changed during extraction")
        if staged.read_bytes() != result:
            raise ValueError("Result staging failed")
        staged.replace(destination)
