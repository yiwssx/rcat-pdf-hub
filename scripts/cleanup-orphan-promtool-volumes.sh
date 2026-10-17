#!/usr/bin/env bash
set -Eeuo pipefail

# Operator-only retirement of orphaned volumes created by Prometheus config CI.
# Default is read-only. This NEVER selects pdf-hub production volumes.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode="${1:---dry-run}"
if [[ "$#" -gt 1 || ( "${mode}" != "--dry-run" && "${mode}" != "--apply" ) ]]; then
  echo "Usage: bash $0 [--dry-run|--apply]" >&2
  exit 2
fi

if [[ "${mode}" == "--apply" ]]; then
  [[ "${CI_CLEANUP_CONFIRM:-}" == "DELETE" ]] || {
    echo "Refusing deletion without CI_CLEANUP_CONFIRM=DELETE" >&2
    exit 2
  }
  mkdir -p "${ROOT}/.local-ci"
  exec 9>"${ROOT}/.local-ci/validator.lock"
  if ! flock -n 9; then
    echo "Local CI validation is running; retry after its cycle completes." >&2
    exit 1
  fi
fi

all_volumes="$(docker volume ls -q)"
mapfile -t names <<<"${all_volumes}"
candidates=0
removed=0
skipped=0

for volume_name in "${names[@]}"; do
  if [[ ! "${volume_name}" =~ ^(pdfhub-promtool-[0-9]+)_(prometheus_data|alertmanager_data|tempo_data)$ ]]; then
    continue
  fi
  project_name="${BASH_REMATCH[1]}"
  volume_key="${BASH_REMATCH[2]}"

  owner="$(docker volume inspect "${volume_name}" --format '{{index .Labels "com.docker.compose.project"}}')"
  compose_key="$(docker volume inspect "${volume_name}" --format '{{index .Labels "com.docker.compose.volume"}}')"
  if [[ "${owner}" != "${project_name}" || "${compose_key}" != "${volume_key}" ]]; then
    printf 'SKIP label mismatch: %s (project=%s, key=%s)\n' "${volume_name}" "${owner}" "${compose_key}" >&2
    skipped=$((skipped + 1))
    continue
  fi

  references="$(docker ps -aq --filter "volume=${volume_name}")"
  if [[ -n "${references}" ]]; then
    printf 'SKIP referenced by container(s): %s\n' "${volume_name}" >&2
    skipped=$((skipped + 1))
    continue
  fi

  candidates=$((candidates + 1))
  if [[ "${mode}" == "--dry-run" ]]; then
    printf 'WOULD REMOVE: %s\n' "${volume_name}"
  else
    # Check again immediately before each deletion. Never use a force flag.
    if [[ -n "$(docker ps -aq --filter "volume=${volume_name}")" ]]; then
      printf 'SKIP newly referenced: %s\n' "${volume_name}" >&2
      skipped=$((skipped + 1))
      continue
    fi
    docker volume rm "${volume_name}"
    removed=$((removed + 1))
  fi
done

printf 'promtool cleanup: mode=%s eligible=%d removed=%d skipped=%d\n' \
  "${mode}" "${candidates}" "${removed}" "${skipped}"
