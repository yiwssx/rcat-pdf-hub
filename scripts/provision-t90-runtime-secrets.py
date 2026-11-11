#!/usr/bin/env python3
"""Create/reuse four Production-only keys without exposing them to GitHub/logs.

Invoked as root on the institution's own Docker host. No secret is printed or
committed. Replace .env atomically with exactly the original owner/group,
mode 0600, and all unrelated existing values preserved byte-for-byte.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
HMAC_KEYS = ("PDFHUB_NATIVE_SIDECAR_SHARED_SECRET",
             "PDFHUB_URL_FETCHER_SHARED_SECRET")
AEAD_KEYS = ("PDFHUB_UNLOCK_PDF_HANDOFF_KEY",
             "PDFHUB_PROTECT_PDF_HANDOFF_KEY")
KEYS = (*HMAC_KEYS, *AEAD_KEYS)
PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def valid(key: str, value: str) -> bool:
    if key in HMAC_KEYS:
        return (40 <= len(value) <= 256 and not value.startswith("change-me")
                and all(33 <= ord(c) <= 126 for c in value))
    try:
        decoded = base64.b64decode(value, altchars=b"-_", validate=True)
        return len(decoded) == 32 and base64.urlsafe_b64encode(decoded).decode() == value
    except (ValueError, UnicodeError):
        return False


def generate(key: str) -> str:
    if key in HMAC_KEYS:
        return secrets.token_urlsafe(48)
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def provision() -> tuple[int, int]:
    if os.geteuid() != 0 or os.getenv("GITHUB_ACTIONS") == "true":
        raise ValueError("must run on authorized root Production host, not CI")
    st = ENV.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ValueError("Production .env must be a regular non-linked file")
    original = ENV.read_bytes()
    text = original.decode("utf-8", errors="strict")
    lines = text.splitlines(keepends=True)
    found: dict[str, tuple[int, str]] = {}
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        name = key.strip()
        if not PATTERN.fullmatch(name):
            continue
        if name in KEYS:
            if name in found:
                raise ValueError("duplicate protected key in Production .env: " + name)
            value = raw.strip().strip('"').strip("'")
            found[name] = (i, value)
    updated = 0
    reused = 0
    for key in KEYS:
        old = found.get(key)
        if old and old[1] and valid(key, old[1]):
            reused += 1
            continue
        if old and old[1] and not valid(key, old[1]):
            raise ValueError("existing key malformed: " + key + " (manual owner review required)")
        value = generate(key)
        assert valid(key, value)
        if old:
            lines[old[0]] = key + "=" + value + "\n"
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(key + "=" + value + "\n")
        found[key] = (old[0] if old else len(lines) - 1, value)
        updated += 1
    values = [found[name][1] for name in KEYS]
    if len(set(values)) != len(values):
        raise ValueError("HMAC and AEAD material must be distinct")
    replacement = "".join(lines).encode("utf-8")
    if replacement == original:
        return (updated, reused)
    fd, path = tempfile.mkstemp(prefix=".env-t90-", dir=ROOT)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, st.st_uid, st.st_gid)
        with os.fdopen(fd, "wb", closefd=True) as f:
            f.write(replacement)
            f.flush()
            os.fsync(f.fileno())
        os.replace(path, ENV)
        directory = os.open(ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    return (updated, reused)


if __name__ == "__main__":
    try:
        count, existing = provision()
        print(f"T90 private secrets: OK; created={count} reused={existing}; values never printed")
    except (OSError, ValueError, UnicodeError) as exc:
        raise SystemExit("T90 private secret provisioning BLOCKED: " + str(exc))
