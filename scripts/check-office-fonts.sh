#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

compose_args=(-f docker-compose.yml)
case "${PDFHUB_COMPOSE_MODE:-default}" in
  default) ;;
  nas) compose_args+=(-f docker-compose.nas.yml) ;;
  prod) compose_args+=(-f docker-compose.prod.yml) ;;
  prod-nas) compose_args+=(-f docker-compose.prod.yml -f docker-compose.nas.yml) ;;
  *)
    echo "Unknown PDFHUB_COMPOSE_MODE (use default, nas, prod, or prod-nas)" >&2
    exit 2
    ;;
esac

echo "Checking fonts inside the running Gotenberg container..."
if ! installed="$(docker compose "${compose_args[@]}" exec -T gotenberg fc-list -f '%{family}\n')"; then
  echo "Unable to inspect Gotenberg. Start the service first." >&2
  exit 1
fi

# Inspect installed family names (NOT fc-match, which silently substitutes fonts).
families="$(printf '%s\n' "$installed" | tr ',' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | sort -fu)"

if (( $# == 0 )); then
  echo "Relevant installed Thai font families (sample):"
  printf '%s\n' "$families" | grep -Ei 'thai|sarabun|tlwg|garuda|kinnari|loma|umpush|waree|purisa|norasi' || true
  echo
  echo 'To REQUIRE exact fonts: bash scripts/check-office-fonts.sh "TH Sarabun New" "TH SarabunPSK"'
  echo "A close-looking fallback can still change pagination."
  exit 0
fi

missing=0
for wanted in "$@"; do
  if printf '%s\n' "$families" | grep -Fxiq -- "$wanted"; then
    echo "PASS exact font family: $wanted"
  else
    echo "FAIL missing font family: $wanted (LibreOffice will use a substitute)" >&2
    missing=1
  fi
done
exit "$missing"
