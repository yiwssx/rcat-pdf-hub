#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PROJECT="${PDFHUB_COMPOSE_PROJECT:?set PDFHUB_COMPOSE_PROJECT to the running production Compose project}"

dc() {
  docker compose -p "${PROJECT}" -f docker-compose.yml -f docker-compose.prod.yml "$@"
}

require_running() {
  local service="$1"
  local cid
  cid="$(dc ps -q "${service}")"
  [ -n "${cid}" ] || { echo "hardening: ${service} is not running" >&2; exit 1; }
  printf '%s' "${cid}"
}

check_resource_bounds() {
  local service="$1"
  local cid pids memory nano_cpus
  cid="$(require_running "${service}")"
  pids="$(docker inspect -f '{{.HostConfig.PidsLimit}}' "${cid}")"
  memory="$(docker inspect -f '{{.HostConfig.Memory}}' "${cid}")"
  nano_cpus="$(docker inspect -f '{{.HostConfig.NanoCpus}}' "${cid}")"
  [ "${pids}" -gt 0 ] || { echo "hardening: ${service} has no PID limit" >&2; exit 1; }
  [ "${memory}" -gt 0 ] || { echo "hardening: ${service} has no memory limit" >&2; exit 1; }
  [ "${nano_cpus}" -gt 0 ] || { echo "hardening: ${service} has no CPU limit" >&2; exit 1; }
}

check_no_new_privileges() {
  local service="$1"
  local cid options
  cid="$(require_running "${service}")"
  options="$(docker inspect -f '{{json .HostConfig.SecurityOpt}}' "${cid}")"
  grep -q 'no-new-privileges' <<<"${options}" || {
    echo "hardening: ${service} is missing no-new-privileges" >&2
    exit 1
  }
}

check_app_sandbox() {
  local service="$1"
  local cid readonly caps tmpfs
  cid="$(require_running "${service}")"
  readonly="$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "${cid}")"
  caps="$(docker inspect -f '{{json .HostConfig.CapDrop}}' "${cid}")"
  tmpfs="$(docker inspect -f '{{json .HostConfig.Tmpfs}}' "${cid}")"

  [ "${readonly}" = "true" ] || { echo "hardening: ${service} root filesystem is writable" >&2; exit 1; }
  grep -q '"ALL"' <<<"${caps}" || { echo "hardening: ${service} does not drop all capabilities" >&2; exit 1; }
  grep -q '"/tmp"' <<<"${tmpfs}" || { echo "hardening: ${service} is missing writable /tmp tmpfs" >&2; exit 1; }
  check_no_new_privileges "${service}"
}

for service in postgres valkey gotenberg api worker cleanup webhook web caddy; do
  check_resource_bounds "${service}"
done

for service in valkey gotenberg caddy; do
  check_no_new_privileges "${service}"
done

for service in api worker cleanup webhook web; do
  check_app_sandbox "${service}"
done

dc exec -T api sh -ceu 'touch /tmp/pdfhub-hardening-probe && rm /tmp/pdfhub-hardening-probe'
dc exec -T web sh -ceu 'touch /tmp/pdfhub-hardening-probe && rm /tmp/pdfhub-hardening-probe'

echo "container hardening: PASS"
