#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

BACKUP_ROOT="${PDFHUB_BACKUP_ROOT:-${ROOT}/backups}"
RETENTION_DAYS="${PDFHUB_BACKUP_RETENTION_DAYS:-14}"
PROJECT="${PDFHUB_COMPOSE_PROJECT:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${1:-${BACKUP_ROOT}/${STAMP}}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

need docker
need sha256sum
need git

docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin is required" >&2; exit 1; }

dc() {
  if [ -n "${PROJECT}" ]; then
    docker compose -p "${PROJECT}" "$@"
  else
    docker compose "$@"
  fi
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

printf 'backup: dumping PostgreSQL\n'
dc exec -T postgres sh -lc 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' >"${BACKUP_DIR}/postgres.dump"

case "${storage_backend}" in
  local)
    printf 'backup: archiving local/NAS data mounted at /data\n'
    dc exec -T api python -c '
import sys, tarfile
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add("/data", arcname=".", recursive=True)
' >"${BACKUP_DIR}/pdf-data.tar.gz"
    ;;
  s3)
    printf 'backup: exporting self-hosted S3 objects\n'
    dc exec -T api python -c '
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
  *)
    echo "Unsupported storage backend: ${storage_backend}" >&2
    exit 1
    ;;
esac

cat >"${BACKUP_DIR}/manifest.env" <<EOF
PDFHUB_BACKUP_FORMAT=1
PDFHUB_BACKUP_CREATED_AT=${STAMP}
PDFHUB_RELEASE=${release}
PDFHUB_GIT_SHA=${git_sha}
PDFHUB_STORAGE_BACKEND=${storage_backend}
EOF

(
  cd "${BACKUP_DIR}"
  sha256sum manifest.env postgres.dump *.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)

if [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] && [ "${RETENTION_DAYS}" -gt 0 ] && [ "${BACKUP_DIR}" = "${BACKUP_ROOT}/"* ]; then
  find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf -- {} +
fi

printf 'backup: PASS %s\n' "${BACKUP_DIR}"
