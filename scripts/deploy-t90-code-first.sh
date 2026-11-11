#!/usr/bin/env bash
# Operator-only: existing RCAT Ubuntu Production host, never GitHub Actions.
# Deploy latest already-checked-out protected main with the source-code-first
# T90 Web/API/worker flags. This does NOT activate native/URL bridges.
# Existing one-command release keeps institution OIDC, exact-SHA CI, verified
# live backup, schema migration, ClamAV and health/ready gates unchanged.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "${GITHUB_ACTIONS:-false}" == "true" ]]; then
  echo "T90 production code rollout refuses GitHub Actions." >&2
  exit 2
fi
test -f .env || { echo "Existing Production .env is missing." >&2; exit 2; }
test -f compose.t90-code-first.yaml || {
  echo "T90 code-first overlay missing." >&2
  exit 2
}
export PDFHUB_T90_PRODUCTION_CODE_ENABLED=true
exec python3 scripts/one-command-release.py
