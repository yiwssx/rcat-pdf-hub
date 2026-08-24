#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
SERVICE="rcat-pdf-hub-local-ci.service"
TIMER="rcat-pdf-hub-local-ci.timer"

command -v systemctl >/dev/null 2>&1 || { echo "systemd/systemctl is required" >&2; exit 1; }
command -v bash >/dev/null 2>&1 || { echo "bash is required" >&2; exit 1; }

mkdir -p "${UNIT_DIR}"

cat >"${UNIT_DIR}/${SERVICE}" <<EOF
[Unit]
Description=RCAT PDF Hub zero-cost local validation
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory="${ROOT}"
ExecStart=/usr/bin/env bash "${ROOT}/scripts/local-ci-cycle.sh"
Nice=10

[Install]
WantedBy=default.target
EOF

cat >"${UNIT_DIR}/${TIMER}" <<EOF
[Unit]
Description=Run RCAT PDF Hub zero-cost local validation periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
RandomizedDelaySec=30
Persistent=true
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
echo "For Dependabot merge automation, install GitHub CLI and run: gh auth login"
echo "For execution after logout/reboot, an administrator may enable user lingering once; this does not require any paid service."
