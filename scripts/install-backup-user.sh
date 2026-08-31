#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
SERVICE="rcat-pdf-hub-backup.service"
TIMER="rcat-pdf-hub-backup.timer"
BACKUP_ROOT="${PDFHUB_BACKUP_ROOT:-${ROOT}/backups}"
RETENTION_DAYS="${PDFHUB_BACKUP_RETENTION_DAYS:-14}"
ON_CALENDAR="${PDFHUB_BACKUP_ON_CALENDAR:-*-*-* 02:30:00}"

for cmd in systemctl bash docker sha256sum git; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo "Docker Compose plugin is required" >&2; exit 1; }

if [[ "${ROOT}" =~ [[:space:]] ]] || [[ "${BACKUP_ROOT}" =~ [[:space:]] ]]; then
  echo "Repository and backup paths must not contain whitespace for this systemd unit" >&2
  exit 1
fi
mkdir -p "${UNIT_DIR}" "${BACKUP_ROOT}"

cat >"${UNIT_DIR}/${SERVICE}" <<EOF
[Unit]
Description=RCAT PDF Hub consistent backup
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${ROOT}
Environment=PDFHUB_BACKUP_ROOT=${BACKUP_ROOT}
Environment=PDFHUB_BACKUP_RETENTION_DAYS=${RETENTION_DAYS}
ExecStart=/usr/bin/env bash ${ROOT}/scripts/backup.sh
Nice=10
EOF

cat >"${UNIT_DIR}/${TIMER}" <<EOF
[Unit]
Description=Run RCAT PDF Hub backup daily

[Timer]
OnCalendar=${ON_CALENDAR}
Persistent=true
RandomizedDelaySec=5m
Unit=${SERVICE}

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "${TIMER}"
printf 'Installed %s\nBackup root: %s\nRetention: %s days\nSchedule: %s\n' "${TIMER}" "${BACKUP_ROOT}" "${RETENTION_DAYS}" "${ON_CALENDAR}"
