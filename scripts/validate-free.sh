#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

WARN_RE='(^|[[:space:]])warn(ing)?([[:space:]:]|$)|npm warn|deprecated|deprecationwarning|⚠|##\[warning\]'
MODE="${1:-all}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
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
  python3 - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Python 3.12 is required to match the production image; found {sys.version.split()[0]}")
PY
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
  export PDFHUB_ALLOWED_ORIGINS=http://localhost:18080
  export PDFHUB_PUBLIC_BASE_URL=http://localhost:18080
  export PDFHUB_NAS_PATH="/tmp/pdfhub-validation-nas-$$"
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
    scripts/install-local-ci-user.sh scripts/uninstall-local-ci-user.sh scripts/validate-direct-dependency.sh; do
    bash -n "${script}"
  done
  python3 -m py_compile scripts/load-smoke.py scripts/validate-release-policy.py scripts/check-direct-dependency.py
  echo 'operations: PASS'
}

backend() {
  require_tool_versions
  local venv log
  venv="$(mktemp -d)/venv"
  log="$(mktemp)"
  python3 -m venv "${venv}"
  # shellcheck disable=SC1090
  source "${venv}/bin/activate"
  python -m pip install --disable-pip-version-check -r apps/api/requirements.txt 2>&1 | tee "${log}"
  check_clean_log "${log}"
  python -m pip check
  python -W error -c 'import ldap3, pyasn1, PIL'
  (
    cd apps/api
    python -m compileall -q app tests alembic
    python -m pytest -q
    rm -f /tmp/pdfhub-migrate-fresh.db /tmp/pdfhub-migrate-adopt.db
    PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-migrate-fresh.db python -c 'from app.migrate import run_migrations; run_migrations()'
    PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-migrate-adopt.db python - <<'PY'
from app.db import engine
from app.models import ApiKey, FileRecord, JobRecord, ServicePolicy
for table in [ApiKey.__table__, ServicePolicy.__table__, FileRecord.__table__, JobRecord.__table__]:
    table.create(bind=engine, checkfirst=True)
PY
    PDFHUB_DATABASE_URL=sqlite+pysqlite:////tmp/pdfhub-migrate-adopt.db python -c 'from app.migrate import run_migrations; run_migrations()'
  )
  deactivate
  echo 'backend: PASS'
}

frontend() {
  require_tool_versions
  local install_log build_log pkg_before
  install_log="$(mktemp)"
  build_log="$(mktemp)"
  pkg_before="$(sha256sum apps/web/package.json | awk '{print $1}')"
  (
    cd apps/web
    rm -f package-lock.json
    NEXT_TELEMETRY_DISABLED=1 NPM_CONFIG_UPDATE_NOTIFIER=false \
      npm install --package-lock=false --no-audit --no-fund 2>&1 | tee "${install_log}"
    npm run typecheck
    mkdir -p .next/cache
    NEXT_TELEMETRY_DISABLED=1 npm run build 2>&1 | tee "${build_log}"
  )
  check_clean_log "${install_log}"
  check_clean_log "${build_log}"
  test ! -e apps/web/package-lock.json
  test "${pkg_before}" = "$(sha256sum apps/web/package.json | awk '{print $1}')"
  git diff --exit-code -- apps/web/package.json apps/web/tsconfig.json
  echo 'frontend: PASS'
}

e2e() {
  require_tool_versions
  local browser_log e2e_log pkg_before browsers_path
  browser_log="$(mktemp)"
  e2e_log="$(mktemp)"
  pkg_before="$(sha256sum apps/web/package.json | awk '{print $1}')"
  browsers_path="${PLAYWRIGHT_BROWSERS_PATH:-${HOME}/.cache/ms-playwright}"
  (
    cd apps/web
    PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" npx playwright install --only-shell chromium 2>&1 | tee "${browser_log}"
    PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" NEXT_TELEMETRY_DISABLED=1 npm run test:e2e 2>&1 | tee "${e2e_log}"
  )
  check_clean_log "${browser_log}"
  check_clean_log "${e2e_log}"
  test ! -e apps/web/package-lock.json
  test "${pkg_before}" = "$(sha256sum apps/web/package.json | awk '{print $1}')"
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
  project="pdfhub-validation-$$"
  browsers_path="${PLAYWRIGHT_BROWSERS_PATH:-${HOME}/.cache/ms-playwright}"
  export PDFHUB_HTTP_PORT=18080
  export PDFHUB_ALLOWED_ORIGINS=http://localhost:${PDFHUB_HTTP_PORT}
  export PDFHUB_PUBLIC_BASE_URL=http://localhost:${PDFHUB_HTTP_PORT}

  dc() {
    docker compose -p "${project}" "$@"
  }

  cleanup_runtime() {
    dc --profile s3 --profile security --profile observability --profile archive down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "${PDFHUB_NAS_PATH}" >/dev/null 2>&1 || true
  }
  trap cleanup_runtime EXIT

  dc build --pull api worker cleanup webhook web 2>&1 | tee "${build_log}"
  check_clean_log "${build_log}"
  dc up -d --no-build --wait --wait-timeout 240 2>&1 | tee "${up_log}"
  check_clean_log "${up_log}"
  curl -fsS "http://localhost:${PDFHUB_HTTP_PORT}/healthz" | python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["status"]=="ok" and p["services"]["database"] and p["services"]["redis"]'
  curl -fsS "http://localhost:${PDFHUB_HTTP_PORT}/readyz" >/dev/null
  dc exec -T api python -m pytest -q
  test "$(dc ps --status running webhook --format json | wc -l)" -ge 1

  (
    cd apps/web
    PDFHUB_E2E_BASE_URL="http://127.0.0.1:${PDFHUB_HTTP_PORT}" \
    PDFHUB_E2E_STACK=1 \
    PDFHUB_E2E_API_KEY="${PDFHUB_ADMIN_API_KEY}" \
    PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" \
    NEXT_TELEMETRY_DISABLED=1 \
      npm run test:e2e:stack 2>&1 | tee "${stack_e2e_log}"
  )
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
