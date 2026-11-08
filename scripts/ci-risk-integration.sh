#!/usr/bin/env bash
# Ephemeral PostgreSQL/RQ/S3 acceptance for risk-scoped GitHub Actions CI.
# Never runs on an institution host: no production secrets, backup mounts,
# Docker Compose project, or access to actual operator environments.
set -Eeuo pipefail

if [[ "${GITHUB_ACTIONS:-}" != "true" || "${RUNNER_ENVIRONMENT:-}" != "github-hosted" ]]; then
  echo 'ci-risk-integration: GitHub-hosted ephemeral runner required' >&2
  exit 2
fi
db="${CI_INTEGRATION_DATABASE:-false}"
stack="${CI_INTEGRATION_T90_STACK:-false}"
case "${db}:${stack}" in
  true:true|true:false|false:true) ;;
  false:false) echo 'ci-risk-integration: no lane selected'; exit 0 ;;
  *) echo 'ci-risk-integration: invalid risk flags' >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
image="rcat-pdf-hub-api-lean:ci"
docker image inspect "${image}" >/dev/null
prefix="pdfhub-ci-${GITHUB_RUN_ID:-0}-${GITHUB_RUN_ATTEMPT:-1}"
pg="${prefix}-pg"
valkey="${prefix}-valkey"
s3="${prefix}-s3"
cleanup() {
  docker rm -f "${s3}" "${valkey}" "${pg}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# No persistent volumes and no routable ports: services are disposable and
# reachable only through 127.0.0.1 on the temporary Actions VM.
docker run -d --rm --name "${pg}" \
  -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=pdfhub_t90_ci \
  -e POSTGRES_PASSWORD=ci-t90-ephemeral-not-a-production-password \
  -e POSTGRES_DB=postgres \
  postgres:18.6-bookworm >/dev/null
ready=false
for _ in $(seq 1 60); do
  if docker exec "${pg}" pg_isready -U pdfhub_t90_ci -d postgres >/dev/null 2>&1; then
    ready=true; break
  fi
  sleep 1
done
if [[ "${ready}" != true ]]; then
  echo 'ci-risk-integration: disposable PostgreSQL not ready' >&2
  exit 1
fi

admin_url='postgresql+psycopg://pdfhub_t90_ci:ci-t90-ephemeral-not-a-production-password@127.0.0.1:5432/postgres'

if [[ "${db}" == true ]]; then
  echo 'ci-risk-integration: PostgreSQL 18 migration/backfill/rollback'
  timeout 8m docker run --rm --network host -w /app \
    -e GITHUB_ACTIONS=true \
    -e PDFHUB_T90_POSTGRES_TEST_URL="${admin_url}" \
    "${image}" python -m pytest -q -p no:cacheprovider \
    tests/test_t90_postgres_migration_ci.py
fi

if [[ "${stack}" == true ]]; then
  echo 'ci-risk-integration: real RQ, Valkey and S3 crash/repair scenarios'
  docker run -d --rm --name "${valkey}" \
    -p 127.0.0.1:6379:6379 valkey/valkey:8.1.9-alpine3.24 \
    valkey-server --save '' --appendonly no >/dev/null
  docker run -d --rm --name "${s3}" \
    -p 127.0.0.1:8333:8333 \
    -e AWS_ACCESS_KEY_ID=t90ci \
    -e AWS_SECRET_ACCESS_KEY=t90ci-ephemeral-key \
    chrislusf/seaweedfs:4.44 \
    server -dir=/data -s3 -s3.port=8333 \
    -master.volumeSizeLimitMB=64 -volume.max=32 >/dev/null
  ready=false
  for _ in $(seq 1 60); do
    if docker exec "${valkey}" valkey-cli ping 2>/dev/null | grep -qx PONG && \
      curl --silent --max-time 2 http://127.0.0.1:8333/ >/dev/null; then
      ready=true; break
    fi
    sleep 1
  done
  if [[ "${ready}" != true ]]; then
    echo 'ci-risk-integration: disposable Valkey/S3 not ready' >&2
    exit 1
  fi
  timeout 12m docker run --rm --network host -w /app \
    -e GITHUB_ACTIONS=true \
    -e PDFHUB_T90_STACK_ENABLED=yes \
    -e PDFHUB_T90_STACK_POSTGRES_ADMIN_URL="${admin_url}" \
    -e PDFHUB_T90_STACK_S3_ENDPOINT=http://127.0.0.1:8333 \
    "${image}" python tests/t90_stack_probe.py
fi

echo 'ci-risk-integration: PASS'
