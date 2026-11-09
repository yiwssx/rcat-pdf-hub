#!/usr/bin/env python3
"""Fail-closed guard for scheduled, private RCAT PDF Hub restore rehearsals.

This module never restores data. The runner uses it to reject public PR
contexts, shared/rootful Docker daemons and writable Production backup paths.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

EXPECTED_BACKUP_ROOT = Path("/mnt/rcat-dr-backups")
HOST_MARKER = Path("/etc/rcat-pdf-hub/dr-isolated-runner.enabled")
MARKER_CONTENT = "RCAT_DR_ISOLATED_RUNNER_V1\n"
STAMP_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def require_context(env: dict[str, str]) -> None:
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "yiwssx/rcat-pdf-hub",
        "GITHUB_REF": "refs/heads/main",
        "RUNNER_ENVIRONMENT": "self-hosted",
    }
    for name, value in expected.items():
        if env.get(name) != value:
            raise ValueError(f"Unexpected DR runner context: {name}")
    if env.get("GITHUB_EVENT_NAME") not in {"schedule", "workflow_dispatch"}:
        raise ValueError("Only a scheduled or operator-authorized main workflow can run DR")
    sha = env.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Missing immutable GitHub main SHA")
    if os.getuid() == 0:
        raise ValueError("DR runner must not run as root")
    if (Path.cwd() / ".env").exists():
        raise ValueError("DR runner workspace must not contain a deployment .env")


def require_host_marker(path: Path = HOST_MARKER) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Dedicated DR runner approval marker is absent/unsafe")
    mode = path.stat()
    if mode.st_uid != 0 or mode.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("DR runner approval marker must be root-owned and non-writable")
    if path.read_text(encoding="utf-8") != MARKER_CONTENT:
        raise ValueError("Invalid dedicated DR runner approval marker")


def choose_snapshot(root: Path) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Read-only DR snapshot mount is absent/unsafe")
    if root.resolve() != EXPECTED_BACKUP_ROOT:
        raise ValueError("DR snapshots must be mounted at /mnt/rcat-dr-backups")
    if not os.statvfs(root).f_flag & os.ST_RDONLY:
        raise ValueError("DR snapshot filesystem must be mounted read-only")
    candidates = []
    for path in root.iterdir():
        if path.is_symlink() or not path.is_dir() or not STAMP_RE.fullmatch(path.name):
            continue
        required = ("manifest.env", "SHA256SUMS", "postgres.dump")
        if any((path / name).is_symlink() or not (path / name).is_file() for name in required):
            continue
        candidates.append(path)
    if not candidates:
        raise ValueError("No verified-format DR backup snapshot is available")
    return max(candidates, key=lambda item: item.name)


def require_rootless_empty_docker() -> None:
    expected = f"unix:///run/user/{os.getuid()}/docker.sock"
    if os.environ.get("DOCKER_HOST") != expected:
        raise ValueError("DR must use dedicated rootless Docker socket")
    result = subprocess.run(
        ["docker", "info", "--format", "{{json .SecurityOptions}}"],
        check=True, capture_output=True, text=True, timeout=15,
    )
    options = json.loads(result.stdout)
    if not isinstance(options, list) or not any("rootless" in str(x) for x in options):
        raise ValueError("Docker daemon is not rootless; Production daemon forbidden")
    # A daemon with stopped containers or pre-existing named volumes is not
    # dedicated either. Refuse rather than risk reusing, mutating or deleting
    # another workload's persistent data during a restore rehearsal.
    for command, label in (
        (["docker", "ps", "-aq"], "containers"),
        (["docker", "volume", "ls", "-q"], "named volumes"),
    ):
        found = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=15,
        )
        if found.stdout.strip():
            raise ValueError(f"DR Docker daemon already contains {label}; refusing shared daemon")


def write_report(output: Path, *, status: str, sha: str, backup: Path | None,
                 started: str, result_code: int) -> None:
    if status not in {"PASS", "FAIL"}:
        raise ValueError("Invalid DR result")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid DR commit")
    digest = None
    stamp = None
    if backup is not None:
        stamp = backup.name
        if not STAMP_RE.fullmatch(stamp):
            raise ValueError("Invalid DR snapshot identifier")
        # The digest identifies the signed/checksummed manifest, not user data.
        digest = hashlib.sha256((backup / "SHA256SUMS").read_bytes()).hexdigest()
    report = {
        "schema": 1,
        "workflow": "rcat-isolated-dr",
        "result": status,
        "commit_sha": sha,
        "backup_stamp": stamp,
        "backup_checksums_sha256": digest,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exit_code": result_code,
        "private_logs_uploaded": False,
        "restored_production": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("select")
    report = sub.add_parser("report")
    report.add_argument("--output", required=True)
    report.add_argument("--status", required=True, choices=("PASS", "FAIL"))
    report.add_argument("--sha", required=True)
    report.add_argument("--started", required=True)
    report.add_argument("--exit-code", required=True, type=int)
    report.add_argument("--backup")
    args = parser.parse_args()
    if args.command == "select":
        require_context(dict(os.environ))
        require_host_marker()
        require_rootless_empty_docker()
        print(choose_snapshot(EXPECTED_BACKUP_ROOT))
    else:
        write_report(
            Path(args.output), status=args.status, sha=args.sha,
            backup=Path(args.backup) if args.backup else None,
            started=args.started, result_code=args.exit_code,
        )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise SystemExit(f"dr-runner: fail-closed preflight/report: {type(exc).__name__}: {exc}") from None
