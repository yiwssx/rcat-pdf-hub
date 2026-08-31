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


def json_at(ref: str, path: str) -> dict:
    return json.loads(git("show", f"{ref}:{path}"))


def validate_lock(package: dict, lock: dict, changed_name: str, changed_version: str) -> None:
    if lock.get("lockfileVersion") != 3:
        raise ValueError("package-lock v3 is required")
    root = lock.get("packages", {}).get("")
    if not isinstance(root, dict):
        raise ValueError("package-lock root package metadata is missing")
    if root.get("version") != package.get("version"):
        raise ValueError("package-lock root version does not match package.json")
    for section in SECTIONS:
        if root.get(section, {}) != package.get(section, {}):
            raise ValueError(f"package-lock root {section} does not match package.json")
    node_entry = lock.get("packages", {}).get(f"node_modules/{changed_name}")
    if not isinstance(node_entry, dict) or node_entry.get("version") != changed_version:
        raise ValueError(f"package-lock does not resolve {changed_name} to {changed_version}")


def validate(base_ref: str, head_ref: str) -> tuple[str, str, str, str]:
    changed = [line for line in git("diff", "--name-only", f"{base_ref}...{head_ref}").splitlines() if line]
    expected = {PACKAGE_PATH, LOCK_PATH}
    if set(changed) != expected or len(changed) != 2:
        raise ValueError(
            f"dependency patch lane accepts exactly {PACKAGE_PATH} + {LOCK_PATH}; changed: {', '.join(changed) or '<none>'}"
        )

    before = json_at(base_ref, PACKAGE_PATH)
    after = json_at(head_ref, PACKAGE_PATH)
    before_lock = json_at(base_ref, LOCK_PATH)
    after_lock = json_at(head_ref, LOCK_PATH)

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

    validate_lock(before, before_lock, name, old_version)
    validate_lock(after, after_lock, name, new_version)
    if before_lock == after_lock:
        raise ValueError("package-lock.json did not change with the direct dependency patch")

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
