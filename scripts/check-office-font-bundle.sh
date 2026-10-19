#!/usr/bin/env bash
# Inspect the exact 13Fonts TTF payload INSIDE the running Gotenberg image.
set -euo pipefail
cd "$(dirname "$0")/.."

compose_args=(-f docker-compose.yml)
case "${PDFHUB_COMPOSE_MODE:-default}" in
  default) ;;
  nas) compose_args+=(-f docker-compose.nas.yml) ;;
  prod) compose_args+=(-f docker-compose.prod.yml) ;;
  prod-nas) compose_args+=(-f docker-compose.prod.yml -f docker-compose.nas.yml) ;;
  *) echo "Unknown PDFHUB_COMPOSE_MODE (default, nas, prod, prod-nas)" >&2; exit 2 ;;
esac

# Hash actual files; 'fc-match' silently substitutes fonts and is insufficient.
installed="$(docker compose "${compose_args[@]}" exec -T gotenberg \
  sh -c 'cd /usr/local/share/fonts/rcat/13fonts && sha256sum -- ./*.ttf')"
printf '%s\n' "$installed" | python3 scripts/verify-office-font-bundle.py

# Verify fontconfig indexes all 57 files, not merely fallback font families.
loaded="$(docker compose "${compose_args[@]}" exec -T gotenberg fc-list -f '%{file}\n' \
  | grep '^/usr/local/share/fonts/rcat/13fonts/' | sort -u | wc -l)"
expected="$(python3 -c 'import json; print(json.load(open("ops/gotenberg/13fonts-manifest.json"))["font_count"])')"
if [[ "$loaded" -ne "$expected" ]]; then
  echo "FAIL fontconfig registered only $loaded/$expected expected font files" >&2
  exit 1
fi
echo "PASS fontconfig registered all $loaded/$expected fonts in Gotenberg"
