import pytest

from app.config import Settings
from app.queue import (
    enqueue_processing_job,
    queue_class_for_operation,
    queue_name_for_operation,
)


EXPECTED_CLASSES = {
    "organize": "interactive",
    "split": "interactive",
    "rotate": "interactive",
    "watermark": "interactive",
    "page-numbers": "interactive",
    "stamp": "interactive",
    "merge": "pdf",
    "compress": "pdf",
    "images-to-pdf": "pdf",
    "ocr": "heavy",
    "pdfa": "heavy",
    "office-to-pdf": "heavy",
    "pdf-to-images": "heavy",
}


@pytest.mark.parametrize(("operation", "expected"), EXPECTED_CLASSES.items())
def test_operation_queue_classification(operation: str, expected: str):
    assert queue_class_for_operation(operation) == expected


def test_unknown_operation_fails_closed():
    with pytest.raises(ValueError, match="Unsupported PDF operation"):
        queue_class_for_operation("not-a-real-operation")


def test_queue_name_uses_configured_class_queue(monkeypatch):
    monkeypatch.setattr("app.queue.settings.rq_interactive_queue", "interactive-test")
    monkeypatch.setattr("app.queue.settings.rq_queue", "standard-test")
    monkeypatch.setattr("app.queue.settings.rq_heavy_queue", "heavy-test")

    assert queue_name_for_operation("rotate") == "interactive-test"
    assert queue_name_for_operation("merge") == "standard-test"
    assert queue_name_for_operation("ocr") == "heavy-test"


def test_enqueue_processing_job_uses_selected_queue(monkeypatch):
    calls: list[tuple[str, tuple, dict]] = []

    class FakeQueue:
        name = "heavy-test"

        def enqueue(self, function: str, *args, **kwargs):
            calls.append((function, args, kwargs))
            return object()

    fake_queue = FakeQueue()
    monkeypatch.setattr("app.queue.queue_for_operation", lambda operation: fake_queue)

    queue, queued = enqueue_processing_job("ocr", "job-123")

    assert queue is fake_queue
    assert queued is not None
    assert calls == [
        (
            "app.worker_tasks.process_job",
            ("job-123",),
            {"job_timeout": 1800, "result_ttl": 86400},
        )
    ]


def test_queue_names_must_be_distinct():
    with pytest.raises(ValueError, match="RQ queue names must be distinct"):
        Settings(
            rq_interactive_queue="same",
            rq_queue="same",
            rq_heavy_queue="heavy",
        )
