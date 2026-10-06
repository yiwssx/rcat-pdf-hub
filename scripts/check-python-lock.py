#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECT_PATH = ROOT / "apps/api/requirements.txt"
LOCK_PATH = ROOT / "apps/api/requirements.lock"
NORMALIZE_RE = re.compile(r"[-_.]+")
LOCK_PIN_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s\\]+)(?:\s+\\)?$")


def normalize(name: str) -> str:
    return NORMALIZE_RE.sub("-", name).lower()


def direct_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in DIRECT_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise SystemExit(f"python lock policy: direct requirement must use ==: {line}")
        requirement, version = line.split("==", 1)
        name = requirement.split("[", 1)[0]
        pins[normalize(name)] = version
    return pins


def locked_pins() -> dict[str, tuple[str, bool]]:
    lines = LOCK_PATH.read_text(encoding="utf-8").splitlines()
    pins: dict[str, tuple[str, bool]] = {}
    indexes: list[tuple[int, re.Match[str]]] = []
    for index, raw in enumerate(lines):
        if raw.startswith((" ", "\t", "#")) or not raw.strip():
            continue
        match = LOCK_PIN_RE.fullmatch(raw.strip())
        if match:
            indexes.append((index, match))

    for pos, (index, match) in enumerate(indexes):
        end = indexes[pos + 1][0] if pos + 1 < len(indexes) else len(lines)
        block = "\n".join(lines[index:end])
        pins[normalize(match.group("name"))] = (
            match.group("version"),
            "--hash=sha256:" in block,
        )
    return pins


def main() -> None:
    if not LOCK_PATH.exists():
        raise SystemExit(f"python lock policy: missing {LOCK_PATH.relative_to(ROOT)}")

    direct = direct_pins()
    locked = locked_pins()
    missing = sorted(name for name in direct if name not in locked)
    if missing:
        raise SystemExit(f"python lock policy: direct requirements missing from lock: {missing}")

    mismatched = sorted(
        f"{name}: {direct[name]} != {locked[name][0]}"
        for name in direct
        if locked[name][0] != direct[name]
    )
    if mismatched:
        raise SystemExit("python lock policy: direct versions differ from lock: " + "; ".join(mismatched))

    unhashed = sorted(name for name, (_, has_hash) in locked.items() if not has_hash)
    if unhashed:
        raise SystemExit(f"python lock policy: locked requirements without SHA-256 hashes: {unhashed}")

    if not locked:
        raise SystemExit("python lock policy: no locked packages found")

    print(
        f"python lock policy: PASS — {len(direct)} direct pins, "
        f"{len(locked)} total hash-pinned packages"
    )


if __name__ == "__main__":
    main()
