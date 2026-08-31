#!/usr/bin/env bash
set -Eeuo pipefail

PR="${1:-${PR:-}}"
[ -n "${PR}" ] || { echo "Usage: $0 <pr-number>" >&2; exit 2; }
for cmd in git gh; do command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }; done
gh auth status >/dev/null 2>&1 || { echo "GitHub CLI is not authenticated" >&2; exit 1; }

repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
readarray -t metadata < <(gh api "repos/${repo}/pulls/${PR}" --jq '.state,.draft,.base.ref,.base.sha,.head.sha')
state="${metadata[0]:-}"
draft="${metadata[1]:-}"
base_ref="${metadata[2]:-}"
base_sha="${metadata[3]:-}"
head_sha="${metadata[4]:-}"

[ "${state}" = "open" ] || { echo "PR #${PR} is not open" >&2; exit 1; }
[ "${draft}" = "false" ] || { echo "PR #${PR} is still draft" >&2; exit 1; }
[ "${base_ref}" = "main" ] || { echo "PR #${PR} must target main" >&2; exit 1; }
current_main="$(gh api "repos/${repo}/git/ref/heads/main" --jq '.object.sha')"
[ "${base_sha}" = "${current_main}" ] || { echo "PR base is stale: ${base_sha} != ${current_main}" >&2; exit 1; }

status_json="$(gh api "repos/${repo}/commits/${head_sha}/status")"
validation_state="$(python3 -c 'import json,sys; p=json.load(sys.stdin); rows=[x for x in p.get("statuses",[]) if x.get("context")=="local-ci/validate-free"]; print(rows[0].get("state","") if rows else "")' <<<"${status_json}")"
[ "${validation_state}" = "success" ] || {
  echo "Refusing merge: local-ci/validate-free on ${head_sha} is '${validation_state:-missing}', not success" >&2
  exit 1
}

# Re-read immediately before mutation so a moved head/main cannot inherit stale approval.
latest_main="$(gh api "repos/${repo}/git/ref/heads/main" --jq '.object.sha')"
latest_head="$(gh api "repos/${repo}/pulls/${PR}" --jq '.head.sha')"
[ "${latest_main}" = "${current_main}" ] || { echo "main moved during merge gate" >&2; exit 1; }
[ "${latest_head}" = "${head_sha}" ] || { echo "PR head moved during merge gate" >&2; exit 1; }

printf 'merge gate: validated PR #%s head=%s base=%s\n' "${PR}" "${head_sha}" "${current_main}"
gh api -X PUT "repos/${repo}/pulls/${PR}/merge" \
  -f sha="${head_sha}" \
  -f merge_method=squash \
  -f commit_title="0.5.1 stabilization: merge PR #${PR}" \
  --jq 'if .merged then "merge gate: PASS merged sha=" + .sha else error(.message) end'
