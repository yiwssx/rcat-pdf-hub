"""Native sandbox CLI mount ordering and secret minimization regression.

Runs without Bubblewrap or native decoders installed. A separate QA check
must still execute the true bwrap process in the RCAT Docker worker.
"""
from __future__ import annotations


import pytest

from app.services import native_sandbox
from app.services.native_sandbox import SANDBOX_INPUT, SANDBOX_OUTPUT


def _setup(monkeypatch, tmp_path):
    executable = tmp_path / "bwrap"
    executable.write_bytes(b"fake executable for command construction")
    monkeypatch.setattr(native_sandbox, "BWRAP", executable)
    return executable


def _args(source, output):
    args = ["/opt/venv/bin/python", "-c", "print('sandbox')", SANDBOX_INPUT]
    if output is not None:
        args += [SANDBOX_OUTPUT + "/page.png"]
    return args


@pytest.mark.parametrize("output_enabled", [False, True])
def test_host_tmp_paths_bound_before_private_tmpfs(monkeypatch, tmp_path, output_enabled):
    _setup(monkeypatch, tmp_path)
    source = tmp_path / "source.bin"
    source.write_bytes(b"test")
    output = tmp_path / "native-output" if output_enabled else None
    if output is not None:
        output.mkdir()
    argv = native_sandbox.isolated_native_command(
        source, output, _args(source, output),
    )
    # Compare the exact host source/target mount pair, never positional
    # assumptions about unrelated runtime binds.
    source_mount = argv.index(str(source.resolve()))
    temp_mount = argv.index("--tmpfs")
    assert argv[source_mount - 1] == "--ro-bind"
    assert argv[source_mount + 1] == SANDBOX_INPUT
    assert source_mount < temp_mount
    if output is not None:
        out_mount = argv.index(str(output.resolve()))
        assert argv[out_mount - 1] == "--bind"
        assert argv[out_mount + 1] == SANDBOX_OUTPUT
        assert out_mount < temp_mount
    else:
        assert SANDBOX_OUTPUT not in argv
    assert argv[temp_mount + 1] == "/tmp"


def test_decoder_has_only_allowlisted_runtime_mounts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    source = tmp_path / "source.bin"
    source.write_bytes(b"hello")
    argv = native_sandbox.isolated_native_command(
        source, None, _args(source, None),
    )
    assert "--unshare-net" in argv and "--unshare-user" in argv
    assert "--clearenv" in argv
    pairs = {(argv[i+1], argv[i+2])
             for i, value in enumerate(argv[:-2])
             if value in {"--ro-bind", "--ro-bind-try"}}
    assert ("/app", "/app") not in pairs
    assert ("/opt", "/opt") not in pairs
    assert ("/app/app", "/app/app") in pairs
    assert ("/opt/venv", "/opt/venv") in pairs
    assert ("/opt/pdfhub/heif", "/opt/pdfhub/heif") in pairs
    assert ("/opt/pdfhub/cad", "/opt/pdfhub/cad") in pairs


def test_sandbox_rejects_symlink_source_and_inapplicable_output(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    file = tmp_path / "file"
    file.write_bytes(b"hello")
    link = tmp_path / "link"
    link.symlink_to(file)
    with pytest.raises(ValueError):
        native_sandbox.isolated_native_command(
            link, None, _args(file, None),
        )
    with pytest.raises(ValueError):
        native_sandbox.isolated_native_command(
            file, None, _args(file, None) + [SANDBOX_OUTPUT + "/bad.pdf"],
        )


def test_output_must_not_reuse_input_parent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    file = tmp_path / "file"
    file.write_bytes(b"hello")
    with pytest.raises(ValueError):
        native_sandbox.isolated_native_command(
            file, tmp_path, _args(file, tmp_path),
        )
