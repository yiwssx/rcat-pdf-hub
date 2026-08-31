#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_DIR="${1:-${BACKUP:-}}"
REQUIRE_QUIESCED="${PDFHUB_BACKUP_REQUIRE_QUIESCED:-false}"
if [ -z "${BACKUP_DIR}" ]; then
  echo "Usage: $0 <backup-directory>" >&2
  exit 2
fi
case "${REQUIRE_QUIESCED}" in true|false) ;; *) echo "PDFHUB_BACKUP_REQUIRE_QUIESCED must be true or false" >&2; exit 2 ;; esac

for cmd in sha256sum python3; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing required command: ${cmd}" >&2; exit 1; }
done

[ -d "${BACKUP_DIR}" ] || { echo "Backup directory not found: ${BACKUP_DIR}" >&2; exit 1; }
[ -f "${BACKUP_DIR}/manifest.env" ] || { echo "Missing manifest.env" >&2; exit 1; }
[ -f "${BACKUP_DIR}/SHA256SUMS" ] || { echo "Missing SHA256SUMS" >&2; exit 1; }
[ -f "${BACKUP_DIR}/postgres.dump" ] || { echo "Missing postgres.dump" >&2; exit 1; }

(
  cd "${BACKUP_DIR}"
  sha256sum -c SHA256SUMS
)

# Read only fixed keys written by backup.sh; never source arbitrary backup content.
backup_format="$(sed -n 's/^PDFHUB_BACKUP_FORMAT=//p' "${BACKUP_DIR}/manifest.env")"
storage_backend="$(sed -n 's/^PDFHUB_STORAGE_BACKEND=//p' "${BACKUP_DIR}/manifest.env")"
consistency="$(sed -n 's/^PDFHUB_BACKUP_CONSISTENCY=//p' "${BACKUP_DIR}/manifest.env")"
case "${backup_format}" in 1|2) ;; *) echo "Unsupported backup format: ${backup_format}" >&2; exit 1 ;; esac
if [ "${backup_format}" = "2" ]; then
  case "${consistency}" in quiesced|live) ;; *) echo "Invalid backup consistency: ${consistency}" >&2; exit 1 ;; esac
else
  consistency="legacy-unknown"
fi
if [ "${REQUIRE_QUIESCED}" = "true" ] && [ "${consistency}" != "quiesced" ]; then
  echo "Production restore requires a quiesced format-2 backup; found consistency=${consistency}" >&2
  exit 1
fi

python3 - "${BACKUP_DIR}/postgres.dump" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
if path.stat().st_size < 5 or path.read_bytes()[:5] != b"PGDMP":
    raise SystemExit("postgres.dump is not a PostgreSQL custom-format dump")
PY

case "${storage_backend}" in
  local) archive="${BACKUP_DIR}/pdf-data.tar.gz" ;;
  s3) archive="${BACKUP_DIR}/s3-objects.tar.gz" ;;
  *) echo "Unsupported storage backend in manifest: ${storage_backend}" >&2; exit 1 ;;
esac
[ -f "${archive}" ] || { echo "Missing storage archive: ${archive}" >&2; exit 1; }

python3 - "${archive}" <<'PY'
from pathlib import Path, PurePosixPath
import sys, tarfile
archive = Path(sys.argv[1])
with tarfile.open(archive, "r:gz") as tf:
    count = 0
    for member in tf:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"Unsafe archive member: {member.name!r}")
        count += 1
print(f"archive members: {count}")
PY

printf 'backup verification: PASS (%s, consistency=%s)\n' "${storage_backend}" "${consistency}"
