#!/usr/bin/env bash
# Require a successful GitHub Actions Lean CI check on the exact merged main SHA.
# This does not run CI, mutate the host, or substitute for release-specific gates.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

command -v gh >/dev/null 2>&1 || {
  echo "CI evidence check needs authenticated gh CLI" >&2
  exit 2
}
gh auth status >/dev/null 2>&1 || {
  echo "CI evidence check: GitHub authentication missing" >&2
  exit 2
}

sha="$(git rev-parse HEAD)"
remote_main="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
if [ -z "${remote_main}" ] || [ "${sha}" != "${remote_main}" ]; then
  echo "CI evidence check: HEAD does not equal origin/main; release refused" >&2
  exit 1
fi
repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
passes="$(gh api -H 'Accept: application/vnd.github+json' \
  "repos/${repo}/commits/${sha}/check-runs?per_page=100" \
  --jq '[.check_runs[] | select(.name == "ci/required" and .conclusion == "success" and .app.slug == "github-actions")] | length')"

if [ "${passes}" -lt 1 ]; then
  echo "CI evidence check: ci/required SUCCESS not found on exact main commit ${sha}" >&2
  exit 1
fi
printf 'CI evidence: PASS (ci/required on %s)\n' "${sha}"
