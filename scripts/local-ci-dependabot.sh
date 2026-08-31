#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="${LOCAL_CI_STATE_ROOT:-${ROOT}/.local-ci}"
cd "${ROOT}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

need git
need gh
need python3
need npm

gh auth status >/dev/null 2>&1 || {
  echo "GitHub CLI is not authenticated. Run: gh auth login" >&2
  exit 1
}

repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner')"
git fetch --quiet --prune origin main
main_sha="$(git rev-parse origin/main)"

post_status() {
  local sha="$1" state="$2" description="$3"
  gh api -X POST "repos/${repo}/statuses/${sha}" \
    -f state="${state}" \
    -f context='local-ci/dependency' \
    -f description="${description}" >/dev/null || true
}

mapfile -t rows < <(
  gh api --paginate "repos/${repo}/pulls?state=open&base=main&per_page=100" \
    --jq '.[] | select(.user.login == "dependabot[bot]") | [.number, .draft, .head.sha, .base.sha] | @tsv'
)

if [ "${#rows[@]}" -eq 0 ]; then
  echo "dependabot: no open direct-dependency PRs"
  exit 0
fi

mkdir -p "${STATE_ROOT}/worktrees" "${STATE_ROOT}/logs" "${STATE_ROOT}/status"

for row in "${rows[@]}"; do
  IFS=$'\t' read -r pr draft head_sha base_sha <<<"${row}"

  if [ "${draft}" = "true" ]; then
    echo "dependabot: PR #${pr} is draft; skip"
    continue
  fi

  if [ "${base_sha}" != "${main_sha}" ]; then
    post_status "${head_sha}" error "Dependency PR is based on stale main; rebase required"
    echo "dependabot: PR #${pr} base ${base_sha} is stale; current main is ${main_sha}; skip"
    continue
  fi

  changed="$(gh api --paginate "repos/${repo}/pulls/${pr}/files?per_page=100" --jq '.[].filename' | LC_ALL=C sort)"
  expected=$'apps/web/package-lock.json\napps/web/package.json'
  if [ "${changed}" != "${expected}" ]; then
    echo "dependabot: PR #${pr} must change package.json + package-lock.json only; full-validation lane owns it"
    continue
  fi

  non_bot="$(gh api --paginate "repos/${repo}/pulls/${pr}/commits?per_page=100" \
    --jq '.[] | select((.author.login // "") != "dependabot[bot]") | .sha' || true)"
  if [ -n "${non_bot}" ]; then
    echo "dependabot: PR #${pr} contains non-Dependabot commits; full-validation lane owns it"
    continue
  fi

  if ! python3 scripts/check-direct-dependency.py "${main_sha}" "${head_sha}" >/dev/null 2>&1; then
    echo "dependabot: PR #${pr} is not an eligible direct forward patch; full-validation lane owns it"
    continue
  fi

  success_file="${STATE_ROOT}/status/dependency-pr-${pr}-success"
  if [ -f "${success_file}" ] && [ "$(cat "${success_file}")" = "${base_sha}:${head_sha}" ]; then
    post_status "${head_sha}" success "Direct dependency patch already validated"
    echo "dependabot: PR #${pr} already validated against current main"
  else
    git fetch --quiet --force origin "pull/${pr}/head:refs/remotes/origin/pr-${pr}"
    fetched_sha="$(git rev-parse "refs/remotes/origin/pr-${pr}")"
    if [ "${fetched_sha}" != "${head_sha}" ]; then
      post_status "${head_sha}" error "Dependency PR head moved while fetching"
      echo "dependabot: PR #${pr} head moved during validation; skip"
      continue
    fi

    worktree="${STATE_ROOT}/worktrees/pr-${pr}"
    git worktree remove --force "${worktree}" >/dev/null 2>&1 || true
    rm -rf "${worktree}"
    git worktree add --quiet --detach "${worktree}" "${head_sha}"

    cleanup_worktree() {
      git -C "${ROOT}" worktree remove --force "${worktree}" >/dev/null 2>&1 || true
      rm -rf "${worktree}"
    }

    post_status "${head_sha}" pending "Direct dependency validation running on institution hardware"
    log="${STATE_ROOT}/logs/dependency-pr-${pr}-${head_sha}.log"
    echo "dependabot: validating PR #${pr} at ${head_sha}"
    if ! (cd "${worktree}" && bash scripts/validate-direct-dependency.sh "${main_sha}") 2>&1 | tee "${log}"; then
      rm -f "${success_file}"
      post_status "${head_sha}" failure "Direct dependency validation failed"
      echo "dependabot: PR #${pr} validation failed; not merged" >&2
      cleanup_worktree
      continue
    fi

    current_main="$(gh api "repos/${repo}/git/ref/heads/main" --jq '.object.sha')"
    current_head="$(gh api "repos/${repo}/pulls/${pr}" --jq '.head.sha')"
    if [ "${current_main}" != "${main_sha}" ] || [ "${current_head}" != "${head_sha}" ]; then
      post_status "${head_sha}" error "PR or main moved during validation; result discarded"
      echo "dependabot: PR #${pr} or main moved after validation; not merged"
      cleanup_worktree
      continue
    fi

    printf '%s\n' "${base_sha}:${head_sha}" >"${success_file}"
    post_status "${head_sha}" success "Direct dependency patch passed locked build and browser smoke"
    cleanup_worktree
  fi

  merge_result="$(gh api -X PUT "repos/${repo}/pulls/${pr}/merge" -f merge_method=squash -f sha="${head_sha}")"
  merged="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("merged", False)).lower())' <<<"${merge_result}")"
  if [ "${merged}" != "true" ]; then
    post_status "${head_sha}" error "Validation passed but GitHub refused merge"
    echo "dependabot: GitHub refused merge for PR #${pr}" >&2
    echo "${merge_result}" >&2
    exit 1
  fi

  echo "dependabot: PR #${pr} validated and squash-merged"
  exit 0
done
