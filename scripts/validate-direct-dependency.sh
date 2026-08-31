#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
BASE_REF="${1:-origin/main}"

for cmd in git python3 node npm npx; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "${cmd} is required" >&2; exit 1; }
done

node -e 'const major=Number(process.versions.node.split(".")[0]); if (major !== 24) { console.error(`Node 24 is required to match the production image; found ${process.versions.node}`); process.exit(1); }'
python3 scripts/check-direct-dependency.py "${BASE_REF}" HEAD

before_hash="$(sha256sum apps/web/package.json | awk '{print $1}')"
install_log="$(mktemp)"
build_log="$(mktemp)"
browser_log="$(mktemp)"
e2e_log="$(mktemp)"
browsers_path="${PLAYWRIGHT_BROWSERS_PATH:-${HOME}/.cache/ms-playwright}"
(
  cd apps/web
  rm -f package-lock.json
  NEXT_TELEMETRY_DISABLED=1 NPM_CONFIG_UPDATE_NOTIFIER=false \
    npm install --package-lock=false --no-audit --no-fund 2>&1 | tee "${install_log}"
  npm run typecheck
  mkdir -p .next/cache
  NEXT_TELEMETRY_DISABLED=1 npm run build 2>&1 | tee "${build_log}"
  PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" npx playwright install --only-shell chromium 2>&1 | tee "${browser_log}"
  PLAYWRIGHT_BROWSERS_PATH="${browsers_path}" NEXT_TELEMETRY_DISABLED=1 npm run test:e2e 2>&1 | tee "${e2e_log}"
)

WARN_RE='(^|[[:space:]])warn(ing)?([[:space:]:]|$)|npm warn|deprecated|deprecationwarning|⚠|##\[warning\]'
if grep -Eqi "${WARN_RE}" "${install_log}" "${build_log}" "${browser_log}" "${e2e_log}"; then
  echo 'Warning/deprecation detected in dependency validation' >&2
  grep -Ein "${WARN_RE}" "${install_log}" "${build_log}" "${browser_log}" "${e2e_log}" >&2 || true
  exit 1
fi

test ! -e apps/web/package-lock.json
test "${before_hash}" = "$(sha256sum apps/web/package.json | awk '{print $1}')"
git diff --exit-code -- apps/web/package.json apps/web/tsconfig.json

echo 'direct dependency validation: PASS'
