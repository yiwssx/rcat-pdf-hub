#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

WARN_RE='(^|[[:space:]])warn(ing)?([[:space:]:]|$)|npm warn|deprecated|deprecationwarning|⚠|##\[warning\]'
MODE="${1:-all}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

pick_validation_http_port() {
  python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

check_clean_log() {
  local file="$1"
  if grep -Eqi "${WARN_RE}" "${file}"; then
    echo "Warning/deprecation detected in ${file}" >&2
    grep -Ein "${WARN_RE}" "${file}" >&2 || true
    exit 1
  fi
}

require_tool_versions() {
  need python3
  need node
  need npm
  need npx
  python3 scripts/check-host-python.py
  node -e 'const major=Number(process.versions.node.split(".")[0]); if (major !== 24) { console.error(`Node 24 is required to match the production image; found ${process.versions.node}`); process.exit(1); }'
}

validation_compose_env() {
  export POSTGRES_DB=pdfhub
  export POSTGRES_USER=pdfhub
  export POSTGRES_PASSWORD=free-ci-postgres-password
  export PDFHUB_API_KEY_PEPPER=free-ci-api-key-pepper-change-me
  export PDFHUB_ADMIN_API_KEY=pdfh_free_ci_admin_key_change_me_1234567890
  export PDFHUB_WEBHOOK_MASTER_SECRET=free-ci-webhook-master-secret-change-me
  export PDFHUB_AUTH_TOKEN_SECRET=free-ci-auth-token-secret-change-me-0123456789abcdef
  export PDFHUB_DOWNLOAD_SIGNING_SECRET=free-ci-download-signing-secret-change-me-0123456789abcdef
  export PDFHUB_GRAFANA_ADMIN_PASSWORD=free-ci-grafana-admin-password-change-me
  local validation_port="${PDFHUB_VALIDATION_HTTP_PORT:-18080}"
  export PDFHUB_ALLOWED_ORIGINS="http://localhost:${validation_port}"
  export PDFHUB_PUBLIC_BASE_URL="http://localhost:${validation_port}"
  export PDFHUB_PUBLIC_BIND_HOST=127.0.0.1
  export PDFHUB_NAS_PATH="/tmp/pdfhub-validation-nas-$$"
  export PDFHUB_SESSION_COOKIE_SECURE=false
  export PDFHUB_WEB_CONSOLE_AUTO_LOGIN=true
  export NEXT_TELEMETRY_DISABLED=1
}

policy() {
  need python3
  python3 scripts/validate-release-policy.py
}

operations() {
  need bash
  need python3
  for script in \
    scripts/backup.sh scripts/verify-backup.sh scripts/restore.sh scripts/dr-drill.sh \
    scripts/install-backup-user.sh scripts/uninstall-backup-user.sh scripts/local-ci-doctor.sh \
    scripts/local-ci-cycle.sh scripts/local-ci-prs.sh scripts/local-ci-dependabot.sh \
    scripts/install-local-ci-user.sh scripts/uninstall-local-ci-user.sh scripts/validate-direct-dependency.sh \
    scripts/compile-python-lock.sh scripts/validate-container-hardening.sh; do
    bash -n "${script}"
  done
  python3 -m py_compile \
    scripts/load-smoke.py \
    scripts/validate-release-policy.py \
    scripts/check-host-python.py \
    scripts/check-direct-dependency.py \
    scripts/check-python-security-dependency.py \
    scripts/check-python-lock.py \
    scripts/check-production-network.py \
    scripts/check-worker-pools.py \
    scripts/check-grafana-provisioning.py \
    scripts/validate-api-contract.py \
    scripts/backend-coverage.py
  echo 'operations: PASS'
}

backend() {
  need python3
  python3 scripts/check-host-python.py
  need docker
  local coverage_image coverage_evidence

  # The host runs stdlib-only orchestration. All pinned application packages,
  # imports, contract checks and migrations run in the canonical API image,
  # regardless of the host's Python minor version.
  python3 scripts/check-python-lock.py
  coverage_image="rcat-pdf-hub-api-coverage:local"
  docker build -t "${coverage_image}" apps/api

  docker run --rm \
    -e PDFHUB_CONTRACT_ARTIFACT=/tmp/openapi.json \
    -v "${ROOT}:/repo:ro" \
    -w /app \
    "${coverage_image}" \
    sh -ceu '
      python -m pip check
      python -W error -c "import ldap3, pyasn1, PIL"
      python -m compileall -q app tests alembic
      cd /repo
      python scripts/check-python-lock.py
      python scripts/validate-api-contract.py
      cd /app
      PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-migrate-fresh.db python -c "from app.migrate import run_migrations; run_migrations()"
      PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-migrate-adopt.db python - <<PY
from app.db import engine
from app.models import ApiKey, FileRecord, JobRecord, ServicePolicy
for table in [ApiKey.__table__, ServicePolicy.__table__, FileRecord.__table__, JobRecord.__table__]:
    table.create(bind=engine, checkfirst=True)
PY
      PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-migrate-adopt.db python -c "from app.migrate import run_migrations; run_migrations()"
    '

  # Keep the baseline denominator stable: tests and coverage always execute
  # in the exact same API image as the contract and migration validations.
  coverage_evidence="$(mktemp -d)"
  chmod 0777 "${coverage_evidence}"
  docker run --rm \
    -e PDFHUB_COVERAGE_ARTIFACT=/coverage/backend-coverage.json \
    -v "${ROOT}:/repo:ro" \
    -v "${coverage_evidence}:/coverage" \
    -w /repo \
    "${coverage_image}" \
    python scripts/backend-coverage.py
  mkdir -p artifacts/quality
  cp "${coverage_evidence}/backend-coverage.json" artifacts/quality/backend-coverage.json
  chmod 0644 artifacts/quality/backend-coverage.json
  rm -rf "${coverage_evidence}"
  echo 'backend: PASS'
}

frontend() {
  require_tool_versions
  local install_log build_log pkg_before lock_before
  install_log="$(mktemp)"
  build_log="$(mktemp)"
  pkg_before="$(sha256sum apps/web/package.json | awk '{print $1}')"
  lock_before="$(sha256sum apps/web/package-lock.json | awk '{print $1}')"
  (
    cd apps/web
    NEXT_TELEMETRY_DISABLED=1 NPM_CONFIG_UPDATE_NOTIFIER=false \
      npm ci --no-audit --no-fund 2>&1 | tee "${install_log}"
    npm run typecheck
    mkdir -p .next/cache
    NEXT_TELEMETRY_DISABLED=1 npm run build 2>&1 | tee "${build_log}"
  )
  check_clean_log "${install_log}"
  check_clean_log "${build_log}"
  test "${pkg_before}" = "$(sha256sum apps/web/package.json | awk '{print $1}')"
  test "${lock_before}" = "$(sha256sum apps/web/package-lock.json | awk '{print $1}')"
  git diff --exit-code -- apps/web/package.json apps/web/package-lock.json apps/web/tsconfig.json
  echo 'frontend: PASS'
}

e2e() {
  require_tool_versions
  local browser_log e2e_log pkg_before lock_before browsers_path
  browser_log="$(mktemp)"
  e2e_log="$(mktemp)"
  pkg_before="$(sha256sum apps/web/package.json | awk '{print $1}')"
  lock_before="$(sha256sum apps/web/package-lock.json | awk '{print $1}')"
  browsers_path="${PLAYWRIGHT_BROWSERS_PATH:-${HOME}/.cache/ms-playwright}"
  (
    cd apps/web
    PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" npx playwright install --only-shell chromium 2>&1 | tee "${browser_log}"
    PDFHUB_E2E_SERVER_MODE=production \
    PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" NEXT_TELEMETRY_DISABLED=1 npm run test:e2e 2>&1 | tee "${e2e_log}"
  )
  check_clean_log "${browser_log}"
  check_clean_log "${e2e_log}"
  test "${pkg_before}" = "$(sha256sum apps/web/package.json | awk '{print $1}')"
  test "${lock_before}" = "$(sha256sum apps/web/package-lock.json | awk '{print $1}')"
  echo 'e2e: PASS'
}

compose_config() {
  need docker
  validation_compose_env
  local err project
  err="$(mktemp)"
  project="pdfhub-validation-$$"
  docker compose -p "${project}" config >/tmp/pdfhub-compose.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  : >"${err}"
  docker compose -p "${project}" --profile s3 --profile security --profile observability --profile archive config >/tmp/pdfhub-compose-all.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  : >"${err}"
  docker compose -p "${project}" -f docker-compose.yml -f docker-compose.nas.yml config >/tmp/pdfhub-compose-nas.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  : >"${err}"
  docker compose -p "${project}" -f docker-compose.yml -f docker-compose.prod.yml config >/tmp/pdfhub-compose-prod.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  : >"${err}"
  docker compose -p "${project}" -f docker-compose.yml -f docker-compose.prod.yml --profile s3 --profile security --profile observability --profile archive config >/tmp/pdfhub-compose-prod-all.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  docker compose -p "${project}" -f docker-compose.yml -f docker-compose.prod.yml --profile s3 --profile security --profile observability --profile archive config --format json >/tmp/pdfhub-compose-prod-all.json
  python3 scripts/check-production-network.py /tmp/pdfhub-compose-prod-all.json "${PDFHUB_PUBLIC_BIND_HOST}" "${PDFHUB_MANAGEMENT_BIND_HOST:-127.0.0.1}"
  python3 scripts/check-worker-pools.py /tmp/pdfhub-compose-prod-all.json
  : >"${err}"
  docker compose -p "${project}" -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nas.yml config >/tmp/pdfhub-compose-prod-nas.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  echo 'compose: PASS'
}

runtime() {
  need docker
  need curl
  require_tool_versions
  validation_compose_env
  local build_log up_log service_log stack_e2e_log project browsers_path
  build_log="$(mktemp)"
  up_log="$(mktemp)"
  service_log="$(mktemp)"
  stack_e2e_log="$(mktemp)"
  project="pdfhub-validation-${BASHPID}"
  browsers_path="${PLAYWRIGHT_BROWSERS_PATH:-${HOME}/.cache/ms-playwright}"
  export PDFHUB_HTTP_PORT="${PDFHUB_VALIDATION_HTTP_PORT:-$(pick_validation_http_port)}"
  export PDFHUB_ALLOWED_ORIGINS="http://localhost:${PDFHUB_HTTP_PORT}"
  export PDFHUB_PUBLIC_BASE_URL="http://localhost:${PDFHUB_HTTP_PORT}"
  printf 'runtime validation HTTP port: %s\n' "${PDFHUB_HTTP_PORT}"

  dc() {
    docker compose -p "${project}" -f docker-compose.yml -f docker-compose.prod.yml "$@"
  }

  cleanup_runtime() {
    dc --profile s3 --profile security --profile observability --profile archive down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "${PDFHUB_NAS_PATH}" >/dev/null 2>&1 || true
  }
  trap cleanup_runtime EXIT

  dc build --pull api worker-interactive worker worker-heavy cleanup webhook web 2>&1 | tee "${build_log}"
  check_clean_log "${build_log}"
  dc up -d --no-build --wait --wait-timeout 240 postgres valkey gotenberg api 2>&1 | tee "${up_log}"
  check_clean_log "${up_log}"
  dc exec -T api python -c 'from app.migrate import run_migrations; run_migrations()' 2>&1 | tee -a "${up_log}"
  check_clean_log "${up_log}"
  dc exec -T api python -c 'from app.db import engine; from sqlalchemy import inspect; tables=set(inspect(engine).get_table_names()); missing={"api_keys", "service_policies", "files", "jobs"}-tables; assert not missing, f"missing validation tables: {sorted(missing)}"' 2>&1 | tee -a "${up_log}"
  check_clean_log "${up_log}"
  dc up -d --no-build --wait --wait-timeout 240 2>&1 | tee -a "${up_log}"
  check_clean_log "${up_log}"
  PDFHUB_COMPOSE_PROJECT="${project}" bash scripts/validate-container-hardening.sh
  docker compose -p "${project}" -f docker-compose.yml -f docker-compose.prod.yml --profile s3 --profile security --profile observability --profile archive config --format json >/tmp/pdfhub-runtime-prod.json
  python3 scripts/check-production-network.py /tmp/pdfhub-runtime-prod.json "${PDFHUB_PUBLIC_BIND_HOST}" "${PDFHUB_MANAGEMENT_BIND_HOST:-127.0.0.1}"
  python3 scripts/check-worker-pools.py /tmp/pdfhub-runtime-prod.json
  curl -fsS "http://localhost:${PDFHUB_HTTP_PORT}/healthz" | python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["status"]=="ok" and p["services"]["database"] and p["services"]["redis"]'
  curl -fsS "http://localhost:${PDFHUB_HTTP_PORT}/readyz" >/dev/null
  dc exec -T \
    -e PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-runtime-tests.db \
    -e PDFHUB_REDIS_URL=redis://valkey:6379/15 \
    -e PDFHUB_DATA_DIR=/tmp/pdfhub-runtime-test-data \
    -e PDFHUB_API_KEY_PEPPER=ci-test-pepper-change-me \
    -e PDFHUB_ADMIN_API_KEY=pdfh_ci_admin_key_change_me \
    -e PDFHUB_WEBHOOK_MASTER_SECRET=ci-webhook-master-secret-change-me \
    -e PDFHUB_DOWNLOAD_SIGNING_SECRET=ci-download-signing-secret-change-me-at-least-32 \
    api python -m pytest -q -p no:cacheprovider
  test "$(dc ps --status running webhook --format json | wc -l)" -ge 1

  if ! (
    cd apps/web
    PDFHUB_E2E_BASE_URL="http://127.0.0.1:${PDFHUB_HTTP_PORT}" \
    PDFHUB_E2E_STACK=1 \
    PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" \
    NEXT_TELEMETRY_DISABLED=1 \
      npm run test:e2e:stack 2>&1 | tee "${stack_e2e_log}"
  ); then
    echo 'production stack E2E failed; API container log follows:' >&2
    dc logs --no-color api >&2 || true
    exit 1
  fi
  check_clean_log "${stack_e2e_log}"

  dc logs --no-color >"${service_log}" 2>&1
  check_clean_log "${service_log}"
  cleanup_runtime
  trap - EXIT
  echo 'runtime: PASS'
}

case "${MODE}" in
  policy) policy ;;
  operations) policy; operations ;;
  backend) policy; backend ;;
  frontend) policy; frontend ;;
  e2e) policy; frontend; e2e ;;
  compose) policy; compose_config ;;
  runtime) policy; operations; frontend; e2e; compose_config; runtime ;;
  all) policy; operations; backend; frontend; e2e; compose_config; runtime ;;
  *) echo "Usage: $0 [policy|operations|backend|frontend|e2e|compose|runtime|all]" >&2; exit 2 ;;
esac

echo "zero-cost validation (${MODE}): PASS"
