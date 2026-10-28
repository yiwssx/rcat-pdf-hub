"""T90-1.6 staged AES-256 protect/unlock PDF engines.

NEVER wire user-supplied passwords to JobRecord.params_json, RQ kwargs,
audit events, telemetry or URL query strings. Implement a reviewed
short-lived secret handoff before exposing this engine through an API.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

_MAX_PAGES = 1000
_MAX_SOURCE_BYTES = 100 * 1024 * 1024
_MAX_PASSWORD_LENGTH = 256


def _check_path(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output PDF paths must differ")
    if source.stat().st_size > _MAX_SOURCE_BYTES:
        raise ValueError("PDF exceeds staged 100 MiB input limit")
    with source.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("Expected a PDF signature")


def _password(value: str, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= _MAX_PASSWORD_LENGTH:
        raise ValueError(f"{field} must be a nonempty bounded string")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _write_atomic(
    writer: PdfWriter, destination: Path, *, expect_encrypted: bool, page_count: int,
) -> None:
    temp: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pdfhub-access-", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as handle:
            temp = handle.name
            writer.write(handle)
        check = PdfReader(temp, strict=True)
        if check.is_encrypted != expect_encrypted:
            raise ValueError("Output PDF encryption state mismatch")
        if expect_encrypted:
            encryption = check.trailer["/Encrypt"]
            if int(encryption["/V"]) != 5 or int(encryption["/R"]) != 6:
                raise ValueError("AES-256 encryption verification failed")
        elif len(check.pages) != page_count:
            raise ValueError("Decrypted output page count mismatch")
        os.replace(temp, destination)
        temp = None
    finally:
        if temp:
            Path(temp).unlink(missing_ok=True)


def protect_pdf(
    source: Path, destination: Path, *, user_password: str, owner_password: str,
) -> None:
    """Create AES-256 revision-6 PDF using distinct supplied user/owner passwords."""
    _password(user_password, "user_password")
    _password(owner_password, "owner_password")
    if user_password == owner_password:
        raise ValueError("Owner and user passwords must differ")
    _check_path(source, destination)
    reader = PdfReader(str(source), strict=True)
    if reader.is_encrypted:
        raise ValueError("Input already encrypted; unlock using valid password first")
    if not 1 <= len(reader.pages) <= _MAX_PAGES:
        raise ValueError("PDF page count outside staged bounds")
    writer = PdfWriter(clone_from=reader)
    writer.encrypt(user_password=user_password, owner_password=owner_password, algorithm="AES-256")
    _write_atomic(writer, destination, expect_encrypted=True, page_count=len(reader.pages))


def unlock_pdf(source: Path, destination: Path, *, password: str) -> None:
    """Decrypt only after a successful user/owner password check."""
    _password(password, "password")
    _check_path(source, destination)
    reader = PdfReader(str(source), strict=True)
    if not reader.is_encrypted:
        raise ValueError("PDF is not password protected")
    if not reader.decrypt(password):
        raise ValueError("Invalid PDF password")
    if not 1 <= len(reader.pages) <= _MAX_PAGES:
        raise ValueError("PDF page count outside staged bounds")
    writer = PdfWriter(clone_from=reader)
    _write_atomic(writer, destination, expect_encrypted=False, page_count=len(reader.pages))
