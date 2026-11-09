#!/usr/bin/env python3
"""Preserve modified host Caddy config without changing its active bind mount.

Keep the existing tracked file bytes intact (and require an audited one-file
exception) because replacing that path could change an existing container on
restarts before a real, separately authorized deployment.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TRACKED = Path("ops/caddy/Caddyfile")
LOCAL_REL = "./.local-config/caddy/Caddyfile"
ENV_KEY = "PDFHUB_CADDYFILE_PATH"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def fail(message: str) -> None:
    raise ValueError(f"site-caddy: BLOCKED — {message}")


def check_dir(path: Path) -> None:
    if path.is_symlink():
        fail("unsafe symlink at local config directory")
    if path.exists() and not path.is_dir():
        fail("local config path is not a directory")
    if not path.exists():
        path.mkdir(mode=0o700)
    path.chmod(0o700)


def migrate(*, check_only: bool = False) -> str:
    status = git("status", "--porcelain", "--untracked-files=no").decode("utf-8")
    if not status.strip():
        return "site-caddy: clean; no migration needed"

    # Never silently amend other source files, or overwrite staged changes.
    if status.splitlines() != [" M ops/caddy/Caddyfile"]:
        fail("only one unstaged host-specific Caddyfile may be migrated")

    caddy = ROOT / TRACKED
    env = ROOT / ".env"
    if caddy.is_symlink() or not caddy.is_file():
        fail("Caddyfile is missing or a symbolic link")
    if env.is_symlink() or not env.is_file():
        fail("production .env is missing or a symbolic link")

    # Index must match HEAD. Do not undo a staged commit or alter Git history.
    index = git("ls-files", "--stage", "--", TRACKED.as_posix()).decode("utf-8").split()
    if len(index) < 2 or index[1] != git("rev-parse", f"HEAD:{TRACKED.as_posix()}").decode().strip():
        fail("Caddyfile staged index differs from HEAD")

    original = caddy.read_bytes()
    canonical = git("show", f"HEAD:{TRACKED.as_posix()}")
    if original == canonical:
        git("update-index", "--refresh", "--", TRACKED.as_posix())
        return "site-caddy: content already identical; Git index refreshed"

    env_text = env.read_text(encoding="utf-8")
    existing = [line.split("=", 1)[1].strip().strip('"').strip("'")
                for line in env_text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
                and line.partition("=")[0].strip() == ENV_KEY]
    if existing and (len(existing) != 1 or existing[0] != LOCAL_REL):
        fail("existing PDFHUB_CADDYFILE_PATH is different; refusing rewrite")

    local_root = ROOT / ".local-config"
    site = local_root / "caddy" / "Caddyfile"
    if check_only:
        if (len(existing) != 1 or existing[0] != LOCAL_REL
                or site.is_symlink() or not site.is_file()
                or site.read_bytes() != original):
            fail("modified host Caddyfile is not covered by the verified site override")
        return "site-caddy: PASS — the sole modified tracked file matches the reviewed site config"
    check_dir(local_root)
    site_dir = local_root / "caddy"
    check_dir(site_dir)
    site = site_dir / "Caddyfile"
    if site.is_symlink():
        fail("local site configuration is a symlink")
    if site.exists():
        if not site.is_file() or site.read_bytes() != original:
            fail("local site Caddyfile exists and differs; refusing overwrite")
    else:
        fd, name = tempfile.mkstemp(dir=site_dir, prefix=".caddy-save-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, site)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    if site.read_bytes() != original:
        fail("saved Caddyfile differs from live content")

    # Append a single non-secret key to the existing .env; never rewrite its
    # other lines or print its contents. Read/write ability is mandatory.
    if not existing:
        newline = "" if not env_text or env_text.endswith("\n") else "\n"
        payload = (newline + ENV_KEY + "=" + LOCAL_REL + "\n").encode()
        flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(env, flags), "ab") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())

    # Never replace the tracked path. It is the current live Docker bind mount
    # source, and rewriting it could unexpectedly affect a restarted container.
    if caddy.read_bytes() != original or site.read_bytes() != original:
        fail("site Caddyfile changed during preservation")
    if git("status", "--porcelain", "--untracked-files=no").decode().splitlines() != [
        " M ops/caddy/Caddyfile"
    ]:
        fail("unexpected additional tracked changes after preserving site Caddyfile")
    return "site-caddy: PASS — original proxy file unchanged and site copy saved; no containers restarted"

if __name__ == "__main__":
    import sys
    if sys.argv[1:] not in ([], ["--check"]):
        raise SystemExit("usage: migrate-site-caddy.py [--check]")
    try:
        print(migrate(check_only=sys.argv[1:] == ["--check"]))
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"site-caddy: fail-closed migration: {type(exc).__name__}: {exc}") from None
