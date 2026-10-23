"""T90-0.6: exercise real Alembic upgrade/backfill/downgrade on isolated SQLite DBs.

The tests deliberately do not touch the configured pytest application DB or
a live deployment. PostgreSQL + S3 production rehearsals are separate gates.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
PRIOR_REVISION = "0004_phase6_file_library_indexes"
T90_REVISION = "0006_t90_write_journal"


def _invoke(db_path: Path, source: str) -> None:
    environment = os.environ.copy()
    environment["PDFHUB_DATABASE_URL"] = f"sqlite+pysqlite:///{db_path}"
    # One isolated Python process per phase: application settings/engine are
    # cached by design and cannot be mutated safely in the pytest process.
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=API_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"migration phase exited {result.returncode}:\n"
        f"stdout:\n{result.stdout[-2000:]}\nstderr:\n{result.stderr[-3000:]}"
    )


def _seed_legacy(db_path: Path) -> dict[str, str]:
    keys = {key: str(uuid4()) for key in (
        "bundle", "pdf", "foreign", "queued", "root_job", "pdf_job",
        "foreign_job", "missing_job", "queued_job", "failed_job", "null_job",
    )}
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as db:
        files = [
            ("bundle", "service-a", "image-pages.zip", "application/zip"),
            ("pdf", "service-a", "compressed.pdf", "application/pdf"),
            ("foreign", "service-b", "other-owner.pdf", "application/pdf"),
            ("queued", "service-a", "still-active.pdf", "application/pdf"),
        ]
        for key, owner, filename, mime in files:
            db.execute(
                "INSERT INTO files (id, original_name, stored_name, content_type, "
                "size, sha256, source_system, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (keys[key], filename, keys[key] + "-" + filename, mime, 123,
                 "a" * 64, owner, now),
            )
        jobs = [
            ("root_job", "pdf-to-images", "completed", "bundle"),
            ("pdf_job", "compress", "completed", "pdf"),
            ("foreign_job", "compress", "completed", "foreign"),
            ("missing_job", "compress", "completed", "absent"),
            ("queued_job", "compress", "queued", "queued"),
            ("failed_job", "compress", "failed", "pdf"),
            ("null_job", "compress", "completed", None),
        ]
        for key, operation, status, file_key in jobs:
            output = str(uuid4()) if file_key == "absent" else keys.get(file_key)
            db.execute(
                "INSERT INTO jobs "
                "(id, operation, status, progress, input_file_ids_json, "
                "output_file_id, params_json, requested_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (keys[key], operation, status, 100 if status == "completed" else 0,
                 "[]", output, "{}", "service-a", now),
            )
    return keys


def _version(db: sqlite3.Connection) -> str:
    return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def _backfill_rows(db: sqlite3.Connection) -> list[tuple[str, str, str, int | None]]:
    return db.execute(
        "SELECT job_id, file_id, role, ordinal "
        "FROM job_output_artifacts ORDER BY job_id, file_id"
    ).fetchall()


@pytest.mark.parametrize("starting_state", ["fresh", "adopted"])
def test_migration_backfill_constraints_and_safe_downgrade(tmp_path: Path, starting_state: str):
    database = tmp_path / f"t90-{starting_state}.db"
    if starting_state == "fresh":
        _invoke(database, (
            "from alembic import command; from app.migrate import _config; "
            f"command.upgrade(_config(), '{PRIOR_REVISION}')"
        ))
    else:
        # Legacy databases were created with SQLAlchemy without alembic_version.
        # Create only pre-Alembic core tables; run_migrations should adopt them.
        _invoke(database, (
            "from app.db import engine; "
            "from app.models import ApiKey, ServicePolicy, FileRecord, JobRecord; "
            "tables = (ApiKey.__table__, ServicePolicy.__table__, FileRecord.__table__, JobRecord.__table__); "
            "[(table.create(bind=engine, checkfirst=True)) for table in tables]; "
            "from sqlalchemy import text; "
            "with_block = engine.begin(); connection = with_block.__enter__(); "
            "[connection.execute(text('ALTER TABLE jobs DROP COLUMN ' + name)) "
            " for name in ('lease_epoch','lease_token','lease_expires_at')]; "
            "with_block.__exit__(None, None, None)"
        ))
        with sqlite3.connect(database) as db:
            assert "alembic_version" not in {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
    ids = _seed_legacy(database)
    with sqlite3.connect(database) as db:
        legacy_jobs = db.execute(
            "SELECT id, output_file_id, status FROM jobs ORDER BY id"
        ).fetchall()
        legacy_files = db.execute("SELECT id, source_system FROM files ORDER BY id").fetchall()

    _invoke(database, "from app.migrate import run_migrations; run_migrations()")
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        assert _version(db) == T90_REVISION
        links = _backfill_rows(db)
        assert set(links) == {
            (ids["root_job"], ids["bundle"], "bundle", None),
            (ids["pdf_job"], ids["pdf"], "result", None),
        }
        assert db.execute("SELECT id, output_file_id, status FROM jobs ORDER BY id").fetchall() == legacy_jobs
        assert db.execute("SELECT id, source_system FROM files ORDER BY id").fetchall() == legacy_files
        indexes = {row[1] for row in db.execute("PRAGMA index_list(job_output_artifacts)")}
        assert "uq_job_output_artifacts_one_primary" in indexes
        assert "ix_job_output_artifacts_file_id" in indexes
        foreign_keys = {row[2] for row in db.execute("PRAGMA foreign_key_list(job_output_artifacts)")}
        assert foreign_keys == {"jobs", "files"}

        # A job must not publish two primary result objects, even when one
        # is a ZIP and the other is a PDF (nullable ordinal would permit this).
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO job_output_artifacts(job_id, file_id, role, ordinal) "
                "VALUES (?, ?, 'result', NULL)",
                (ids["root_job"], ids["pdf"]),
            )
        db.rollback()
        # Non-primary part ordinal 1 is permitted once, then must be unique.
        db.execute(
            "INSERT INTO job_output_artifacts(job_id, file_id, role, ordinal) "
            "VALUES (?, ?, 'part', 1)",
            (ids["root_job"], ids["queued"]),
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO job_output_artifacts(job_id, file_id, role, ordinal) "
                "VALUES (?, ?, 'part', 1)",
                (ids["root_job"], ids["pdf"]),
            )
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO job_output_artifacts(job_id, file_id, role, ordinal) "
                "VALUES (?, ?, 'part', 0)",
                (ids["pdf_job"], ids["queued"]),
            )
        db.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO job_output_artifacts(job_id, file_id, role, ordinal) "
                "VALUES (?, ?, 'result', NULL)",
                (str(uuid4()), ids["queued"]),
            )
        db.rollback()

    _invoke(database, (
        "from alembic import command; from app.migrate import _config; "
        f"command.downgrade(_config(), '{PRIOR_REVISION}')"
    ))
    with sqlite3.connect(database) as db:
        assert _version(db) == PRIOR_REVISION
        assert "job_output_artifacts" not in {
            row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert db.execute("SELECT id, output_file_id, status FROM jobs ORDER BY id").fetchall() == legacy_jobs
        assert db.execute("SELECT id, source_system FROM files ORDER BY id").fetchall() == legacy_files

    # Rollback and re-upgrade should reconstruct only safe historical links.
    _invoke(database, "from app.migrate import run_migrations; run_migrations()")
    with sqlite3.connect(database) as db:
        assert _version(db) == T90_REVISION
        assert set(_backfill_rows(db)) == {
            (ids["root_job"], ids["bundle"], "bundle", None),
            (ids["pdf_job"], ids["pdf"], "result", None),
        }
        assert db.execute("SELECT id, output_file_id, status FROM jobs ORDER BY id").fetchall() == legacy_jobs


def test_new_schema_root_uniqueness_holds_on_sqlite_without_nullable_ordinal_exception(tmp_path: Path):
    database = tmp_path / "fresh-t90.db"
    _invoke(database, "from app.migrate import run_migrations; run_migrations()")
    with sqlite3.connect(database) as db:
        assert _version(db) == T90_REVISION
        entries = db.execute("PRAGMA index_list(job_output_artifacts)").fetchall()
        assert any(row[1] == "uq_job_output_artifacts_one_primary" and row[2] == 1 for row in entries)
        # The constraint applies only to result/bundle roots, not numbered parts.
        sql = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' "
            "AND name='uq_job_output_artifacts_one_primary'"
        ).fetchone()[0]
        assert "WHERE role IN ('result', 'bundle')" in sql
