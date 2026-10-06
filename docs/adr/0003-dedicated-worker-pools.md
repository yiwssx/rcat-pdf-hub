# ADR-0003: Isolate worker capacity by workload queue

- Status: Accepted
- Date: 2026-10-06

## Context

ADR-0002 introduced deterministic routing into three RQ queues, but Task 6C.1 deliberately kept one transitional worker listening to all queues. That proved routing without leaving jobs unserved, but one worker process still allowed heavy OCR/Office work to consume the only available execution capacity.

The Phase 6 acceptance criterion requires lightweight work to retain execution capacity even when the heavy queue is backlogged.

## Decision

Run three independent RQ worker services:

- `worker-interactive` consumes only `PDFHUB_RQ_INTERACTIVE_QUEUE`;
- `worker` consumes only the standard `PDFHUB_RQ_QUEUE`;
- `worker-heavy` consumes only `PDFHUB_RQ_HEAVY_QUEUE`.

Each service starts one RQ worker process by default. Horizontal concurrency is explicit through the `scale-workers` / `scale-prod-workers` targets.

Default scale target:

- interactive: 2 worker processes;
- standard PDF: 2 worker processes;
- heavy: 1 worker process.

Execution timeouts are also class-specific:

- interactive: 600 seconds;
- standard PDF: 1800 seconds;
- heavy: 3600 seconds.

Production resource ceilings are intentionally asymmetric. Interactive workers have a smaller footprint, standard workers receive moderate capacity, and heavy workers receive the largest CPU/memory/tmpfs envelope.

NAS mounts, restore stop/start logic, runtime hardening checks, and production network policy include all three worker services.

## Consequences

- A backlog in `pdf-heavy` cannot occupy the worker process reserved for `pdf-interactive`.
- Heavy concurrency can be kept deliberately low to protect the host while interactive capacity is scaled independently.
- Worker scaling becomes slightly more explicit operationally, but no new broker or orchestration platform is introduced.
- Job/API contracts and persisted operation names remain unchanged.
- Queue depth/worker observability can be refined per class in Task 6C.3.

## Validation

Rendered Compose configuration must prove that every worker service consumes exactly one queue and never another queue.

The runtime production validation starts all three worker pools and checks container hardening/network policy. Backend tests verify workload-specific timeout selection and queue routing.
