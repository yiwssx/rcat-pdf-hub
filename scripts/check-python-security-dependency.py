#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

TARGET = "apps/api/requirements.txt"
PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[A-Za-z0-9_,.-]+\])?==(?P<version>\d+\.\d+\.\d+)$"
)


@dataclass(frozen=True)
class Pin:
    name: str
    extras: str
    version: tuple[int, int, int]
    raw: str


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def parse_requirements(text: str) -> dict[str, Pin]:
    pins: dict[str, Pin] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if not match:
            continue
        key = match.group("name").lower().replace("_", "-")
        pins[key] = Pin(
            name=match.group("name"),
            extras=match.group("extras") or "",
            version=tuple(int(part) for part in match.group("version").split(".")),
            raw=line,
        )
    return pins


def fail(message: str) -> None:
    raise SystemExit(f"python security dependency policy: NOT ELIGIBLE — {message}")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} BASE_REF HEAD_REF")

    base, head = sys.argv[1:]
    changed = [line for line in git("diff", "--name-only", base, head).splitlines() if line]
    if changed != [TARGET]:
        fail(f"security lane accepts exactly {TARGET}; changed: {', '.join(changed) or '(none)'}")

    base_text = git("show", f"{base}:{TARGET}")
    head_text = git("show", f"{head}:{TARGET}")
    base_pins = parse_requirements(base_text)
    head_pins = parse_requirements(head_text)

    if base_pins.keys() != head_pins.keys():
        fail("dependency names changed; only one existing exact pin may advance")

    changed_pins = [name for name in base_pins if base_pins[name].raw != head_pins[name].raw]
    if len(changed_pins) != 1:
        fail(f"expected exactly one changed pinned dependency; found {len(changed_pins)}")

    name = changed_pins[0]
    before = base_pins[name]
    after = head_pins[name]
    if before.name != after.name or before.extras != after.extras:
        fail(f"dependency identity/extras changed for {name}")
    if after.version <= before.version:
        fail(f"dependency version must move forward: {before.raw} -> {after.raw}")

    # Require the raw file diff to be exactly one removed pin and one added pin.
    diff = git("diff", "--unified=0", base, head, "--", TARGET)
    removed = [line[1:] for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    if removed != [before.raw] or added != [after.raw]:
        fail("requirements diff contains changes beyond the single verified exact pin")

    print(f"python security dependency policy: PASS — {before.raw} -> {after.raw}")


if __name__ == "__main__":
    main()
