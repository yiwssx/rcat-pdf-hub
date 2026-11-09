"""M03 document-grounded, offline extractive PDF summarization.

Extracts and ranks sentences already present in the searchable PDF text layer.
No generative model, translation, OCR, guessed facts or external network. Every
result sentence is a verbatim source excerpt with a one-based source page.
"""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pypdf import PdfReader

MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024
MAX_PAGES = 60
MAX_EXTRACTED_CHARS = 120_000
MAX_SENTENCES = 10
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।。！？])\s+|\n+")
_SPACE = re.compile(r"[ \t]+")
_MAX_CANDIDATES = 2500


def _features(sentence: str) -> set[str]:
    # Unicode character n-grams also work with Thai without requiring an
    # external dictionary or pretending whitespace tokenization is sufficient.
    content = "".join(ch.casefold() for ch in sentence if ch.isalnum())
    if len(content) < 3:
        return set()
    return {content[i:i + 3] for i in range(len(content) - 2)}


def summarize_pdf_text(source: Path, destination: Path, *, sentence_count: int = 6) -> None:
    if (type(sentence_count) is not int
            or not 1 <= sentence_count <= MAX_SENTENCES):
        raise ValueError("Summary sentence count must be 1–10")
    if (source.is_symlink() or not source.is_file()
            or source.resolve() == destination.resolve()
            or destination.exists() or destination.is_symlink()):
        raise ValueError("M03 input/output must be distinct regular paths")
    if not 24 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("M03 PDF source size outside supported budget")
    with source.open("rb") as fh:
        if fh.read(5) != b"%PDF-":
            raise ValueError("M03 only accepts actual PDF input")
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Encrypted or excessive-page PDF unsupported")

    candidates: list[tuple[int, str, set[str]]] = []
    chars = 0
    for page_num, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        chars += len(extracted)
        if chars > MAX_EXTRACTED_CHARS:
            raise ValueError("M03 extracted text exceeds bounded source budget")
        for segment in _SENTENCE_SPLIT.split(extracted):
            sentence = _SPACE.sub(" ", segment.strip())
            if not 30 <= len(sentence) <= 500:
                continue
            if any(ord(ch) < 32 for ch in sentence):
                continue
            features = _features(sentence)
            if len(features) < 10:
                continue
            candidates.append((page_num, sentence, features))
            if len(candidates) > _MAX_CANDIDATES:
                raise ValueError("M03 document has too many candidate sentences")
    if not candidates:
        raise ValueError("No summarizable searchable text layer: run OCR first for scanned PDF")

    df: Counter[str] = Counter()
    for _, _, features in candidates:
        df.update(features)
    total = len(candidates)
    scored = []
    for order, (page, sentence, features) in enumerate(candidates):
        signal = sum(
            math.log1p(df[feature]) * math.log(1 + total / (1 + df[feature]))
            for feature in features
        ) / math.sqrt(len(features))
        # Lead sentences may convey more context, but cannot dominate
        # cross-document relevance. This is ranking, never fabricated prose.
        signal += .10 / (1 + order)
        scored.append((signal, order, page, sentence, features))
    scored.sort(key=lambda item: (-item[0], item[1]))

    chosen: list[tuple[int, int, str, set[str]]] = []
    for _, order, page, sentence, features in scored:
        if len(chosen) >= sentence_count:
            break
        # Avoid near-duplicate quotes dominating the returned extract.
        if any(len(features & previous) / max(1, len(features | previous)) > .7
               for _, _, _, previous in chosen):
            continue
        chosen.append((order, page, sentence, features))
    if not chosen:
        raise ValueError("No distinct meaningful text segments found")
    chosen.sort(key=lambda item: item[0])
    summary = [
        "RCAT PDF HUB - M03 Extractive PDF Summary",
        "Method: offline extraction of verbatim source sentences; not generative AI.",
        "Each excerpt references the original page. Verify interpretation against the document.",
        "",
    ]
    summary.extend(f"[page {page}] {sentence}" for _, page, sentence, _ in chosen)
    payload = ("\n".join(summary) + "\n").encode("utf-8")
    if not 80 <= len(payload) <= MAX_OUTPUT_BYTES:
        raise ValueError("M03 summary outside output budget")
    with TemporaryDirectory(prefix="pdfhub-m03-extractive-") as folder:
        staged = Path(folder) / "summary.txt"
        with staged.open("xb") as out:
            out.write(payload)
        if staged.read_bytes() != payload:
            raise ValueError("M03 summary bytes failed roundtrip")
        staged.replace(destination)
