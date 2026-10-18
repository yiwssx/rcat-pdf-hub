#!/usr/bin/env bash
set -Eeuo pipefail

# Only the ephemeral /tmp bind-mount directory created by runtime validation
# can be created/removed here. Never recursively delete a directory.
action="${1:-}"
nas_dir="${2:-}"

if [[ "$#" -ne 2 || ! "${nas_dir}" =~ ^/tmp/pdfhub-validation-nas-[0-9]+$ ]]; then
  echo "ci-nas: refusing unexpected path (expected /tmp/pdfhub-validation-nas-<PID>)" >&2
  exit 2
fi

case "${action}" in
  create)
    # Docker Compose creates missing bind-mount host directories as root. The
    # caller must own the mount source *before* Docker creates any containers.
    if [[ -e "${nas_dir}" || -L "${nas_dir}" ]]; then
      echo "ci-nas: refusing existing path: ${nas_dir}" >&2
      exit 1
    fi
    mkdir -m 0700 -- "${nas_dir}"
    ;;
  remove)
    if [[ ! -d "${nas_dir}" || -L "${nas_dir}" ]]; then
      echo "ci-nas: refusing missing or non-directory path: ${nas_dir}" >&2
      exit 1
    fi
    owner="$(stat -c '%u' -- "${nas_dir}")"
    if [[ "${owner}" != "$(id -u)" ]]; then
      echo "ci-nas: unsafe owner uid=${owner} for ${nas_dir}; not removing" >&2
      exit 1
    fi
    # Local runtime uses the regular pdf_data named volume; this NAS bind
    # mount is a disposable placeholder and should remain empty.
    # If a test unexpectedly wrote files here, FAIL and preserve evidence.
    if ! rmdir -- "${nas_dir}"; then
      echo "ci-nas: temporary bind directory not empty or not removable: ${nas_dir}" >&2
      exit 1
    fi
    ;;
  *)
    echo "Usage: bash scripts/ci-nas-dir.sh <create|remove> /tmp/pdfhub-validation-nas-<PID>" >&2
    exit 2
    ;;
esac
