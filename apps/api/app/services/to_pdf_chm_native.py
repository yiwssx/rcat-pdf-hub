"""T90-2 native CHM import draft: isolated reader -> offline HTML -> PDF.

This module is NOT wired into uploads, the public router, or the catalog.
Native chmlib still requires a dedicated network-denied sandbox and
independent source-fidelity/security acceptance before staging T30.
"""
from __future__ import annotations

import json
from pathlib import Path
import resource
import subprocess
import sys
from tempfile import TemporaryFile

from app.config import get_settings
from app.services.native_sandbox import SANDBOX_INPUT, isolated_native_command

MAX_CHM_BYTES = 20 * 1024 * 1024
MAX_HTML_BYTES = 16 * 1024 * 1024
CHM_READER_TIMEOUT_SECONDS = 25


def _reader_limits() -> None:
    # Every native decoder invocation gets its own process/address space.
    # This does NOT replace an OS/container network-denied execution sandbox.
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_HTML_BYTES * 2, MAX_HTML_BYTES * 2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))


def chm_to_safe_html(source: Path) -> str:
    """Decode bounded CHM pages without extracting any archive member to disk."""
    if not 128 <= source.stat().st_size <= MAX_CHM_BYTES:
        raise ValueError("CHM source is absent or outside size limits")
    with source.open("rb") as fh:
        if fh.read(4) != b"ITSF":
            raise ValueError("CHM ITSF signature is missing")

    # A module run with a fully resolved command, no user arguments aside
    # from the source file, no shell and no ambient python search path.
    # The module is imported from the read-only API working directory.
    app_root = Path(__file__).resolve().parents[2]
    command = isolated_native_command(
        source, None,
        [sys.executable, "-m", "app.services.to_pdf_chm_worker", SANDBOX_INPUT],
    )
    # Only wrapper setup environment, never the service's credential-bearing
    # process environment. Bubblewrap clears the child environment itself.
    env = {"PATH": "/usr/bin:/bin"}
    # Never use capture_output=True for untrusted native processes. Redirect
    # stdout to a capped regular file: RLIMIT_FSIZE bounds both the helper's
    # write volume and what the parent may ever read. stderr is discarded.
    with TemporaryFile(mode="w+b") as captured:
        try:
            completed = subprocess.run(
                command,
                cwd=str(app_root),
                env=env,
                stdout=captured,
                stderr=subprocess.DEVNULL,
                check=False,
                close_fds=True,
                start_new_session=True,
                timeout=CHM_READER_TIMEOUT_SECONDS,
                preexec_fn=_reader_limits,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("CHM native decoder timed out or could not start") from exc
        if completed.returncode != 0:
            raise ValueError("CHM native decoder rejected the source document")
        size = captured.tell()
        if not 2 <= size <= MAX_HTML_BYTES * 2:
            raise ValueError("CHM decoded response exceeds safe limits")
        captured.seek(0)
        payload = captured.read(MAX_HTML_BYTES * 2 + 1)
    try:
        result = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("CHM decoder returned malformed content") from exc
    if (not isinstance(result, dict) or set(result) != {"html"}
            or not isinstance(result["html"], str)
            or not result["html"].strip()
            or len(result["html"].encode("utf-8")) > MAX_HTML_BYTES):
        raise ValueError("CHM decoder returned unusable or oversized HTML")
    return result["html"]


def chm_to_pdf(source: Path, output: Path) -> None:
    """CHM page/illustration transcript to PDF; internal development entry only."""
    if source.resolve() == output.resolve():
        raise ValueError("CHM source and output must differ")
    settings = get_settings()
    if not settings.to_pdf_tools_enabled or not settings.chm_native_dev_enabled:
        raise RuntimeError("CHM native development engine is disabled")
    html = chm_to_safe_html(source)
    # The isolated native chmlib decoder is lower-trust than Chromium's
    # privileged PDF worker. A valid JSON response is not HTML authorization.
    from app.services.chm_html_boundary import validate_chm_html_fragment
    safe_html = validate_chm_html_fragment(html)
    from app.services.to_pdf_engine import _html_to_pdf
    _html_to_pdf(safe_html, output)
