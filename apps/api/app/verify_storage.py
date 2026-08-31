import hashlib
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.models import FileRecord
from app.storage import is_s3_stored_name, path_for_stored_name, s3_client

settings = get_settings()


def _digest(path: Path) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            size += len(chunk)
            hasher.update(chunk)
    return size, hasher.hexdigest()


def verify_database_storage_consistency() -> dict[str, object]:
    with SessionLocal() as db:
        records = list(db.query(FileRecord).order_by(FileRecord.created_at).all())

    expected: set[str] = set()
    failures: list[str] = []
    verified = 0
    for record in records:
        try:
            path = path_for_stored_name(record.stored_name)
            actual_size, actual_hash = _digest(path)
        except Exception as exc:
            failures.append(f"{record.id}: missing/unreadable {record.stored_name}: {exc}")
            continue
        if actual_size != int(record.size):
            failures.append(f"{record.id}: size {actual_size} != DB {record.size}")
        if actual_hash != record.sha256:
            failures.append(f"{record.id}: sha256 mismatch for {record.stored_name}")
        expected.add(record.stored_name)
        verified += 1

    if settings.storage_backend == "local":
        actual = {
            item.name
            for folder in (settings.data_dir / "originals", settings.data_dir / "processed")
            if folder.exists()
            for item in folder.iterdir()
            if item.is_file()
        }
        expected_local = {name for name in expected if not is_s3_stored_name(name)}
        failures.extend(
            f"orphan storage file not referenced by DB: {name}"
            for name in sorted(actual - expected_local)
        )
    else:
        prefix = settings.s3_prefix.strip("/")
        actual_keys: set[str] = set()
        paginator = s3_client().get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=(prefix + "/") if prefix else ""):
            actual_keys.update(str(item["Key"]) for item in page.get("Contents", []))
        expected_keys = {
            name.removeprefix("s3:")
            for name in expected
            if is_s3_stored_name(name)
        }
        failures.extend(
            f"orphan S3 object not referenced by DB: {name}"
            for name in sorted(actual_keys - expected_keys)
        )

    return {"records": len(records), "verified": verified, "failures": failures}


def main() -> int:
    result = verify_database_storage_consistency()
    failures = list(result["failures"])
    print(
        f"restored-data records={result['records']} "
        f"verified={result['verified']} failures={len(failures)}"
    )
    for failure in failures[:100]:
        print(f"FAIL: {failure}")
    if len(failures) > 100:
        print(f"FAIL: {len(failures) - 100} additional mismatch(es) omitted")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
