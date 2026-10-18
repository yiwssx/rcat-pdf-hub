#!/usr/bin/env bash
set -Eeuo pipefail

# Operator-controlled revalidation of ONE PR after investigating the logged failure.
# Never reports a success or starts validation in the middle of a running cycle.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

pr="${1:-}"
mode="${2:---dry-run}"
if [[ "$#" -lt 1 || "$#" -gt 2 || ! "${pr}" =~ ^[1-9][0-9]*$ ]] ||
   [[ "${mode}" != "--dry-run" && "${mode}" != "--apply" ]]; then
  echo "Usage: bash scripts/local-ci-retry-pr.sh <PR-number> [--dry-run|--apply]" >&2
  exit 2
fi

for status in failure attempt; do
  marker="${ROOT}/.local-ci/status/pr-${pr}-${status}"
  if [[ -f "${marker}" ]]; then
    printf '%s: %s\n' "${status}" "$(cat "${marker}")"
  else
    echo "${status}: (none)"
  fi
done

if [[ "${mode}" == "--dry-run" ]]; then
  echo "Dry-run only; use --apply to clear this PR's cached failure/interruption."
  exit 0
fi

# A systemd oneshot can be active while the timer remains enabled.
if systemctl --user is-active --quiet rcat-pdf-hub-local-ci.service; then
  echo "Local CI service is active; retry not permitted until the current cycle finishes." >&2
  exit 1
fi

exec 9>"${ROOT}/.local-ci/validator.lock"
if ! flock -n 9; then
  echo "CI validator lock is held; retry cancelled." >&2
  exit 1
fi

rm -f -- "${ROOT}/.local-ci/status/pr-${pr}-failure" \
  "${ROOT}/.local-ci/status/pr-${pr}-attempt"
echo "PR #${pr}: failure/interruption cache cleared. The next enabled timer cycle may revalidate."
echo "No GitHub PASS status was posted and no Docker resources were changed."
