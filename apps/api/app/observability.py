import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from rq import Worker

from app.config import get_settings
from app.queue import (
    all_processing_queues,
    queue_class_for_name,
    queue_class_for_operation,
    redis_conn,
)

settings = get_settings()

HTTP_REQUESTS = Counter(
    "pdfhub_http_requests_total",
    "HTTP requests handled by PDF Hub",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "pdfhub_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
)
JOBS = Counter("pdfhub_jobs_total", "PDF jobs by operation and terminal state", ["operation", "state"])
FILES = Counter("pdfhub_files_total", "File lifecycle events", ["event", "backend"])
MALWARE = Counter("pdfhub_malware_scans_total", "Malware scanning outcomes", ["outcome"])
ARCHIVE = Counter("pdfhub_archive_submissions_total", "Archive integration submissions", ["integration", "outcome"])

QUEUE_DEPTH = Gauge(
    "pdfhub_queue_depth",
    "Current RQ queue depth",
    ["queue", "queue_class"],
)
QUEUE_OLDEST_AGE = Gauge(
    "pdfhub_queue_oldest_job_age_seconds",
    "Age in seconds of the oldest waiting job in an RQ processing queue",
    ["queue", "queue_class"],
)
QUEUE_WORKERS = Gauge(
    "pdfhub_queue_workers",
    "Active RQ workers registered for a processing queue",
    ["queue", "queue_class"],
)
QUEUE_METRICS_COLLECTION_OK = Gauge(
    "pdfhub_queue_metrics_collection_ok",
    "Whether queue/worker runtime metrics were collected successfully",
)

JOB_EVENTS_CUMULATIVE = Gauge(
    "pdfhub_job_events_cumulative",
    "Redis-backed cumulative PDF job events visible across API and worker processes",
    ["queue_class", "operation", "state"],
)
JOB_DURATION_SUM_CUMULATIVE = Gauge(
    "pdfhub_job_duration_seconds_sum_cumulative",
    "Redis-backed cumulative processed-job duration in seconds",
    ["queue_class", "operation", "state"],
)
JOB_DURATION_COUNT_CUMULATIVE = Gauge(
    "pdfhub_job_duration_count_cumulative",
    "Redis-backed cumulative count of processed-job duration samples",
    ["queue_class", "operation", "state"],
)
JOB_METRICS_COLLECTION_OK = Gauge(
    "pdfhub_job_metrics_collection_ok",
    "Whether Redis-backed cross-process job metrics were collected successfully",
)

JOB_EVENTS_KEY = "pdfhub:metrics:job-events"
JOB_DURATION_SUM_KEY = "pdfhub:metrics:job-duration-sum"
JOB_DURATION_COUNT_KEY = "pdfhub:metrics:job-duration-count"


def _metric_field(queue_class: str, operation: str, state: str) -> str:
    return f"{queue_class}|{operation}|{state}"


def _parse_metric_field(value: str | bytes) -> tuple[str, str, str]:
    text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
    queue_class, operation, state = text.split("|", 2)
    return queue_class, operation, state


def _decode_number(value: Any) -> float:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return float(value)


def record_job(operation: str, state: str) -> None:
    JOBS.labels(operation=operation, state=state).inc()
    try:
        queue_class = queue_class_for_operation(operation)
        redis_conn.hincrby(JOB_EVENTS_KEY, _metric_field(queue_class, operation, state), 1)
    except Exception:
        # Telemetry is best-effort and must never change job/API behavior.
        pass


def record_job_duration(operation: str, state: str, seconds: float) -> None:
    try:
        queue_class = queue_class_for_operation(operation)
        field = _metric_field(queue_class, operation, state)
        redis_conn.hincrbyfloat(JOB_DURATION_SUM_KEY, field, max(0.0, float(seconds)))
        redis_conn.hincrby(JOB_DURATION_COUNT_KEY, field, 1)
    except Exception:
        # Redis-backed telemetry must not turn a completed/failed job into an error.
        pass


def record_file(event: str, backend: str | None = None) -> None:
    FILES.labels(event=event, backend=backend or settings.storage_backend).inc()


def record_malware(outcome: str) -> None:
    MALWARE.labels(outcome=outcome).inc()


def record_archive(integration: str, outcome: str) -> None:
    ARCHIVE.labels(integration=integration, outcome=outcome).inc()


def set_queue_depth(queue: str, depth: int) -> None:
    queue_class = queue_class_for_name(queue)
    QUEUE_DEPTH.labels(queue=queue, queue_class=queue_class).set(depth)


