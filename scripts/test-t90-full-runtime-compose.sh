#!/usr/bin/env bash
# Disposable CI-only Compose shape validation. No host firewall manipulation,
# Docker builds, actual credentials, format QA or Production effects.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
unlock="$(python3 -c 'import base64;print(base64.urlsafe_b64encode(bytes([1])*32).decode())')"
protect="$(python3 -c 'import base64;print(base64.urlsafe_b64encode(bytes([2])*32).decode())')"
export PDFHUB_RCAT_INSTITUTIONAL_ONLY=true
export PDFHUB_OIDC_ENABLED=true
export PDFHUB_OIDC_ISSUER=https://accounts.google.com
export PDFHUB_OIDC_CLIENT_ID=ci-nonprod-example-client
export PDFHUB_OIDC_CLIENT_SECRET=ci-nonprod-example-secret
export PDFHUB_LDAP_ENABLED=false
export PDFHUB_CLAMAV_ENABLED=true
export PDFHUB_CLAMAV_FAIL_CLOSED=true
export PDFHUB_SESSION_COOKIE_SECURE=true
export PDFHUB_WEB_CONSOLE_AUTO_LOGIN=false
export PDFHUB_PUBLIC_BASE_URL=https://pdf.rcat.ac.th
export PDFHUB_UNLOCK_PDF_HANDOFF_KEY="$unlock"
export PDFHUB_PROTECT_PDF_HANDOFF_KEY="$protect"
export PDFHUB_NATIVE_SIDECAR_SHARED_SECRET="$(printf '%064d' 1)"
export PDFHUB_URL_FETCHER_SHARED_SECRET="$(printf '%064d' 2)"
# Simulate a Host-selected /28, not the legacy hard-coded subnet.
export PDFHUB_URL_EGRESS_SUBNET=10.254.240.0/28
export PDFHUB_URL_EGRESS_IPV4=10.254.240.2
docker compose -p pdfhub-t90-runtime-ci \
  -f docker-compose.yml -f docker-compose.prod.yml \
  -f compose.t90-code-first.yaml \
  -f compose.native-sidecar.yaml \
  -f compose.url-fetcher.yaml \
  -f compose.t90-full-runtime.yaml \
  --profile native-dev --profile url-import-dev \
  config --format json |
  python3 scripts/release1-host-preflight.py
echo "T90 full-runtime Compose config: PASS (CI-only synthetic secrets)"
