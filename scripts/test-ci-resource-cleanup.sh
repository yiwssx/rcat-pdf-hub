#!/usr/bin/env bash
set -Eeuo pipefail

# No Docker daemon or production resources are used by these regression tests.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

cat > "${tmp}/docker" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$MOCK_DOCKER_LOG"
if [[ "$1" == "compose" ]]; then
  if [[ " $* " == *" down "* ]]; then
    exit "${MOCK_DOWN_FAIL:-0}"
  fi
  exit 0
elif [[ "$1" == "ps" && "$2" == "-aq" ]]; then
  printf '%s' "${MOCK_REFS:-}"
elif [[ "$1" == "volume" && "$2" == "ls" ]]; then
  if [[ " $* " == *" --filter "* ]]; then
    printf '%s' "${MOCK_REMAINING_VOLUMES:-}"
  else
    printf '%s' "${MOCK_VOLUME_LIST:-}"
  fi
elif [[ "$1" == "volume" && "$2" == "inspect" ]]; then
  name="$3"
  if [[ " $* " == *"com.docker.compose.project"* ]]; then
    printf '%s\n' "${MOCK_LABEL_OWNER:-${name%%_*}}"
  else
    printf '%s\n' "${MOCK_LABEL_KEY:-${name#*_}}"
  fi
elif [[ "$1" == "volume" && "$2" == "rm" ]]; then
  printf '%s\n' "$3"
fi
MOCK

chmod +x "${tmp}/docker"
export PATH="${tmp}:${PATH}"
export MOCK_DOCKER_LOG="${tmp}/docker.log"
export CI_CLEANUP_LOCK_FILE="${tmp}/validator.lock"
: > "${MOCK_DOCKER_LOG}"

fail_test() { echo "CI cleanup regression FAIL: $*" >&2; exit 1; }
expect_failure() {
  if "$@" >"${tmp}/case.out" 2>&1; then
    fail_test "unexpected success: $*"
  fi
}
expect_success() {
  if ! "$@" >"${tmp}/case.out" 2>&1; then
    cat "${tmp}/case.out" >&2
    fail_test "unexpected failure: $*"
  fi
}

cd "${ROOT}"

# Scope guard must reject production before calling Docker.
expect_failure bash scripts/cleanup-ci-project.sh pdf-hub runtime
[[ ! -s "${MOCK_DOCKER_LOG}" ]] || fail_test "production rejection touched Docker"

# Successful Promtool cleanup removes volumes (down -v) and verifies absence.
expect_success bash scripts/cleanup-ci-project.sh pdfhub-promtool-123 promtool
grep -q -- '--profile observability down -v --remove-orphans' "${MOCK_DOCKER_LOG}" ||
  fail_test "Promtool cleanup omitted named volume removal"

# Runtime cleanup uses the production Compose overlay and all optional profiles.
: > "${MOCK_DOCKER_LOG}"
expect_success bash scripts/cleanup-ci-project.sh pdfhub-validation-456 runtime
grep -q -- '-f docker-compose.yml -f docker-compose.prod.yml' "${MOCK_DOCKER_LOG}" ||
  fail_test "runtime cleanup omitted production Compose overlay"
grep -q -- 'down -v --remove-orphans' "${MOCK_DOCKER_LOG}" ||
  fail_test "runtime cleanup omitted named volume removal"

# Teardown error or residual resources must fail, never report a green gate.
export MOCK_DOWN_FAIL=1
expect_failure bash scripts/cleanup-ci-project.sh pdfhub-promtool-123 promtool
unset MOCK_DOWN_FAIL
export MOCK_REMAINING_VOLUMES=orphan-id
expect_failure bash scripts/cleanup-ci-project.sh pdfhub-promtool-123 promtool
unset MOCK_REMAINING_VOLUMES
export MOCK_REFS=container-id
expect_failure bash scripts/cleanup-ci-project.sh pdfhub-validation-456 runtime
unset MOCK_REFS

# Historical orphan cleanup: preview-only by default and strict name/labels.
export MOCK_VOLUME_LIST=$'pdfhub-promtool-100_prometheus_data\npdf-hub_pdf_data\n'
: > "${MOCK_DOCKER_LOG}"
expect_success bash scripts/cleanup-orphan-promtool-volumes.sh --dry-run
grep -q -- 'WOULD REMOVE: pdfhub-promtool-100_prometheus_data' "${tmp}/case.out" ||
  fail_test "dry-run did not report safe candidate"
if grep -q 'volume rm' "${MOCK_DOCKER_LOG}"; then
  fail_test "dry-run removed a volume"
fi

expect_failure bash scripts/cleanup-orphan-promtool-volumes.sh --apply
export CI_CLEANUP_CONFIRM=DELETE
export MOCK_LABEL_OWNER=wrong-project
expect_success bash scripts/cleanup-orphan-promtool-volumes.sh --apply
if grep -q 'volume rm' "${MOCK_DOCKER_LOG}"; then
  fail_test "mismatched Compose label allowed deletion"
fi
unset MOCK_LABEL_OWNER
export MOCK_REFS=container-id
expect_success bash scripts/cleanup-orphan-promtool-volumes.sh --apply
if grep -q 'volume rm' "${MOCK_DOCKER_LOG}"; then
  fail_test "referenced volume allowed deletion"
fi
unset MOCK_REFS
expect_success bash scripts/cleanup-orphan-promtool-volumes.sh --apply
grep -q -- 'volume rm pdfhub-promtool-100_prometheus_data' "${MOCK_DOCKER_LOG}" ||
  fail_test "confirmed orphan volume was not removed"
if grep -q -- 'volume rm pdf-hub_pdf_data' "${MOCK_DOCKER_LOG}"; then
  fail_test "production volume was targeted"
fi

echo "CI resource cleanup regression: PASS"
