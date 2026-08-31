#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="${LOCAL_CI_STATE_ROOT:-${ROOT}/.local-ci}"
cd "${ROOT}"

for cmd in git gh python3; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }
done

gh auth status >/dev/null 2>&1 || {
  echo "GitHub CLI is not authenticated; PR validation cannot report status" >&2
  exit 1
}

repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
git fetch --quiet --prune origin main
main_sha="$(git rev-parse origin/main)"
mkdir -p "${STATE_ROOT}/worktrees" "${STATE_ROOT}/logs" "${STATE_ROOT}/status"

post_status() {
  local sha="$1" state="$2" description="$3"
  gh api -X POST "repos/${repo}/statuses/${sha}" \
    -f state="${state}" \
    -f context='local-ci/validate-free' \
    -f description="${description}" >/dev/null || true
}

mapfile -t rows < <(
  gh api --paginate "repos/${repo}/pulls?state=open&base=main&per_page=100" \
    --jq '.[] | [.number, .draft, .head.sha, .base.sha, .user.login] | @tsv'
)

if [ "${#rows[@]}" -eq 0 ]; then
  echo "local-ci: no open PRs"
  exit 0
fi

for row in "${rows[@]}"; do
  IFS=$'\t' read -r pr draft head_sha base_sha author <<<"${row}"

  if [ "${draft}" = "true" ]; then
    echo "local-ci: PR #${pr} is draft; skip"
    continue
  fi
  if [ "${base_sha}" != "${main_sha}" ]; then
    post_status "${head_sha}" error "PR base is stale; update branch to current main"
    echo "local-ci: PR #${pr} base is stale; status marked error until updated"
    continue
  fi

  success_file="${STATE_ROOT}/status/pr-${pr}-success"
  if [ -f "${success_file}" ] && [ "$(cat "${success_file}")" = "${base_sha}:${head_sha}" ]; then
    post_status "${head_sha}" success "Zero-cost full validation already passed"
    echo "local-ci: PR #${pr} ${head_sha} already passed against ${base_sha}"
    continue
  fi

  git fetch --quiet --force origin "pull/${pr}/head:refs/remotes/origin/pr-${pr}"
  fetched_sha="$(git rev-parse "refs/remotes/origin/pr-${pr}")"
  if [ "${fetched_sha}" != "${head_sha}" ]; then
    post_status "${head_sha}" error "PR head moved while fetching; retrying next cycle"
    echo "local-ci: PR #${pr} head moved while fetching; retry next cycle"
    continue
  fi

  if [ "${author}" = "dependabot[bot]" ]; then
    changed="$(gh api --paginate "repos/${repo}/pulls/${pr}/files?per_page=100" --jq '.[].filename' | LC_ALL=C sort)"
    expected=$'apps/web/package-lock.json\napps/web/package.json'
    non_bot="$(gh api --paginate "repos/${repo}/pulls/${pr}/commits?per_page=100" \
      --jq '.[] | select((.author.login // "") != "dependabot[bot]") | .sha' || true)"
    if [ "${changed}" = "${expected}" ] && [ -z "${non_bot}" ] && \
       python3 scripts/check-direct-dependency.py "${main_sha}" "${head_sha}" >/dev/null 2>&1; then
      echo "local-ci: Dependabot PR #${pr} is an eligible package.json + package-lock patch; dependency lane owns validation/status"
      continue
    fi
    echo "local-ci: Dependabot PR #${pr} is outside the auto-merge lane; running full validation with no auto-merge"
  fi

  worktree="${STATE_ROOT}/worktrees/pr-full-${pr}"
  git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
  rm -rf "${worktree}"
  git worktree add --quiet --detach "${worktree}" "${head_sha}"

  cleanup_worktree() {
    git -C "${ROOT}" worktree remove --force "${worktree}" >/dev/null 2>&1 || true
    rm -rf "${worktree}"
  }

  post_status "${head_sha}" pending "Zero-cost full validation running on institution-owned hardware"

  log="${STATE_ROOT}/logs/pr-${pr}-${head_sha}.log"
  echo "local-ci: full validation PR #${pr} at ${head_sha}"
  if (cd "${worktree}" && make validate-free) 2>&1 | tee "${log}"; then
    current_main="$(gh api "repos/${repo}/git/ref/heads/main" --jq '.object.sha')"
    current_head="$(gh api "repos/${repo}/pulls/${pr}" --jq '.head.sha')"
    if [ "${current_main}" = "${main_sha}" ] && [ "${current_head}" = "${head_sha}" ]; then
      printf '%s\n' "${base_sha}:${head_sha}" > "${success_file}"
      post_status "${head_sha}" success "Zero-cost full validation passed"
      echo "local-ci: PR #${pr} PASS"
    else
      post_status "${head_sha}" error "PR or main moved during validation; result discarded"
      echo "local-ci: PR #${pr} moved during validation; result discarded"
    fi
  else
    rm -f "${success_file}"
    post_status "${head_sha}" failure "Zero-cost full validation failed; inspect local CI log"
    echo "local-ci: PR #${pr} FAIL — ${log}" >&2
  fi

  cleanup_worktree
  exit 0
done
