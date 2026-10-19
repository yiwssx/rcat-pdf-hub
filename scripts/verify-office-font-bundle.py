#!/usr/bin/env python3
"""Verify the 13Fonts set installed in Gotenberg via sha256sum output."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from office_font_bundle import fingerprint

manifest = json.loads((Path(__file__).resolve().parents[1] / "ops/gotenberg/13fonts-manifest.json").read_text(encoding="utf-8"))
entries: dict[str, str] = {}
for line in sys.stdin:
    checksum, sep, path = line.rstrip("\n").partition("  ")
    filename = path.removeprefix("./")
    if not sep or len(checksum) != 64 or not all(c in "0123456789abcdef" for c in checksum) or "/" in filename or "\\" in filename or filename in entries:
        print(f"FAIL invalid or duplicate font checksum entry: {line.rstrip()!r}", file=sys.stderr)
        raise SystemExit(1)
    entries[filename] = checksum
if len(entries) != manifest["font_count"] or fingerprint(entries) != manifest["fingerprint_sha256"]:
    print(f"FAIL Gotenberg fonts do not match uploaded 13Fonts.zip ({len(entries)}/{manifest['font_count']} files)", file=sys.stderr)
    raise SystemExit(1)
print(f"PASS verified {len(entries)} exact font files and contents in Gotenberg")
