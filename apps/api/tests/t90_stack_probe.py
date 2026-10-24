"""T90-0.11 real PostgreSQL + Valkey/RQ + self-hosted SeaweedFS CI probe.

This file is deliberately NOT a normal pytest test: each subprocess must
inherit the same uniquely allocated Postgres database, isolated Redis DB,
temporary S3 bucket and feature flags. Run only by its dedicated CI step.
Never accept a remote endpoint or an existing Production database.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import boto3
import psycopg
from botocore.config import Config
from botocore.exceptions import ClientError
from redis import Redis
from sqlalchemy.engine import URL, make_url
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORKER = ROOT / "tests" / "t90_stack_worker.py"


def _require_ephemeral_ci() -> tuple[dict, str]:
    if os.getenv("GITHUB_ACTIONS") != "true" or os.getenv("PDFHUB_T90_STACK_ENABLED") != "yes":
        raise RuntimeError("Real stack probe is restricted to explicit ephemeral GitHub Actions CI")
    db = make_url(os.environ["PDFHUB_T90_STACK_POSTGRES_ADMIN_URL"])
    if (db.drivername != "postgresql+psycopg"
        or db.host != "127.0.0.1" or db.port != 5432
        or db.database != "postgres" or db.username != "pdfhub_t90_ci" or not db.password):
        raise RuntimeError("Refusing PostgreSQL target that is not the isolated CI administrator")
    s3 = os.environ["PDFHUB_T90_STACK_S3_ENDPOINT"]
    if s3 != "http://127.0.0.1:8333":
        raise RuntimeError("Refusing S3 endpoint outside ephemeral local CI service")
    return {
        "host": db.host, "port": db.port, "dbname": db.database,
        "user": db.username, "password": db.password,
        "connect_timeout": 8,
    }, s3


def _wait_ready(r: Redis, s3_client) -> None:
    last_error = None
    for _ in range(50):
        try:
            assert r.ping()
            s3_client.list_buckets()
            return
        except Exception as exc:
            last_error = type(exc).__name__
            time.sleep(0.5)
    raise RuntimeError(f"Local CI Redis or S3 service failed readiness ({last_error})")


def _invoke(env: dict, *args, timeout: int = 100) -> str:
    result = subprocess.run(
        [sys.executable, str(WORKER), *args],
        env=env, cwd=ROOT, text=True, capture_output=True, timeout=timeout,
    )
    if result.returncode:
        raise AssertionError(
            f"Real-stack child {args[0]} exited {result.returncode}:\n"
            f"{result.stdout[-1200:]}\n{result.stderr[-2200:]}"
        )
    return result.stdout[-1200:]


def _seed(db, bucket: str, key: str, owner: str, *, queue_id: str | None = None) -> str:
    from app.models import FileRecord, JobRecord, ServicePolicy
    content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    db.add(ServicePolicy(
        service_name=owner, rate_limit_per_minute=1000,
        daily_job_limit=1000, max_storage_mb=100, webhook_url=None,
    )) if db.get(ServicePolicy, owner) is None else None
    input_record = FileRecord(
        original_name="source.pdf", stored_name=f"s3:{key}",
        content_type="application/pdf", size=len(content),
        sha256="a" * 64, source_system=owner,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=3),
    )
    db.add(input_record)
    db.flush()
    job = JobRecord(
        operation="compress", status="queued", progress=0,
        input_file_ids_json=f'["{input_record.id}"]', params_json="{}",
        requested_by=owner, rq_job_id=queue_id,
    )
    db.add(job)
    db.commit()
    return job.id


def _assert_result(db, job_id: str, *, status: str, journal_status: str):
    from app.models import ArtifactWriteJournal, FileRecord, JobRecord, JobOutputArtifact
    from sqlalchemy import select

    db.expire_all()
    job = db.get(JobRecord, job_id)
    assert job is not None and job.status == status, (status, job.status if job else None)
    rows = list(db.scalars(select(ArtifactWriteJournal).where(
        ArtifactWriteJournal.job_id == job_id
    )))
    assert len(rows) == 1 and rows[0].state == journal_status, [(r.state, r.stored_name) for r in rows]
    assert rows[0].lease_epoch == 1
    assert rows[0].stored_name.startswith("s3:")
    if status == "completed":
        record = db.get(FileRecord, job.output_file_id)
        assert record is not None and record.stored_name == rows[0].stored_name
        assert rows[0].file_id == record.id
        links = list(db.scalars(select(JobOutputArtifact).where(
            JobOutputArtifact.job_id == job_id
        )))
        assert len(links) == 1 and links[0].file_id == record.id
    else:
        assert job.output_file_id is None
        assert not db.scalar(select(FileRecord.id).where(
            FileRecord.stored_name == rows[0].stored_name
        ))
        assert not db.scalar(select(JobOutputArtifact.job_id).where(
            JobOutputArtifact.job_id == job_id
        ))
    return rows[0].stored_name.removeprefix("s3:")


def _object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _dispose_s3(s3, bucket: str) -> None:
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            s3.delete_object(Bucket=bucket, Key=item["Key"])
    s3.delete_bucket(Bucket=bucket)


def main() -> None:
    admin, endpoint = _require_ephemeral_ci()
    token = uuid4().hex[:12]
    database = "pdfhub_t90_stack_" + token
    queue_name = "pdf-t90-stack-" + token
    bucket = "pdfhub-t90-ci-" + token
    r = Redis.from_url("redis://127.0.0.1:6379/15", socket_connect_timeout=3)
    s3 = boto3.client(
        "s3", endpoint_url=endpoint, region_name="us-east-1",
        aws_access_key_id="t90ci", aws_secret_access_key="t90ci-ephemeral-key",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      connect_timeout=3, read_timeout=5,
                      retries={"max_attempts": 2}),
    )
    _wait_ready(r, s3)
    with psycopg.connect(**admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    bucket_created = False
    children: list[subprocess.Popen] = []
    try:
        s3.create_bucket(Bucket=bucket)
        bucket_created = True
        # Listing buckets can become healthy before SeaweedFS master/volume
        # registration finishes. Require a real writable volume before chaos.
        for attempt in range(25):
            try:
                s3.put_object(
                    Bucket=bucket, Key="t90-ci/bootstrap-check",
                    Body=b"volume-ready",
                )
                s3.delete_object(Bucket=bucket, Key="t90-ci/bootstrap-check")
                break
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code", "")) != "InternalError":
                    raise
                if attempt == 24:
                    raise RuntimeError("SeaweedFS has no writable CI volumes") from exc
                time.sleep(1)
        dsn = URL.create(
            "postgresql+psycopg", username=admin["user"],
            password=admin["password"], host=admin["host"],
            port=admin["port"], database=database,
        ).render_as_string(hide_password=False)
        with tempfile.TemporaryDirectory(prefix="pdfhub-t90-stack-") as data_dir:
            env = os.environ.copy()
            env.update({
                "PDFHUB_DATABASE_URL": dsn,
                "PDFHUB_REDIS_URL": "redis://127.0.0.1:6379/15",
                "PDFHUB_STORAGE_BACKEND": "s3",
                "PDFHUB_S3_ENDPOINT_URL": endpoint,
                "PDFHUB_S3_BUCKET": bucket,
                "PDFHUB_S3_ACCESS_KEY": "t90ci",
                "PDFHUB_S3_SECRET_KEY": "t90ci-ephemeral-key",
                "PDFHUB_S3_PREFIX": "t90-ci",
                "PDFHUB_S3_AUTO_CREATE_BUCKET": "false",
                "PDFHUB_ARTIFACT_WRITE_JOURNAL_ENABLED": "true",
                "PDFHUB_MULTI_OUTPUT_ARTIFACTS_ENABLED": "false",
                "PDFHUB_LEASE_HEARTBEAT_INTERVAL_SECONDS": "5",
                "PDFHUB_LEASE_HEARTBEAT_TTL_SECONDS": "120",
                "PDFHUB_DATA_DIR": data_dir,
            })
            os.environ.update(env)
            from app.db import SessionLocal
            from app.migrate import run_migrations
            from app.models import JobRecord
            from rq import Queue
            from rq.job import Job as RQJob
            from app.lease_recovery import inspect_or_recover_expired_job

            run_migrations()
            queue = Queue(queue_name, connection=r)
            owner = "t90-stack-ci-" + token

            print("T90/1: two independent RQ worker processes, one DB job", flush=True)
            primary_input = "t90-ci/originals/source-" + token + ".pdf"
            s3.put_object(
                Bucket=bucket, Key=primary_input,
                Body=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
            )
            with SessionLocal() as db:
                job_id = _seed(db, bucket, primary_input, owner)
            first = queue.enqueue(
                "app.worker_tasks.process_job", job_id,
                job_timeout=120, result_ttl=600, failure_ttl=600,
            )
            second = queue.enqueue(
                "app.worker_tasks.process_job", job_id,
                job_timeout=120, result_ttl=600, failure_ttl=600,
            )
            with SessionLocal() as db:
                db.get(JobRecord, job_id).rq_job_id = first.id
                db.commit()
            for i in range(2):
                process = subprocess.Popen(
                    [sys.executable, str(WORKER), "rq", queue_name, str(i)],
                    env=env, cwd=ROOT, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True,
                )
                children.append(process)
            for process in list(children):
                output, _ = process.communicate(timeout=90)
                assert process.returncode == 0, ("RQ worker failed", output[-2000:])
            children.clear()
            assert first.get_status(refresh=True).value == "finished"
            assert second.get_status(refresh=True).value == "finished"
            with SessionLocal() as db:
                key = _assert_result(db, job_id, status="completed", journal_status="committed")
            assert _object_exists(s3, bucket, key)
            print("PASS: two real RQ processes, single fenced DB/S3 result", flush=True)

            print("T90/2: SIGKILL directly after real S3 upload, before DB result commit", flush=True)
            crash_input = "t90-ci/originals/crash-" + token + ".pdf"
            s3.put_object(
                Bucket=bucket, Key=crash_input,
                Body=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
            )
            with SessionLocal() as db:
                crash_id = _seed(db, bucket, crash_input, owner)
            # Queue reference stays queued because this scenario executes
            # a real worker task directly in its own killable process.
            # It MUST NOT be mistaken for an RQ-verified terminal task.
            held_rq = queue.enqueue(
                "app.worker_tasks.process_job", crash_id,
                job_timeout=120, result_ttl=600,
            )
            with SessionLocal() as db:
                db.get(JobRecord, crash_id).rq_job_id = held_rq.id
                db.commit()
            marker = Path(data_dir) / "uploaded.flag"
            child = subprocess.Popen(
                [sys.executable, str(WORKER), "stall-after-s3", crash_id, str(marker)],
                env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True,
            )
            children.append(child)
            deadline = time.monotonic() + 35
            while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.2)
            assert marker.exists(), "Hard-crash child never reached a real S3 upload"
            key = marker.read_text(encoding="utf-8").removeprefix("s3:")
            assert _object_exists(s3, bucket, key)
            child.kill()  # SIGKILL: no Python finally/compensation can run
            child.wait(timeout=10)
            assert child.returncode == -signal.SIGKILL
            children.remove(child)
            from app.models import ArtifactWriteJournal
            from sqlalchemy import select
            with SessionLocal() as db:
                key_after = _assert_result(db, crash_id, status="running", journal_status="planned")
                assert key_after == key
                job = db.get(JobRecord, crash_id)
                job.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=12)
                db.commit()
                # A queued RQ task is NOT proof of worker death. Fail closed.
                try:
                    inspect_or_recover_expired_job(
                        db, job_id=crash_id, expected_epoch=1,
                        rq_job=RQJob.fetch(held_rq.id, connection=r),
                        actor="ci-operator", apply=True,
                    )
                except ValueError as exc:
                    assert "terminal" in str(exc), str(exc)
                else:
                    raise AssertionError("Recovery incorrectly accepted nonterminal RQ evidence")
                db.refresh(job)
                assert job.status == "running"
            assert _object_exists(s3, bucket, key)
            print("PASS: SIGKILL preserves planned journal/orphan and refuses unsafe takeover", flush=True)

            print("T90/3: real S3 PUT then lost network ACK, compensating DELETE", flush=True)
            ack_input = "t90-ci/originals/ack-" + token + ".pdf"
            s3.put_object(
                Bucket=bucket, Key=ack_input,
                Body=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
            )
            with SessionLocal() as db:
                ack_id = _seed(db, bucket, ack_input, owner)
            _invoke(env, "ack-lost", ack_id, timeout=55)
            with SessionLocal() as db:
                ack_key = _assert_result(db, ack_id, status="failed", journal_status="compensated")
            assert not _object_exists(s3, bucket, ack_key)
            print("PASS: self-hosted S3 failure compensation and DB journal consistency", flush=True)
            # Remove the deliberately held RQ reference from T90/2 so its
            # queued delivery cannot interfere with this real work-horse test.
            held_rq.cancel()
            print("T90/4: SIGKILL actual RQ forked work-horse, verify live queue failure", flush=True)
            horse_input = "t90-ci/originals/horse-" + token + ".pdf"
            s3.put_object(
                Bucket=bucket, Key=horse_input,
                Body=b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
            )
            with SessionLocal() as db:
                horse_id = _seed(db, bucket, horse_input, owner)
            horse_rq = queue.enqueue(
                "app.worker_tasks.process_job", horse_id,
                job_timeout=120, result_ttl=600, failure_ttl=600,
            )
            with SessionLocal() as db:
                db.get(JobRecord, horse_id).rq_job_id = horse_rq.id
                db.commit()
            horse_marker = Path(data_dir) / "rq-workhorse-uploaded.json"
            supervisor = subprocess.Popen(
                [sys.executable, str(WORKER), "rq-kill-workhorse", queue_name, str(horse_marker)],
                env=env, cwd=ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True,
            )
            children.append(supervisor)
            deadline = time.monotonic() + 40
            while (
                not horse_marker.exists()
                and supervisor.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.2)
            assert horse_marker.exists(), "Real RQ work-horse did not reach S3 PUT"
            marker_info = json.loads(horse_marker.read_text(encoding="utf-8"))
            horse_pid, horse_ppid = marker_info["pid"], marker_info["ppid"]
            assert horse_pid != supervisor.pid and horse_ppid == supervisor.pid, (
                "Fault injection must target RQ's FORKED work-horse, not the supervisor",
                marker_info, supervisor.pid,
            )
            horse_key = marker_info["stored_name"].removeprefix("s3:")
            assert _object_exists(s3, bucket, horse_key)
            assert horse_rq.get_status(refresh=True).value == "started", (
                "RQ job must be actively running when its work-horse is killed",
                horse_rq.get_status(refresh=True),
            )
            with SessionLocal() as db:
                _assert_result(db, horse_id, status="running", journal_status="planned")
            os.kill(horse_pid, signal.SIGKILL)
            supervisor_output, _ = supervisor.communicate(timeout=70)
            children.remove(supervisor)
            assert supervisor.returncode == 0, (
                "RQ parent failed to reap dead work-horse", supervisor_output[-2400:],
            )
            from app.lease_recovery import TERMINAL_RQ_STATUSES
            refreshed = RQJob.fetch(horse_rq.id, connection=r)
            rq_state = refreshed.get_status(refresh=True)
            rq_state = getattr(rq_state, "value", rq_state)
            assert rq_state in TERMINAL_RQ_STATUSES, (
                "RQ failed to mark SIGKILLed forked work-horse terminal",
                rq_state, supervisor_output[-2400:],
            )
            with SessionLocal() as db:
                _assert_result(db, horse_id, status="running", journal_status="planned")
                record = db.get(JobRecord, horse_id)
                observed_epoch = record.lease_epoch
                # Before lease expiry, even terminal RQ evidence must NOT
                # authorize an operator-controlled recovery.
                try:
                    inspect_or_recover_expired_job(
                        db, job_id=horse_id, expected_epoch=observed_epoch,
                        rq_job=refreshed, actor="t90-ci-operator", apply=True,
                    )
                except ValueError as exc:
                    assert "expired" in str(exc).lower() or "lease" in str(exc).lower()
                else:
                    raise AssertionError("Recovery accepted a still-valid lease")
                db.rollback()
                # Simulate waiting for expiry+grace WITHOUT lengthening CI by
                # 5+ minutes. This only modifies the disposable CI database.
                record = db.get(JobRecord, horse_id)
                record.lease_expires_at = datetime.now(timezone.utc) - timedelta(minutes=12)
                db.commit()
                preview = inspect_or_recover_expired_job(
                    db, job_id=horse_id, expected_epoch=observed_epoch,
                    rq_job=refreshed, actor="t90-ci-operator", apply=False,
                )
                assert preview["dry_run"] is True
                applied = inspect_or_recover_expired_job(
                    db, job_id=horse_id, expected_epoch=observed_epoch,
                    rq_job=refreshed, actor="t90-ci-operator", apply=True,
                )
                assert applied["dry_run"] is False and applied["auto_deleted"] is False
                db.expire_all()
                recovered = db.get(JobRecord, horse_id)
                assert recovered.status == "failed" and recovered.lease_token is None
                journal_key = _assert_result(
                    db, horse_id, status="failed", journal_status="planned",
                )
                assert journal_key == horse_key
                assert not db.scalar(select(FileRecord.id).where(
                    FileRecord.stored_name == "s3:" + horse_key
                ))
                assert not db.scalar(select(JobOutputArtifact.job_id).where(
                    JobOutputArtifact.job_id == horse_id
                ))
            from app.models import FileRecord, JobOutputArtifact
            from app.audit import read_audit_events
            assert any(
                event.get("event") == "job.lease_recovery_requested"
                and event.get("resource_id") == horse_id
                for event in read_audit_events(limit=100)
            ), "Recovery approval was not durably audited"
            assert _object_exists(s3, bucket, horse_key), (
                "Supervised recovery must NOT delete the orphaned object",
            )
            print("PASS: actual RQ work-horse SIGKILL, terminal RQ status, audited fenced recovery", flush=True)
            print("T90 real-stack rehearsal: 4/4 scenarios passed (synthetic data only)", flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)
        if bucket_created:
            _dispose_s3(s3, bucket)
        # Restricted Redis DB 15 on CI-only Valkey instance.
        r.flushdb()
        with psycopg.connect(**admin, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()", (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
