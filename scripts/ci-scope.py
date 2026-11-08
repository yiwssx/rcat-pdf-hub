#!/usr/bin/env python3
"""Classify changed repository paths for the one always-reported Lean CI gate.

Conservative routing: unknown files run all lanes rather than being silently
skipped. This is an optimization of PR validation, not a Production release
authorization or replacement for CodeQL/Dependency Review.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


LANES = ("backend", "frontend", "ops", "gotenberg")


def classify(paths: list[str], *, force_all: bool = False) -> dict[str, bool]:
    selected = {lane: bool(force_all) for lane in LANES}
    for raw in paths:
        path = raw.strip().removeprefix("./")
        if not path:
            continue
        if path.endswith(".md") or path.startswith("docs/"):
            continue
        if path.startswith("apps/api/"):
            selected["backend"] = True
        elif path.startswith("apps/web/"):
            selected["frontend"] = True
        elif path.startswith("ops/gotenberg/"):
            selected["ops"] = True
            selected["gotenberg"] = True
        elif (
            path.startswith(("scripts/", "ops/", ".github/"))
            or path.startswith(("docker-compose", "compose."))
            or path in {"Makefile", ".env.example", ".gitignore", "Caddyfile"}
        ):
            selected["ops"] = True
        elif path.startswith("quality/backend"):
            selected["backend"] = True
        elif path.startswith("quality/browser"):
            selected["frontend"] = True
        else:
            # An unfamiliar path must never bypass meaningful validation.
            selected["backend"] = True
            selected["frontend"] = True
            selected["ops"] = True
    return selected


def changed_paths(base: str, head: str) -> list[str]:
    if not base or not head or set(base) == {"0"}:
        raise ValueError("CI must provide real base and head commits")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACDMRT", base, head],
        check=True, capture_output=True, text=True,
    )
    return proc.stdout.splitlines()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--github-output")
    args = parser.parse_args()
    if not args.all and (not args.base or not args.head):
        parser.error("--base and --head are required unless --all is provided")
    paths = [] if args.all else changed_paths(args.base, args.head)
    selected = classify(paths, force_all=args.all)
    output = "\n".join(f"{k}={str(v).lower()}" for k, v in selected.items()) + "\n"
    print(f"lean-ci changed files: {len(paths)}")
    print(output, end="")
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as stream:
            stream.write(output)


if __name__ == "__main__":
    main()
