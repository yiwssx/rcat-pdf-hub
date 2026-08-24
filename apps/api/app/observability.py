import time

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.config import get_settings

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
QUEUE_DEPTH = Gauge("pdfhub_queue_depth", "Current RQ queue depth", ["queue"])


def record_job(operation: str, state: str) -> None:
    JOBS.labels(operation=operation, state=state).inc()


def record_file(event: str, backend: str | None = None) -> None:
    FILES.labels(event=event, backend=backend or settings.storage_backend).inc()


def record_malware(outcome: str) -> None:
    MALWARE.labels(outcome=outcome).inc()


def record_archive(integration: str, outcome: str) -> None:
    ARCHIVE.labels(integration=integration, outcome=outcome).inc()


def set_queue_depth(queue: str, depth: int) -> None:
    QUEUE_DEPTH.labels(queue=queue).set(depth)


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
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    _setup_otel(app)
