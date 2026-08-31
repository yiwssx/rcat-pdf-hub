#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${PDFHUB_RELEASE_MODE:-production}"
BACKUP_DIR="${BACKUP:-}"
TARGET_URL="${URL:-}"
ENV_FILE="${ENV_FILE:-.env}"

case "${MODE}" in
  code|production) ;;
  *) echo "PDFHUB_RELEASE_MODE must be code or production" >&2; exit 2 ;;
esac

printf 'release-readiness: running full repository validation\n'
make validate-free

if [ "${MODE}" = "code" ]; then
  printf 'release-readiness: PASS (code gate only; not production certification)\n'
  exit 0
fi

[ -n "${BACKUP_DIR}" ] || { echo "Production readiness requires BACKUP=/path/to/verified-backup" >&2; exit 2; }
[ -n "${TARGET_URL}" ] || { echo "Production readiness requires URL=https://intended-pdf-hub-endpoint" >&2; exit 2; }

printf 'release-readiness: checking production environment safety\n'
production_args=(--env-file "${ENV_FILE}" --url "${TARGET_URL}")
if [ "${PDFHUB_ALLOW_INSECURE_PRODUCTION:-false}" = "true" ]; then
  production_args+=(--allow-insecure)
fi
python3 scripts/check-production-env.py "${production_args[@]}"

printf 'release-readiness: checking local CI enforcement\n'
make local-ci-doctor

printf 'release-readiness: verifying quiesced backup\n'
PDFHUB_BACKUP_REQUIRE_QUIESCED=true bash scripts/verify-backup.sh "${BACKUP_DIR}"

if [ "${PDFHUB_RELEASE_SKIP_DR:-false}" != "true" ]; then
  printf 'release-readiness: running isolated disaster-recovery drill\n'
  PDFHUB_BACKUP_REQUIRE_QUIESCED=true bash scripts/dr-drill.sh "${BACKUP_DIR}"
else
  printf 'release-readiness: WARNING DR drill explicitly skipped by operator\n' >&2
fi

printf 'release-readiness: running readiness load/latency smoke\n'
python3 scripts/load-smoke.py \
  --url "${TARGET_URL}" \
  --path "${LOAD_PATH:-/readyz}" \
  --requests "${REQUESTS:-100}" \
  --concurrency "${CONCURRENCY:-10}" \
  --max-error-rate "${MAX_ERROR_RATE:-0.01}" \
  --max-p95-ms "${MAX_P95_MS:-1500}"

api_key="${API_KEY:-}"
if [ -z "${api_key}" ] && [ -f "${ENV_FILE}" ]; then
  api_key="$(sed -n 's/^PDFHUB_ADMIN_API_KEY=//p' "${ENV_FILE}" | tail -n1)"
fi
[ -n "${api_key}" ] || { echo "Production readiness requires API_KEY or PDFHUB_ADMIN_API_KEY in ENV_FILE for real PDF workload validation" >&2; exit 2; }

printf 'release-readiness: running real PDF workload gate\n'
python3 scripts/pdf-workload-smoke.py \
  --url "${TARGET_URL}" \
  --api-key "${api_key}" \
  --requests "${PDF_REQUESTS:-8}" \
  --concurrency "${PDF_CONCURRENCY:-2}" \
  --max-error-rate "${PDF_MAX_ERROR_RATE:-0}" \
  --max-p95-ms "${PDF_MAX_P95_MS:-30000}"

printf 'release-readiness: PASS (production gate)\n'
