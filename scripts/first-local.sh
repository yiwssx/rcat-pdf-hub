#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

EXPECTED_BRANCH="${PDFHUB_FIRST_LOCAL_BRANCH:-stabilization/0.5.1-correctness}"
PUSH_LOCKS="${PDFHUB_FIRST_LOCAL_PUSH_LOCKS:-false}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "FIRST-LOCAL FAIL: missing command $1" >&2; exit 1; }; }
for cmd in bash git python3 node npm npx docker curl openssl gh make; do need "${cmd}"; done

docker compose version >/dev/null 2>&1 || { echo "FIRST-LOCAL FAIL: Docker Compose plugin is required" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "FIRST-LOCAL FAIL: Docker daemon is not reachable" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "FIRST-LOCAL FAIL: run 'gh auth login' first" >&2; exit 1; }

python3 - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"FIRST-LOCAL FAIL: Python 3.12 required; found {sys.version.split()[0]}")
PY
node -e 'if (Number(process.versions.node.split(".")[0]) !== 24) { console.error(`FIRST-LOCAL FAIL: Node 24 required; found ${process.versions.node}`); process.exit(1); }'

branch="$(git branch --show-current)"
[ "${branch}" = "${EXPECTED_BRANCH}" ] || {
  echo "FIRST-LOCAL FAIL: checkout ${EXPECTED_BRANCH}; current branch is ${branch:-detached}" >&2
  exit 1
}
if [ -n "$(git status --porcelain)" ]; then
  echo "FIRST-LOCAL FAIL: working tree must be clean before bootstrap" >&2
  git status --short >&2
  exit 1
fi

printf '\n[1/9] Preparing local secrets and Local Admin login\n'
if [ ! -f .env ]; then
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets
path = Path('.env')
values = {
    'POSTGRES_PASSWORD': secrets.token_hex(24),
    'PDFHUB_API_KEY_PEPPER': secrets.token_hex(32),
    'PDFHUB_ADMIN_API_KEY': 'pdfh_admin_' + secrets.token_urlsafe(32),
    'PDFHUB_WEBHOOK_MASTER_SECRET': secrets.token_hex(32),
    'PDFHUB_AUTH_TOKEN_SECRET': secrets.token_hex(48),
    'PDFHUB_DOWNLOAD_SIGNING_SECRET': secrets.token_hex(48),
    'PDFHUB_LOCAL_AUTH_ENABLED': 'true',
    'PDFHUB_LOCAL_ADMIN_USERNAME': 'admin',
    'PDFHUB_LOCAL_ADMIN_PASSWORD': secrets.token_urlsafe(24),
    'PAPERLESS_DB_PASSWORD': secrets.token_hex(24),
    'PAPERLESS_SECRET_KEY': secrets.token_hex(48),
}
lines = path.read_text(encoding='utf-8').splitlines()
out = []
seen = set()
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key = line.split('=', 1)[0]
        if key in values:
            line = f'{key}={values[key]}'
            seen.add(key)
    out.append(line)
for key, value in values.items():
    if key not in seen:
        out.append(f'{key}={value}')
path.write_text('\n'.join(out) + '\n', encoding='utf-8')
PY
  chmod 600 .env
  echo "Created .env with random local secrets and Local Admin credentials"
else
  echo "Using existing .env (not overwritten)"
fi

local_user="$(sed -n 's/^PDFHUB_LOCAL_ADMIN_USERNAME=//p' .env | tail -n1)"
local_enabled="$(sed -n 's/^PDFHUB_LOCAL_AUTH_ENABLED=//p' .env | tail -n1)"
if [ "${local_enabled}" != "true" ]; then
  echo "FIRST-LOCAL FAIL: PDFHUB_LOCAL_AUTH_ENABLED=true is required for first local browser testing" >&2
  exit 1
fi
if [ -z "$(sed -n 's/^PDFHUB_LOCAL_ADMIN_PASSWORD=//p' .env | tail -n1)" ]; then
  echo "FIRST-LOCAL FAIL: PDFHUB_LOCAL_ADMIN_PASSWORD is empty" >&2
  exit 1
fi

printf '\n[2/9] Resolving deterministic dependency locks\n'
bash scripts/generate-locks.sh

printf '\n[3/9] Installing Playwright Chromium runtime\n'
(
  cd apps/web
  npx playwright install --with-deps chromium
)

printf '\n[4/9] Running complete repository validation\n'
make validate-free

printf '\n[5/9] Starting first local stack\n'
docker compose up -d --build --wait --wait-timeout 300
port="$(sed -n 's/^PDFHUB_HTTP_PORT=//p' .env | tail -n1)"
port="${port:-8080}"
base="http://127.0.0.1:${port}"
admin_key="$(sed -n 's/^PDFHUB_ADMIN_API_KEY=//p' .env | tail -n1)"
[ -n "${admin_key}" ] || { echo "FIRST-LOCAL FAIL: PDFHUB_ADMIN_API_KEY missing from .env" >&2; exit 1; }
curl -fsS "${base}/healthz" >/dev/null
curl -fsS "${base}/readyz" >/dev/null
python3 scripts/pdf-workload-smoke.py --url "${base}" --api-key "${admin_key}" --requests 3 --concurrency 1 --max-error-rate 0 --max-p95-ms 30000

printf '\n[6/9] Creating and verifying first quiesced backup\n'
backup_dir="${ROOT}/backups/first-local-$(date -u +%Y%m%dT%H%M%SZ)"
PDFHUB_BACKUP_QUIESCE=true BACKUP="${backup_dir}" make backup
PDFHUB_BACKUP_REQUIRE_QUIESCED=true BACKUP="${backup_dir}" make backup-verify

printf '\n[7/9] Running isolated disaster-recovery drill\n'
BACKUP="${backup_dir}" make dr-drill

printf '\n[8/9] Recording generated lockfiles\n'
git add apps/web/package-lock.json apps/api/requirements.lock
if git diff --cached --quiet; then
  echo "Lockfiles already match the repository"
else
  if [ "${PUSH_LOCKS}" != "true" ]; then
    echo "FIRST-LOCAL ACTION REQUIRED: validation passed, but generated lockfiles are not committed." >&2
    echo "Re-run with PDFHUB_FIRST_LOCAL_PUSH_LOCKS=true to commit/push them and continue Local CI." >&2
    exit 2
  fi
  git commit -m "chore(deps): lock 0.5.1 resolved dependency graph"
  git push origin HEAD
fi

printf '\n[9/9] Installing/running institution-owned Local CI\n'
make install-local-ci
make local-ci-cycle
make local-ci-doctor

printf '\nFIRST-LOCAL: PASS\n'
printf 'Local URL: %s\n' "${base}"
printf 'Local login username: %s\n' "${local_user:-admin}"
printf 'Local login password: read PDFHUB_LOCAL_ADMIN_PASSWORD from .env (chmod 600)\n'
printf 'Verified backup: %s\n' "${backup_dir}"
printf 'The stack is intentionally left running for manual browser inspection.\n'
