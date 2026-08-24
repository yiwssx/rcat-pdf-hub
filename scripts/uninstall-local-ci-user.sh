#!/usr/bin/env bash
set -Eeuo pipefail

UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
SERVICE="rcat-pdf-hub-local-ci.service"
TIMER="rcat-pdf-hub-local-ci.timer"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now "${TIMER}" >/dev/null 2>&1 || true
  systemctl --user stop "${SERVICE}" >/dev/null 2>&1 || true
fi

rm -f "${UNIT_DIR}/${SERVICE}" "${UNIT_DIR}/${TIMER}"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user reset-failed >/dev/null 2>&1 || true
fi

echo "Removed RCAT PDF Hub local CI user service/timer"
