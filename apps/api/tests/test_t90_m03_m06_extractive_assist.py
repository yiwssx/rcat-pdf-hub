"""M03/M06 are genuinely extracted, owner-delivered, bounded TXT artifacts."""
from hashlib import sha256

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_extractive_assist import analyze_pdf


def make_pdf(tmp_path):
    source = tmp_path / "source.pdf"
    doc = canvas.Canvas(str(source), pagesize=(595, 842))
    doc.drawString(45, 740, "The irrigation controller monitors water temperature and dissolved oxygen.")
    doc.drawString(45, 714, "The controller sends alerts when dissolved oxygen falls below the limit.")
    doc.showPage()
    doc.drawString(45, 740, "Students use the dashboard to inspect water temperature history.")
    doc.drawString(45, 714, "Access controls prevent unauthorized downloads of school reports.")
    doc.save()
    return source


def test_m03_extractive_summary_contains_true_excerpts_and_page_refs(tmp_path):
    source = make_pdf(tmp_path)
    baseline = sha256(source.read_bytes()).hexdigest()
    dest = tmp_path / "summary.txt"
    analyze_pdf(source, dest, mode="summary")
    result = dest.read_text("utf-8")
    assert "EXTRACTIVE PDF SUMMARY" in result
    assert "[Page 1]" in result
    assert "dissolved oxygen" in result
    assert "[Page 2]" in result
    assert "Access controls" in result
    assert sha256(source.read_bytes()).hexdigest() == baseline


def test_m06_evidence_search_never_invents_an_answer(tmp_path):
    source = make_pdf(tmp_path)
    dest = tmp_path / "evidence.txt"
    analyze_pdf(source, dest, mode="evidence", question="dissolved oxygen")
    result = dest.read_text("utf-8")
    assert "[Page 1]" in result
    assert "dissolved oxygen" in result
    assert "[Page 2]" not in result
    assert "Not AI reasoning" in result
    no_match = tmp_path / "no-match.txt"
    analyze_pdf(source, no_match, mode="evidence", question="quantum reactor xyzzy")
    assert "No matching quoted evidence" in no_match.read_text("utf-8")


def test_m03_m06_fail_closed_for_invalid_and_nontext_sources(tmp_path):
    source = tmp_path / "fake.pdf"
    source.write_bytes(b"%PDF-"+b"x"*200)
    with pytest.raises(Exception):
        analyze_pdf(source, tmp_path / "invalid.txt", mode="summary")
    source = make_pdf(tmp_path)
    with pytest.raises(ValueError, match="Question"):
        analyze_pdf(source, tmp_path / "question.txt", mode="evidence", question="x")
    with pytest.raises(ValueError, match="Unexpected question"):
        analyze_pdf(source, tmp_path / "mixed.txt", mode="summary", question="password")
    with pytest.raises(ValueError, match="separate"):
        analyze_pdf(source, source, mode="summary")
    with pytest.raises(ValueError, match="separate"):
        analyze_pdf(source, source, mode="evidence", question="water temperature")


def test_m03_m06_reject_encrypted_pdf(tmp_path):
    source = make_pdf(tmp_path)
    encrypted = tmp_path / "encrypted.pdf"
    reader = PdfReader(str(source))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("open-secret")
    with encrypted.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="Encrypted"):
        analyze_pdf(encrypted, tmp_path / "blocked.txt", mode="summary")


def test_m03_m06_reject_oversized_source_before_hashing(tmp_path):
    from app.services.pdf_extractive_assist import MAX_SOURCE_BYTES
    src = tmp_path / "oversize.pdf"
    with src.open("wb") as stream:
        stream.write(b"%PDF-")
        stream.seek(MAX_SOURCE_BYTES)
        stream.write(b"X")
    with pytest.raises(ValueError, match="size cap"):
        analyze_pdf(src, tmp_path / "no-output.txt", mode="summary")
    assert not (tmp_path / "no-output.txt").exists()
