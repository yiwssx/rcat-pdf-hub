#!/usr/bin/env python3
"""Migrate only a modified host Caddyfile to a private, ignored config path.

Preserves the exact site bytes; atomically replaces the repository-tracked
path with a NEW inode so an existing Docker single-file bind mount keeps its
original content until an approved cutover. No Docker or Caddy restarts.
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


def migrate() -> str:
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

    # Preserve current mounted old inode. git restore may truncate that same
    # inode and thereby change a live container's configuration unexpectedly.
    if caddy.read_bytes() != original:
        fail("original Caddyfile changed during preservation; aborting")
    fd, temp_name = tempfile.mkstemp(dir=caddy.parent, prefix=".caddy-git-")
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(canonical)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, caddy)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

    if caddy.read_bytes() != canonical or site.read_bytes() != original:
        fail("post-migration verification failed")
    git("update-index", "--refresh", "--", TRACKED.as_posix())
    if git("status", "--porcelain", "--untracked-files=no").strip():
        fail("tracked files still modified after migrating site Caddyfile")
    return "site-caddy: PASS — live config preserved in ignored site file; Git clean; no containers restarted"


if __name__ == "__main__":
    try:
        print(migrate())
    except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"site-caddy: fail-closed migration: {type(exc).__name__}: {exc}") from None
