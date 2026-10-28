"""Real binary T90-1.6 AES-256 password security tests."""
import hashlib
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services.pdf_access_control import protect_pdf, unlock_pdf


def _fixture(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=(500, 700))
    c.drawString(72, 600, "SECRET PDF CONTENT T90")
    c.showPage()
    c.save()
    return path


def test_aes256_encrypt_and_unlock_content_preservation(tmp_path: Path):
    source = _fixture(tmp_path / "original.pdf")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    encrypted, clear = tmp_path / "locked.pdf", tmp_path / "clear.pdf"
    protect_pdf(source, encrypted, user_password="user:ภาษาไทย", owner_password="owner:secure-256")
    locked = PdfReader(str(encrypted), strict=True)
    assert locked.is_encrypted
    assert int(locked.trailer["/Encrypt"]["/V"]) == 5
    assert int(locked.trailer["/Encrypt"]["/R"]) == 6
    authenticated = locked.decrypt("user:ภาษาไทย")
    assert authenticated != 0
    assert "SECRET PDF" in locked.pages[0].extract_text()
    unlock_pdf(encrypted, clear, password="user:ภาษาไทย")
    result = PdfReader(str(clear), strict=True)
    assert not result.is_encrypted
    assert len(result.pages) == 1
    assert "SECRET PDF CONTENT T90" in result.pages[0].extract_text()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_owner_password_authorized_unlock(tmp_path: Path):
    source = _fixture(tmp_path / "original.pdf")
    encrypted, clear = tmp_path / "locked.pdf", tmp_path / "clear.pdf"
    protect_pdf(source, encrypted, user_password="user-pass", owner_password="owner-pass")
    unlock_pdf(encrypted, clear, password="owner-pass")
    assert not PdfReader(str(clear)).is_encrypted


@pytest.mark.parametrize("bad", ["wrong", "not-owner", "user-pass "])
def test_wrong_password_no_output(tmp_path: Path, bad: str):
    source = _fixture(tmp_path / "original.pdf")
    encrypted = tmp_path / "locked.pdf"
    protect_pdf(source, encrypted, user_password="user-pass", owner_password="owner-pass")
    out = tmp_path / "no.pdf"
    with pytest.raises(ValueError, match="Invalid PDF password"):
        unlock_pdf(encrypted, out, password=bad)
    assert not out.exists()


@pytest.mark.parametrize("bad", ["", "X" * 257, "newline\npass", "control\x00pass", 123])
def test_protect_bad_password_rejected(tmp_path: Path, bad):
    source = _fixture(tmp_path / "original.pdf")
    out = tmp_path / "no.pdf"
    with pytest.raises(ValueError):
        protect_pdf(source, out, user_password=bad, owner_password="owner-pass")
    assert not out.exists()


def test_no_plaintext_unlock_and_distinct_owner_password(tmp_path: Path):
    source = _fixture(tmp_path / "original.pdf")
    out = tmp_path / "no.pdf"
    with pytest.raises(ValueError):
        protect_pdf(source, out, user_password="same", owner_password="same")
    with pytest.raises(ValueError, match="not password protected"):
        unlock_pdf(source, out, password="wrong")
    assert not out.exists()


def test_reject_wrong_signature_and_source_equals_target(tmp_path: Path):
    source = _fixture(tmp_path / "original.pdf")
    invalid = tmp_path / "bad.pdf"
    invalid.write_bytes(b"not a PDF file")
    with pytest.raises(ValueError, match="differ"):
        protect_pdf(source, source, user_password="pass", owner_password="owner-pass")
    with pytest.raises(ValueError, match="signature"):
        protect_pdf(invalid, tmp_path / "out.pdf", user_password="pass", owner_password="owner-pass")
