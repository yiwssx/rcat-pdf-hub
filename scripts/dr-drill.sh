#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

BACKUP_DIR="${1:-${BACKUP:-}}"
if [ -z "${BACKUP_DIR}" ]; then
  echo "Usage: $0 <backup-directory>" >&2
  exit 2
fi
PDFHUB_BACKUP_REQUIRE_QUIESCED=true bash scripts/verify-backup.sh "${BACKUP_DIR}"

storage_backend="$(sed -n 's/^PDFHUB_STORAGE_BACKEND=//p' "${BACKUP_DIR}/manifest.env")"
project="pdfhub-drill-$(date -u +%Y%m%d%H%M%S)-$$"
port="${PDFHUB_DRILL_HTTP_PORT:-18081}"

# A DR drill deliberately restores into isolated named volumes, regardless of whether
# the production backup came from default-volume or NAS compose mode.
export PDFHUB_COMPOSE_PROJECT="${project}"
export PDFHUB_COMPOSE_MODE=default
export PDFHUB_RESTORE_ALLOW_COMPOSE_MODE_CHANGE=true
export PDFHUB_BACKUP_REQUIRE_QUIESCED=true
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
  dc up -d --wait --wait-timeout 120 seaweedfs postgres valkey gotenberg >/dev/null
else
  dc up -d --wait --wait-timeout 120 postgres valkey gotenberg >/dev/null
fi

PDFHUB_RESTORE_CONFIRM=YES bash scripts/restore.sh "${BACKUP_DIR}"

base="http://127.0.0.1:${port}"
curl -fsS "${base}/healthz" >/dev/null
curl -fsS "${base}/readyz" >/dev/null

printf 'dr-drill: exercising real upload -> RQ worker -> PDF -> preview flow\n'
tmp="$(mktemp -d)"
python3 - "${tmp}/pixel.png" <<'PY'
import base64, pathlib, sys
# 1x1 opaque PNG
raw = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
pathlib.Path(sys.argv[1]).write_bytes(raw)
PY
upload_json="$(curl -fsS -H "X-API-Key: ${PDFHUB_ADMIN_API_KEY}" -F "file=@${tmp}/pixel.png;type=image/png" "${base}/api/v1/files")"
file_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${upload_json}")"
job_json="$(curl -fsS -H "X-API-Key: ${PDFHUB_ADMIN_API_KEY}" -H 'Content-Type: application/json' -d "{\"file_ids\":[\"${file_id}\"]}" "${base}/api/v1/pdf/images-to-pdf")"
job_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${job_json}")"
output_id=""
for _ in $(seq 1 120); do
  state_json="$(curl -fsS -H "X-API-Key: ${PDFHUB_ADMIN_API_KEY}" "${base}/api/v1/jobs/${job_id}")"
  status="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"${state_json}")"
  if [ "${status}" = "completed" ]; then
    output_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["output_file_id"])' <<<"${state_json}")"
    break
  fi
  if [ "${status}" = "failed" ]; then
    echo "DR transaction job failed: ${state_json}" >&2
    exit 1
  fi
  sleep 1
done
[ -n "${output_id}" ] || { echo "DR transaction timed out waiting for worker" >&2; exit 1; }
curl -fsS -H "X-API-Key: ${PDFHUB_ADMIN_API_KEY}" "${base}/api/v1/files/${output_id}/download" -o "${tmp}/output.pdf"
curl -fsS -H "X-API-Key: ${PDFHUB_ADMIN_API_KEY}" "${base}/api/v1/files/${output_id}/preview?page=1&width=320" -o "${tmp}/preview.png"
python3 - "${tmp}/output.pdf" "${tmp}/preview.png" <<'PY'
from pathlib import Path
import sys
pdf, png = map(Path, sys.argv[1:])
if not pdf.read_bytes().startswith(b"%PDF"):
    raise SystemExit("downloaded DR output is not a PDF")
if not png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
    raise SystemExit("DR preview is not a PNG")
PY
rm -rf "${tmp}"

python3 scripts/load-smoke.py --url "${base}" --requests 30 --concurrency 5 --max-error-rate 0 --max-p95-ms 2000

printf 'dr-drill: PASS %s restore integrity and real PDF transaction validated\n' "${project}"
