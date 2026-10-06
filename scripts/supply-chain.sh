#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

MODE="${1:-all}"
TRIVY_IMAGE="${PDFHUB_TRIVY_IMAGE:-aquasec/trivy:0.75.0}"
CACHE_VOLUME="${PDFHUB_TRIVY_CACHE_VOLUME:-pdfhub-trivy-cache}"
OUT_DIR="${PDFHUB_SUPPLY_CHAIN_OUT:-${ROOT}/artifacts/supply-chain}"
API_IMAGE="${PDFHUB_SUPPLY_CHAIN_API_IMAGE:-rcat-pdf-hub-api-scan}"
WEB_IMAGE="${PDFHUB_SUPPLY_CHAIN_WEB_IMAGE:-rcat-pdf-hub-web-scan}"
BUILD_IMAGES="${PDFHUB_SUPPLY_CHAIN_BUILD_IMAGES:-true}"
SKIP_API="${PDFHUB_SUPPLY_CHAIN_SKIP_API:-false}"
SKIP_WEB="${PDFHUB_SUPPLY_CHAIN_SKIP_WEB:-false}"

case "${MODE}" in
  source|images|all) ;;
  *) echo "usage: $0 [source|images|all]" >&2; exit 2 ;;
esac

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
mkdir -p "${OUT_DIR}"

trivy_fs() {
  docker run --rm \
    -v "${CACHE_VOLUME}:/root/.cache/trivy" \
    -v "${ROOT}:/work:ro" \
    -v "${OUT_DIR}:/out" \
    "${TRIVY_IMAGE}" fs "$@"
}

trivy_image() {
  docker run --rm \
    -v "${CACHE_VOLUME}:/root/.cache/trivy" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${OUT_DIR}:/out" \
    "${TRIVY_IMAGE}" image "$@"
}

scan_source() {
  echo "supply-chain: generating source CycloneDX SBOM"
  trivy_fs --quiet --format cyclonedx --output /out/source.cdx.json /work

  echo "supply-chain: recording HIGH/CRITICAL dependency findings"
  trivy_fs --quiet --scanners vuln --severity HIGH,CRITICAL --format json \
    --output /out/source-vulnerabilities.json /work

  echo "supply-chain: recording HIGH/CRITICAL configuration findings"
  docker run --rm \
    -v "${CACHE_VOLUME}:/root/.cache/trivy" \
    -v "${ROOT}:/work:ro" \
    -v "${OUT_DIR}:/out" \
    "${TRIVY_IMAGE}" config --quiet --severity HIGH,CRITICAL --format json \
    --output /out/config-findings.json /work

  echo "supply-chain: enforcing fixable CRITICAL dependency gate"
  trivy_fs --quiet --scanners vuln --severity CRITICAL --ignore-unfixed --exit-code 1 /work
}

scan_one_image() {
  local label="$1"
  local image="$2"

  echo "supply-chain: generating ${label} image CycloneDX SBOM"
  trivy_image --quiet --format cyclonedx --output "/out/${label}-image.cdx.json" "${image}"

  echo "supply-chain: recording ${label} HIGH/CRITICAL image findings"
  trivy_image --quiet --severity HIGH,CRITICAL --format json \
    --output "/out/${label}-image-vulnerabilities.json" "${image}"

  echo "supply-chain: enforcing fixable CRITICAL gate for ${label} image"
  trivy_image --quiet --severity CRITICAL --ignore-unfixed --exit-code 1 "${image}"
}

scan_images() {
  if [ "${BUILD_IMAGES}" = "true" ]; then
    if [ "${SKIP_API}" != "true" ]; then
      docker build --pull -t "${API_IMAGE}" apps/api
    fi
    if [ "${SKIP_WEB}" != "true" ]; then
      docker build --pull -t "${WEB_IMAGE}" apps/web
    fi
  fi

  if [ "${SKIP_API}" != "true" ]; then
    scan_one_image api "${API_IMAGE}"
  fi
  if [ "${SKIP_WEB}" != "true" ]; then
    scan_one_image web "${WEB_IMAGE}"
  fi
}

case "${MODE}" in
  source) scan_source ;;
  images) scan_images ;;
  all) scan_source; scan_images ;;
esac

echo "supply-chain: PASS — artifacts in ${OUT_DIR}"
