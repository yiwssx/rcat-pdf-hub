#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: check-worker-pools.py COMPOSE_CONFIG_JSON")

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
services = config.get("services", {})

expected = {
    "worker-interactive": "PDFHUB_RQ_INTERACTIVE_QUEUE",
    "worker": "PDFHUB_RQ_QUEUE",
    "worker-heavy": "PDFHUB_RQ_HEAVY_QUEUE",
}
all_queue_vars = set(expected.values())

for service, queue_var in expected.items():
    if service not in services:
        raise SystemExit(f"worker pool policy: missing service {service}")
    command = services[service].get("command") or []
    if isinstance(command, str):
        rendered = command
    else:
        rendered = " ".join(str(part) for part in command)
    if "rq worker" not in rendered:
        raise SystemExit(f"worker pool policy: {service} does not run rq worker")
    if f"${queue_var}" not in rendered:
        raise SystemExit(f"worker pool policy: {service} does not consume ${queue_var}")
    unexpected = sorted(
        variable for variable in all_queue_vars - {queue_var}
        if f"${variable}" in rendered
    )
    if unexpected:
        raise SystemExit(
            f"worker pool policy: {service} also consumes unexpected queues {unexpected}"
        )

print("worker pool policy: PASS")
