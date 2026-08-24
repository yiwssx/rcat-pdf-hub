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

changed="$(git diff --name-only "${BASE_REF}...HEAD")"
if [ "${changed}" != "apps/web/package.json" ]; then
  echo 'Dependency validation accepts exactly one changed file: apps/web/package.json' >&2
  printf '%s\n' "${changed}" >&2
  exit 1
fi

base_pkg="$(git show "${BASE_REF}:apps/web/package.json")"
head_pkg="$(cat apps/web/package.json)"
BASE_PKG="${base_pkg}" HEAD_PKG="${head_pkg}" python3 - <<'PY'
import copy
import json
import os
import re

before = json.loads(os.environ['BASE_PKG'])
after = json.loads(os.environ['HEAD_PKG'])
sections = ('dependencies', 'devDependencies')

before_static = copy.deepcopy(before)
after_static = copy.deepcopy(after)
for section in sections:
    before_static.pop(section, None)
    after_static.pop(section, None)
assert before_static == after_static, 'package.json changed outside dependency declarations'

changes = []
for section in sections:
    old = before.get(section, {})
    new = after.get(section, {})
    assert set(old) == set(new), f'dependency names changed in {section}'
    for name in sorted(old):
        if old[name] != new[name]:
            changes.append((section, name, old[name], new[name]))

assert len(changes) == 1, f'exactly one direct dependency must change; found {len(changes)}'
section, name, old_version, new_version = changes[0]
semver = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')
a = semver.fullmatch(old_version)
b = semver.fullmatch(new_version)
assert a and b, f'exact x.y.z versions required: {name} {old_version} -> {new_version}'
old_major, old_minor, old_patch = map(int, a.groups())
new_major, new_minor, new_patch = map(int, b.groups())
assert (new_major, new_minor) == (old_major, old_minor), 'only patch updates are allowed'
assert new_patch > old_patch, 'dependency version must move forward'
print(f'direct dependency policy: PASS — {section}.{name} {old_version} -> {new_version}')
PY

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
