#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${PDFHUB_RELEASE_MODE:-production}"
BACKUP_DIR="${BACKUP:-}"
TARGET_URL="${URL:-}"

case "${MODE}" in
  code|production) ;;
  *) echo "PDFHUB_RELEASE_MODE must be code or production" >&2; exit 2 ;;
esac

printf 'release-readiness: running full repository validation\n'
make validate-free

if [ "${MODE}" = "code" ]; then
  printf 'release-readiness: PASS (code gate)\n'
  exit 0
fi

printf 'release-readiness: checking local CI enforcement\n'
make local-ci-doctor

if [ -z "${BACKUP_DIR}" ]; then
  echo "Production readiness requires BACKUP=/path/to/verified-backup" >&2
  exit 2
fi
if [ -z "${TARGET_URL}" ]; then
  echo "Production readiness requires URL=https://intended-pdf-hub-endpoint" >&2
  exit 2
fi

printf 'release-readiness: verifying backup\n'
bash scripts/verify-backup.sh "${BACKUP_DIR}"

if [ "${PDFHUB_RELEASE_SKIP_DR:-false}" != "true" ]; then
  printf 'release-readiness: running isolated disaster-recovery drill\n'
  bash scripts/dr-drill.sh "${BACKUP_DIR}"
else
  printf 'release-readiness: DR drill explicitly skipped by operator\n'
fi

printf 'release-readiness: running deployment load/latency smoke\n'
python3 scripts/load-smoke.py \
  --url "${TARGET_URL}" \
  --path "${LOAD_PATH:-/healthz}" \
  --requests "${REQUESTS:-100}" \
  --concurrency "${CONCURRENCY:-10}" \
  --max-error-rate "${MAX_ERROR_RATE:-0.01}" \
  --max-p95-ms "${MAX_P95_MS:-1500}"

printf 'release-readiness: PASS (production gate)\n'
