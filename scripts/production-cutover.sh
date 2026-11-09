#!/usr/bin/env bash
# Guarded production cutover for the institution's own Ubuntu host.
# Modes: check is read-only; deploy is explicit, gated and never automatic.
# Default release requires CI + institutional OIDC + verified live backup;
# a separate opt-in strict mode additionally requires official isolated DR.
# Never run this via a public PR, GitHub-hosted CI job or an arbitrary SSH agent.
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${1:-check}"
case "${MODE}" in check|deploy) ;; *)
  echo "usage: BACKUP=/absolute/snapshot [PDFHUB_COMPOSE_MODE=prod] bash scripts/production-cutover.sh check|deploy" >&2
  exit 2;;
esac
case "${PDFHUB_COMPOSE_MODE:-prod}" in
  prod) compose=(-f docker-compose.yml -f docker-compose.prod.yml) ;;
  prod-nas) compose=(-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.nas.yml) ;;
  *) echo 'cutover: only prod or prod-nas is authorized' >&2; exit 2 ;;
esac
if [[ "${GITHUB_ACTIONS:-false}" == "true" ]]; then
  echo 'cutover: refuses to operate from GitHub Actions' >&2; exit 2
fi
if [[ -z "${BACKUP:-}" || "${BACKUP}" != /* || ! -d "${BACKUP}" ]]; then
  echo 'cutover: BACKUP must be an existing absolute local path' >&2; exit 2
fi
# Standard releases do not need a GitHub self-hosted DR runner. Explicit
# strict DR releases are still fully supported with the original proof gate.
if [[ "${PDFHUB_RELEASE_REQUIRE_DR:-false}" != false && "${PDFHUB_RELEASE_REQUIRE_DR:-false}" != true ]]; then
  echo 'cutover: PDFHUB_RELEASE_REQUIRE_DR must be true or false' >&2; exit 2
fi
strict_dr=false
if [[ "${PDFHUB_RELEASE_REQUIRE_DR:-false}" == true || -n "${DR_RUN_ID:-}" ]]; then
  strict_dr=true
  if [[ ! "${DR_RUN_ID:-}" =~ ^[1-9][0-9]*$ ]]; then
    echo 'cutover: strict DR mode requires a completed, verified GitHub DR_RUN_ID' >&2; exit 2
  fi
fi
for cmd in docker gh git python3 curl; do
  command -v "${cmd}" >/dev/null || { echo "cutover: missing ${cmd}" >&2; exit 2; }
done
docker compose version >/dev/null
test -f .env || { echo 'cutover: existing .env required (never printed or modified)' >&2; exit 1; }
# One explicitly audited host Caddyfile exception is allowed only if the
# local file and .env override match a separately preserved site copy. Other
# tracked edits remain forbidden. Check mode never writes files.
python3 scripts/migrate-site-caddy.py --check || {
  echo 'cutover: unverified tracked modifications detected; refusing release' >&2; exit 1
}
sha="$(git rev-parse HEAD)"
if [[ "${RCAT_DEPLOY_SHA:-${sha}}" != "${sha}" ]]; then
  echo 'cutover: requested release SHA does not match checked-out commit' >&2; exit 1
fi
test "$(gh repo view --json nameWithOwner --jq .nameWithOwner)" = 'yiwssx/rcat-pdf-hub' || {
  echo 'cutover: unexpected GitHub repository' >&2; exit 1;
}
# This proves CI succeeded on the exact current protected main commit.
bash scripts/verify-ci-evidence.sh
# Use only the pre-existing, reviewed OIDC/RCAT/AV policy verifier. No .env dump.
docker compose "${compose[@]}" config --format json | python3 scripts/release1-host-preflight.py
# Verify actual backup contents (not only a directory name or timestamp).
bash scripts/verify-backup.sh "${BACKUP}" >/dev/null

if [[ "${strict_dr}" == true ]]; then
  echo 'cutover: strict mode — verifying official isolated DR restore evidence'
  tmp="$(mktemp -d)"
  trap 'rm -rf -- "${tmp}"' EXIT
  gh api "repos/yiwssx/rcat-pdf-hub/actions/runs/${DR_RUN_ID}" > "${tmp}/run.json"
  # Only download artifacts from the selected official GitHub workflow run.
  gh run download "${DR_RUN_ID}" --repo yiwssx/rcat-pdf-hub \
    --pattern 'rcat-dr-evidence-*' --dir "${tmp}/artifact" >/dev/null
  mapfile -d '' proofs < <(find "${tmp}/artifact" -type f -name dr-evidence.json -print0)
  if [[ "${#proofs[@]}" -ne 1 ]]; then
    echo 'cutover: exactly one private DR evidence report required' >&2; exit 1
  fi
  python3 scripts/verify-release-dr-evidence.py "${tmp}/run.json" "${proofs[0]}" "${BACKUP}" "${sha}"
  echo "cutover: PASS (readiness and matching immutable DR evidence, SHA ${sha:0:12})"

else
  echo 'cutover: standard mode — CI, RCAT policy and live backup verified; automated DR deferred'
fi

if [[ "${MODE}" == check ]]; then
  echo 'cutover: CHECK ONLY — no production services modified'
  exit 0
fi

if [[ "${RCAT_DEPLOY_CONFIRM:-}" != "YES" || "${RCAT_DEPLOY_SHA:-}" != "${sha}" ]]; then
  echo 'cutover: deployment requires RCAT_DEPLOY_CONFIRM=YES and RCAT_DEPLOY_SHA=<exact current main SHA>' >&2
  exit 2
fi

# Backups and restore evidence are prerequisites, never generated just to
# gloss over a failing release gate. Keep database and volumes intact.
dc() { docker compose "${compose[@]}" "$@"; }
services=(api worker-interactive worker worker-heavy cleanup webhook web)
# Optional extra image scans remain available but are not coupled to every
# normal production update; Github CI and dependency gates have already passed.
case "${PDFHUB_RELEASE_EXTRA_SCANS:-false}" in
  true)
    echo 'cutover: additional release supply-chain scans requested'
    make validate-supply-chain-source
    make validate-supply-chain-images
    ;;
  false)
    echo 'cutover: additional Trivy scans deferred; exact protected-main CI verified'
    ;;
  *) echo 'cutover: PDFHUB_RELEASE_EXTRA_SCANS must be true or false' >&2; exit 2 ;;
esac
echo 'cutover: building reviewed application images (existing containers remain running)'
dc build gotenberg "${services[@]}"

# The Production OIDC/AV policy requires ClamAV fail-closed, but the Compose
# service is intentionally hidden behind the optional "security" profile.
# Bring up ONLY the scanner, without starting unrelated profile services or
# stopping existing application writers. Abort before planned downtime if the
# scanner cannot actually respond to a PING through the API data network.
echo 'cutover: ensuring the required ClamAV service is running'
dc --profile security up -d --no-deps clamav >/dev/null
scanner_ready=false
for _ in $(seq 1 90); do
  if dc exec -T api python -c 'from app.malware import ping_clamav; import sys; sys.exit(0 if ping_clamav() else 1)' >/dev/null 2>&1; then
    scanner_ready=true
    break
  fi
  sleep 5
done
if [[ "${scanner_ready}" != true ]]; then
  echo 'cutover: CLAMAV NOT READY — aborting before stopping application writers; inspect clamav logs and memory capacity.' >&2
  exit 1
fi
echo 'cutover: ClamAV PING PASS, safe to proceed with schema migration'
echo 'cutover: stopping writers before the schema migration'
dc stop "${services[@]}" >/dev/null
# One migration under the new image, while old workers cannot write.
if ! dc run --rm --no-deps -T api python -c 'from app.migrate import run_migrations; run_migrations()'; then
  echo 'cutover: MIGRATION FAILED; production writers remain stopped, verified backup retained. Restore under approved incident procedure.' >&2
  exit 1
fi
echo 'cutover: activating reviewed application containers; retaining database, queue and volumes'
# Reconcile the reverse proxy too: its routing/config may have changed.
# Caddy is not stopped before the application containers are ready to start.
dc up -d --no-deps --no-build gotenberg "${services[@]}" caddy >/dev/null

# Get actual Caddy bound interface from the rendered Compose configuration,
# without reading or sourcing shell commands from .env.
hostport="$(dc config --format json | python3 -c '
import json,sys
ports=json.load(sys.stdin)["services"]["caddy"]["ports"]
http=next(p for p in ports if int(p.get("target",0))==80)
host= http.get("host_ip") or "127.0.0.1"
if host in ("0.0.0.0","::"): host="127.0.0.1"
if ":" in host: host="[" + host + "]"
print(str(host) + ":" + str(http["published"]))
')"
ready=false
for _ in $(seq 1 60); do
  if curl -fsS --max-time 4 "http://${hostport}/healthz" >/dev/null 2>&1 && \
     curl -fsS --max-time 4 "http://${hostport}/readyz" >/dev/null 2>&1; then
    ready=true; break
  fi
  sleep 2
done
if [[ "${ready}" != true ]]; then
  echo 'cutover: READINESS FAILED. Do not claim success. Verified backup and old commit history preserved; restore requires incident-controlled rollback.' >&2
  exit 1
fi
echo "cutover: DEPLOYED ${sha} (healthz/readyz PASS)"
