from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FileRecord
from app.storage import S3_PREFIX, is_s3_stored_name, s3_client

settings = get_settings()


def _managed_s3_prefixes() -> tuple[str, str]:
    prefix = settings.s3_prefix.strip("/")
    base = f"{prefix}/" if prefix else ""
    return (f"{base}originals/", f"{base}processed/")


def _scan_s3_objects() -> dict[str, dict]:
    client = s3_client()
    prefix = settings.s3_prefix.strip("/")
    request: dict[str, object] = {"Bucket": settings.s3_bucket}
    if prefix:
        request["Prefix"] = prefix + "/"

    managed_prefixes = _managed_s3_prefixes()
    objects: dict[str, dict] = {}
    while True:
        page = client.list_objects_v2(**request)
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if not key.startswith(managed_prefixes):
                continue
            stored_name = S3_PREFIX + key
            objects[stored_name] = {
                "stored_name": stored_name,
                "location": key,
                "size": int(item.get("Size") or 0),
            }
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
        if not token:
            break
        request["ContinuationToken"] = token
    return objects


def _scan_local_objects() -> tuple[list[dict], dict[str, list[dict]]]:
    objects: list[dict] = []
    by_name: dict[str, list[dict]] = defaultdict(list)
    for area in ("originals", "processed"):
        directory = settings.data_dir / area
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            item = {
                "stored_name": path.name,
                "location": f"{area}/{path.name}",
                "size": path.stat().st_size,
            }
            objects.append(item)
            by_name[path.name].append(item)
    return objects, by_name


def reconcile_storage(db: Session, detail_limit: int = 200) -> dict:
    """Compare FileRecord metadata with managed storage without mutating either side."""
    records = list(db.scalars(select(FileRecord).order_by(FileRecord.id)))
    issues: list[dict] = []

    def add_issue(
        category: str,
        *,
        record: FileRecord | None = None,
        stored_name: str,
        expected_size: int | None = None,
        actual_size: int | None = None,
        locations: list[str] | None = None,
    ) -> None:
        issues.append(
            {
                "category": category,
                "file_id": record.id if record else None,
                "stored_name": stored_name,
                "expected_size": expected_size,
                "actual_size": actual_size,
                "locations": locations or [],
            }
        )

    if settings.storage_backend == "s3":
        objects = _scan_s3_objects()
        referenced: set[str] = set()
        for record in records:
            if not is_s3_stored_name(record.stored_name):
                add_issue(
                    "backend_mismatch",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                )
                continue
            referenced.add(record.stored_name)
            item = objects.get(record.stored_name)
            if item is None:
                add_issue(
                    "missing_object",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                )
                continue
            if int(item["size"]) != int(record.size):
                add_issue(
                    "size_mismatch",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                    actual_size=int(item["size"]),
                    locations=[str(item["location"])],
                )
        for stored_name, item in objects.items():
            if stored_name not in referenced:
                add_issue(
                    "orphan_object",
                    stored_name=stored_name,
                    actual_size=int(item["size"]),
                    locations=[str(item["location"])],
                )
        storage_count = len(objects)
    else:
        objects, by_name = _scan_local_objects()
        referenced: set[str] = set()
        for record in records:
            if is_s3_stored_name(record.stored_name):
                add_issue(
                    "backend_mismatch",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                )
                continue
            logical_name = Path(record.stored_name).name
            if logical_name != record.stored_name:
                add_issue(
                    "invalid_stored_name",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                )
            referenced.add(logical_name)
            matches = by_name.get(logical_name, [])
            if not matches:
                add_issue(
                    "missing_object",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                )
                continue
            if len(matches) > 1:
                add_issue(
                    "duplicate_storage_name",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                    locations=[str(item["location"]) for item in matches],
                )
                continue
            item = matches[0]
            if int(item["size"]) != int(record.size):
                add_issue(
                    "size_mismatch",
                    record=record,
                    stored_name=record.stored_name,
                    expected_size=record.size,
                    actual_size=int(item["size"]),
                    locations=[str(item["location"])],
                )
        for item in objects:
            if str(item["stored_name"]) not in referenced:
                add_issue(
                    "orphan_object",
                    stored_name=str(item["stored_name"]),
                    actual_size=int(item["size"]),
                    locations=[str(item["location"])],
                )
        storage_count = len(objects)

    issues.sort(key=lambda issue: (issue["category"], issue["stored_name"], issue["file_id"] or ""))
    total_issues = len(issues)
    # Aggregate on the full issue set before trimming potentially sensitive details.
    category_counts = dict(sorted(Counter(issue["category"] for issue in issues).items()))
    return {
        "category_counts": category_counts,
        "dry_run": True,
        "backend": settings.storage_backend,
        "database_records": len(records),
        "storage_objects": storage_count,
        "issue_count": total_issues,
        "healthy": total_issues == 0,
        "truncated": total_issues > detail_limit,
        "issues": issues[:detail_limit],
    }
