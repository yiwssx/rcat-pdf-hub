"""T90-2 network-isolated native decoder boundary — no real codecs required.

These tests exercise the authenticated protocol, prohibited fallback and
codec-only dispatch. Docker security is separately tested in native CI.
"""
from __future__ import annotations

import hmac

import pytest

from app.services.native_sidecar_client import MAX_INPUT, MAX_PDF, signature
from app.staged_to_pdf_adapters import NATIVE_DEV_TO_PDF_INPUTS, NATIVE_DEV_TO_PDF_OPERATIONS


def test_hmac_native_request_and_response_bound_to_operation_nonce_payload():
    key = b"k" * 48
    body = b"ITSF" + bytes(180)
    stamp = "1793600000"
    nonce = "a" * 32
    signed = signature(key, b"request", "chm-to-pdf", stamp, nonce, body)
    assert len(signed) == 64
    assert hmac.compare_digest(signed, signature(
        key, b"request", "chm-to-pdf", stamp, nonce, body))
    assert not hmac.compare_digest(signed, signature(
        key, b"request", "heic-to-pdf", stamp, nonce, body))
    assert not hmac.compare_digest(signed, signature(
        key, b"request", "chm-to-pdf", stamp, "b" * 32, body))
    assert not hmac.compare_digest(signed, signature(
        key, b"request", "chm-to-pdf", stamp, nonce, body + b"tamper"))
    assert not hmac.compare_digest(signed, signature(
        key, b"response", "chm-to-pdf", stamp, nonce, body))


def test_only_five_native_formats_and_all_have_independent_type_checks():
    assert set(NATIVE_DEV_TO_PDF_INPUTS) == NATIVE_DEV_TO_PDF_OPERATIONS
    assert set(NATIVE_DEV_TO_PDF_INPUTS) == {
        "chm-to-pdf", "heif-to-pdf", "heic-to-pdf", "dwg-to-pdf", "wps-to-pdf",
    }
    for operation, (mime, ext, flag) in NATIVE_DEV_TO_PDF_INPUTS.items():
        assert mime and ext.startswith(".") and flag.endswith("_native_dev_enabled")
        assert operation == ext[1:] + "-to-pdf"
    assert 16 <= MAX_INPUT <= 24 * 1024 * 1024
    assert 16 <= MAX_PDF <= 40 * 1024 * 1024


def test_trusted_worker_native_dispatch_rejects_missing_remote_service(monkeypatch, tmp_path):
    from app import staged_to_pdf_adapters as staged
    from app.services import native_sidecar_client
    from app.config import get_settings

    # The trusted worker may never locally decode a document as fallback
    # when the isolated native service is missing or misconfigured.
    options = get_settings()
    monkeypatch.setattr(options, "to_pdf_tools_enabled", True)
    monkeypatch.setattr(options, "chm_native_dev_enabled", True)
    monkeypatch.setattr(options, "native_sidecar_shared_secret", "")
    source = tmp_path / "source.chm"
    source.write_bytes(b"ITSF" + b"\x00" * 128)
    output = tmp_path / "result.pdf"
    with pytest.raises(ValueError, match="not provisioned"):
        native_sidecar_client.convert_native_remotely("chm-to-pdf", source, output)
    assert not output.exists()
    # API-level dispatch remains independent from direct native engine imports.
    assert "execute_native_dev_to_pdf_operation" in dir(staged)


def test_sidecar_dispatch_rejects_unflagged_codec(monkeypatch, tmp_path):
    from app.config import get_settings
    from app.services.native_sidecar_server import execute_isolated_native
    settings = get_settings()
    monkeypatch.setattr(settings, "to_pdf_tools_enabled", False)
    input_path = tmp_path / "source.chm"
    input_path.write_bytes(b"ITSF" + b"\x00" * 128)
    with pytest.raises(ValueError, match="unavailable"):
        execute_isolated_native("chm-to-pdf", input_path, tmp_path / "out.pdf")
