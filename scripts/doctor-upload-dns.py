#!/usr/bin/env python3
"""Read-only DNS/TCP probes of PDF Hub service dependencies from INSIDE API.

Run with: docker compose ... exec -T api python - < scripts/doctor-upload-dns.py
No credentials, uploads, database writes, or external network checks.
"""
from __future__ import annotations

import os
import socket
import sys
from urllib.parse import urlsplit


def target_from_url(env_key: str, default: str, default_port: int) -> tuple[str, int] | None:
    value = os.environ.get(env_key, default).strip()
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.hostname:
        raise ValueError(f"{env_key} is not a valid service URL")
    return parsed.hostname, parsed.port or default_port


def targets_from_environment() -> dict[str, tuple[str, int]]:
    targets: dict[str, tuple[str, int]] = {}
    config = (
        ("PostgreSQL", "PDFHUB_DATABASE_URL", "postgresql+psycopg://postgres:5432/pdfhub", 5432),
        ("Valkey", "PDFHUB_REDIS_URL", "redis://valkey:6379/0", 6379),
        ("Gotenberg", "PDFHUB_GOTENBERG_URL", "http://gotenberg:3000", 3000),
    )
    for label, key, default, port in config:
        target = target_from_url(key, default, port)
        if target is not None:
            targets[label] = target
    if os.environ.get("PDFHUB_STORAGE_BACKEND", "local") == "s3":
        target = target_from_url("PDFHUB_S3_ENDPOINT_URL", "", 443)
        if target is None:
            raise ValueError("S3 is enabled without PDFHUB_S3_ENDPOINT_URL")
        targets["S3 storage"] = target
    if os.environ.get("PDFHUB_CLAMAV_ENABLED", "false").lower() == "true":
        host = os.environ.get("PDFHUB_CLAMAV_HOST", "clamav").strip()
        if not host:
            raise ValueError("ClamAV host is empty")
        targets["ClamAV"] = (host, int(os.environ.get("PDFHUB_CLAMAV_PORT", "3310")))
    return targets


def check_target(label: str, host: str, port: int) -> bool:
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        print(f"FAIL {label}: DNS resolution failed for {host}:{port} ({exc})")
        return False
    try:
        with socket.create_connection((host, port), timeout=3.0):
            pass
    except OSError as exc:
        print(f"FAIL {label}: DNS resolved {host}, but TCP {port} is unavailable ({exc})")
        return False
    print(f"PASS {label}: DNS + TCP reachable at {host}:{port}")
    return True


def main() -> int:
    print("PDF Hub upload dependency doctor (read-only, from API container)")
    try:
        targets = targets_from_environment()
    except (ValueError, OverflowError) as exc:
        print(f"FAIL configuration: {exc}")
        return 2
    results = [check_target(label, host, port) for label, (host, port) in targets.items()]
    if all(results):
        print("PASS all configured dependency DNS/TCP checks (service authentication and writes not tested)")
        return 0
    print("FAIL dependency DNS/TCP; check the selected Docker Compose deployment mode, networks, and service logs")
    return 1


if __name__ == "__main__":
    sys.exit(main())
