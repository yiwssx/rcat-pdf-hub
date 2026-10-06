#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys

PACKAGE_PATH = "apps/web/package.json"
LOCK_PATH = "apps/web/package-lock.json"
SECTIONS = ("dependencies", "devDependencies")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def package_at(ref: str) -> dict:
    return json.loads(git("show", f"{ref}:{PACKAGE_PATH}"))


def lock_at(ref: str) -> dict:
    return json.loads(git("show", f"{ref}:{LOCK_PATH}"))


def validate_lock(package: dict, lock: dict, label: str) -> None:
    if lock.get("lockfileVersion") != 3:
        raise ValueError(f"{label} package-lock.json must use lockfileVersion 3")
    root = lock.get("packages", {}).get("")
    if not isinstance(root, dict):
        raise ValueError(f"{label} package-lock.json is missing the root package entry")
    for key in ("name", "version"):
        if root.get(key) != package.get(key):
            raise ValueError(f"{label} package-lock root {key} does not match package.json")
    for section in SECTIONS:
        if root.get(section, {}) != package.get(section, {}):
            raise ValueError(f"{label} package-lock root {section} does not match package.json")


def validate(base_ref: str, head_ref: str) -> tuple[str, str, str, str]:
    changed = set(filter(None, git("diff", "--name-only", f"{base_ref}...{head_ref}").splitlines()))
    expected = {PACKAGE_PATH, LOCK_PATH}
    if changed != expected:
        raise ValueError(
            f"dependency patch lane accepts exactly {sorted(expected)}; changed: {sorted(changed) or '<none>'}"
        )

    before = package_at(base_ref)
    after = package_at(head_ref)
    before_lock = lock_at(base_ref)
    after_lock = lock_at(head_ref)
    validate_lock(before, before_lock, "base")
    validate_lock(after, after_lock, "head")

    before_static = copy.deepcopy(before)
    after_static = copy.deepcopy(after)
    for section in SECTIONS:
        before_static.pop(section, None)
        after_static.pop(section, None)
    if before_static != after_static:
        raise ValueError("package.json changed outside dependency declarations")

    changes: list[tuple[str, str, str, str]] = []
    for section in SECTIONS:
        old = before.get(section, {})
        new = after.get(section, {})
        if set(old) != set(new):
            raise ValueError(f"dependency names changed in {section}")
        for name in sorted(old):
            if old[name] != new[name]:
                changes.append((section, name, old[name], new[name]))

    if len(changes) != 1:
        raise ValueError(f"exactly one direct dependency must change; found {len(changes)}")

    section, name, old_version, new_version = changes[0]
    old_match = SEMVER.fullmatch(old_version)
    new_match = SEMVER.fullmatch(new_version)
    if not old_match or not new_match:
        raise ValueError(f"exact x.y.z versions required: {name} {old_version} -> {new_version}")

    old_major, old_minor, old_patch = map(int, old_match.groups())
    new_major, new_minor, new_patch = map(int, new_match.groups())
    if (new_major, new_minor) != (old_major, old_minor):
        raise ValueError("only patch updates are eligible for the automatic dependency lane")
    if new_patch <= old_patch:
        raise ValueError("dependency version must move forward")

    return section, name, old_version, new_version


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: check-direct-dependency.py BASE_REF HEAD_REF", file=sys.stderr)
        return 2
    try:
        section, name, old_version, new_version = validate(sys.argv[1], sys.argv[2])
    except (ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"direct dependency policy: NOT ELIGIBLE — {exc}", file=sys.stderr)
        return 1
    print(f"direct dependency policy: PASS — {section}.{name} {old_version} -> {new_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
