"""T90-0.10: fail-closed supervised lease recovery + multi-session heartbeat."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import t90_recovery_operator as recovery
from app import write_journal
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, FileRecord, JobRecord

NOW = datetime.now(timezone.utc)


def _job(*, status="running", epoch=3, expires_minutes=-10, rq="rq-test-001"):
    job_id, token = str(uuid4()), str(uuid4())
    with SessionLocal() as db:
        db.add(JobRecord(
            id=job_id, operation="compress", status=status, progress=25,
            requested_by="service-a", rq_job_id=rq,
            input_file_ids_json="[]", params_json="{}",
            lease_epoch=epoch, lease_token=token,
            lease_expires_at=NOW + timedelta(minutes=expires_minutes),
        ))
        db.add(ArtifactWriteJournal(
            id=str(uuid4()), job_id=job_id, lease_epoch=epoch,
            lease_token=token, stored_name=f"{job_id}-{token}.pdf",
            role="result", state="planned",
        ))
        db.commit()
    return job_id, token


def _status(value):
    return lambda _id: value


def test_inspection_dry_run_redacts_token_and_never_modifies_rows():
    job_id, token = _job()
    other, _ = _job(expires_minutes=10)
    with SessionLocal() as db:
        report = recovery.inspect_expired_leases(db, now=NOW)
        assert report["dry_run"] is True
        assert report["auto_requeue"] is False and report["auto_delete"] is False
        assert len(report["candidates"]) == 1
        assert report["candidates"][0]["job_id"] == job_id
        assert report["candidates"][0]["epoch"] == 3
        assert report["candidates"][0]["unresolved_writes"] == 1
        assert token not in str(report)
        assert db.get(JobRecord, job_id).status == "running"
        assert db.get(JobRecord, other).status == "running"


@pytest.mark.parametrize("status", ["queued", "started", "finished", "deferred", "scheduled", None])
def test_recovery_refuses_nonterminal_and_unknown_rq_status(status):
    job_id, token = _job()
    with SessionLocal() as db:
        assert not recovery.recover_expired_lease(
            db, job_id, expected_epoch=3, rq_status=_status(status), now=NOW,
        )
        assert db.get(JobRecord, job_id).status == "running"
        assert db.scalar(select(ArtifactWriteJournal)).state == "planned"


@pytest.mark.parametrize("rq_state", ["failed", "stopped", "canceled"])
def test_expired_stopped_rq_job_is_fenced_and_journal_retained(rq_state):
    job_id, token = _job()
    seen = []

    def verified(id_):
        seen.append(id_)
        return rq_state

    with SessionLocal() as db:
        assert recovery.recover_expired_lease(
            db, job_id, expected_epoch=3, rq_status=verified, now=NOW
        )
    assert seen == ["rq-test-001"]
    with SessionLocal() as db:
        record = db.get(JobRecord, job_id)
        journal = db.scalar(select(ArtifactWriteJournal))
        assert record.status == "failed"
        assert record.output_file_id is None
        assert record.lease_epoch == 3 and record.lease_token is None
        assert journal.state == "needs_review"
        assert journal.lease_token == token and journal.file_id is None
        assert not write_journal.lease_is_current(db, record, token)
        assert not recovery.recover_expired_lease(
            db, job_id, expected_epoch=3, rq_status=verified, now=NOW,
        )


def test_recovery_refuses_stale_epoch_even_when_queue_is_terminal():
    job_id, token = _job()
    with SessionLocal() as db:
        assert not recovery.recover_expired_lease(
            db, job_id, expected_epoch=2, rq_status=_status("failed"), now=NOW,
        )
        assert db.get(JobRecord, job_id).lease_token == token


def test_recovery_refuses_live_lease_cancelled_and_missing_queue_reference():
    live_id, _ = _job(expires_minutes=10)
    canceled_id, _ = _job(status="cancelled")
    missing_id, _ = _job(rq=None)
    with SessionLocal() as db:
        for job_id in (live_id, canceled_id, missing_id):
            assert not recovery.recover_expired_lease(
                db, job_id, expected_epoch=3, rq_status=_status("failed"), now=NOW,
            )


def test_redis_outage_fails_closed_leaving_journal():
    job_id, token = _job()

    def outage(_):
        raise ConnectionError("queue unavailable")

    with SessionLocal() as db:
        assert not recovery.recover_expired_lease(
            db, job_id, expected_epoch=3, rq_status=outage, now=NOW,
        )
        assert db.get(JobRecord, job_id).lease_token == token
        assert db.scalar(select(ArtifactWriteJournal)).state == "planned"


def test_expired_worker_cannot_be_revived_by_heartbeat():
    job_id, token = _job()
    with SessionLocal() as db:
        assert not write_journal.renew_lease(db, job_id, token, 3, 120)
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "running"


def test_active_worker_heartbeat_renews_but_wrong_token_epoch_fail():
    job_id, token = _job(expires_minutes=5)
    with SessionLocal() as db:
        assert not write_journal.renew_lease(db, job_id, "wrong", 3, 120)
        assert not write_journal.renew_lease(db, job_id, token, 2, 120)
        assert write_journal.renew_lease(db, job_id, token, 3, 120)
    with SessionLocal() as db:
        expiry = db.get(JobRecord, job_id).lease_expires_at
        assert expiry is not None
        # SQLite stores naive UTC, PostgreSQL timezone-aware.
        assert expiry.replace(tzinfo=timezone.utc) > NOW


def test_renewal_fails_after_user_cancellation():
    job_id, token = _job(expires_minutes=5)
    with SessionLocal() as db:
        j = db.get(JobRecord, job_id)
        j.status = "cancelled"
        db.commit()
    with SessionLocal() as db:
        assert not write_journal.renew_lease(db, job_id, token, 3, 120)


def test_two_competing_sessions_only_one_recovers_expired_epoch():
    job_id, token = _job()
    gate = Barrier(2)

    def attempt():
        with SessionLocal() as db:
            gate.wait(timeout=10)
            return recovery.recover_expired_lease(
                db, job_id, expected_epoch=3, rq_status=_status("failed"), now=NOW
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(attempt)
        second = pool.submit(attempt)
        assert sorted([first.result(timeout=15), second.result(timeout=15)]) == [False, True]
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "failed"
        assert db.scalar(select(ArtifactWriteJournal)).state == "needs_review"


def test_heartbeat_renewal_fences_supervised_recovery():
    job_id, token = _job(expires_minutes=-1)
    with SessionLocal() as db:
        # An expired lease cannot be rescued by heartbeat.
        assert not write_journal.renew_lease(db, job_id, token, 3, 120)
    with SessionLocal() as db:
        assert recovery.recover_expired_lease(
            db, job_id, expected_epoch=3, rq_status=_status("failed"), now=NOW
        )
    with SessionLocal() as db:
        assert not write_journal.renew_lease(db, job_id, token, 3, 120)


def test_bad_limit_and_epoch_fail_closed():
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            recovery.inspect_expired_leases(db, limit=0)
        with pytest.raises(ValueError):
            recovery.recover_expired_lease(db, str(uuid4()), expected_epoch=0,
                                          rq_status=_status("failed"))
