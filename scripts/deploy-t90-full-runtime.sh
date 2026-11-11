#!/usr/bin/env bash
# Host-only single command after root provisioning and protected-main pull.
# Reuses exact-main CI, OIDC+AV policy, fresh verified backup and schema cutover.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "${GITHUB_ACTIONS:-false}" == "true" ]]; then
  echo "T90 full Production runtime refuses GitHub Actions" >&2; exit 2
fi
test -f .env || { echo "Production .env missing" >&2; exit 2; }
for f in compose.t90-code-first.yaml compose.native-sidecar.yaml \
         compose.url-fetcher.yaml compose.t90-full-runtime.yaml; do
  test -f "$f" || { echo "Missing reviewed runtime overlay: $f" >&2; exit 2; }
done
command -v systemctl >/dev/null || { echo "systemd host required" >&2; exit 2; }
systemctl is-active --quiet pdfhub-url-firewall-guard.timer || {
  echo "T90 host firewall lease timer inactive; run root provisioning first" >&2; exit 2;
}
python3 scripts/check-t90-host-url-lease.py
export PDFHUB_T90_PRODUCTION_CODE_ENABLED=true
export PDFHUB_T90_FULL_RUNTIME_ENABLED=true
exec python3 scripts/one-command-release.py
