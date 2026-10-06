#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit(
        "usage: check-production-network.py COMPOSE_CONFIG_JSON PUBLIC_BIND_HOST MANAGEMENT_BIND_HOST"
    )

config_path = Path(sys.argv[1])
public_bind = sys.argv[2]
management_bind = sys.argv[3]
config = json.loads(config_path.read_text(encoding="utf-8"))
services = config.get("services", {})
networks = config.get("networks", {})

required_networks = {"edge", "app", "data", "management", "egress"}
missing_networks = required_networks - set(networks)
if missing_networks:
    raise SystemExit(f"production network policy: missing networks {sorted(missing_networks)}")

for name in ("app", "data", "management"):
    if networks[name].get("internal") is not True:
        raise SystemExit(f"production network policy: {name} must be internal")

for name in ("edge", "egress"):
    if networks[name].get("internal") is True:
        raise SystemExit(f"production network policy: {name} must allow external connectivity")

expected_membership = {
    "postgres": {"data"},
    "valkey": {"data"},
    "gotenberg": {"data"},
    "api": {"app", "data", "management", "egress"},
    "worker-interactive": {"data", "management", "egress"},
    "worker": {"data", "management", "egress"},
    "worker-heavy": {"data", "management", "egress"},
    "cleanup": {"data", "management", "egress"},
    "webhook": {"data", "management", "egress"},
    "web": {"app"},
    "caddy": {"edge", "app"},
    "seaweedfs": {"data"},
    "clamav": {"data"},
    "prometheus": {"management"},
    "alertmanager": {"management"},
    "tempo": {"management"},
    "otel-collector": {"management"},
    "paperless-db": {"data"},
    "paperless": {"data", "management", "egress"},
}

for service, expected in expected_membership.items():
    if service not in services:
        raise SystemExit(f"production network policy: missing service {service}")
    raw_networks = services[service].get("networks") or {}
    actual = set(raw_networks if isinstance(raw_networks, list) else raw_networks.keys())
    if actual != expected:
        raise SystemExit(
            f"production network policy: {service} networks {sorted(actual)} != {sorted(expected)}"
        )

private_services = {
    "postgres",
    "valkey",
    "gotenberg",
    "api",
    "worker-interactive",
    "worker",
    "worker-heavy",
    "cleanup",
    "webhook",
    "web",
    "seaweedfs",
    "clamav",
    "paperless-db",
}
for service in sorted(private_services):
    if services[service].get("ports"):
        raise SystemExit(f"production network policy: {service} must not publish host ports")

def host_ips(service: str) -> set[str]:
    return {
        str(item.get("host_ip") or "0.0.0.0")
        for item in services[service].get("ports", [])
    }

caddy_hosts = host_ips("caddy")
if caddy_hosts != {public_bind}:
    raise SystemExit(
        f"production network policy: caddy host bind {sorted(caddy_hosts)} != [{public_bind!r}]"
    )

for service in ("prometheus", "alertmanager", "tempo", "otel-collector", "paperless"):
    ports = services[service].get("ports", [])
    if ports and host_ips(service) != {management_bind}:
        raise SystemExit(
            f"production network policy: {service} management ports must bind only to {management_bind}"
        )

print("production network policy: PASS")
