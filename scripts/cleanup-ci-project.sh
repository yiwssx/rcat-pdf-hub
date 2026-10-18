#!/usr/bin/env bash
set -Eeuo pipefail

# Clean exactly one ephemeral CI Compose project. Never accepts the production
# "pdf-hub" project or an arbitrary Compose project name.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

project="${1:-}"
kind="${2:-}"
if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 <pdfhub-promtool-N|pdfhub-validation-N> <promtool|runtime>" >&2
  exit 2
fi

compose=(docker compose -p "${project}")
case "${kind}" in
  promtool)
    [[ "${project}" =~ ^pdfhub-promtool-[0-9]+$ ]] || {
      echo "Refusing cleanup of non-promtool project: ${project}" >&2
      exit 2
    }
    profiles=(--profile observability)
    ;;
  runtime)
    [[ "${project}" =~ ^pdfhub-validation-[0-9]+$ ]] || {
      echo "Refusing cleanup of non-validation project: ${project}" >&2
      exit 2
    }
    compose+=(-f docker-compose.yml -f docker-compose.prod.yml)
    profiles=(--profile s3 --profile security --profile observability --profile archive)
    ;;
  *)
    echo "Unknown CI cleanup kind: ${kind}" >&2
    exit 2
    ;;
esac

if ! "${compose[@]}" "${profiles[@]}" down -v --remove-orphans; then
  echo "ci-cleanup: Docker Compose cleanup FAILED for ${project}" >&2
  exit 1
fi

# Compose may return success while leaving a resource behind. Verify ownership
# using Compose labels, not a broad name prefix or global Docker prune.
remaining_containers="$(docker ps -aq --filter "label=com.docker.compose.project=${project}")"
remaining_volumes="$(docker volume ls -q --filter "label=com.docker.compose.project=${project}")"
if [[ -n "${remaining_containers}" || -n "${remaining_volumes}" ]]; then
  echo "ci-cleanup: residual resources for ${project}" >&2
  [[ -z "${remaining_containers}" ]] || printf 'Containers:\n%s\n' "${remaining_containers}" >&2
  [[ -z "${remaining_volumes}" ]] || printf 'Volumes:\n%s\n' "${remaining_volumes}" >&2
  exit 1
fi

echo "ci-cleanup: PASS ${project} (containers and named volumes absent)"
