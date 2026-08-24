#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
BASE_REF="${1:-origin/main}"

command -v git >/dev/null 2>&1 || { echo 'git is required' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'python3 is required' >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo 'node is required' >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo 'npm is required' >&2; exit 1; }

node -e 'const major=Number(process.versions.node.split(".")[0]); if (major !== 24) { console.error(`Node 24 is required to match the production image; found ${process.versions.node}`); process.exit(1); }'
python3 scripts/check-direct-dependency.py "${BASE_REF}" HEAD

before_hash="$(sha256sum apps/web/package.json | awk '{print $1}')"
install_log="$(mktemp)"
build_log="$(mktemp)"
(
  cd apps/web
  rm -f package-lock.json
  NEXT_TELEMETRY_DISABLED=1 NPM_CONFIG_UPDATE_NOTIFIER=false \
    npm install --package-lock=false --no-audit --no-fund 2>&1 | tee "${install_log}"
  npm run typecheck
  mkdir -p .next/cache
  NEXT_TELEMETRY_DISABLED=1 npm run build 2>&1 | tee "${build_log}"
)

WARN_RE='(^|[[:space:]])warn(ing)?([[:space:]:]|$)|npm warn|deprecated|deprecationwarning|⚠|##\[warning\]'
if grep -Eqi "${WARN_RE}" "${install_log}" "${build_log}"; then
  echo 'Warning/deprecation detected in dependency validation' >&2
  grep -Ein "${WARN_RE}" "${install_log}" "${build_log}" >&2 || true
  exit 1
fi

test ! -e apps/web/package-lock.json
test "${before_hash}" = "$(sha256sum apps/web/package.json | awk '{print $1}')"
git diff --exit-code -- apps/web/package.json apps/web/tsconfig.json

echo 'direct dependency validation: PASS'
