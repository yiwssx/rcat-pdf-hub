"""T90-0.10: CAS heartbeat, multi-worker duplicate fencing, audited recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event

import pytest
from sqlalchemy import select

from app import supervised_recovery, write_journal
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, JobRecord, JobOutputArtifact


def _job():
    with SessionLocal() as db:
        job = JobRecord(
            operation="compress", requested_by="test-tenant",
            status="queued", progress=0, input_file_ids_json="[]", params_json="{}",
            rq_job_id="test-rq-terminal",
        )
        db.add(job)
        db.commit()
        return job.id


def _claim(job_id):
    with SessionLocal() as db:
        return write_journal.claim_queued_job(db, db.get(JobRecord, job_id), 90)


def _expiry(job_id, *, seconds=-1):
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        db.commit()


def test_cas_renewal_only_for_current_running_unexpired_token():
    job_id = _job()
    token = _claim(job_id)
    with SessionLocal() as db:
        old = db.get(JobRecord, job_id).lease_expires_at
        assert write_journal.renew_execution_lease(db, job_id, token, 180)
        db.refresh(db.get(JobRecord, job_id))
        assert db.get(JobRecord, job_id).lease_expires_at > old
        assert not write_journal.renew_execution_lease(db, job_id, "wrong-token", 180)
        assert db.get(JobRecord, job_id).status == "running"

    _expiry(job_id)
    with SessionLocal() as db:
        assert not write_journal.renew_execution_lease(db, job_id, token, 180)
        assert not write_journal.lease_is_current(db, db.get(JobRecord, job_id), token)


def test_cancelled_job_cannot_be_revived_by_heartbeat():
    job_id = _job()
    token = _claim(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        job.status = "cancelled"
        db.commit()
        assert not write_journal.renew_execution_lease(db, job_id, token, 90)
        assert db.get(JobRecord, job_id).status == "cancelled"


def test_heartbeat_uses_separate_db_session_and_stops(monkeypatch):
    job_id = _job()
    token = _claim(job_id)
    observed = Event()
    real_renew = write_journal.renew_execution_lease

    def observed_renew(db, *args, **kwargs):
        result = real_renew(db, *args, **kwargs)
        if result:
            observed.set()
        return result

    monkeypatch.setattr(write_journal, "renew_execution_lease", observed_renew)
    hb = write_journal.LeaseHeartbeat(
        SessionLocal, job_id, token, 90, interval_seconds=0.04
    ).start()
    try:
        assert observed.wait(timeout=3), "Heartbeat did not renew in its own Session"
        assert not hb.lost.is_set()
    finally:
        hb.stop()
    assert not hb._thread.is_alive()


def test_heartbeat_rejects_revoked_token_and_marks_lost():
    job_id = _job()
    token = _claim(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        job.lease_token = "replacement-owner"
        db.commit()
    hb = write_journal.LeaseHeartbeat(
        SessionLocal, job_id, token, 90, interval_seconds=0.04
    ).start()
    try:
        assert hb.lost.wait(timeout=3)
    finally:
        hb.stop()
    assert not hb._thread.is_alive()


def test_two_simultaneous_workers_cannot_both_claim_same_job():
    job_id = _job()
    ready = Barrier(2)

    def attempt():
        with SessionLocal() as db:
            job = db.get(JobRecord, job_id)
            ready.wait(timeout=3)
            return write_journal.claim_queued_job(db, job, 90)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(token is not None for token in results) == 1
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).lease_epoch == 1


def test_stale_lease_inventory_is_read_only_and_tracks_planned_journal():
    job_id = _job()
    token = _claim(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        write_journal.reserve_writes(db, job, token, [(f"{job_id}-{token}.pdf", "result")])
    _expiry(job_id)
    with SessionLocal() as db:
        report = supervised_recovery.inspect_stale_leases(db)
        assert report["dry_run"] is True and report["mutated"] is False
        assert len(report["candidates"]) == 1
        entry = report["candidates"][0]
        assert entry["job_id"] == job_id
        assert entry["lease_token"] == token
        assert entry["lease_epoch"] == 1
        assert entry["rq_job_present"] is True
        assert entry["unresolved_journal_count"] == 1
        assert db.get(JobRecord, job_id).status == "running"
        assert db.scalar(select(ArtifactWriteJournal)).state == "planned"


def test_quarantine_requires_expired_and_authoritative_terminal_rq(monkeypatch):
    job_id = _job()
    token = _claim(job_id)
    monkeypatch.setattr(supervised_recovery, "_verified_rq_state", lambda _: "failed")
    monkeypatch.setattr(supervised_recovery, "audit_event", lambda *a, **k: True)
    with SessionLocal() as db:
        assert not supervised_recovery.quarantine_expired_job(
            db, job_id, expected_token=token, expected_epoch=1
        )
    _expiry(job_id)
    monkeypatch.setattr(supervised_recovery, "_verified_rq_state", lambda _: "started")
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="not verifiably terminal"):
            supervised_recovery.quarantine_expired_job(
                db, job_id, expected_token=token, expected_epoch=1
            )
        assert db.get(JobRecord, job_id).status == "running"


def test_manual_quarantine_fences_worker_without_deleting_journal(monkeypatch):
    job_id = _job()
    token = _claim(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        write_journal.reserve_writes(db, job, token, [(f"{job_id}-{token}.pdf", "result")])
    _expiry(job_id)
    observed = []
    monkeypatch.setattr(supervised_recovery, "_verified_rq_state", lambda _: "stopped")
    monkeypatch.setattr(
        supervised_recovery, "audit_event",
        lambda event, actor, target, id_, details: observed.append(
            (event, id_, details["rq_status"])
        ) or True,
    )
    with SessionLocal() as db:
        assert not supervised_recovery.quarantine_expired_job(
            db, job_id, expected_token="wrong", expected_epoch=1
        )
        assert supervised_recovery.quarantine_expired_job(
            db, job_id, expected_token=token, expected_epoch=1
        )
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed"
        assert job.lease_epoch == 2 and job.lease_token is None
        assert job.output_file_id is None
        assert not write_journal.renew_execution_lease(db, job_id, token, 90)
        assert db.scalar(select(ArtifactWriteJournal)).state == "planned"
        assert db.scalar(select(JobOutputArtifact)) is None
        assert not supervised_recovery.quarantine_expired_job(
            db, job_id, expected_token=token, expected_epoch=1
        )
    assert observed == [("job.stale_lease_quarantine_requested", job_id, "stopped")]


def test_recovery_fails_closed_on_redis_or_audit_error(monkeypatch):
    job_id = _job()
    token = _claim(job_id)
    _expiry(job_id)
    monkeypatch.setattr(
        supervised_recovery, "_verified_rq_state",
        lambda _: (_ for _ in ()).throw(OSError("redis unavailable")),
    )
    with SessionLocal() as db:
        with pytest.raises(OSError, match="redis unavailable"):
            supervised_recovery.quarantine_expired_job(
                db, job_id, expected_token=token, expected_epoch=1
            )
        assert db.get(JobRecord, job_id).status == "running"
    monkeypatch.setattr(supervised_recovery, "_verified_rq_state", lambda _: "failed")
    monkeypatch.setattr(supervised_recovery, "audit_event", lambda *a, **k: False)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            supervised_recovery.quarantine_expired_job(
                db, job_id, expected_token=token, expected_epoch=1
            )
        assert db.get(JobRecord, job_id).status == "running"


def test_recovery_rejects_already_published_output_even_if_expired(monkeypatch):
    job_id = _job()
    token = _claim(job_id)
    _expiry(job_id)
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        job.output_file_id = "published-file-ref"
        db.commit()
    monkeypatch.setattr(
        supervised_recovery, "_verified_rq_state",
        lambda _: (_ for _ in ()).throw(AssertionError("must not query RQ")),
    )
    with SessionLocal() as db:
        assert not supervised_recovery.quarantine_expired_job(
            db, job_id, expected_token=token, expected_epoch=1
        )


def test_invalid_inventory_or_heartbeat_parameters_rejected():
    job_id = _job()
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="limit"):
            supervised_recovery.inspect_stale_leases(db, limit=101)
        with pytest.raises(ValueError, match="timestamp"):
            supervised_recovery.inspect_stale_leases(
                db, now=datetime(2026, 10, 23)
            )
    with pytest.raises(ValueError, match="cadence"):
        write_journal.LeaseHeartbeat(SessionLocal, job_id, "test", 90, 31)
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="Execution lease"):
            write_journal.renew_execution_lease(db, job_id, "test", 5)