def collect_queue_runtime_snapshot(
    *,
    now: datetime | None = None,
    queues: tuple[Any, ...] | list[Any] | None = None,
    workers: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, dict[str, float | int | str]]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    queue_list = list(queues if queues is not None else all_processing_queues())
    if workers is None:
        # RQ documents Worker.count(queue=...) as the efficient monitoring seam.
        # Using it also avoids depending on private worker serialization details.
        worker_counts = {queue.name: Worker.count(queue=queue) for queue in queue_list}
    else:
        worker_counts = {queue.name: 0 for queue in queue_list}
        for worker in workers:
            try:
                worker_queues = worker.queues
            except Exception:
                continue
            for worker_queue in worker_queues:
                queue_name = getattr(worker_queue, "name", str(worker_queue))
                if queue_name in worker_counts:
                    worker_counts[queue_name] += 1

    snapshot: dict[str, dict[str, float | int | str]] = {}
    for queue in queue_list:
        queue_class = queue_class_for_name(queue.name)
        depth = len(queue)
        oldest_age = 0.0
        if depth > 0:
            jobs = queue.get_jobs(offset=0, length=1)
            if jobs:
                enqueued_at = getattr(jobs[0], "enqueued_at", None)
                if enqueued_at is not None:
                    if enqueued_at.tzinfo is None:
                        enqueued_at = enqueued_at.replace(tzinfo=timezone.utc)
                    oldest_age = max(0.0, (current - enqueued_at).total_seconds())
        snapshot[queue.name] = {
            "queue_class": queue_class,
            "depth": depth,
            "oldest_job_age_seconds": oldest_age,
            "workers": worker_counts[queue.name],
        }
    return snapshot


def refresh_queue_runtime_metrics() -> dict[str, dict[str, float | int | str]]:
    try:
        snapshot = collect_queue_runtime_snapshot()
        QUEUE_DEPTH.clear()
        QUEUE_OLDEST_AGE.clear()
        QUEUE_WORKERS.clear()
        for queue_name, values in snapshot.items():
            queue_class = str(values["queue_class"])
            QUEUE_DEPTH.labels(queue=queue_name, queue_class=queue_class).set(int(values["depth"]))
            QUEUE_OLDEST_AGE.labels(queue=queue_name, queue_class=queue_class).set(
                float(values["oldest_job_age_seconds"])
            )
            QUEUE_WORKERS.labels(queue=queue_name, queue_class=queue_class).set(int(values["workers"]))
        QUEUE_METRICS_COLLECTION_OK.set(1)
        return snapshot
    except Exception:
        QUEUE_METRICS_COLLECTION_OK.set(0)
        return {}


def refresh_distributed_job_metrics() -> None:
    try:
        event_rows = redis_conn.hgetall(JOB_EVENTS_KEY)
        duration_sum_rows = redis_conn.hgetall(JOB_DURATION_SUM_KEY)
        duration_count_rows = redis_conn.hgetall(JOB_DURATION_COUNT_KEY)

        # Redis can be restarted/restored independently of the API process.
        # Clear previously exported label sets so vanished Redis fields cannot
        # remain as stale in-process Gauge samples indefinitely.
        JOB_EVENTS_CUMULATIVE.clear()
        JOB_DURATION_SUM_CUMULATIVE.clear()
        JOB_DURATION_COUNT_CUMULATIVE.clear()

        for field, value in event_rows.items():
            queue_class, operation, state = _parse_metric_field(field)
            JOB_EVENTS_CUMULATIVE.labels(
                queue_class=queue_class,
                operation=operation,
                state=state,
            ).set(_decode_number(value))

        all_duration_fields = set(duration_sum_rows) | set(duration_count_rows)
        for field in all_duration_fields:
            queue_class, operation, state = _parse_metric_field(field)
            label_values = {
                "queue_class": queue_class,
                "operation": operation,
                "state": state,
            }
            JOB_DURATION_SUM_CUMULATIVE.labels(**label_values).set(
                _decode_number(duration_sum_rows.get(field, 0))
            )
            JOB_DURATION_COUNT_CUMULATIVE.labels(**label_values).set(
                _decode_number(duration_count_rows.get(field, 0))
            )

        JOB_METRICS_COLLECTION_OK.set(1)
    except Exception:
        JOB_METRICS_COLLECTION_OK.set(0)


def _setup_otel(app: FastAPI) -> None:
    if not settings.otel_endpoint:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": settings.otel_service_name}))
    exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def prometheus_http_metrics(request: Request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route_obj = request.scope.get("route")
            route = getattr(route_obj, "path", request.url.path)
            if route != "/metrics":
                HTTP_REQUESTS.labels(method=request.method, route=route, status=str(status)).inc()
                HTTP_DURATION.labels(method=request.method, route=route).observe(time.perf_counter() - started)

    if settings.prometheus_enabled:
        @app.get("/metrics", include_in_schema=False)
        def metrics():
            refresh_queue_runtime_metrics()
            refresh_distributed_job_metrics()
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    _setup_otel(app)
