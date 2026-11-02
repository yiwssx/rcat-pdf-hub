#!/usr/bin/env bash
# T90-2 SAFE READ-ONLY host preflight.
# Use on the RCAT PDF Hub Docker host after checking out the feature branch.
# No feature flags are enabled, no tests modify stored documents, no containers
# are built/recreated and NO firewall changes are made by this script.
set -u

# Prefer the caller\u0027s existing RCAT checkout so a detached QA script can
# audit the live Compose project without switching production branches.
if [[ -f "$PWD/docker-compose.yml" ]]; then
  ROOT="$PWD"
else
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
if [[ ! -f "$ROOT/docker-compose.yml" ]]; then
  echo "No RCAT docker-compose.yml in current checkout; refusing mismatched host inspection" >&2
  exit 2
fi
cd "$ROOT" || exit 2
echo "T90-2 READ-ONLY HOST PREFLIGHT"
date -Is
echo "Repository commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "Repository branch: $(git branch --show-current 2>/dev/null || echo unknown)"
echo "Host kernel: $(uname -r)"
echo "Host UID: $(id -u)"
echo
echo "=== DOCKER / COMPOSE (no start or build) ==="
if command -v docker >/dev/null 2>&1; then
  docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}}' || true
  docker compose version || true
  docker info --format 'Security={{json .SecurityOptions}}' || true
  docker compose -f docker-compose.yml ps || true
else
  echo "BLOCKED: Docker CLI not available on this host"
fi
echo
echo "=== HOST BINARIES (only versions; no conversions) ==="
for tool in bwrap heif-dec dwgread wps2odt iptables nft; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "FOUND $tool at $(command -v "$tool")"
    case "$tool" in
      heif-dec) "$tool" --version 2>&1 | head -3 || true ;;
      bwrap) "$tool" --version 2>&1 | head -3 || true ;;
    esac
  else
    echo "MISSING $tool"
  fi
done
echo
echo "=== API CONTAINER NATIVE RUNTIMES (read-only queries) ==="
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.yml exec -T api sh -c '
    id
    for tool in bwrap heif-dec dwgread wps2odt; do
      command -v "$tool" || echo "MISSING $tool"
    done
    python - <<PY
import pathlib, os, sys
print("python=",sys.version.split()[0])
for f in (
    "/opt/pdfhub/heif/bin/heif-dec",
    "/opt/pdfhub/heif/lib/libheif.so.1",
    "/opt/pdfhub/cad/bin/dwgread",
    "/usr/bin/bwrap",
    "/usr/bin/wps2odt",
):
    p=pathlib.Path(f)
    print(f,"present=",p.is_file(),"symlink=",p.is_symlink())
PY
  ' || echo "BLOCKED: Could not inspect running API container"
fi
echo
echo "=== OUTSTANDING MANUAL GATES ==="
echo "1. Target-host Bubblewrap unprivileged namespace + no-network validation"
echo "2. Patched libheif >=1.23.7 and externally audited binary/plugin hashes"
echo "3. Real-source HEIC HEIF DWG CHM Works corpus with golden PDF comparisons"
echo "4. URL firewall backend, packet-level private/metadata denial and lease"
echo "5. Pinned image / complete CI before any VERIFIED/RELEASED promotion"
echo "Preflight completed. No production settings or firewall rules changed."
