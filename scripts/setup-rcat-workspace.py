#!/usr/bin/env python3
"""Configure existing RCAT PDF HUB .env for Google Workspace without replacing other secrets.

Interactive only on the operator's local terminal. Nothing is uploaded or logged.
The program does not touch Docker, DNS, Google Cloud, or a running service.
"""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)$")
GOOGLE_CLIENT = re.compile(r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com\Z")

# All other existing .env values, secrets and network bindings are preserved.
POLICY = {
    "PDFHUB_RCAT_INSTITUTIONAL_ONLY": "true",
    "PDFHUB_OIDC_ENABLED": "true",
    "PDFHUB_OIDC_ISSUER": "https://accounts.google.com",
    "PDFHUB_OIDC_AUDIENCE": "",
    "PDFHUB_OIDC_DISCOVERY_URL": "",
    "PDFHUB_LDAP_ENABLED": "false",
    "PDFHUB_WEB_CONSOLE_AUTO_LOGIN": "false",
    "PDFHUB_SESSION_COOKIE_SECURE": "true",
    "PDFHUB_PUBLIC_BASE_URL": "https://pdf.rcat.ac.th",
    "PDFHUB_ALLOWED_ORIGINS": "https://pdf.rcat.ac.th",
    "PDFHUB_CLAMAV_ENABLED": "true",
    "PDFHUB_CLAMAV_FAIL_CLOSED": "true",
    "PDFHUB_FROM_PDF_TOOLS_ENABLED": "false",
}
CLIENT_ID = "PDFHUB_OIDC_CLIENT_ID"
CLIENT_SECRET = "PDFHUB_OIDC_CLIENT_SECRET"


def parse_values(source: str) -> dict[str, str]:
    """Read assignments without sourcing/executing .env or interpreting secrets."""
    values = {}
    for line in source.splitlines():
        match = ASSIGNMENT.match(line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def valid_client_id(value: str) -> bool:
    return bool(GOOGLE_CLIENT.fullmatch(unquote(value)))


def valid_secret(value: str) -> bool:
    value = unquote(value)
    return bool(
        value and len(value) <= 4096 and "\n" not in value and "\r" not in value
        and not value.lower().startswith(("replace-", "your_", "example", "<"))
        and not value.startswith("ใส่")
    )


def quote_dotenv(value: str) -> str:
    if "\n" in value or "\r" in value or "\0" in value:
        raise ValueError("Google credentials may not contain line breaks")
    # Docker Compose treats single-quoted .env values literally, including $.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def merge_settings(source: str, assignments: dict[str, str]) -> str:
    """Replace only targeted assignments; collapse duplicate targeted keys."""
    result: list[str] = []
    seen: set[str] = set()
    for line in source.splitlines():
        match = ASSIGNMENT.match(line)
        key = match.group(1) if match else None
        if key in assignments:
            if key not in seen:
                result.append(f"{key}={assignments[key]}")
                seen.add(key)
            continue
        result.append(line)
    missing = [key for key in assignments if key not in seen]
    if missing:
        if result and result[-1].strip():
            result.append("")
        result.append("# RCAT Google Workspace — set by scripts/setup-rcat-workspace.py")
        result.extend(f"{key}={assignments[key]}" for key in missing)
    return "\n".join(result).rstrip("\n") + "\n"


def write_secure(path: Path, original: str, new_text: str) -> bool:
    """Back up existing values and atomically replace file with mode 0600."""
    if new_text == original:
        os.chmod(path, 0o600)
        return False
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(path.name + ".backup." + stamp + "." + secrets.token_hex(3))
    backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(backup_fd, "w", encoding="utf-8") as handle:
        handle.write(original)
        handle.flush()
        os.fsync(handle.fileno())
    temp_fd, temp_name = tempfile.mkstemp(prefix=".env.rcat-", dir=path.parent)
    try:
        os.fchmod(temp_fd, 0o600)
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            handle.write(new_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    print("Previous configuration backed up locally:", backup.name)
    return True


def configure(path: Path, rotate: bool = False, check_only: bool = False) -> int:
    if path.is_symlink() or not path.is_file():
        print("Missing or unsafe .env; create it from .env.example first.", file=sys.stderr)
        return 2
    source = path.read_text(encoding="utf-8")
    values = parse_values(source)

    if check_only:
        ready = all(values.get(key) == expected for key, expected in POLICY.items())
        ready = ready and valid_client_id(values.get(CLIENT_ID, ""))
        ready = ready and valid_secret(values.get(CLIENT_SECRET, ""))
        ready = ready and stat.S_IMODE(path.stat().st_mode) == 0o600
        print("RCAT Workspace configuration:", "READY" if ready else "INCOMPLETE",
              "(settings only; Google OAuth and HTTPS not tested)")
        return 0 if ready else 1

    assignments = dict(POLICY)
    if rotate or not valid_client_id(values.get(CLIENT_ID, "")):
        if not sys.stdin.isatty():
            print("An interactive terminal is required to enter Google Client ID.", file=sys.stderr)
            return 2
        client_id = input("Google OAuth Client ID: ").strip()
        if not valid_client_id(client_id):
            print("Invalid Google OAuth Web Client ID.", file=sys.stderr)
            return 2
        assignments[CLIENT_ID] = quote_dotenv(client_id)
    else:
        assignments[CLIENT_ID] = values[CLIENT_ID]

    if rotate or not valid_secret(values.get(CLIENT_SECRET, "")):
        if not sys.stdin.isatty():
            print("An interactive terminal is required to enter Google Client Secret.", file=sys.stderr)
            return 2
        client_secret = getpass.getpass("Google OAuth Client Secret (hidden): ").strip()
        if not valid_secret(client_secret):
            print("Invalid or missing Client Secret.", file=sys.stderr)
            return 2
        assignments[CLIENT_SECRET] = quote_dotenv(client_secret)
    else:
        assignments[CLIENT_SECRET] = values[CLIENT_SECRET]

    new_text = merge_settings(source, assignments)
    changed = write_secure(path, source, new_text)
    print("RCAT Workspace:", "configured" if changed else "already configured")
    print("Existing database keys, passwords, API secrets and bind ports preserved.")
    print("Next (read-only): make rcat-workspace-check && make release1-host-preflight")
    print("Do not deploy until HTTPS callback, backup, and host access are verified.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure RCAT Google Workspace OIDC in existing .env.")
    parser.add_argument("--check", action="store_true", help="Check only; no secrets printed or writes.")
    parser.add_argument("--rotate-client", action="store_true", help="Replace both OAuth client credentials.")
    args = parser.parse_args()
    raise SystemExit(configure(ENV_PATH, rotate=args.rotate_client, check_only=args.check))


if __name__ == "__main__":
    main()
