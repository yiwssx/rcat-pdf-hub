#!/usr/bin/env bash
# Operator-owned, idempotent rule installation on host ONLY.
# Never runs inside Docker, GitHub Actions or a public build.
set -Eeuo pipefail
[[ "${EUID}" -eq 0 ]] || { echo "URL firewall setup requires root" >&2; exit 1; }
ROOT=/usr/local/libexec/pdfhub
command -v iptables >/dev/null || exit 1
if iptables -w -S PDFHUB_T90_URL_EGRESS >/dev/null 2>&1; then
  # Chain exists: verify exact earlier reviewed order, never overwrite it.
  exec bash "$ROOT/verify-host-egress-firewall.sh"
fi
exec bash "$ROOT/install-host-egress-firewall.sh"
