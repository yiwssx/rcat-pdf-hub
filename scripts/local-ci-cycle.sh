#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

for cmd in git flock; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }
done

mkdir -p .local-ci/logs .local-ci/worktrees
exec 9>.local-ci/validator.lock
if ! flock -n 9; then
  echo "local-ci: another validation cycle is running"
  exit 0
fi

git fetch --quiet --prune origin main
main_sha="$(git rev-parse origin/main)"
last_pass=""
if [ -f .local-ci/last-main-pass ]; then
  last_pass="$(cat .local-ci/last-main-pass)"
fi

if [ "${main_sha}" != "${last_pass}" ]; then
  worktree="${ROOT}/.local-ci/worktrees/main-${main_sha}"
  git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
  rm -rf "${worktree}"
  git worktree add --quiet --detach "${worktree}" "${main_sha}"
  log="${ROOT}/.local-ci/logs/main-${main_sha}.log"

  echo "local-ci: validating main ${main_sha}"
  if (cd "${worktree}" && make validate-free) 2>&1 | tee "${log}"; then
    printf '%s\n' "${main_sha}" > .local-ci/last-main-pass
    echo "local-ci: main ${main_sha} PASS"
  else
    echo "local-ci: main ${main_sha} FAIL — see ${log}" >&2
    git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
    rm -rf "${worktree}"
    exit 1
  fi

  git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
  rm -rf "${worktree}"
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  bash scripts/local-ci-dependabot.sh
else
  echo "local-ci: gh is unavailable or unauthenticated; main validation is active, Dependabot auto-validation is skipped"
fi
