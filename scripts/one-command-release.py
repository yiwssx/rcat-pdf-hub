#!/usr/bin/env python3
"""One-command RCAT production release: preflight, verified backup, guarded deploy.

Automated isolated DR is a separate optional hardening workstream. Production
rollout still requires exact-main CI, institutional OIDC policy, live backup
integrity, explicit SHA, safe migration, and post-deploy health checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = "yiwssx/rcat-pdf-hub"


def blocked(message: str) -> None:
    raise SystemExit("one-command-release: BLOCKED — " + message)


def call(*argv: str, env: dict[str, str] | None = None,
         capture: bool = True, input_text: str | None = None,
         timeout: int | None = 60) -> str:
    result = subprocess.run(
        list(argv), cwd=ROOT, env=env, input=input_text,
        text=True, capture_output=capture, check=False, timeout=timeout,
    )
    if result.returncode:
        blocked("required step failed: " + " ".join(argv[:3]))
    return (result.stdout or "").strip()


def gh_json(endpoint: str) -> dict:
    return json.loads(call("gh", "api", endpoint, timeout=30))


def live_compose_mode() -> str:
    ids = call(
        "docker", "ps", "-q",
        "--filter", "label=com.docker.compose.service=api",
    ).split()
    if not ids:
        blocked("no running Compose API; cannot back up the current live data")
    containers = json.loads(call("docker", "inspect", *ids))
    modes = []
    for container in containers:
        labels = container.get("Config", {}).get("Labels") or {}
        working_dir = labels.get("com.docker.compose.project.working_dir", "")
        if not working_dir or Path(working_dir).resolve() != ROOT:
            continue
        files = {
            Path(name.strip()).name
            for name in labels.get("com.docker.compose.project.config_files", "").split(",")
            if name.strip()
        }
        if {"docker-compose.yml", "docker-compose.prod.yml"}.issubset(files):
            modes.append("prod-nas" if "docker-compose.nas.yml" in files else "prod")
    if len(modes) != 1:
        blocked("running production API Compose project is not uniquely verifiable")
    return modes[0]


def backup_root() -> Path:
    value = ""
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, data = raw.split("=", 1)
        if key.strip() == "PDFHUB_BACKUP_ROOT":
            value = data.strip().strip('"').strip("'")
    path = Path(value).expanduser() if value else ROOT / "backups"
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if path == Path("/"):
        blocked("unsafe configured backup directory")
    return path


def main() -> None:
    os.chdir(ROOT)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        blocked("must run from authorized Ubuntu production host, not GitHub Actions")
    if not (ROOT / ".env").is_file():
        blocked("production .env is absent; no settings will be generated or changed")
    for cmd in ("git", "gh", "docker", "bash", "python3", "curl"):
        if shutil.which(cmd) is None:
            blocked("missing required Ubuntu command: " + cmd)
    call("docker", "compose", "version")
    call("gh", "auth", "status")
    # Preserve only the audited live Caddyfile customization, without
    # changing its current Docker bind-mount source or running containers.
    # Every other tracked edit is rejected by the strict one-file verifier.
    call("python3", "scripts/migrate-site-caddy.py", timeout=60)
    call("python3", "scripts/migrate-site-caddy.py", "--check", timeout=60)
    if call("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner") != REPO:
        blocked("GitHub repository identity does not match")
    sha = call("git", "rev-parse", "HEAD")
    remote = call("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    if sha != remote:
        blocked("current working tree does not equal protected origin/main")
    mode = live_compose_mode()
    print(f"one-command-release: production Compose={mode}, target SHA={sha[:12]}", flush=True)

    # Read-only trust gates BEFORE creating a backup.
    call("bash", "scripts/verify-ci-evidence.sh", timeout=90)
    overlays = ["-f", "docker-compose.yml", "-f", "docker-compose.prod.yml"]
    if mode == "prod-nas":
        overlays += ["-f", "docker-compose.nas.yml"]
    config = call("docker", "compose", *overlays, "config", "--format", "json")
    call("python3", "scripts/release1-host-preflight.py", input_text=config)

    root = backup_root()
    snapshot = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if snapshot.exists():
        blocked("fresh backup snapshot name already exists")
    backup_env = dict(os.environ)
    backup_env.update(
        PDFHUB_BACKUP_ROOT=str(root),
        PDFHUB_BACKUP_RETENTION_DAYS="0",  # Never prune earlier recovery points.
        PDFHUB_COMPOSE_MODE=mode,
    )
    print("one-command-release: creating backup of current running version", flush=True)
    call("bash", "scripts/backup.sh", str(snapshot), env=backup_env, timeout=3600)
    call("bash", "scripts/verify-backup.sh", str(snapshot), timeout=3600)

    # A verified live backup is sufficient for the standard release gate.
    # Isolated automated DR remains available separately, but is NOT
    # a prerequisite to update existing production containers.
    print("one-command-release: backup verified; private DR automation deferred", flush=True)

    deploy_env = dict(os.environ)
    deploy_env.update(
        PDFHUB_COMPOSE_MODE=mode,
        BACKUP=str(snapshot),
        RCAT_DEPLOY_SHA=sha,
        RCAT_DEPLOY_CONFIRM="YES",
    )
    print("one-command-release: starting standard backup-gated production cutover", flush=True)
    call("bash", "scripts/production-cutover.sh", "deploy", env=deploy_env,
         capture=False, timeout=7200)
    print(
        f"one-command-release: DEPLOYED SHA={sha} "
        f"backup={snapshot.name} healthz/readyz=PASS (automated DR deferred)",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        blocked(f"release stopped without bypassing safety gates ({type(exc).__name__})")
