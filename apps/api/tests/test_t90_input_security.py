"""T90-0.14 bounded Office archive preflight and PDF job input type enforcement."""
from __future__ import annotations

import stat
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import filetypes
from app.services import zip_preflight
from app.filetypes import validate_uploaded_file
from app.routers.pdf import PDF_INPUT_OPERATIONS, _create_job, _is_pdf


def package(path: Path, entries: list[tuple[str, bytes | str]], *,
            mode: int | None = None) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (name, payload) in enumerate(entries):
            if mode is not None and index == len(entries) - 1:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = mode << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, payload)
            else:
                archive.writestr(name, payload)
    return path


def docx_entries():
    return [
        ("[Content_Types].xml", b"<Types/>"),
        ("word/document.xml", b"<w:document/>"),
    ]


@pytest.mark.parametrize("suffix,main,mime", [
    (".docx", "word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    (".xlsx", "xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    (".pptx", "ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
])
def test_small_valid_ooxml_documents_remain_accepted(tmp_path, suffix, main, mime):
    p = package(tmp_path / ("good" + suffix), [
        ("[Content_Types].xml", b"<Types/>"),
        (main, b"<root/>"),
    ])
    assert validate_uploaded_file(p, p.name) == mime


@pytest.mark.parametrize("bad_member", [
    "../outside.xml",
    "/absolute.xml",
    "word/../../escape.xml",
    "word\\evil.xml",
    "C:secret.xml",
    "word//double.xml",
    "word/./dot.xml",
])
def test_office_archive_path_hazards_rejected(tmp_path, bad_member):
    p = package(tmp_path / "bad.docx", docx_entries() + [(bad_member, b"malicious")])
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


def test_duplicate_zip_members_rejected(tmp_path):
    # Python zipfile warns when constructing a deliberate duplicate ZIP entry.
    with pytest.warns(UserWarning, match="Duplicate name"):
        p = package(tmp_path / "duplicate.docx", docx_entries() + [
            ("word/document.xml", b"replacement"),
        ])
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


def test_fake_ooxml_missing_required_main_part_rejected(tmp_path):
    p = package(tmp_path / "fake.docx", [
        ("[Content_Types].xml", b"<Types/>"),
        ("word/fake.xml", b"<w:document/>"),
    ])
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


@pytest.mark.parametrize("bad_member", [
    "word/vbaProject.bin", "word/activeX/activeX1.bin",
])
def test_macros_and_activex_rejected_from_macro_free_ooxml(tmp_path, bad_member):
    p = package(tmp_path / "macro.docx", docx_entries() + [(bad_member, b"payload")])
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


def test_zip_symlink_rejected(tmp_path):
    p = package(tmp_path / "symlink.docx", docx_entries() + [
        ("word/link", b"../../etc/passwd"),
    ], mode=stat.S_IFLNK | 0o777)
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


@pytest.mark.parametrize("limit,value", [
    ("MAX_OFFICE_ZIP_ENTRIES", 1),
    ("MAX_OFFICE_ZIP_ENTRY_BYTES", 5),
    ("MAX_OFFICE_ZIP_UNCOMPRESSED", 8),
])
def test_office_archive_limits_fail_closed(tmp_path, monkeypatch, limit, value):
    p = package(tmp_path / "large.docx", docx_entries())
    monkeypatch.setattr(zip_preflight, limit, value)
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


def test_oversized_declared_expansion_rejected_without_decompression(tmp_path, monkeypatch):
    p = package(tmp_path / "ratio.docx", docx_entries() + [
        ("word/repetitive.xml", b"A" * 50000),
    ])
    monkeypatch.setattr(zip_preflight, "MAX_OFFICE_ZIP_EXPANSION", 1)
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(p, p.name)
    assert exc.value.status_code == 415


def test_valid_odt_preserved_and_invalid_large_mimetype_rejected(tmp_path):
    mime = "application/vnd.oasis.opendocument.text"
    good = package(tmp_path / "good.odt", [
        ("mimetype", mime.encode()),
        ("content.xml", b"<office:document/>"),
    ])
    assert validate_uploaded_file(good, good.name) == mime
    bad = package(tmp_path / "bad.odt", [
        ("mimetype", b"A" * 257),
        ("content.xml", b"<office:document/>"),
    ])
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(bad, bad.name)
    assert exc.value.status_code == 415


def test_pdf_filename_never_overrides_persisted_mime():
    assert not _is_pdf(SimpleNamespace(content_type="image/png", original_name="renamed.pdf"))
    assert _is_pdf(SimpleNamespace(content_type="application/pdf", original_name="any.name"))


@pytest.mark.parametrize("operation", sorted(PDF_INPUT_OPERATIONS))
def test_non_pdf_inputs_fail_before_pdf_job_enqueue(operation):
    record = SimpleNamespace(
        content_type="image/png", original_name="spoofed.pdf",
        source_system="test-user", expires_at=None,
    )
    db = SimpleNamespace(get=lambda model, ident: record)
    principal = SimpleNamespace(name="test-user", scopes={"*"}, is_bootstrap_admin=True)
    with pytest.raises(HTTPException) as exc:
        _create_job(db, principal, operation, ["id"], {})
    assert exc.value.status_code == 415


def test_pdf_named_as_office_and_image_rejected_before_job_enqueue():
    record = SimpleNamespace(
        content_type="application/pdf", original_name="fake.docx",
        source_system="test-user", expires_at=None,
    )
    db = SimpleNamespace(get=lambda model, ident: record)
    principal = SimpleNamespace(name="test-user", scopes={"*"}, is_bootstrap_admin=True)
    for operation in ("office-to-pdf", "images-to-pdf"):
        with pytest.raises(HTTPException) as exc:
            _create_job(db, principal, operation, ["id"], {})
        assert exc.value.status_code == 415
