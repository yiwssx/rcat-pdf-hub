#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_ROOT="${LOCAL_CI_STATE_ROOT:-${ROOT}/.local-ci}"
cd "${ROOT}"

failures=0
ok() { printf 'OK   %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*" >&2; failures=$((failures + 1)); }

for cmd in systemctl git make python3 node npm npx docker flock curl gh; do
  if command -v "${cmd}" >/dev/null 2>&1; then ok "command ${cmd}"; else fail "missing command ${cmd}"; fi
done

if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'; then ok "Python 3.12"; else fail "Python 3.12 required ($(python3 --version 2>&1))"; fi
fi
if command -v node >/dev/null 2>&1; then
  if node -e 'process.exit(Number(process.versions.node.split(".")[0]) === 24 ? 0 : 1)'; then ok "Node 24"; else fail "Node 24 required ($(node --version 2>&1))"; fi
fi

if docker compose version >/dev/null 2>&1; then ok "Docker Compose plugin"; else fail "Docker Compose plugin unavailable"; fi
if docker info >/dev/null 2>&1; then ok "Docker daemon reachable"; else fail "Docker daemon not reachable"; fi

repo=""
if gh auth status >/dev/null 2>&1; then
  ok "GitHub CLI authenticated"
  repo="$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || true)"
  if [ -n "${repo}" ]; then ok "GitHub repository ${repo}"; else fail "cannot resolve GitHub repository from origin"; fi
else
  fail "GitHub CLI is not authenticated; PR status reporting cannot work"
fi

service="rcat-pdf-hub-local-ci.service"
timer="rcat-pdf-hub-local-ci.timer"
if systemctl --user is-enabled "${timer}" >/dev/null 2>&1; then ok "${timer} enabled"; else fail "${timer} not enabled"; fi
if systemctl --user is-active "${timer}" >/dev/null 2>&1; then ok "${timer} active"; else fail "${timer} not active"; fi

if [ -f "${STATE_ROOT}/last-main-pass" ]; then
  last_main="$(cat "${STATE_ROOT}/last-main-pass")"
  current_main="$(git ls-remote origin refs/heads/main 2>/dev/null | awk '{print $1}')"
  if [ -n "${current_main}" ] && [ "${last_main}" = "${current_main}" ]; then
    ok "current main ${current_main} has a recorded full-validation pass"
  else
    fail "last validated main (${last_main}) is not current origin/main (${current_main:-unknown})"
  fi
else
  fail "no ${STATE_ROOT}/last-main-pass record"
fi

if [ -n "${repo}" ]; then
  main_sha="$(gh api "repos/${repo}/git/ref/heads/main" --jq '.object.sha' 2>/dev/null || true)"
  mapfile -t prs < <(gh api --paginate "repos/${repo}/pulls?state=open&base=main&per_page=100" --jq '.[] | select(.draft == false) | [.number,.head.sha,.base.sha] | @tsv' 2>/dev/null || true)
  for row in "${prs[@]}"; do
    IFS=$'\t' read -r pr head_sha base_sha <<<"${row}"
    if [ "${base_sha}" != "${main_sha}" ]; then
      fail "PR #${pr} is based on stale main ${base_sha}"
      continue
    fi
    contexts="$(gh api "repos/${repo}/commits/${head_sha}/status" --jq '.statuses[]?.context' 2>/dev/null | grep '^local-ci/' || true)"
    if [ -n "${contexts}" ]; then
      state="$(gh api "repos/${repo}/commits/${head_sha}/status" --jq '.state' 2>/dev/null || printf unknown)"
      ok "PR #${pr} has local CI status (${state}): $(tr '\n' ',' <<<"${contexts}" | sed 's/,$//')"
    else
      fail "PR #${pr} head ${head_sha} has no local-ci/* commit status"
    fi
  done
fi

if [ "${failures}" -gt 0 ]; then
  printf 'local-ci doctor: FAIL (%d problem(s))\n' "${failures}" >&2
  exit 1
fi
printf 'local-ci doctor: PASS\n'
