"""T90-2 5 native-format experimental gates and internal dispatch contract.

These regression cases deliberately do NOT execute external native codecs,
change production flags, require shell privileges or proclaim T09/20/25/30/34
visually verified. Real acceptance must run on the target Docker/host.
"""
from __future__ import annotations

import struct

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.queue import queue_class_for_operation
from app.staged_to_pdf_adapters import (
    NATIVE_DEV_TO_PDF_INPUTS, NATIVE_DEV_TO_PDF_OPERATIONS,
    STAGED_TO_PDF_OPERATIONS, execute_native_dev_to_pdf_operation,
    native_dev_enabled,
)
from app.t90_2_catalog import FORMAT_CAPABILITIES

CASES = [
    ("heic-to-pdf", ".heic", "image/heic", "heif_native_dev_enabled"),
    ("heif-to-pdf", ".heif", "image/heif", "heif_native_dev_enabled"),
    ("dwg-to-pdf", ".dwg", "image/vnd.dwg", "dwg_native_dev_enabled"),
    ("chm-to-pdf", ".chm", "application/vnd.ms-htmlhelp", "chm_native_dev_enabled"),
    ("wps-to-pdf", ".wps", "application/vnd.ms-works", "wps_native_dev_enabled"),
]


def _source(suffix: str) -> bytes:
    if suffix == ".heic":
        return struct.pack(">I", 24) + b"ftypheic" + b"\x00" * 4 + b"mif1heix"
    if suffix == ".heif":
        return struct.pack(">I", 24) + b"ftypmif1" + b"\x00" * 4 + b"msf1heif"
    if suffix == ".dwg":
        return b"AC1027" + b"\x00" * 42
    if suffix == ".chm":
        return b"ITSF" + b"\x00" * 124
    if suffix == ".wps":
        # No authoritative Works binary signature; actual parser MUST vet it.
        return b"not-a-validated-works-document"
    raise AssertionError(suffix)


def test_native_experimental_routes_do_not_claim_staged_or_verified():
    assert len(CASES) == len(NATIVE_DEV_TO_PDF_OPERATIONS) == 5
    assert not (STAGED_TO_PDF_OPERATIONS & NATIVE_DEV_TO_PDF_OPERATIONS)
    assert sum(c.engineering_state == "BLOCKED" for c in FORMAT_CAPABILITIES) == 6
    assert all(c.operations == () for c in FORMAT_CAPABILITIES
               if c.item_id in {"T09", "T20", "T25", "T30", "T34", "T33"})


@pytest.mark.parametrize("operation,suffix,mime,flag", CASES)
def test_native_upload_and_queue_require_both_flags(monkeypatch, tmp_path,
                                                     operation, suffix, mime, flag):
    settings = get_settings()
    source = tmp_path / ("native" + suffix)
    source.write_bytes(_source(suffix))
    assert NATIVE_DEV_TO_PDF_INPUTS[operation] == (mime, suffix, flag)
    monkeypatch.setattr(settings, "to_pdf_tools_enabled", False)
    monkeypatch.setattr(settings, flag, False)
    assert not native_dev_enabled(operation)
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(source, source.name)
    assert exc.value.status_code == 415
    with pytest.raises(ValueError):
        queue_class_for_operation(operation)

    monkeypatch.setattr(settings, "to_pdf_tools_enabled", True)
    assert not native_dev_enabled(operation)
    monkeypatch.setattr(settings, flag, True)
    assert native_dev_enabled(operation)
    assert validate_uploaded_file(source, source.name) == mime
    assert queue_class_for_operation(operation) == "heavy"
    monkeypatch.setattr(settings, "to_pdf_tools_enabled", False)
    assert not native_dev_enabled(operation)


@pytest.mark.parametrize("operation,suffix,mime,flag", CASES)
def test_native_dispatch_rejects_bad_inputs_and_params(monkeypatch, tmp_path,
                                                       operation, suffix, mime, flag):
    settings = get_settings()
    monkeypatch.setattr(settings, "to_pdf_tools_enabled", True)
    monkeypatch.setattr(settings, flag, True)
    source = tmp_path / ("native" + suffix)
    source.write_bytes(_source(suffix))
    target = tmp_path / "output.pdf"

    kwargs = {"original_name": source.name, "content_type": mime}
    with pytest.raises(ValueError):
        execute_native_dev_to_pdf_operation(operation, [], target, {}, **kwargs)
    with pytest.raises(ValueError):
        execute_native_dev_to_pdf_operation(operation, [source], target, {"extra": True}, **kwargs)
    with pytest.raises(ValueError):
        execute_native_dev_to_pdf_operation(
            operation, [source], target, {}, original_name="fake.exe", content_type=mime)
    with pytest.raises(ValueError):
        execute_native_dev_to_pdf_operation(
            operation, [source], target, {}, original_name=source.name,
            content_type="application/octet-stream")
    monkeypatch.setattr(settings, flag, False)
    with pytest.raises(ValueError):
        execute_native_dev_to_pdf_operation(operation, [source], target, {}, **kwargs)
    assert not target.exists()
