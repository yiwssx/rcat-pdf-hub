#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin is required" >&2; exit 1; }

# Required only for Compose interpolation; no application/data service is started.
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-promtool-postgres-placeholder}"
export PDFHUB_API_KEY_PEPPER="${PDFHUB_API_KEY_PEPPER:-promtool-api-pepper-placeholder}"
export PDFHUB_ADMIN_API_KEY="${PDFHUB_ADMIN_API_KEY:-pdfh_promtool_admin_placeholder_1234567890}"
export PDFHUB_WEBHOOK_MASTER_SECRET="${PDFHUB_WEBHOOK_MASTER_SECRET:-promtool-webhook-placeholder}"
export PDFHUB_AUTH_TOKEN_SECRET="${PDFHUB_AUTH_TOKEN_SECRET:-promtool-auth-secret-placeholder-0123456789abcdef}"
export PDFHUB_DOWNLOAD_SIGNING_SECRET="${PDFHUB_DOWNLOAD_SIGNING_SECRET:-promtool-download-secret-placeholder-0123456789abcdef}"

project="pdfhub-promtool-$$"
cleanup() { docker compose -p "${project}" --profile observability down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker compose -p "${project}" --profile observability run --rm --no-deps \
  --entrypoint /bin/promtool prometheus \
  check config /etc/prometheus/prometheus.yml

cleanup
trap - EXIT
echo "prometheus validation: PASS"
