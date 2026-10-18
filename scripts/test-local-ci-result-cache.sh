#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="$(mktemp -d)"
trap 'rm -rf -- "${STATE_ROOT}"' EXIT
mkdir -p "${STATE_ROOT}/status"
source "${ROOT}/scripts/local-ci-result-cache.sh"

pr=159
base=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
head=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
key="${base}:${head}"

assert_result() {
  local expected="$1" pair="$2" actual
  actual="$(local_ci_result "${pr}" "${pair}")"
  if [[ "${expected}" != "${actual}" ]]; then
    echo "Expected ${expected}, got ${actual} for ${pair}" >&2
    exit 1
  fi
}

assert_result needs-validation "${key}"
local_ci_record_start "${pr}" "${key}"
assert_result interrupted "${key}"

# A new head or a new main base must trigger its own validation.
assert_result needs-validation "${base}:cccccccccccccccccccccccccccccccccccccccc"
assert_result needs-validation "dddddddddddddddddddddddddddddddddddddddd:${head}"

local_ci_record_failure "${pr}" "${key}"
assert_result failure "${key}"
[[ ! -e "${STATE_ROOT}/status/pr-159-attempt" ]] || exit 1

# Repeated reads never change failed state (no automatic full retry).
for i in 1 2 3; do
  assert_result failure "${key}"
done

# A new commit is not blocked by the old failure.
next_key="${base}:cccccccccccccccccccccccccccccccccccccccc"
assert_result needs-validation "${next_key}"
local_ci_record_start "${pr}" "${next_key}"
assert_result interrupted "${next_key}"
local_ci_record_success "${pr}" "${next_key}"
assert_result success "${next_key}"
assert_result needs-validation "${key}"
[[ ! -e "${STATE_ROOT}/status/pr-159-failure" ]] || exit 1
[[ ! -e "${STATE_ROOT}/status/pr-159-attempt" ]] || exit 1

# Failed tests after a previous pass must invalidate cached success.
local_ci_record_start "${pr}" "${key}"
local_ci_record_failure "${pr}" "${key}"
assert_result failure "${key}"
[[ ! -e "${STATE_ROOT}/status/pr-159-success" ]] || exit 1

echo "local-ci SHA-pair retry guard regression: PASS"
