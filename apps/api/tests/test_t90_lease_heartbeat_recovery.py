"""T90-0.10: heartbeat, multi-session fencing, and manually verified recovery."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import lease_recovery, write_journal
from app.db import SessionLocal
from app.models import ArtifactWriteJournal, JobRecord
from app.worker_heartbeat import WorkerHeartbeat


def _new_job(*, rq_id=None):
    with SessionLocal() as db:
        job = JobRecord(
            id=str(uuid4()), status="queued", progress=0,
            operation="compress", requested_by="service-a",
            input_file_ids_json="[]", params_json="{}",
            rq_job_id=rq_id or str(uuid4()),
        )
        db.add(job)
        db.commit()
        return job.id


def _claim(job_id):
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        token = write_journal.claim_queued_job(db, job, 120)
        return token, job.lease_epoch


def _set_expiry(job_id, delta_minutes):
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        job.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)
        db.commit()


class FakeRQJob:
    func_name = "app.worker_tasks.process_job"
    def __init__(self, job_id, rq_id, status="failed"):
        self.id = rq_id
        self.args = (job_id,)
        self.status = status
        self.refresh_called = False

    def get_status(self, *, refresh):
        assert refresh is True
        self.refresh_called = True
        return self.status


def _make_expired_with_rq():
    job_id = _new_job()
    token, epoch = _claim(job_id)
    _set_expiry(job_id, -15)
    with SessionLocal() as db:
        rq_id = db.get(JobRecord, job_id).rq_job_id
    return job_id, token, epoch, FakeRQJob(job_id, rq_id)


def test_heartbeat_extends_only_live_current_attempt():
    job_id = _new_job()
    token, epoch = _claim(job_id)
    with SessionLocal() as db:
        original = db.get(JobRecord, job_id).lease_expires_at
        # SQLAlchemy SQLite datetimes are timezone-naive; compare after loading.
        future = datetime.now(timezone.utc) + timedelta(seconds=30)
        assert write_journal.renew_execution_lease(
            db, job_id=job_id, token=token, epoch=epoch,
            ttl_seconds=300, now=future,
        )
    with SessionLocal() as db:
        new_expiry = db.get(JobRecord, job_id).lease_expires_at
        assert new_expiry.replace(tzinfo=timezone.utc) > original.replace(tzinfo=timezone.utc)
        assert db.get(JobRecord, job_id).status == "running"


@pytest.mark.parametrize("change", ["wrong_token", "wrong_epoch", "expired", "cancelled", "completed"])
def test_heartbeat_cannot_revive_stale_or_terminal_lease(change):
    job_id = _new_job()
    token, epoch = _claim(job_id)
    if change in {"expired", "cancelled", "completed"}:
        with SessionLocal() as db:
            job = db.get(JobRecord, job_id)
            if change == "expired":
                job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            else:
                job.status = change
            db.commit()
    with SessionLocal() as db:
        assert write_journal.renew_execution_lease(
            db, job_id=job_id,
            token="invalid" if change == "wrong_token" else token,
            epoch=epoch + 1 if change == "wrong_epoch" else epoch,
            ttl_seconds=120,
        ) is False


def test_two_independent_worker_sessions_cannot_both_claim():
    job_id = _new_job()
    barrier = Barrier(2)

    def claim():
        with SessionLocal() as db:
            job = db.get(JobRecord, job_id)
            barrier.wait(timeout=5)
            return write_journal.claim_queued_job(db, job, 120)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), [0, 1]))
    assert len([token for token in results if token is not None]) == 1
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "running" and job.lease_epoch == 1


def test_worker_heartbeat_loop_loses_token_then_exits(monkeypatch):
    job_id = _new_job()
    token, epoch = _claim(job_id)
    beat = WorkerHeartbeat(job_id, token, epoch, ttl_seconds=120, interval_seconds=5)
    with SessionLocal() as db:
        db.get(JobRecord, job_id).status = "cancelled"
        db.commit()
    # Drive exactly one iteration synchronously, without timers or sleeps.
    calls = iter([False])
    monkeypatch.setattr(beat._stop, "wait", lambda _: next(calls))
    beat._run()
    assert beat.lost is True


def test_heartbeat_refuses_unsafe_period_or_ttl():
    with pytest.raises(ValueError):
        WorkerHeartbeat("job", "token", 1, ttl_seconds=120, interval_seconds=40)
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            write_journal.renew_execution_lease(
                db, job_id="invalid", token="invalid", epoch=1, ttl_seconds=10
            )


def test_dry_run_never_mutates_expired_job(monkeypatch):
    job_id, token, epoch, rq = _make_expired_with_rq()
    result = None
    with SessionLocal() as db:
        result = lease_recovery.inspect_or_recover_expired_job(
            db, job_id=job_id, expected_epoch=epoch,
            rq_job=rq, actor="test-operator",
        )
    assert result["dry_run"] and result["action"] == "eligible_for_operator_review"
    assert not result["auto_requeued"] and not result["auto_deleted"]
    assert rq.refresh_called
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "running" and job.lease_token == token


@pytest.mark.parametrize("bad", ["started", "queued", "finished", "unknown"])
def test_recovery_refuses_live_or_unverifiable_queue_state(bad):
    job_id, _, epoch, rq = _make_expired_with_rq()
    rq.status = bad
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="terminal"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator", apply=True,
            )
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "running"


def test_recovery_refuses_wrong_rq_identity_and_arguments():
    job_id, _, epoch, rq = _make_expired_with_rq()
    rq.id = str(uuid4())
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="does not match"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator",
            )
    with SessionLocal() as db:
        rq.id = db.get(JobRecord, job_id).rq_job_id
        rq.args = ("another-job",)
        with pytest.raises(ValueError, match="invocation"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator",
            )


def test_recovery_refuses_early_action_or_stale_epoch():
    job_id, _, epoch, rq = _make_expired_with_rq()
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="epoch"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch+1,
                rq_job=rq, actor="test-operator", apply=True,
            )
        with pytest.raises(ValueError, match="grace"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator", apply=True,
                grace_seconds=86400,
            )


def test_committed_artifact_blocks_manual_recovery():
    job_id, token, epoch, rq = _make_expired_with_rq()
    with SessionLocal() as db:
        db.add(ArtifactWriteJournal(
            job_id=job_id, lease_epoch=epoch, lease_token=token,
            stored_name=f"{job_id}-{token}.pdf", role="result",
            state="committed", file_id=str(uuid4()),
        ))
        db.commit()
        with pytest.raises(ValueError, match="committed"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator", apply=True,
            )
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "running"


def test_audit_failure_prevents_recovery(monkeypatch):
    job_id, _, epoch, rq = _make_expired_with_rq()
    monkeypatch.setattr(lease_recovery, "audit_event", lambda *a, **kw: False)
    with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="Audit log"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator", apply=True,
            )
    with SessionLocal() as db:
        assert db.get(JobRecord, job_id).status == "running"


def test_manual_recovery_revokes_fence_and_preserves_pending_objects(monkeypatch):
    job_id, token, epoch, rq = _make_expired_with_rq()
    calls = []
    monkeypatch.setattr(lease_recovery, "audit_event", lambda *a, **kw: calls.append(a[0]) or True)
    with SessionLocal() as db:
        db.add(ArtifactWriteJournal(
            job_id=job_id, lease_epoch=epoch, lease_token=token,
            stored_name=f"{job_id}-{token}.pdf", role="result", state="planned",
        ))
        db.commit()
        result = lease_recovery.inspect_or_recover_expired_job(
            db, job_id=job_id, expected_epoch=epoch,
            rq_job=rq, actor="test-operator", apply=True,
        )
    assert result["action"] == "mark_failed_no_retry" and not result["dry_run"]
    assert calls == ["job.lease_recovery_requested", "job.lease_recovered"]
    with SessionLocal() as db:
        job = db.get(JobRecord, job_id)
        assert job.status == "failed" and job.lease_token is None
        assert job.lease_epoch == epoch
        assert db.scalar(select(ArtifactWriteJournal).where(
            ArtifactWriteJournal.job_id == job_id
        )).state == "planned"
        assert write_journal.renew_execution_lease(
            db, job_id=job_id, token=token, epoch=epoch, ttl_seconds=120,
        ) is False
        with pytest.raises(ValueError, match="epoch|current"):
            lease_recovery.inspect_or_recover_expired_job(
                db, job_id=job_id, expected_epoch=epoch,
                rq_job=rq, actor="test-operator", apply=True,
            )
