#!/usr/bin/env bash
set -Eeuo pipefail

# Scope-safe runtime EXIT trap regression. Uses a fake Docker CLI and real
# strictly guarded temporary NAS directories; never contacts production.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

mkdir -p "${tmp}/bin"
cat > "${tmp}/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "${MOCK_DOCKER_LOG}"
if [[ "${1:-}" == "compose" ]]; then
  if [[ " $* " == *" down "* ]]; then
    if [[ "${MOCK_DOWN_FAIL:-0}" == "1" ]]; then exit 27; fi
    rm -f -- "${MOCK_RESOURCE_DIR}/container" "${MOCK_RESOURCE_DIR}/volume"
    exit 0
  fi
  if [[ " $* " == *" up "* ]]; then
    echo 'mock: container image missing before services healthy' >&2
    exit 32
  fi
  exit 0
elif [[ "${1:-}" == "ps" && "${2:-}" == "-aq" ]]; then
  [[ ! -f "${MOCK_RESOURCE_DIR}/container" ]] || printf 'mock-container\n'
elif [[ "${1:-}" == "volume" && "${2:-}" == "ls" ]]; then
  [[ ! -f "${MOCK_RESOURCE_DIR}/volume" ]] || printf 'mock-volume\n'
else
  echo "Unexpected Docker command: $*" >&2
  exit 99
fi
MOCK
chmod +x "${tmp}/bin/docker"

fail_test() { echo "runtime EXIT trap regression FAIL: $*" >&2; exit 1; }

run_case() {
  local case_name="$1" expected_status="$2"
  local workspace="${tmp}/${case_name}" actual=0
  mkdir -p "${workspace}"
  printf 'partial container\n' > "${workspace}/container"
  printf 'partial named volume\n' > "${workspace}/volume"
  export PATH="${tmp}/bin:${PATH}"
  export MOCK_RESOURCE_DIR="${workspace}"
  export MOCK_DOCKER_LOG="${workspace}/docker.log"
  export TEST_EXIT_CASE="${case_name}"
  if [[ "${case_name}" == "down-fails" ]]; then
    export MOCK_DOWN_FAIL=1
  else
    unset MOCK_DOWN_FAIL || true
  fi

  bash -c '
    set -Eeuo pipefail
    source scripts/runtime-exit-cleanup.sh
    simulate_runtime() {
      local project="pdfhub-validation-$$"
      local nas_dir="/tmp/pdfhub-validation-nas-$$"
      printf "%s\n" "$nas_dir" > "$MOCK_RESOURCE_DIR/nas_path"
      bash scripts/ci-nas-dir.sh create "$nas_dir"
      runtime_cleanup_install "$project" "$nas_dir"
      if [[ "$TEST_EXIT_CASE" == "success" ]]; then
        runtime_cleanup_finish "$project" "$nas_dir"
      else
        # Simulate a failed Compose up *after* resources were partially created.
        docker compose -p "$project" up -d --wait
      fi
    }
    simulate_runtime
  ' >"${workspace}/output" 2>&1 || actual="$?"

  [[ "${actual}" -eq "${expected_status}" ]] ||
    { cat "${workspace}/output" >&2; fail_test "${case_name}: expected exit ${expected_status}, got ${actual}"; }
  local nas_dir
  nas_dir="$(cat "${workspace}/nas_path")"
  [[ ! -e "${nas_dir}" && ! -L "${nas_dir}" ]] ||
    fail_test "${case_name}: temporary NAS directory was not removed"

  grep -q -- 'down -v --remove-orphans' "${workspace}/docker.log" ||
    fail_test "${case_name}: missing scoped Compose volume cleanup"
  ! grep -q -- 'unbound variable' "${workspace}/output" ||
    fail_test "${case_name}: cleanup still uses an out-of-scope variable"
  if [[ "${case_name}" == "down-fails" ]]; then
    grep -q -- 'runtime: CI resource cleanup failed' "${workspace}/output" ||
      fail_test "${case_name}: cleanup failure was not reported"
    [[ -e "${workspace}/container" && -e "${workspace}/volume" ]] ||
      fail_test "${case_name}: failed down unexpectedly altered evidence"
  else
    [[ ! -e "${workspace}/container" && ! -e "${workspace}/volume" ]] ||
      fail_test "${case_name}: mock Compose resources remain after cleanup"
  fi
}

run_case early-up-failure 32
run_case down-fails 32
run_case success 0

echo "runtime EXIT cleanup (missing image, failed down, normal success): PASS"
