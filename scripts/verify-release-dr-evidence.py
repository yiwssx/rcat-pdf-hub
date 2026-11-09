#!/usr/bin/env python3
"""Verify DR evidence downloaded from a trusted, successful GitHub Actions run.

Inputs contain metadata only. Never print backup content, credentials or JSON
payloads to release logs. The source backup must be checksum-verified separately.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

SHA = re.compile(r"^[a-f0-9]{40}$")
STAMP = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")
TRUSTED_PATH = ".github/workflows/isolated-dr.yml"
REPO = "yiwssx/rcat-pdf-hub"


def verify(run: dict, evidence: dict, backup: Path, sha: str, now: datetime | None = None) -> None:
    if not SHA.fullmatch(sha):
        raise ValueError("invalid release commit SHA")
    if (run.get("head_sha") != sha or run.get("head_branch") != "main"
            or run.get("conclusion") != "success"
            or run.get("status") != "completed"
            or run.get("event") not in ("schedule", "workflow_dispatch")
            or run.get("path", "").split("@")[0] != TRUSTED_PATH
            or run.get("repository", {}).get("full_name") != REPO):
        raise ValueError("DR evidence is not from a completed trusted main workflow")
    if (evidence.get("schema") != 1
            or evidence.get("workflow") != "rcat-isolated-dr"
            or evidence.get("result") != "PASS"
            or evidence.get("commit_sha") != sha
            or evidence.get("exit_code") != 0
            or evidence.get("private_logs_uploaded") is not False
            or evidence.get("restored_production") is not False):
        raise ValueError("DR restore PASS proof is incomplete or inconsistent")
    stamp = backup.name
    if not STAMP.fullmatch(stamp) or evidence.get("backup_stamp") != stamp:
        raise ValueError("DR snapshot does not match the approved backup")
    checksum = backup / "SHA256SUMS"
    if checksum.is_symlink() or not checksum.is_file():
        raise ValueError("backup checksum manifest is missing/unsafe")
    expected_digest = hashlib.sha256(checksum.read_bytes()).hexdigest()
    if evidence.get("backup_checksums_sha256") != expected_digest:
        raise ValueError("DR-tested backup checksum does not match the release backup")
    current = now or datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(evidence["started_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(evidence["finished_utc"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError) as err:
        raise ValueError("invalid DR evidence timestamp") from err
    if (start.tzinfo is None or end.tzinfo is None or
            start > end or end > current + timedelta(minutes=5) or
            current - end > timedelta(hours=72)):
        raise ValueError("DR evidence expired or timestamps are inconsistent")


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: verify-release-dr-evidence.py RUN_JSON EVIDENCE_JSON BACKUP_DIR SHA", file=sys.stderr)
        return 2
    try:
        run = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        report = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        verify(run, report, Path(sys.argv[3]), sys.argv[4])
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as err:
        print(f"Release DR evidence: BLOCKED ({type(err).__name__}); no private data printed", file=sys.stderr)
        return 1
    print("Release DR evidence: PASS (matching SHA, verified backup and successful isolated restore)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
