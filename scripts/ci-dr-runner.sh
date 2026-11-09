#!/usr/bin/env bash
# Produce only sanitized GitHub evidence for a real, isolated backup restore.
# Raw converter/API/backup logs stay private on the DR host, never in Actions.
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sha="${GITHUB_SHA:-}"
report="${GITHUB_WORKSPACE:-${ROOT}}/dr-evidence.json"
state="${HOME}/.local/state/rcat-pdf-hub-dr"
mkdir -p -- "${state}"
chmod 0700 -- "${state}"
log="${state}/dr-${GITHUB_RUN_ID:-unknown}-${GITHUB_RUN_ATTEMPT:-1}.log"
backup=""

record_failure() {
  python3 scripts/dr-runner-policy.py report \
    --output "${report}" --status FAIL --sha "${sha}" \
    --started "${started}" --exit-code "${1:-1}" \
    ${backup:+--backup "${backup}"}
}

# GitHub credentials are only used to read commit-check evidence. They are
# explicitly removed from the environment passed to the restore process.
if ! python3 - "${sha}" <<'PY'
import json
import os
import re
import subprocess
import sys
from urllib.request import Request, urlopen

sha = sys.argv[1]
if not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("dr-runner: invalid SHA")
current = subprocess.check_output(
    ["git", "ls-remote", "origin", "refs/heads/main"], text=True
).split()[0]
checked_out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
if current != sha or checked_out != sha:
    raise SystemExit("dr-runner: exact current protected main required")
token = os.environ.get("GITHUB_TOKEN", "")
if not token:
    raise SystemExit("dr-runner: read-only GitHub credential missing")
req = Request(
    f"https://api.github.com/repos/yiwssx/rcat-pdf-hub/commits/{sha}/check-runs?per_page=100",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
)
with urlopen(req, timeout=15) as resp:
    data = json.load(resp)
checks = {
    item["name"]: item
    for item in data["check_runs"]
    if item.get("app", {}).get("slug") == "github-actions"
}
required = ("ci/required", "CodeQL (python)", "CodeQL (javascript-typescript)")
if any(checks.get(name, {}).get("conclusion") != "success" for name in required):
    raise SystemExit("dr-runner: required main SHA checks are not all successful")
print("dr-runner: exact protected main and required checks verified")
PY
then
  record_failure 1
  exit 1
fi

# A dedicated rootless Docker socket is *mandatory*. Unique Compose project
# names alone cannot prevent image-tag overwrites on a shared Docker daemon.
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
if ! backup="$(python3 scripts/dr-runner-policy.py select)"; then
  record_failure 2
  exit 1
fi

echo "dr-runner: isolated backup snapshot selected; raw logs remain on private runner"
result=0
# Environment is a whitelist: no Production .env, GitHub token, origin URLs
# or deployment secrets can leak into Docker Compose or the restore process.
timeout 75m env -i \
  PATH="${PATH}" HOME="${HOME}" USER="${USER:-dr-runner}" \
  DOCKER_HOST="${DOCKER_HOST}" \
  PDFHUB_CLAMAV_ENABLED=false \
  bash scripts/dr-drill.sh "${backup}" >"${log}" 2>&1 || result="$?"

if [[ "${result}" -eq 0 ]]; then
  python3 scripts/dr-runner-policy.py report \
    --output "${report}" --status PASS --sha "${sha}" \
    --started "${started}" --exit-code 0 --backup "${backup}"
  echo "dr-runner: PASS — checksum-verified backup restored and probed in isolated rootless Docker"
else
  record_failure "${result}"
  echo "dr-runner: FAIL (exit ${result}); details are in the isolated runner's private log" >&2
  exit 1
fi
