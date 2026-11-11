#!/usr/bin/env bash
# Disposable GitHub Actions acceptance ONLY. Never execute against RCAT host.
# This creates a temporary bridged service on an isolated GitHub runner and
# installs the repo's exact reviewed iptables rule set, never a fake marker.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true ]] || {
  echo "Refusing T33 firewall CI exercise outside GitHub's disposable runner" >&2
  exit 2
}
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bridge=rcat-t90-url-public-qa
internal=rcat-t90-url-internal-qa
cleanup() {
  docker rm -f t90-url-fetcher t90-url-gotenberg >/dev/null 2>&1 || true
  docker network rm "$internal" "$bridge" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker build --build-arg PDFHUB_NATIVE_ONLY=1 -t t90-url-app-qa apps/api
docker build -t t90-url-gotenberg-qa ops/gotenberg
docker build -f ops/url-fetcher/Dockerfile -t t90-url-fetcher-qa .
# The exact static bridge name/IP are required by the verified host policy.
docker network create -d bridge --subnet 172.30.243.0/28 \
  --gateway 172.30.243.1 -o com.docker.network.bridge.name=br-pdfhub-url "$bridge"
docker network create -d bridge --internal "$internal"
# The CI host really installs and attests active INPUT/FORWARD rules; never
# simply generate a boot-id marker to fool the sidecar.
sudo bash ops/url-fetcher/install-host-egress-firewall.sh
sudo bash ops/url-fetcher/verify-host-egress-firewall.sh
test -s /etc/pdfhub/url-egress.attested
secret="$(openssl rand -hex 32)"
docker run -d --name t90-url-gotenberg --network "$internal" \
  --network-alias native-gotenberg --cap-drop=ALL \
  --security-opt=no-new-privileges --pids-limit 128 --memory 1024m \
  --tmpfs /tmp:rw,nosuid,nodev,size=512m \
  t90-url-gotenberg-qa
docker run -d --name t90-url-fetcher --network "$bridge" \
  --ip 172.30.243.2 --cap-drop=ALL --security-opt=no-new-privileges \
  --read-only --pids-limit 64 --memory 128m \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  --mount type=bind,src=/etc/pdfhub/url-egress.attested,dst=/run/pdfhub/url-egress.attested,readonly \
  -e "PDFHUB_URL_FETCHER_SHARED_SECRET=$secret" \
  t90-url-fetcher-qa
docker network connect --alias url-fetcher "$internal" t90-url-fetcher
# Packet-level private/metadata/host/HTTP denial inside the real fetcher
# container. Fast ICMP REJECT is expected; timeout is not proof of a rule.
docker exec -i t90-url-fetcher python - <<'PY'
import errno
import socket
import time
for host, port in [
    ("169.254.169.254", 443), ("10.0.0.2", 443),
    ("172.30.243.1", 443), ("8.8.8.8", 80),
]:
    start = time.monotonic()
    try:
        conn = socket.create_connection((host, port), timeout=1.8)
    except OSError as exc:
        elapsed = time.monotonic() - start
        # This one address is Docker's LOCAL host gateway, so the
        # exact host INPUT rule is DROP (timeout), not FORWARD REJECT.
        # The installer and verifier have already checked the first
        # INPUT rule matches br-pdfhub-url. Don't mistake the gateway
        # timeout for proof of FORWARD packet rejection.
        if host == "172.30.243.1":
            if not isinstance(exc, TimeoutError) and exc.errno != errno.ETIMEDOUT:
                raise AssertionError(f"Host-gateway INPUT-DROP semantics changed: {exc!r}")
            print(f"PASS HOST INPUT-DROP {host}:{port} with verified host rule")
            continue
        if elapsed > 1.7 or exc.errno not in {
            errno.ECONNREFUSED, errno.ENETUNREACH,
            errno.EHOSTUNREACH, errno.EACCES, errno.EPERM,
        }:
            raise AssertionError(f"Packet denied without verified FORWARD REJECT: {host}:{port}, {exc!r}")
        print(f"PASS HOST FIREWALL REJECT {host}:{port} errno={exc.errno}")
    else:
        conn.close()
        raise AssertionError(f"Private or prohibited network destination reachable: {host}:{port}")
PY
ready=0
for attempt in $(seq 1 30); do
  if docker run --rm --network "$internal" --entrypoint curl t90-url-app-qa \
    -fsS --max-time 3 http://native-gotenberg:3000/health >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 2
done
test "$ready" -eq 1
# The short-lived attestation must be live at the actual HTTPS request time.
sudo bash ops/url-fetcher/verify-host-egress-firewall.sh
docker run --rm --network "$internal" \
  --cap-drop=ALL --security-opt=no-new-privileges --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  -e HOME=/tmp -e "PDFHUB_URL_FETCHER_SHARED_SECRET=$secret" \
  -e PDFHUB_TO_PDF_TOOLS_ENABLED=true \
  -e PDFHUB_URL_TO_PDF_DEV_ENABLED=true \
  -e PDFHUB_GOTENBERG_URL=http://native-gotenberg:3000 \
  t90-url-app-qa python -m app.services.t90_2_url_live_ci_selftest
# The same guard must refuse requests immediately when its lease expires.
# Unit regression verifies expiry separately; do not sabotage host rules or
# temporarily deactivate a security boundary while CI is running.
