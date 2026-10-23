"""T90 crash-orphan recovery inventory: intentionally read-only and fail-closed.

A terminated worker may leave generated processed output before FileRecord
commit. This diagnostic never deletes, mutates, or exposes a download URL.
It returns *candidates* for operator review, not proof an object is safe to
delete. Live jobs and unknown/stale metadata must never be reclaimed here.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import FileRecord, JobRecord
from app import storage_reconciliation

# Only the specific generated filenames from process_job. Unrecognized keys,
# original uploads and arbitrary tenant files MUST NOT be garbage-collected.
JOB_ID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
ROOT = re.compile(rf"^({JOB_ID})\.(?:pdf|zip)$", re.IGNORECASE)
PART = re.compile(rf"^({JOB_ID})-page-[0-9]{{4,}}\.(?:png|jpg)$", re.IGNORECASE)
TERMINAL_ORPHAN_STATUSES = frozenset({"failed", "cancelled"})
MIN_GRACE_HOURS = 24


def _job_id(filename: str) -> str | None:
    for pattern in (ROOT, PART):
        match = pattern.fullmatch(filename)
        if match:
            return match.group(1).lower()
    return None


def _aware(value) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def inventory_orphan_job_outputs(
    db: Session, *, min_age_hours: int = MIN_GRACE_HOURS,
    now: datetime | None = None, detail_limit: int = 200,
) -> dict:
    """Return only old, unreferenced outputs of verifiably terminal jobs.

    This reads managed local/S3 inventory and DB records. It never calls a
    mutating object-store method. Require manual review before any eventual
    deletion feature. Missing timestamps, unknown job IDs, and in-flight jobs
    are excluded rather than guessed. The full scan is needed for safety.
    """
    if type(min_age_hours) is not int or min_age_hours < MIN_GRACE_HOURS:
        raise ValueError("At least 24 hours of grace is required")
    if type(detail_limit) is not int or not 1 <= detail_limit <= 200:
        raise ValueError("detail_limit must be 1..200")
    now = _aware(now or datetime.now(timezone.utc))
    if now is None:
        raise ValueError("now must be timezone-aware")
    cutoff = now - timedelta(hours=min_age_hours)
    # Use ALL FileRecords, not only completed-job links: uploads or records of
    # other operations may reference the same physical storage object.
    referenced = set(db.scalars(select(FileRecord.stored_name)).all())
    jobs = {
        job.id.lower(): job.status
        for job in db.scalars(select(JobRecord)).all()
    }
    backend = storage_reconciliation.settings.storage_backend
    if backend == "s3":
        objects = list(storage_reconciliation._scan_s3_objects().values())
        prefix = storage_reconciliation.settings.s3_prefix.strip("/")
        base = f"{prefix}/" if prefix else ""
        managed = "s3:" + base + "processed/"
    elif backend == "local":
        scanned, _ = storage_reconciliation._scan_local_objects()
        objects = scanned
        managed = "processed/"
    else:
        raise ValueError("Unexpected storage backend")
    candidates: list[dict] = []
    # Count only syntactically recognized T90 worker outputs, never arbitrary
    # abandoned uploads or unmanaged S3 object prefixes.
    recognized = 0
    for item in objects:
        stored_name = item["stored_name"]
        location = item["location"]
        if backend == "s3":
            if not stored_name.startswith(managed):
                continue
            filename = stored_name[len(managed):]
        else:
            if not location.startswith(managed):
                continue
            filename = location[len(managed):]
        job_id = _job_id(filename)
        if job_id is None:
            continue
        recognized += 1
        if stored_name in referenced:
            continue
        if jobs.get(job_id) not in TERMINAL_ORPHAN_STATUSES:
            continue
        modified = _aware(item.get("modified_at"))
        if modified is None or modified > cutoff:
            continue
        candidates.append({
            "job_id": job_id,
            "stored_name": stored_name,
            "size": int(item["size"]),
            "age_hours": int((now - modified).total_seconds() // 3600),
        })
    candidates.sort(key=lambda x: (x["job_id"], x["stored_name"]))
    return {
        "dry_run": True, "auto_delete": False, "backend": backend,
        "minimum_grace_hours": min_age_hours,
        "recognized_job_objects": recognized,
        "eligible_count": len(candidates),
        "truncated": len(candidates) > detail_limit,
        "candidates": candidates[:detail_limit],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only T90 orphan output inventory. Does not delete files."
    )
    parser.add_argument("--min-age-hours", type=int, default=MIN_GRACE_HOURS)
    parser.add_argument("--detail-limit", type=int, default=50)
    args = parser.parse_args()
    with SessionLocal() as db:
        report = inventory_orphan_job_outputs(
            db, min_age_hours=args.min_age_hours, detail_limit=args.detail_limit
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
