#!/usr/bin/env python3
"""One-command RCAT production release: live backup -> private DR -> gated deploy.

All values are discovered, never typed by the operator. Refuses deployment
unless the existing protected-main, institutional OIDC and isolated DR gates
are genuinely ready. Does not install a private runner or modify production
settings to manufacture a PASS result.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = "yiwssx/rcat-pdf-hub"
WORKFLOW = "isolated-dr.yml"


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
    if call("git", "status", "--porcelain", "--untracked-files=no"):
        blocked("tracked local modifications detected; no deployment attempted")
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

    variables = gh_json(f"repos/{REPO}/actions/variables/RCAT_DR_RUNNER_READY")
    if variables.get("value") != "true":
        blocked("RCAT_DR_RUNNER_READY is not true; isolated runner not authorized")
    runners = gh_json(f"repos/{REPO}/actions/runners")
    approved = [
        r for r in runners.get("runners", [])
        if r.get("status") == "online"
        and any(x.get("name") == "rcat-dr-isolated" for x in r.get("labels", []))
    ]
    if not approved:
        blocked("no online approved rcat-dr-isolated self-hosted runner")

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

    url = f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&branch=main&per_page=30"
    previous = max((int(run["id"]) for run in gh_json(url).get("workflow_runs", [])), default=0)
    print("one-command-release: requesting protected-main private isolated DR", flush=True)
    call("gh", "workflow", "run", WORKFLOW, "--repo", REPO, "--ref", "main")
    run_id: int | None = None
    for _ in range(30):
        candidates = [
            int(run["id"])
            for run in gh_json(url).get("workflow_runs", [])
            if int(run.get("id", 0)) > previous and run.get("head_sha") == sha
        ]
        if candidates:
            run_id = min(candidates)
            break
        time.sleep(3)
    if run_id is None:
        blocked("could not find dispatched DR run for exact main SHA")
    print(f"one-command-release: DR run {run_id} started", flush=True)
    # Run may be queued or fail due to inaccessible read-only snapshot. That
    # MUST block deploy; never convert a skipped/failed run to PASS.
    subprocess.run(
        ["gh", "run", "watch", str(run_id), "--repo", REPO, "--exit-status"],
        cwd=ROOT, check=True, timeout=6300,
    )

    # Existing cutover re-verifies the immutable main SHA, GitHub run
    # provenance, matching SHA256SUMS digest and 72-hour freshness BEFORE
    # performing production supply-chain scans or changing running services.
    deploy_env = dict(os.environ)
    deploy_env.update(
        PDFHUB_COMPOSE_MODE=mode,
        BACKUP=str(snapshot),
        DR_RUN_ID=str(run_id),
        RCAT_DEPLOY_SHA=sha,
        RCAT_DEPLOY_CONFIRM="YES",
    )
    print("one-command-release: verified DR finished; starting guarded production cutover", flush=True)
    call("bash", "scripts/production-cutover.sh", "deploy", env=deploy_env,
         capture=False, timeout=7200)
    print(
        f"one-command-release: DEPLOYED SHA={sha} "
        f"backup={snapshot.name} DR_RUN_ID={run_id} healthz/readyz=PASS",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        blocked(f"release stopped without bypassing safety gates ({type(exc).__name__})")
