#!/usr/bin/env bash
# Read-only DNS/TCP diagnostics from the existing API container.
set -euo pipefail
cd "$(dirname "$0")/.."

compose_args=(-f docker-compose.yml)
case "${PDFHUB_COMPOSE_MODE:-default}" in
  default) ;;
  prod) compose_args+=(-f docker-compose.prod.yml) ;;
  nas) compose_args+=(-f docker-compose.nas.yml) ;;
  prod-nas) compose_args+=(-f docker-compose.prod.yml -f docker-compose.nas.yml) ;;
  *) echo "Set PDFHUB_COMPOSE_MODE to default, prod, nas, or prod-nas" >&2; exit 2 ;;
esac

echo "=== Current Compose services ==="
docker compose "${compose_args[@]}" ps api postgres valkey gotenberg
echo
echo "=== Service DNS/TCP reachability from the API container ==="
docker compose "${compose_args[@]}" exec -T api python - < scripts/doctor-upload-dns.py
