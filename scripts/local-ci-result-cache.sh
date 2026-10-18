#!/usr/bin/env bash
# Sourced by local-ci-prs.sh. Persistent gate is keyed by BOTH the target base
# and PR head SHA; new commits or a changed base are eligible for validation.
# Expected variable STATE_ROOT must be set by the caller.

local_ci_result() {
  local pr="$1" key="$2"
  if [[ -f "${STATE_ROOT}/status/pr-${pr}-success" ]] &&
     [[ "$(cat "${STATE_ROOT}/status/pr-${pr}-success")" == "${key}" ]]; then
    echo success
  elif [[ -f "${STATE_ROOT}/status/pr-${pr}-failure" ]] &&
       [[ "$(cat "${STATE_ROOT}/status/pr-${pr}-failure")" == "${key}" ]]; then
    echo failure
  elif [[ -f "${STATE_ROOT}/status/pr-${pr}-attempt" ]] &&
       [[ "$(cat "${STATE_ROOT}/status/pr-${pr}-attempt")" == "${key}" ]]; then
    echo interrupted
  else
    echo needs-validation
  fi
}

local_ci_record_start() {
  local pr="$1" key="$2"
  printf '%s\n' "${key}" >"${STATE_ROOT}/status/pr-${pr}-attempt"
}

local_ci_record_success() {
  local pr="$1" key="$2"
  printf '%s\n' "${key}" >"${STATE_ROOT}/status/pr-${pr}-success"
  rm -f -- "${STATE_ROOT}/status/pr-${pr}-attempt" \
    "${STATE_ROOT}/status/pr-${pr}-failure"
}

local_ci_record_failure() {
  local pr="$1" key="$2"
  printf '%s\n' "${key}" >"${STATE_ROOT}/status/pr-${pr}-failure"
  rm -f -- "${STATE_ROOT}/status/pr-${pr}-attempt" \
    "${STATE_ROOT}/status/pr-${pr}-success"
}
