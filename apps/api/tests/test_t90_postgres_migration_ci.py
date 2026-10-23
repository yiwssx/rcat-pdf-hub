"""T90-0.7: PostgreSQL 18 CI-only Alembic migration/backfill/rollback rehearsal.

Requires GITHUB_ACTIONS=true plus a loopback, purpose-built PostgreSQL
service. Creates/drops only uniquely named disposable databases. The suite
does not accept production database URLs or use a real database backup.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from sqlalchemy.engine import make_url

API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "0004_phase6_file_library_indexes"
LATEST = "0006_t90_write_journal"
ENV_NAME = "PDFHUB_T90_POSTGRES_TEST_URL"
CI_USER = "pdfhub_t90_ci"


def _admin_connection_kwargs() -> dict:
    uri = os.environ.get(ENV_NAME)
    if not uri:
        pytest.skip("PostgreSQL CI rehearsal runs only when isolated test service is configured")
    if os.environ.get("GITHUB_ACTIONS") != "true":
        pytest.fail("T90 PostgreSQL rehearsal must run only in ephemeral GitHub Actions CI")
    url = make_url(uri)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port != 5432
        or url.database != "postgres"
        or url.username != CI_USER
        or not url.password
    ):
        pytest.fail("Refusing non-loopback or non-CI PostgreSQL connection")
    return {
        "host": "127.0.0.1", "port": 5432, "dbname": "postgres",
        "user": CI_USER, "password": url.password, "connect_timeout": 8,
    }


@pytest.fixture()
def isolated_postgres():
    """Allocate and ALWAYS drop a fresh prefixed database in the disposable CI PG."""
    kwargs = _admin_connection_kwargs()
    name = "pdfhub_t90_ci_" + uuid.uuid4().hex[:16]
    with psycopg.connect(**kwargs, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    db_kwargs = {**kwargs, "dbname": name}
    try:
        yield db_kwargs
    finally:
        # terminate orphaned clients only in the freshly allocated database,
        # even when Alembic or a test phase raised an exception.
        with psycopg.connect(**kwargs, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def _dsn(kwargs):
    from sqlalchemy.engine import URL
    return URL.create(
        "postgresql+psycopg", username=kwargs["user"],
        password=kwargs["password"], host=kwargs["host"],
        port=kwargs["port"], database=kwargs["dbname"],
    ).render_as_string(hide_password=False)


def _phase(kwargs, code):
    env = os.environ.copy()
    env["PDFHUB_DATABASE_URL"] = _dsn(kwargs)
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env, cwd=API_ROOT, capture_output=True, text=True,
        timeout=90, check=False,
    )
    if result.returncode:
        # Never include a traceback or DSN that could leak CI credentials.
        pytest.fail(
            f"T90 migration subprocess failed (exit {result.returncode}); "
            "inspect CI logs for sanitized diagnostic output"
        )


def _legacy_seed(conn):
    keys = {name: str(uuid.uuid4()) for name in (
        "bundle", "pdf", "foreign", "queued", "root_job", "pdf_job",
        "foreign_job", "missing_job", "queued_job", "failed_job", "null_job",
    )}
    now = datetime.now(timezone.utc)
    for name, owner, label, mime in (
        ("bundle", "service-a", "historical-pages.zip", "application/zip"),
        ("pdf", "service-a", "historical.pdf", "application/pdf"),
        ("foreign", "service-b", "other-owner.pdf", "application/pdf"),
        ("queued", "service-a", "queued.pdf", "application/pdf"),
    ):
        conn.execute(
            "INSERT INTO files "
            "(id, original_name, stored_name, content_type, size, sha256, "
            "source_system, created_at, expires_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL)",
            (keys[name], label, keys[name] + ".bin", mime,
             128, "a" * 64, owner, now),
        )
    for name, operation, status, file_key in (
        ("root_job", "pdf-to-images", "completed", "bundle"),
        ("pdf_job", "compress", "completed", "pdf"),
        ("foreign_job", "compress", "completed", "foreign"),
        ("missing_job", "compress", "completed", "missing"),
        ("queued_job", "compress", "queued", "queued"),
        ("failed_job", "compress", "failed", "pdf"),
        ("null_job", "compress", "completed", None),
    ):
        output = str(uuid.uuid4()) if file_key == "missing" else keys.get(file_key)
        conn.execute(
            "INSERT INTO jobs "
            "(id, operation, status, progress, input_file_ids_json, "
            "output_file_id, params_json, requested_by, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (keys[name], operation, status, 100 if status == "completed" else 0,
             "[]", output, "{}", "service-a", now),
        )
    return keys


def _rows(conn):
    return conn.execute(
        "SELECT job_id, file_id, role, ordinal "
        "FROM job_output_artifacts ORDER BY job_id, file_id"
    ).fetchall()


def _version(conn):
    return conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def _legacy_snapshot(conn):
    return (
        conn.execute("SELECT id, status, output_file_id, requested_by FROM jobs ORDER BY id").fetchall(),
        conn.execute("SELECT id, source_system, stored_name FROM files ORDER BY id").fetchall(),
    )


def _reject(conn, statement, params, expected_error):
    # The connection stays usable after a failed INSERT because each statement
    # is protected by a subtransaction/savepoint.
    with pytest.raises(expected_error):
        with conn.transaction():
            conn.execute(statement, params)


@pytest.mark.parametrize("baseline", ["migrated_0004", "pre_alembic_adopted"])
def test_postgres_migration_lifecycle_with_historical_rows(isolated_postgres, baseline):
    args = isolated_postgres
    if baseline == "migrated_0004":
        _phase(args, (
            "from alembic import command; from app.migrate import _config; "
            f"command.upgrade(_config(), '{PREVIOUS}')"
        ))
    else:
        _phase(args, (
            "from app.db import engine; "
            "from app.models import ApiKey, ServicePolicy, FileRecord, JobRecord; "
            "for_table = (ApiKey.__table__, ServicePolicy.__table__, FileRecord.__table__, JobRecord.__table__); "
            "[item.create(bind=engine, checkfirst=True) for item in for_table]"
        ))

    with psycopg.connect(**args, autocommit=True) as conn:
        keys = _legacy_seed(conn)
        before = _legacy_snapshot(conn)
        if baseline == "pre_alembic_adopted":
            assert conn.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0] is None

    _phase(args, "from app.migrate import run_migrations; run_migrations()")
    # Repeat upgrade to make sure replays do not duplicate historical links.
    _phase(args, "from app.migrate import run_migrations; run_migrations()")
    with psycopg.connect(**args, autocommit=True) as conn:
        assert _version(conn) == LATEST
        assert _legacy_snapshot(conn) == before
        assert set(_rows(conn)) == {
            (keys["root_job"], keys["bundle"], "bundle", None),
            (keys["pdf_job"], keys["pdf"], "result", None),
        }
        index = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
            "AND tablename='job_output_artifacts' "
            "AND indexname='uq_job_output_artifacts_one_primary'"
        ).fetchone()
        assert index is not None and "UNIQUE INDEX" in index[0]
        assert "WHERE" in index[0] and "role" in index[0]

        _reject(
            conn, "INSERT INTO job_output_artifacts(job_id,file_id,role,ordinal) "
            "VALUES (%s,%s,'result',NULL)",
            (keys["root_job"], keys["pdf"]), psycopg.errors.UniqueViolation,
        )
        conn.execute(
            "INSERT INTO job_output_artifacts(job_id,file_id,role,ordinal) "
            "VALUES (%s,%s,'part',1)",
            (keys["root_job"], keys["queued"]),
        )
        _reject(
            conn, "INSERT INTO job_output_artifacts(job_id,file_id,role,ordinal) "
            "VALUES (%s,%s,'part',1)",
            (keys["root_job"], keys["pdf"]), psycopg.errors.UniqueViolation,
        )
        _reject(
            conn, "INSERT INTO job_output_artifacts(job_id,file_id,role,ordinal) "
            "VALUES (%s,%s,'part',0)",
            (keys["pdf_job"], keys["queued"]), psycopg.errors.CheckViolation,
        )
        _reject(
            conn, "INSERT INTO job_output_artifacts(job_id,file_id,role,ordinal) "
            "VALUES (%s,%s,'part',201)",
            (keys["pdf_job"], keys["queued"]), psycopg.errors.CheckViolation,
        )
        _reject(
            conn, "INSERT INTO job_output_artifacts(job_id,file_id,role,ordinal) "
            "VALUES (%s,%s,'result',NULL)",
            (str(uuid.uuid4()), keys["queued"]), psycopg.errors.ForeignKeyViolation,
        )

    _phase(args, (
        "from alembic import command; from app.migrate import _config; "
        f"command.downgrade(_config(), '{PREVIOUS}')"
    ))
    with psycopg.connect(**args, autocommit=True) as conn:
        assert _version(conn) == PREVIOUS
        assert conn.execute("SELECT to_regclass('public.job_output_artifacts')").fetchone()[0] is None
        assert _legacy_snapshot(conn) == before

    _phase(args, "from app.migrate import run_migrations; run_migrations()")
    with psycopg.connect(**args, autocommit=True) as conn:
        assert _version(conn) == LATEST
        assert _legacy_snapshot(conn) == before
        assert set(_rows(conn)) == {
            (keys["root_job"], keys["bundle"], "bundle", None),
            (keys["pdf_job"], keys["pdf"], "result", None),
        }


def test_ci_postgres_in_memory_new_schema_and_root_index(isolated_postgres):
    args = isolated_postgres
    _phase(args, "from app.migrate import run_migrations; run_migrations()")
    with psycopg.connect(**args, autocommit=True) as conn:
        assert _version(conn) == LATEST
        assert conn.execute("SELECT count(*) FROM job_output_artifacts").fetchone()[0] == 0
        # Match SQLAlchemy/Alembic to exact PostgreSQL filtered unique index.
        row = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
            "AND tablename='job_output_artifacts' "
            "AND indexname='uq_job_output_artifacts_one_primary'"
        ).fetchone()
        assert row is not None and "UNIQUE" in row[0] and "WHERE" in row[0]
