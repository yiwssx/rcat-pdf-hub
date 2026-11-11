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
from app.t90_2_catalog import FORMAT_CAPABILITIES, EXPERIMENTAL_CODE_PATHS

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



def test_all_forty_format_ids_have_an_engineering_code_path_not_a_release():
    # The user's code-only milestone excludes physical target-host/file tests.
    # Presence of a gated path must never be treated as VERIFIED or RELEASED.
    items = {item.item_id: item for item in FORMAT_CAPABILITIES}
    assert len(items) == len(FORMAT_CAPABILITIES) == 40
    assert set(items) == {f"T{i:02d}" for i in range(1, 41)}
    assert all(item.code_prepared for item in items.values())
    assert sum(item.engineering_state == "STAGED" for item in items.values()) == 34
    assert sum(item.engineering_state == "BLOCKED" for item in items.values()) == 6
    assert set(EXPERIMENTAL_CODE_PATHS) == {
        "T09", "T20", "T25", "T30", "T33", "T34",
    }
    assert set().union(*(set(ops) for ops in EXPERIMENTAL_CODE_PATHS.values())) == (
        set(NATIVE_DEV_TO_PDF_OPERATIONS) | {"url-to-pdf"}
    )
    for item in items.values():
        assert item.development_operations
        if item.item_id in EXPERIMENTAL_CODE_PATHS:
            assert item.operations == ()
            assert item.engineering_state == "BLOCKED"
        else:
            assert item.operations
            assert item.engineering_state == "STAGED"


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


def test_t20_groupcode_metadata_is_allowed_but_entity_xdata_is_rejected(tmp_path):
    """Real DWG readers may emit DXF XDATA codes outside modelspace only."""
    from app.services.to_pdf_dwg_native import _normalize_dwg_dxf

    source = tmp_path / "whole.dxf"
    canonical = tmp_path / "geometry.dxf"
    header = "0\\nSECTION\\n2\\nHEADER\\n1000\\nmetadata-only\\n0\\nENDSEC\\n"
    entities = ("0\\nSECTION\\n2\\nENTITIES\\n0\\nLINE\\n"
                "10\\n10\\n20\\n10\\n11\\n90\\n21\\n40\\n"
                "210\\n0\\n220\\n0\\n230\\n1\\n"
                "0\\nENDSEC\\n0\\nEOF\\n")
    source.write_text(header + entities, encoding="ascii")
    assert _normalize_dwg_dxf(source, canonical) == 1
    assert "1000" not in canonical.read_text(encoding="ascii")
    source.write_text(header + entities.replace(
        "0\\nLINE\\n", "0\\nLINE\\n1000\\nunsafe-entity-xdata\\n",
    ), encoding="ascii")
    with pytest.raises(ValueError, match="unsupported semantics"):
        _normalize_dwg_dxf(source, canonical)
