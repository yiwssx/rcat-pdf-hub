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
# Pick an unused local port, or validate the operator's explicit choice.
# The drill-specific Compose overlay below binds Caddy on loopback only.
port="$(python3 scripts/select-drill-port.py)"

# A DR drill deliberately restores into isolated named volumes, regardless of whether
# the production backup came from default-volume or NAS compose mode.
export PDFHUB_COMPOSE_PROJECT="${project}"
export PDFHUB_COMPOSE_MODE=default
export COMPOSE_FILE="${ROOT}/docker-compose.yml:${ROOT}/docker-compose.drill.yml"
export PDFHUB_RESTORE_ALLOW_COMPOSE_MODE_CHANGE=true
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
  profiles+=(--profile s3)
fi

dc() { docker compose -p "${project}" "${profiles[@]}" "$@"; }

# Compose loads the operator's .env itself. Check the *rendered* API policy,
# rather than sourcing .env or guessing from the shell environment.
clamav_enabled="$(dc config --format json | python3 -c 'import json,sys; env=json.load(sys.stdin)["services"]["api"]["environment"]; print(str(env.get("PDFHUB_CLAMAV_ENABLED", "false")).lower())')"
case "${clamav_enabled}" in
  true)
    # A restored data set must not talk to a Production antivirus endpoint.
    export PDFHUB_CLAMAV_HOST=clamav
    export PDFHUB_CLAMAV_PORT=3310
    profiles+=(--profile security)
    ;;
  false) ;;
  *) echo "dr-drill: invalid PDFHUB_CLAMAV_ENABLED=${clamav_enabled}" >&2; exit 2 ;;
esac

cleanup() {
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${PDFHUB_NAS_PATH}" >/dev/null 2>&1 || true
}
report_failure() {
  local code="$?"
  trap - ERR
  printf 'dr-drill: FAIL (exit %s); isolated service diagnostics follow\n' "${code}" >&2
  dc ps --all >&2 || true
  local endpoint body status
  for endpoint in healthz readyz; do
    body="$(mktemp)"
    status="$(curl -sS --max-time 5 -o "${body}" -w '%{http_code}' "http://127.0.0.1:${port}/${endpoint}" 2>/dev/null || true)"
    printf 'dr-drill: %s HTTP %s\n' "${endpoint}" "${status:-unavailable}" >&2
    if [ "${endpoint}" = readyz ] && [ "${status}" = 503 ]; then
      head -c 1200 "${body}" >&2 || true
      printf '\n' >&2
    fi
    rm -f "${body}"
  done
  dc logs --tail 25 --no-color api caddy clamav >&2 || true
}
trap report_failure ERR
trap cleanup EXIT

printf 'dr-drill: starting isolated dependencies %s\n' "${project}"
dependencies=(postgres valkey gotenberg)
if [ "${storage_backend}" = "s3" ]; then dependencies+=(seaweedfs); fi
if [ "${clamav_enabled}" = true ]; then dependencies+=(clamav); fi
dc up -d --wait --wait-timeout 120 "${dependencies[@]}" >/dev/null

# restore.sh intentionally uses --no-build when starting recovered services.
# A fresh isolated Compose project has no worker/web images yet, so prepare them
# here without changing restore.sh behavior or any Production containers.
printf 'dr-drill: building isolated application images\n'
dc build api worker-interactive worker worker-heavy cleanup webhook web

if [ "${clamav_enabled}" = true ]; then
  printf 'dr-drill: waiting for isolated ClamAV readiness\n'
  # Fresh ClamAV signature downloads can take longer than the restore health
  # window. Wait for a real clamd PONG before restoring, without bypassing AV.
  dc run --rm --no-deps -T api python - <<'PY'
import socket
import sys
import time

for _ in range(120):
    try:
        with socket.create_connection(("clamav", 3310), timeout=3) as conn:
            conn.settimeout(3)
            conn.sendall(b"zPING\0")
            response = conn.recv(64).rstrip(b"\0\r\n")
        if response.upper() == b"PONG":
            print("dr-drill: isolated ClamAV PONG")
            break
    except (OSError, TimeoutError):
        pass
    time.sleep(3)
else:
    sys.exit("dr-drill: isolated ClamAV did not become ready")
PY
fi

PDFHUB_RESTORE_CONFIRM=YES bash scripts/restore.sh "${BACKUP_DIR}"

curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null
curl -fsS "http://127.0.0.1:${port}/readyz" >/dev/null
python3 scripts/load-smoke.py --url "http://127.0.0.1:${port}" --requests 30 --concurrency 5 --max-error-rate 0 --max-p95-ms 2000

printf 'dr-drill: PASS %s restored and validated in isolated project\n' "${project}"
