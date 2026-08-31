#!/usr/bin/env bash
set -Eeuo pipefail

UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
SERVICE="rcat-pdf-hub-backup.service"
TIMER="rcat-pdf-hub-backup.timer"

systemctl --user disable --now "${TIMER}" >/dev/null 2>&1 || true
rm -f "${UNIT_DIR}/${SERVICE}" "${UNIT_DIR}/${TIMER}"
systemctl --user daemon-reload
systemctl --user reset-failed "${SERVICE}" >/dev/null 2>&1 || true
printf 'Uninstalled %s\n' "${TIMER}"
