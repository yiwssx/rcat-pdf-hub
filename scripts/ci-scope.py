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


LANES = ("backend", "frontend", "ops", "gotenberg", "database", "t90_stack", "web_regression")

# Extra, real-service integration is routed only when its contracts change.
# Core unit/contract/coverage runs in the ordinary backend lane already.
DATABASE_PATHS = (
    "apps/api/alembic/",
    "apps/api/app/db.py",
    "apps/api/app/models.py",
    "apps/api/app/migrate.py",
    "apps/api/tests/test_t90_postgres_migration_ci.py",
)
T90_STACK_PATHS = (
    "apps/api/app/queue.py",
    "apps/api/app/worker.py",
    "apps/api/app/worker_tasks.py",
    "apps/api/app/lease_recovery.py",
    "apps/api/app/storage.py",
    "apps/api/tests/t90_stack_probe.py",
)
WEB_REGRESSION_PATHS = (
    "apps/web/app/",
    "apps/web/components/",
    "apps/web/tests/e2e/pdf-hub.ui-regression.spec.ts",
)


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
            if path.startswith(DATABASE_PATHS):
                selected["database"] = True
            if path.startswith(T90_STACK_PATHS):
                selected["t90_stack"] = True
            # A Python dependency update can change database and RQ/S3
            # behavior. Exercise real disposable services only for this case.
            if path in {"apps/api/requirements.txt", "apps/api/requirements.lock", "apps/api/Dockerfile"}:
                selected["database"] = True
                selected["t90_stack"] = True
        elif path.startswith("apps/web/"):
            selected["frontend"] = True
            if path.startswith(WEB_REGRESSION_PATHS):
                selected["web_regression"] = True
        elif path.startswith("ops/gotenberg/"):
            selected["ops"] = True
            selected["gotenberg"] = True
        elif path == "scripts/ci-risk-integration.sh":
            # A change to the integration harness itself must exercise both
            # real-service tracks before being trusted as a required gate.
            selected["ops"] = True
            selected["backend"] = True
            selected["database"] = True
            selected["t90_stack"] = True
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
            selected["database"] = True
            selected["t90_stack"] = True
            selected["web_regression"] = True
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
