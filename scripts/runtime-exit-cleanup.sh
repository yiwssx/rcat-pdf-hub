#!/usr/bin/env bash
# Sourced by scripts/validate-free.sh. All cleanup targets are captured at trap
# installation time: function-local Bash variables may be out of scope at EXIT.
# Only the existing guarded CI cleanup scripts may remove Docker/NAS resources.

runtime_cleanup_resources() {
  local ci_project="${1:?CI project required}"
  local ci_nas_dir="${2:?CI NAS path required}"
  local cleanup_failed=0

  if ! bash scripts/cleanup-ci-project.sh "${ci_project}" runtime; then
    echo "runtime: CI resource cleanup failed for ${ci_project}" >&2
    cleanup_failed=1
  fi
  # A bind-mounted NAS placeholder must be removed only by its strict helper.
  if ! bash scripts/ci-nas-dir.sh remove "${ci_nas_dir}"; then
    echo "runtime: failed to remove temporary NAS directory" >&2
    cleanup_failed=1
  fi
  return "${cleanup_failed}"
}

runtime_cleanup_on_exit() {
  local original_status="${1:?Exit status required}"
  local ci_project="${2:?CI project required}"
  local ci_nas_dir="${3:?CI NAS path required}"
  trap - EXIT
  # Preserve a failing root-cause exit status even when cleanup also fails.
  if ! runtime_cleanup_resources "${ci_project}" "${ci_nas_dir}"; then
    if [[ "${original_status}" -eq 0 ]]; then original_status=1; fi
  fi
  exit "${original_status}"
}

runtime_cleanup_install() {
  local ci_project="${1:?CI project required}"
  local ci_nas_dir="${2:?CI NAS path required}"
  local handler
  [[ "${ci_project}" =~ ^pdfhub-validation-[0-9]+$ ]] || return 2
  [[ "${ci_nas_dir}" =~ ^/tmp/pdfhub-validation-nas-[0-9]+$ ]] || return 2

  # %q shell-quotes immutable target arguments while $? is evaluated at EXIT.
  printf -v handler 'runtime_cleanup_on_exit "$?" %q %q' "${ci_project}" "${ci_nas_dir}"
  trap "${handler}" EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  trap 'exit 129' HUP
}

runtime_cleanup_finish() {
  # Normal path: retire traps before explicit, once-only cleanup. A failure
  # is returned to the caller and must not print a successful runtime gate.
  trap - EXIT INT TERM HUP
  runtime_cleanup_resources "${1:?CI project required}" "${2:?CI NAS path required}"
}
