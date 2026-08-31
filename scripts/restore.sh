#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

BACKUP_DIR="${1:-${BACKUP:-}}"
PROJECT="${PDFHUB_COMPOSE_PROJECT:-}"
COMPOSE_MODE="${PDFHUB_COMPOSE_MODE:-default}"
if [ -z "${BACKUP_DIR}" ]; then
  echo "Usage: PDFHUB_RESTORE_CONFIRM=YES $0 <backup-directory>" >&2
  exit 2
fi
if [ "${PDFHUB_RESTORE_CONFIRM:-}" != "YES" ]; then
  echo "Restore is destructive. Set PDFHUB_RESTORE_CONFIRM=YES to continue." >&2
  exit 2
fi
case "${COMPOSE_MODE}" in default|nas) ;; *) echo "PDFHUB_COMPOSE_MODE must be default or nas" >&2; exit 2 ;; esac

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}
need docker
need curl

dc() {
  local args=()
  if [ "${COMPOSE_MODE}" = "nas" ]; then args+=(-f docker-compose.yml -f docker-compose.nas.yml); fi
  if [ -n "${PROJECT}" ]; then args+=(-p "${PROJECT}"); fi
  docker compose "${args[@]}" "$@"
}

bash scripts/verify-backup.sh "${BACKUP_DIR}"
storage_backend="$(sed -n 's/^PDFHUB_STORAGE_BACKEND=//p' "${BACKUP_DIR}/manifest.env")"
backup_compose_mode="$(sed -n 's/^PDFHUB_COMPOSE_MODE=//p' "${BACKUP_DIR}/manifest.env")"
export PDFHUB_STORAGE_BACKEND="${storage_backend}"

if [ -n "${backup_compose_mode}" ] && [ "${backup_compose_mode}" != "${COMPOSE_MODE}" ]; then
  echo "Restore compose mode (${COMPOSE_MODE}) differs from backup source (${backup_compose_mode})." >&2
  echo "Set PDFHUB_COMPOSE_MODE explicitly if this storage migration is intentional." >&2
  [ "${PDFHUB_RESTORE_ALLOW_COMPOSE_MODE_CHANGE:-false}" = "true" ] || exit 2
fi

# Stop request/worker surfaces while keeping database/queue infrastructure available for replacement.
dc stop caddy web worker cleanup webhook api >/dev/null 2>&1 || true

dc up -d --wait --wait-timeout 120 postgres valkey gotenberg >/dev/null
printf 'restore: replacing PostgreSQL database\n'
dc exec -T postgres sh -lc 'exec pg_restore --clean --if-exists --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <"${BACKUP_DIR}/postgres.dump"

# RQ entries are ephemeral coordination state. Flush only DB 0 so old queued jobs cannot run against restored metadata.
dc exec -T valkey valkey-cli -n 0 FLUSHDB >/dev/null

case "${storage_backend}" in
  local)
    printf 'restore: replacing /data contents (%s compose mode)\n' "${COMPOSE_MODE}"
    dc run --rm --no-deps -T api python -c '
import shutil, sys, tarfile
from pathlib import Path, PurePosixPath
root = Path("/data").resolve()
root.mkdir(parents=True, exist_ok=True)
for child in root.iterdir():
    if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
    else: child.unlink(missing_ok=True)
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
    for member in archive:
        rel = PurePosixPath(member.name)
        if rel.is_absolute() or ".." in rel.parts:
            raise RuntimeError(f"Unsafe archive member: {member.name!r}")
        archive.extract(member, root, filter="data")
' <"${BACKUP_DIR}/pdf-data.tar.gz"
    ;;
  s3)
    printf 'restore: replacing self-hosted S3 bucket objects\n'
    dc run --rm --no-deps -T api python -c '
import sys, tarfile, tempfile
from pathlib import PurePosixPath
from app.config import get_settings
from app.storage import s3_client
settings = get_settings(); client = s3_client(); bucket = settings.s3_bucket
keys = []
paginator = client.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket):
    keys.extend(item["Key"] for item in page.get("Contents", []))
for offset in range(0, len(keys), 1000):
    batch = keys[offset:offset + 1000]
    if batch:
        client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True})
with tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz") as archive:
    for member in archive:
        rel = PurePosixPath(member.name)
        if rel.is_absolute() or ".." in rel.parts or not member.isfile():
            if member.isdir(): continue
            raise RuntimeError(f"Unsafe S3 archive member: {member.name!r}")
        extracted = archive.extractfile(member)
        if extracted is None: raise RuntimeError(f"Cannot read {member.name!r}")
        with tempfile.NamedTemporaryFile() as temp:
            while True:
                chunk = extracted.read(1024 * 1024)
                if not chunk: break
                temp.write(chunk)
            temp.flush(); temp.seek(0)
            client.upload_fileobj(temp, bucket, member.name)
' <"${BACKUP_DIR}/s3-objects.tar.gz"
    ;;
esac

# Adopt/upgrade the restored schema to the current release before accepting traffic.
dc run --rm --no-deps -T api python -c 'from app.migrate import run_migrations; run_migrations()'

dc up -d --no-build --wait --wait-timeout 180 api worker cleanup webhook web caddy >/dev/null

if [ "${PDFHUB_RESTORE_SKIP_HEALTHCHECK:-false}" != "true" ]; then
  port="${PDFHUB_HTTP_PORT:-8080}"
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:${port}/readyz" >/dev/null 2>&1; then
      printf 'restore: PASS and service ready\n'
      exit 0
    fi
    sleep 2
  done
  echo "Restore completed but readiness check timed out" >&2
  exit 1
fi

printf 'restore: PASS (health check skipped by operator)\n'
