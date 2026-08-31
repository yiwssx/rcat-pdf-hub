#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }
for cmd in python3 node npm; do need "${cmd}"; done

python3 - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Python 3.12 is required; found {sys.version.split()[0]}")
PY
node -e 'if (Number(process.versions.node.split(".")[0]) !== 24) { console.error(`Node 24 is required; found ${process.versions.node}`); process.exit(1); }'

printf 'locks: resolving frontend dependency graph with npm\n'
(
  cd apps/web
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund
  npm ci --ignore-scripts --no-audit --no-fund
)

printf 'locks: resolving backend dependency graph with Python 3.12\n'
tmp="$(mktemp -d)"
cleanup() { rm -rf "${tmp}"; }
trap cleanup EXIT
python3 -m venv "${tmp}/venv"
# shellcheck disable=SC1091
source "${tmp}/venv/bin/activate"
python -m pip install --disable-pip-version-check -r apps/api/requirements.txt
python -m pip check
python -m pip freeze --exclude-editable | LC_ALL=C sort > apps/api/requirements.lock
deactivate

[ -s apps/web/package-lock.json ] || { echo "package-lock.json was not created" >&2; exit 1; }
[ -s apps/api/requirements.lock ] || { echo "requirements.lock was not created" >&2; exit 1; }

printf 'locks: PASS\n'
printf '  apps/web/package-lock.json\n'
printf '  apps/api/requirements.lock\n'
printf 'Commit both generated lockfiles before merging a release PR.\n'
