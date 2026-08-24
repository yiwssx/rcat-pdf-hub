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

policy() {
  need python3
  python3 - <<'PY'
from pathlib import Path
import json
import yaml

root = Path('.')
workflow_dir = root / '.github' / 'workflows'
workflow_files = []
if workflow_dir.exists():
    workflow_files = [p for p in workflow_dir.rglob('*') if p.suffix in {'.yml', '.yaml'}]
assert not workflow_files, f"Hosted GitHub Actions workflows are forbidden by zero-cost policy: {workflow_files}"

cfg = yaml.safe_load((root / '.github' / 'dependabot.yml').read_text(encoding='utf-8'))
updates = cfg.get('updates', [])
assert len(updates) == 1, updates
item = updates[0]
assert item.get('package-ecosystem') == 'npm', item
assert item.get('directory') == '/apps/web', item
allow = item.get('allow', [])
assert allow == [{'dependency-type': 'direct'}], allow

pkg = json.loads((root / 'apps' / 'web' / 'package.json').read_text(encoding='utf-8'))
for section in ('dependencies', 'devDependencies'):
    for name, version in pkg.get(section, {}).items():
        parts = version.split('.')
        assert len(parts) == 3 and all(part.isdigit() for part in parts), f"{name} must use exact x.y.z: {version}"

assert not (root / 'apps' / 'web' / 'package-lock.json').exists(), 'package-lock.json is intentionally not tracked: transitive updates must not be committed automatically'
print('policy: PASS')
PY
}

backend() {
  need python3
  local venv log
  venv="$(mktemp -d)/venv"
  log="$(mktemp)"
  python3 -m venv "${venv}"
  # shellcheck disable=SC1090
  source "${venv}/bin/activate"
  python -m pip install --disable-pip-version-check -r apps/api/requirements.txt 2>&1 | tee "${log}"
  check_clean_log "${log}"
  python -m pip check
  python -W error -c 'import ldap3, pyasn1'
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
  need npm
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

compose_config() {
  need docker
  local err
  err="$(mktemp)"
  docker compose config >/tmp/pdfhub-compose.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  docker compose --profile s3 --profile security --profile observability --profile archive config >/tmp/pdfhub-compose-all.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  docker compose -f docker-compose.yml -f docker-compose.nas.yml config >/tmp/pdfhub-compose-nas.out 2>"${err}"
  test ! -s "${err}" || { cat "${err}" >&2; exit 1; }
  echo 'compose: PASS'
}

runtime() {
  need docker
  need curl
  local build_log up_log service_log
  build_log="$(mktemp)"
  up_log="$(mktemp)"
  service_log="$(mktemp)"
  export POSTGRES_DB=pdfhub
  export POSTGRES_USER=pdfhub
  export POSTGRES_PASSWORD=free-ci-postgres-password
  export PDFHUB_API_KEY_PEPPER=free-ci-api-key-pepper-change-me
  export PDFHUB_ADMIN_API_KEY=pdfh_free_ci_admin_key_change_me_1234567890
  export PDFHUB_WEBHOOK_MASTER_SECRET=free-ci-webhook-master-secret-change-me
  export PDFHUB_AUTH_TOKEN_SECRET=free-ci-auth-token-secret-change-me-0123456789abcdef
  export PDFHUB_HTTP_PORT=18080
  export PDFHUB_ALLOWED_ORIGINS=http://localhost:18080
  export PDFHUB_PUBLIC_BASE_URL=http://localhost:18080
  export NEXT_TELEMETRY_DISABLED=1

  cleanup_runtime() {
    docker compose --profile s3 --profile security --profile observability --profile archive down -v --remove-orphans >/dev/null 2>&1 || true
  }
  trap cleanup_runtime EXIT

  docker compose build --pull api worker cleanup web 2>&1 | tee "${build_log}"
  check_clean_log "${build_log}"
  docker compose up -d --no-build --wait --wait-timeout 240 2>&1 | tee "${up_log}"
  check_clean_log "${up_log}"
  curl -fsS "http://localhost:${PDFHUB_HTTP_PORT}/healthz" | python3 -c 'import json,sys; p=json.load(sys.stdin); assert p["status"]=="ok" and p["services"]["database"] and p["services"]["redis"]'
  curl -fsS "http://localhost:${PDFHUB_HTTP_PORT}/readyz" >/dev/null
  docker compose exec -T api python -m pytest -q
  docker compose logs --no-color >"${service_log}" 2>&1
  check_clean_log "${service_log}"
  cleanup_runtime
  trap - EXIT
  echo 'runtime: PASS'
}

case "${MODE}" in
  policy) policy ;;
  backend) policy; backend ;;
  frontend) policy; frontend ;;
  compose) policy; compose_config ;;
  runtime) policy; compose_config; runtime ;;
  all) policy; backend; frontend; compose_config; runtime ;;
  *) echo "Usage: $0 [policy|backend|frontend|compose|runtime|all]" >&2; exit 2 ;;
esac

echo "zero-cost validation (${MODE}): PASS"
