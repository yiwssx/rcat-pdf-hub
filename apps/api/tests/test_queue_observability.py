from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.observability import (
    JOB_DURATION_COUNT_KEY,
    JOB_DURATION_SUM_KEY,
    JOB_EVENTS_KEY,
    collect_queue_runtime_snapshot,
    record_job,
    record_job_duration,
)


class FakeQueue:
    def __init__(self, name: str, depth: int, enqueued_at: datetime | None = None):
        self.name = name
        self._depth = depth
        self._enqueued_at = enqueued_at

    def __len__(self) -> int:
        return self._depth

    def get_jobs(self, offset: int = 0, length: int = -1):
        assert offset == 0
        assert length == 1
        if self._depth <= 0 or self._enqueued_at is None:
            return []
        return [SimpleNamespace(enqueued_at=self._enqueued_at)]


class FakeWorker:
    def __init__(self, *queues: str):
        self._queues = list(queues)

    def queue_names(self) -> list[str]:
        return self._queues


def test_queue_runtime_snapshot_reports_depth_age_and_reserved_workers():
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    queues = [
        FakeQueue("pdf-interactive", 2, now - timedelta(seconds=45)),
        FakeQueue("pdf", 0),
        FakeQueue("pdf-heavy", 7, now - timedelta(minutes=12)),
    ]
    workers = [
        FakeWorker("pdf-interactive"),
        FakeWorker("pdf-interactive"),
        FakeWorker("pdf"),
        FakeWorker("pdf-heavy"),
    ]

    snapshot = collect_queue_runtime_snapshot(now=now, queues=queues, workers=workers)

    assert snapshot["pdf-interactive"] == {
        "queue_class": "interactive",
        "depth": 2,
        "oldest_job_age_seconds": 45.0,
        "workers": 2,
    }
    assert snapshot["pdf"] == {
        "queue_class": "pdf",
        "depth": 0,
        "oldest_job_age_seconds": 0.0,
        "workers": 1,
    }
    assert snapshot["pdf-heavy"] == {
        "queue_class": "heavy",
        "depth": 7,
        "oldest_job_age_seconds": 720.0,
        "workers": 1,
    }


def test_record_job_writes_cross_process_event(monkeypatch):
    calls = []

    class FakeRedis:
        def hincrby(self, key, field, amount):
            calls.append((key, field, amount))

    monkeypatch.setattr("app.observability.redis_conn", FakeRedis())

    record_job("ocr", "failed")

    assert calls == [(JOB_EVENTS_KEY, "heavy|ocr|failed", 1)]


def test_record_job_duration_writes_sum_and_count(monkeypatch):
    calls = []

    class FakeRedis:
        def hincrbyfloat(self, key, field, amount):
            calls.append(("float", key, field, amount))

        def hincrby(self, key, field, amount):
            calls.append(("int", key, field, amount))

    monkeypatch.setattr("app.observability.redis_conn", FakeRedis())

    record_job_duration("rotate", "completed", 1.25)

    assert calls == [
        ("float", JOB_DURATION_SUM_KEY, "interactive|rotate|completed", 1.25),
        ("int", JOB_DURATION_COUNT_KEY, "interactive|rotate|completed", 1),
    ]


def test_record_job_telemetry_failure_is_non_fatal(monkeypatch):
    class BrokenRedis:
        def hincrby(self, *args, **kwargs):
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.observability.redis_conn", BrokenRedis())

    record_job("merge", "queued")
