"""Native output descriptor hardening regression coverage.

These are source-authored tests, NOT executed or interpreted as acceptance.
They do not launch CHM, Works, HEIF or LibreDWG binaries.
"""
from __future__ import annotations

import os

import pytest

from app.services.native_output_guard import copy_native_regular_output


def test_native_output_regular_file_promoted_to_separate_private_path(tmp_path):
    raw = tmp_path / "untrusted"
    verified = tmp_path / "verified"
    raw.mkdir()
    verified.mkdir()
    source = raw / "document.odt"
    contents = b"known-bounded-native-bytes"
    source.write_bytes(contents)
    target = verified / "document.odt"

    written = copy_native_regular_output(
        source, target, maximum_bytes=128, minimum_bytes=len(contents),
    )
    assert written == len(contents)
    assert target.read_bytes() == contents
    assert source.read_bytes() == contents


def test_native_output_symlink_cannot_exfiltrate_other_job(tmp_path):
    secret = tmp_path / "private-other-job-token"
    secret.write_bytes(b"not-for-native-reader")
    raw = tmp_path / "untrusted"
    verified = tmp_path / "verified"
    raw.mkdir()
    verified.mkdir()
    (raw / "document.odt").symlink_to(secret)
    target = verified / "document.odt"

    with pytest.raises(ValueError):
        copy_native_regular_output(raw / "document.odt", target, maximum_bytes=256)
    assert not target.exists()


def test_native_output_hardlinks_are_rejected(tmp_path):
    raw = tmp_path / "raw"
    verified = tmp_path / "trusted"
    raw.mkdir()
    verified.mkdir()
    source = raw / "image.png"
    source.write_bytes(b"PNG-data")
    os.link(source, raw / "duplicate.png")
    with pytest.raises(ValueError):
        copy_native_regular_output(
            source, verified / "image.png", maximum_bytes=256,
        )


def test_native_output_fifo_rejected_without_blocking(tmp_path):
    raw = tmp_path / "raw"
    verified = tmp_path / "trusted"
    raw.mkdir()
    verified.mkdir()
    pipe = raw / "document.odt"
    os.mkfifo(pipe)
    with pytest.raises(ValueError):
        copy_native_regular_output(pipe, verified / "document.odt", maximum_bytes=1024)


def test_native_output_rejects_invalid_sizes_and_reuse(tmp_path):
    raw = tmp_path / "raw"
    trusted = tmp_path / "trusted"
    raw.mkdir()
    trusted.mkdir()
    source = raw / "source.dxf"
    source.write_bytes(b"0123456789")
    target = trusted / "source.dxf"
    with pytest.raises(ValueError):
        copy_native_regular_output(source, target, maximum_bytes=9)
    with pytest.raises(ValueError):
        copy_native_regular_output(
            source, target, maximum_bytes=100, minimum_bytes=11,
        )
    with pytest.raises(ValueError):
        copy_native_regular_output(
            source, raw / "another.dxf", maximum_bytes=100,
        )
    target.write_bytes(b"untouched")
    with pytest.raises(ValueError):
        copy_native_regular_output(source, target, maximum_bytes=100)
    assert target.read_bytes() == b"untouched"
