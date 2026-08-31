#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDER_FRAGMENTS = (
    "replace-with",
    "change-me",
    "placeholder",
    "development-password",
    "development-secret",
)
REQUIRED_SECRETS = (
    "POSTGRES_PASSWORD",
    "PDFHUB_API_KEY_PEPPER",
    "PDFHUB_ADMIN_API_KEY",
    "PDFHUB_WEBHOOK_MASTER_SECRET",
    "PDFHUB_AUTH_TOKEN_SECRET",
    "PDFHUB_DOWNLOAD_SIGNING_SECRET",
)


def parse_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production RCAT PDF Hub environment safety")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--url", default=None, help="Intended public production URL")
    parser.add_argument("--allow-insecure", action="store_true")
    args = parser.parse_args()

    values = parse_env(Path(args.env_file))
    values.update({key: value for key, value in os.environ.items() if key in values or key.startswith("PDFHUB_") or key.startswith("POSTGRES_")})
    failures: list[str] = []

    for key in REQUIRED_SECRETS:
        value = values.get(key, "")
        if len(value) < 20:
            failures.append(f"{key} is missing or too short")
        if any(fragment in value.lower() for fragment in PLACEHOLDER_FRAGMENTS):
            failures.append(f"{key} still contains a placeholder value")

    public_url = args.url or values.get("PDFHUB_PUBLIC_BASE_URL", "")
    parsed = urlparse(public_url)
    if not args.allow_insecure:
        if parsed.scheme != "https" or not parsed.hostname:
            failures.append("production public URL must use https://")
        if values.get("PDFHUB_SESSION_COOKIE_SECURE", "false").lower() != "true":
            failures.append("PDFHUB_SESSION_COOKIE_SECURE must be true in production")
    elif parsed.scheme not in {"http", "https"}:
        failures.append("public URL must use http:// or https://")

    management_bind = values.get("PDFHUB_MANAGEMENT_BIND_HOST", "127.0.0.1")
    if management_bind in {"0.0.0.0", "::", "*"}:
        failures.append("management services must not bind all interfaces")

    if values.get("PDFHUB_LDAP_ENABLED", "false").lower() == "true":
        ldap_url = values.get("PDFHUB_LDAP_URL", "")
        if not args.allow_insecure and not ldap_url.lower().startswith("ldaps://"):
            failures.append("production LDAP must use ldaps://")

    if values.get("PDFHUB_STORAGE_BACKEND", "local").lower() == "s3":
        endpoint = values.get("PDFHUB_S3_ENDPOINT_URL", "")
        if not endpoint:
            failures.append("self-hosted S3 endpoint must be explicit")

    if failures:
        for item in failures:
            print(f"FAIL: {item}")
        print(f"production environment: FAIL ({len(failures)} problem(s))")
        return 1

    print(f"production environment: PASS ({public_url})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
