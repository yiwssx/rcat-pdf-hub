#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# No Docker daemon, sudo, or live Production files are used.
nas_dir="/tmp/pdfhub-validation-nas-${BASHPID}${RANDOM}${RANDOM}"

cleanup_test() {
  if [[ -d "${nas_dir}" && ! -L "${nas_dir}" ]]; then
    rm -f -- "${nas_dir}/ci-canary"
    rmdir -- "${nas_dir}" 2>/dev/null || true
  elif [[ -L "${nas_dir}" ]]; then
    rm -- "${nas_dir}"
  fi
}
trap cleanup_test EXIT

fail() { echo "ci-nas regression FAIL: $*" >&2; exit 1; }
expect_failure() {
  if "$@" >/dev/null 2>&1; then
    fail "expected command to fail: $*"
  fi
}

expect_failure bash scripts/ci-nas-dir.sh create /tmp/not-validation-nas-999
expect_failure bash scripts/ci-nas-dir.sh remove /tmp/not-validation-nas-999

bash scripts/ci-nas-dir.sh create "${nas_dir}"
[[ -d "${nas_dir}" && ! -L "${nas_dir}" ]] || fail "directory was not created"
[[ "$(stat -c '%u' -- "${nas_dir}")" == "$(id -u)" ]] ||
  fail "directory not owned by runner"
[[ "$(stat -c '%a' -- "${nas_dir}")" == 700 ]] ||
  fail "directory permissions are not 700"

# The source must be new, not an existing directory created by Docker/root.
expect_failure bash scripts/ci-nas-dir.sh create "${nas_dir}"

# No broad rm -rf: refuse to remove a directory containing data.
printf '%s\n' do-not-delete > "${nas_dir}/ci-canary"
expect_failure bash scripts/ci-nas-dir.sh remove "${nas_dir}"
[[ -f "${nas_dir}/ci-canary" ]] || fail "unexpected data deletion"
rm -- "${nas_dir}/ci-canary"

bash scripts/ci-nas-dir.sh remove "${nas_dir}"
[[ ! -e "${nas_dir}" ]] || fail "empty directory not removed"

# Symlink collision must not affect the target.
ln -s -- /tmp "${nas_dir}"
expect_failure bash scripts/ci-nas-dir.sh create "${nas_dir}"
expect_failure bash scripts/ci-nas-dir.sh remove "${nas_dir}"
[[ -L "${nas_dir}" ]] || fail "symlink unexpectedly deleted"
rm -- "${nas_dir}"

echo "CI temporary NAS directory lifecycle regression: PASS"
