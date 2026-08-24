#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="${ROOT}/.local-ci"
cd "${ROOT}"

for cmd in git flock; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }
done

mkdir -p "${STATE_ROOT}/logs" "${STATE_ROOT}/worktrees" "${STATE_ROOT}/status"
exec 9>"${STATE_ROOT}/validator.lock"
if ! flock -n 9; then
  echo "local-ci: another validation cycle is running"
  exit 0
fi

git fetch --quiet --prune origin main
main_sha="$(git rev-parse origin/main)"
last_pass=""
if [ -f "${STATE_ROOT}/last-main-pass" ]; then
  last_pass="$(cat "${STATE_ROOT}/last-main-pass")"
fi

worktree="${STATE_ROOT}/worktrees/main-${main_sha}"
git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
rm -rf "${worktree}"
git worktree add --quiet --detach "${worktree}" "${main_sha}"

cleanup_main_worktree() {
  git -C "${ROOT}" worktree remove --force "${worktree}" >/dev/null 2>&1 || true
  rm -rf "${worktree}"
}
trap cleanup_main_worktree EXIT

if [ "${main_sha}" != "${last_pass}" ]; then
  log="${STATE_ROOT}/logs/main-${main_sha}.log"
  echo "local-ci: validating main ${main_sha}"
  if (cd "${worktree}" && make validate-free) 2>&1 | tee "${log}"; then
    printf '%s\n' "${main_sha}" > "${STATE_ROOT}/last-main-pass"
    echo "local-ci: main ${main_sha} PASS"
  else
    echo "local-ci: main ${main_sha} FAIL — see ${log}" >&2
    exit 1
  fi
fi

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  (
    cd "${worktree}"
    LOCAL_CI_STATE_ROOT="${STATE_ROOT}" bash scripts/local-ci-prs.sh
    LOCAL_CI_STATE_ROOT="${STATE_ROOT}" bash scripts/local-ci-dependabot.sh
  )
else
  echo "local-ci: gh is unavailable or unauthenticated; main validation remains active, PR/Dependabot validation is skipped"
fi

cleanup_main_worktree
trap - EXIT
