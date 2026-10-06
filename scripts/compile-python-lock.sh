#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

IMAGE="${PDFHUB_PYTHON_LOCK_IMAGE:-python:3.12.14-slim-bookworm}"
PIP_TOOLS_VERSION="${PDFHUB_PIP_TOOLS_VERSION:-7.5.2}"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }

docker run --rm \
  -e HOST_UID="${HOST_UID}" \
  -e HOST_GID="${HOST_GID}" \
  -v "${ROOT}/apps/api:/work" \
  -w /work \
  "${IMAGE}" \
  sh -ceu '
    python -m pip install --disable-pip-version-check --no-cache-dir "pip-tools=='"${PIP_TOOLS_VERSION}"'" >/dev/null
    pip-compile --quiet --generate-hashes --strip-extras --output-file=requirements.lock requirements.txt
    chown "${HOST_UID}:${HOST_GID}" requirements.lock
  '

python3 scripts/check-python-lock.py
echo "python dependency lock: refreshed"
