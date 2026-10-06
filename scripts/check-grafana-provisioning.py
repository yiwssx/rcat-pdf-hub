#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dashboard_path = ROOT / "ops/grafana/dashboards/pdfhub-operations.json"
datasources_path = ROOT / "ops/grafana/provisioning/datasources/datasources.yml"
providers_path = ROOT / "ops/grafana/provisioning/dashboards/dashboards.yml"

dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
datasources = datasources_path.read_text(encoding="utf-8")
providers = providers_path.read_text(encoding="utf-8")

if dashboard.get("uid") != "rcat-pdfhub-operations":
    raise SystemExit("grafana dashboard policy: canonical dashboard UID is missing")
if dashboard.get("title") != "RCAT PDF Hub — Operations":
    raise SystemExit("grafana dashboard policy: canonical dashboard title is missing")

expressions = {
    target.get("expr", "")
    for panel in dashboard.get("panels", [])
    for target in panel.get("targets", [])
}
required_fragments = {
    'up{job="pdf-hub-api"}': "availability",
    "pdfhub_http_request_duration_seconds_bucket": "latency",
    "pdfhub_queue_depth": "queue depth",
    "pdfhub_job_events_cumulative": "failures",
    "pdfhub_queue_workers": "workers",
    "pdfhub_storage_bytes": "storage capacity",
}
for fragment, label in required_fragments.items():
    if not any(fragment in expr for expr in expressions):
        raise SystemExit(f"grafana dashboard policy: missing {label} query")

links = dashboard.get("links", [])
if not any(link.get("url") == "/explore" for link in links):
    raise SystemExit("grafana dashboard policy: trace Explore link is missing")

for required in (
    "uid: prometheus",
    "url: http://prometheus:9090",
    "uid: tempo",
    "url: http://tempo:3200",
):
    if required not in datasources:
        raise SystemExit(f"grafana datasource policy: missing {required!r}")

if "path: /var/lib/grafana/dashboards" not in providers:
    raise SystemExit("grafana dashboard policy: provisioned dashboard path is missing")

print("grafana dashboard policy: PASS")
