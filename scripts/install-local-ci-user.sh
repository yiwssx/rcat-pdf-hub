#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
SERVICE="rcat-pdf-hub-local-ci.service"
TIMER="rcat-pdf-hub-local-ci.timer"

for cmd in systemctl bash git make python3 node npm docker flock curl; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }
done

docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin is required" >&2; exit 1; }
git -C "${ROOT}" remote get-url origin >/dev/null 2>&1 || { echo "Repository must have an origin remote" >&2; exit 1; }

python3 - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"Python 3.12 is required to match the production image; found {sys.version.split()[0]}")
PY
node -e 'const major=Number(process.versions.node.split(".")[0]); if (major !== 24) { console.error(`Node 24 is required to match the production image; found ${process.versions.node}`); process.exit(1); }'

if [[ "${ROOT}" =~ [[:space:]] ]]; then
  echo "Repository path must not contain whitespace for the systemd user service: ${ROOT}" >&2
  exit 1
fi

mkdir -p "${UNIT_DIR}"

cat >"${UNIT_DIR}/${SERVICE}" <<EOF
[Unit]
Description=RCAT PDF Hub zero-cost local validation
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${ROOT}
ExecStart=/usr/bin/env bash ${ROOT}/scripts/local-ci-cycle.sh
Nice=10
EOF

cat >"${UNIT_DIR}/${TIMER}" <<EOF
[Unit]
Description=Run RCAT PDF Hub zero-cost local validation periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
RandomizedDelaySec=30
Unit=${SERVICE}

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "${TIMER}"

echo "Installed ${TIMER}"
echo "Repository: ${ROOT}"
echo "Status: systemctl --user status ${TIMER}"
echo "Logs:   journalctl --user -u ${SERVICE}"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI authentication detected: Dependabot local validation/merge is enabled."
else
  echo "Main validation is enabled. To enable Dependabot local validation/merge, install GitHub CLI and run: gh auth login"
fi
echo "For execution after logout/reboot, an administrator may enable user lingering once; this does not require any paid service."
