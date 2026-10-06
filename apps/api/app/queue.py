from typing import Literal

from redis import Redis
from rq import Queue
from rq.job import Job as RQJob

from app.config import get_settings


QueueClass = Literal["interactive", "pdf", "heavy"]

INTERACTIVE_OPERATIONS = frozenset({
    "organize",
    "split",
    "rotate",
    "watermark",
    "page-numbers",
    "stamp",
})
PDF_OPERATIONS = frozenset({
    "merge",
    "compress",
    "images-to-pdf",
})
HEAVY_OPERATIONS = frozenset({
    "ocr",
    "pdfa",
    "office-to-pdf",
    "pdf-to-images",
})
SUPPORTED_OPERATIONS = INTERACTIVE_OPERATIONS | PDF_OPERATIONS | HEAVY_OPERATIONS

settings = get_settings()
redis_conn = Redis.from_url(settings.redis_url)

interactive_queue = Queue(
    settings.rq_interactive_queue,
    connection=redis_conn,
    default_timeout=settings.rq_interactive_job_timeout_seconds,
)
pdf_queue = Queue(
    settings.rq_queue,
    connection=redis_conn,
    default_timeout=settings.rq_job_timeout_seconds,
)
heavy_queue = Queue(
    settings.rq_heavy_queue,
    connection=redis_conn,
    default_timeout=settings.rq_heavy_job_timeout_seconds,
)


def queue_class_for_operation(operation: str) -> QueueClass:
    if operation in INTERACTIVE_OPERATIONS:
        return "interactive"
    if operation in PDF_OPERATIONS:
        return "pdf"
    if operation in HEAVY_OPERATIONS:
        return "heavy"
    raise ValueError(f"Unsupported PDF operation for queue routing: {operation}")


def queue_name_for_operation(operation: str) -> str:
    queue_class = queue_class_for_operation(operation)
    return {
        "interactive": settings.rq_interactive_queue,
        "pdf": settings.rq_queue,
        "heavy": settings.rq_heavy_queue,
    }[queue_class]


def queue_timeout_for_operation(operation: str) -> int:
    queue_class = queue_class_for_operation(operation)
    return {
        "interactive": settings.rq_interactive_job_timeout_seconds,
        "pdf": settings.rq_job_timeout_seconds,
        "heavy": settings.rq_heavy_job_timeout_seconds,
    }[queue_class]


def queue_for_operation(operation: str) -> Queue:
    queue_name = queue_name_for_operation(operation)
    return {
        settings.rq_interactive_queue: interactive_queue,
        settings.rq_queue: pdf_queue,
        settings.rq_heavy_queue: heavy_queue,
    }[queue_name]


def all_processing_queues() -> tuple[Queue, Queue, Queue]:
    return interactive_queue, pdf_queue, heavy_queue


def enqueue_processing_job(operation: str, job_id: str) -> tuple[Queue, RQJob]:
    queue = queue_for_operation(operation)
    queued = queue.enqueue(
        "app.worker_tasks.process_job",
        job_id,
        job_timeout=queue_timeout_for_operation(operation),
        result_ttl=86400,
    )
    return queue, queued
