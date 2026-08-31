#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

BACKUP_DIR="${1:-${BACKUP:-}}"
if [ -z "${BACKUP_DIR}" ]; then
  echo "Usage: $0 <backup-directory>" >&2
  exit 2
fi
bash scripts/verify-backup.sh "${BACKUP_DIR}"

storage_backend="$(sed -n 's/^PDFHUB_STORAGE_BACKEND=//p' "${BACKUP_DIR}/manifest.env")"
project="pdfhub-drill-$(date -u +%Y%m%d%H%M%S)-$$"
port="${PDFHUB_DRILL_HTTP_PORT:-18081}"

export PDFHUB_COMPOSE_PROJECT="${project}"
export PDFHUB_HTTP_PORT="${port}"
export PDFHUB_ALLOWED_ORIGINS="http://localhost:${port}"
export PDFHUB_PUBLIC_BASE_URL="http://localhost:${port}"
export PDFHUB_STORAGE_BACKEND="${storage_backend}"
export POSTGRES_DB=pdfhub
export POSTGRES_USER=pdfhub
export POSTGRES_PASSWORD=drill-postgres-password-change-me
export PDFHUB_API_KEY_PEPPER=drill-api-key-pepper-change-me
export PDFHUB_ADMIN_API_KEY=pdfh_drill_admin_key_change_me_1234567890
export PDFHUB_WEBHOOK_MASTER_SECRET=drill-webhook-master-secret-change-me
export PDFHUB_AUTH_TOKEN_SECRET=drill-auth-token-secret-change-me-0123456789abcdef
export PDFHUB_DOWNLOAD_SIGNING_SECRET=drill-download-signing-secret-change-me-0123456789abcdef
export PDFHUB_NAS_PATH="/tmp/${project}-nas"

profiles=()
if [ "${storage_backend}" = "s3" ]; then
  export PDFHUB_S3_ENDPOINT_URL=http://seaweedfs:8333
  export PDFHUB_S3_REGION=us-east-1
  export PDFHUB_S3_BUCKET=pdfhub-drill
  export PDFHUB_S3_ACCESS_KEY=pdfhub-drill
  export PDFHUB_S3_SECRET_KEY=pdfhub-drill-secret
  export PDFHUB_S3_AUTO_CREATE_BUCKET=true
  profiles=(--profile s3)
fi

dc() { docker compose -p "${project}" "${profiles[@]}" "$@"; }
cleanup() {
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${PDFHUB_NAS_PATH}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf 'dr-drill: starting isolated dependencies %s\n' "${project}"
if [ "${storage_backend}" = "s3" ]; then
  dc up -d seaweedfs postgres valkey gotenberg >/dev/null
else
  dc up -d postgres valkey gotenberg >/dev/null
fi

PDFHUB_RESTORE_CONFIRM=YES bash scripts/restore.sh "${BACKUP_DIR}"

curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null
curl -fsS "http://127.0.0.1:${port}/readyz" >/dev/null
python3 scripts/load-smoke.py --url "http://127.0.0.1:${port}" --requests 30 --concurrency 5 --max-error-rate 0 --max-p95-ms 2000

printf 'dr-drill: PASS %s restored and validated in isolated project\n' "${project}"
