#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

BACKUP_ROOT="${PDFHUB_BACKUP_ROOT:-${ROOT}/backups}"
RETENTION_DAYS="${PDFHUB_BACKUP_RETENTION_DAYS:-14}"
PROJECT="${PDFHUB_COMPOSE_PROJECT:-}"
COMPOSE_MODE="${PDFHUB_COMPOSE_MODE:-default}"
QUIESCE="${PDFHUB_BACKUP_QUIESCE:-true}"
DRAIN_TIMEOUT_SECONDS="${PDFHUB_BACKUP_DRAIN_TIMEOUT_SECONDS:-1800}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${1:-${BACKUP_ROOT}/${STAMP}}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

need docker
need sha256sum
need git

docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin is required" >&2; exit 1; }

case "${COMPOSE_MODE}" in default|nas) ;; *) echo "PDFHUB_COMPOSE_MODE must be default or nas" >&2; exit 2 ;; esac
case "${QUIESCE}" in true|false) ;; *) echo "PDFHUB_BACKUP_QUIESCE must be true or false" >&2; exit 2 ;; esac
[[ "${DRAIN_TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] || { echo "PDFHUB_BACKUP_DRAIN_TIMEOUT_SECONDS must be an integer" >&2; exit 2; }

dc() {
  local args=()
  if [ "${COMPOSE_MODE}" = "nas" ]; then args+=(-f docker-compose.yml -f docker-compose.nas.yml); fi
  if [ -n "${PROJECT}" ]; then args+=(-p "${PROJECT}"); fi
  docker compose "${args[@]}" "$@"
}

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

if ! dc exec -T postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null; then
  echo "PostgreSQL must be running before backup" >&2
  exit 1
fi
if ! dc exec -T api python -c 'from app.config import get_settings; print(get_settings().storage_backend)' >/dev/null; then
  echo "PDF Hub API must be running before backup" >&2
  exit 1
fi

storage_backend="$(dc exec -T api python -c 'from app.config import get_settings; print(get_settings().storage_backend)' | tr -d '\r')"
release="$(dc exec -T api python -c 'from app.main import app; print(app.version)' | tr -d '\r')"
git_sha="$(git rev-parse HEAD 2>/dev/null || printf 'unknown')"
consistency="live"

mapfile -t running_before < <(dc ps --services --filter status=running)
was_running() {
  local candidate="$1" item
  for item in "${running_before[@]}"; do
    [ "${item}" = "${candidate}" ] && return 0
  done
  return 1
}

resume_services=()
resume_if_needed() {
  local status=$?
  if [ "${#resume_services[@]}" -gt 0 ]; then
    printf 'backup: resuming services: %s\n' "${resume_services[*]}"
    dc up -d --no-build "${resume_services[@]}" >/dev/null 2>&1 || {
      echo "WARNING: backup could not fully resume previously running services" >&2
      status=1
    }
  fi
  return "${status}"
}
trap resume_if_needed EXIT

if [ "${QUIESCE}" = "true" ]; then
  for service in caddy web api worker cleanup webhook; do
    if was_running "${service}"; then resume_services+=("${service}"); fi
  done

  # Close public ingress first. API has no host port in the baseline Compose,
  # so this prevents new external mutations while existing RQ work drains.
  dc stop -t 30 caddy web >/dev/null 2>&1 || true

  printf 'backup: draining queued/running jobs before snapshot\n'
  deadline=$((SECONDS + DRAIN_TIMEOUT_SECONDS))
  while true; do
    active_jobs="$(dc exec -T api python - <<'PY'
from sqlalchemy import func, select
from app.db import SessionLocal
from app.models import JobRecord
with SessionLocal() as db:
    value = db.scalar(select(func.count()).select_from(JobRecord).where(JobRecord.status.in_(("queued", "running")))) or 0
    print(int(value))
PY
)"
    active_jobs="$(tr -d '\r\n ' <<<"${active_jobs}")"
    [ "${active_jobs}" = "0" ] && break
    if [ "${SECONDS}" -ge "${deadline}" ]; then
      echo "Backup drain timed out with ${active_jobs} queued/running job(s); refusing a non-quiesced snapshot" >&2
      exit 1
    fi
    sleep 2
  done

  # Freeze every component that can mutate PostgreSQL or binary storage before
  # either half of the snapshot is captured.
  dc stop -t 60 worker cleanup webhook api >/dev/null 2>&1 || true
  consistency="quiesced"
fi

printf 'backup: dumping PostgreSQL (%s snapshot)\n' "${consistency}"
dc exec -T postgres sh -lc 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' >"${BACKUP_DIR}/postgres.dump"

case "${storage_backend}" in
  local)
    printf 'backup: archiving local/NAS data mounted at /data\n'
    dc run --rm --no-deps -T api python -c '
import sys, tarfile
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add("/data", arcname=".", recursive=True)
' >"${BACKUP_DIR}/pdf-data.tar.gz"
    ;;
  s3)
    printf 'backup: exporting self-hosted S3 objects\n'
    dc run --rm --no-deps -T api python -c '
import os, sys, tarfile, tempfile
from app.config import get_settings
from app.storage import s3_client
settings = get_settings()
client = s3_client()
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.s3_bucket):
        for item in page.get("Contents", []):
            key = item["Key"]
            if not key or key.startswith("/") or ".." in key.split("/"):
                raise RuntimeError(f"Unsafe S3 key in backup: {key!r}")
            with tempfile.NamedTemporaryFile() as temp:
                client.download_fileobj(settings.s3_bucket, key, temp)
                temp.flush(); temp.seek(0)
                info = tarfile.TarInfo(name=key)
                info.size = os.fstat(temp.fileno()).st_size
                info.mtime = 0
                archive.addfile(info, temp)
' >"${BACKUP_DIR}/s3-objects.tar.gz"
    ;;
  *) echo "Unsupported storage backend: ${storage_backend}" >&2; exit 1 ;;
esac

cat >"${BACKUP_DIR}/manifest.env" <<EOF
PDFHUB_BACKUP_FORMAT=2
PDFHUB_BACKUP_CREATED_AT=${STAMP}
PDFHUB_RELEASE=${release}
PDFHUB_GIT_SHA=${git_sha}
PDFHUB_STORAGE_BACKEND=${storage_backend}
PDFHUB_COMPOSE_MODE=${COMPOSE_MODE}
PDFHUB_BACKUP_CONSISTENCY=${consistency}
EOF

(
  cd "${BACKUP_DIR}"
  sha256sum manifest.env postgres.dump *.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)

if [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] && [ "${RETENTION_DAYS}" -gt 0 ] && [ "${BACKUP_DIR}" = "${BACKUP_ROOT}/"* ]; then
  find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf -- {} +
fi

printf 'backup: PASS %s consistency=%s\n' "${BACKUP_DIR}" "${consistency}"
