#!/usr/bin/env python3
"""Read-only on-host URL firewall lease guard; no keys or private data logged."""
from __future__ import annotations

from pathlib import Path
import time

PATH = Path("/etc/pdfhub/url-egress.attested")
BOOT = Path("/proc/sys/kernel/random/boot_id")
VERSION = "RCAT-T90-2-URL-FETCH-EGRESS-V2"


def lease_valid() -> bool:
    try:
        if PATH.is_symlink() or not PATH.is_file():
            return False
        data = PATH.read_text(encoding="ascii").splitlines()
        if len(data) != 3 or data[0] != VERSION:
            return False
        if data[1] != BOOT.read_text(encoding="ascii").strip():
            return False
        if not data[2].isascii() or not data[2].isdecimal():
            return False
        age = time.time() - int(data[2])
        return -10 <= age <= 120
    except (OSError, ValueError, UnicodeError):
        return False


if __name__ == "__main__":
    if not lease_valid():
        raise SystemExit("T90 URL host firewall lease: INVALID / expired / wrong boot")
    print("T90 URL host firewall lease: CURRENT (trusted root guard required)")
